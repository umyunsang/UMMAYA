# SPDX-License-Identifier: Apache-2.0
"""HIRA hospital search adapter — T054.

Wraps the ``getHospBasisList`` endpoint from HIRA
(건강보험심사평가원, Health Insurance Review and Assessment Service).

Input: WGS84 coordinates (xPos, yPos) + radius in meters,
       optional medical specialty (dgsbjt) + institution type (clCd).
Output: LookupCollection of hospital records, sorted by distance ASC client-side.

Endpoint: https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList

FR-021: Accepts (xPos, yPos, radius) — native coord+radius spatial input.
FR-023: Ships happy-path AND error-path tests with recorded fixtures.
FR-024: Fail-closed defaults (non-auth tool — read-only gate per Epic δ #2295,
        is_concurrency_safe=True, cache_ttl_seconds=0).
FR-037: Adapter is an async coroutine.

D + E fix (2026-05-04, snap-009 distance/specialty lookup regression):
  D — HIRA's getHospBasisList returns ``distance`` (a high-precision decimal
      string in meters from the query xPos/yPos) but does NOT sort by it.
      Live verification 2026-05-04: a coordinate-radius baseline call returned
      d=829, 760, 479, 610, 757 (registration order, not distance ASC).
      We now sort items by distance ascending client-side after deserializing
      the upstream response.
  E — Add ``dgsbjt`` (medical specialty natural-language input → 진료과목코드
      mapping; e.g. "내과" → "01") and ``clCd`` (종별코드, e.g. "31"=의원,
      "21"=병원, "11"=상급종합) so the citizen's "근처 내과" query becomes
      ``dgsbjt='내과'`` server-side filter (118 results, not 907) instead of
      a generic radius search returning every clinic and hospital mixed.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from ummaya.tools._description_template import build_description_v4
from ummaya.tools._outbound_trace import traced_async_client
from ummaya.tools.errors import ToolExecutionError, _require_env
from ummaya.tools.models import AdapterRealDomainPolicy, GovAPITool

logger = logging.getLogger(__name__)

_BASE_URL = "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"
_LOCAL_PHONE_RE = re.compile(r"^\d{3,4}-\d{4}$")
_AREA_CODE_BY_SIDO: dict[str, str] = {
    "서울": "02",
    "서울특별시": "02",
    "부산": "051",
    "부산광역시": "051",
    "대구": "053",
    "대구광역시": "053",
    "인천": "032",
    "인천광역시": "032",
    "광주": "062",
    "광주광역시": "062",
    "대전": "042",
    "대전광역시": "042",
    "울산": "052",
    "울산광역시": "052",
    "세종": "044",
    "세종특별자치시": "044",
    "경기": "031",
    "경기도": "031",
    "강원": "033",
    "강원특별자치도": "033",
    "충북": "043",
    "충청북도": "043",
    "충남": "041",
    "충청남도": "041",
    "전북": "063",
    "전북특별자치도": "063",
    "전라북도": "063",
    "전남": "061",
    "전라남도": "061",
    "경북": "054",
    "경상북도": "054",
    "경남": "055",
    "경상남도": "055",
    "제주": "064",
    "제주특별자치도": "064",
}


def _infer_area_code(*, sido: str, addr: str) -> str | None:
    """Infer Korean landline area code from HIRA region/address fields."""
    candidates = [sido.strip(), addr.strip().split(maxsplit=1)[0] if addr.strip() else ""]
    for candidate in candidates:
        if not candidate:
            continue
        exact = _AREA_CODE_BY_SIDO.get(candidate)
        if exact:
            return exact
        for region_name, area_code in _AREA_CODE_BY_SIDO.items():
            if candidate.startswith(region_name):
                return area_code
    return None


def _normalize_hira_telno(raw_telno: object, *, sido: str, addr: str) -> str:
    """Prefix local HIRA landline numbers with the address-derived area code."""
    telno = str(raw_telno or "").strip()
    if not telno or telno.startswith("0") or not _LOCAL_PHONE_RE.fullmatch(telno):
        return telno
    area_code = _infer_area_code(sido=sido, addr=addr)
    if not area_code:
        return telno
    return f"{area_code}-{telno}"


# ---------------------------------------------------------------------------
# Code maps (HIRA canonical 진료과목코드 + 종별코드, verified live 2026-05-04)
# ---------------------------------------------------------------------------

# 진료과목코드 — HIRA dgsbjtCd. Source: 한국사회보장정보원 보건기관 진료과목 코드정보
# (data.go.kr 15049696) cross-checked against live getHospBasisList probe near
# a Seoul sample coordinate returning non-zero totals for 01–16, 19, 21,
# 23, 24, 26, 80 on 2026-05-04. Aliases include common citizen vocabulary
# (e.g. "이비인후과" / "ENT" → 13).
_DGSBJT_CODE_MAP: dict[str, str] = {
    # 01 내과
    "내과": "01",
    "internal medicine": "01",
    # 02 신경과
    "신경과": "02",
    "neurology": "02",
    # 03 정신건강의학과
    "정신건강의학과": "03",
    "정신과": "03",
    "psychiatry": "03",
    # 04 외과
    "외과": "04",
    "surgery": "04",
    # 05 정형외과
    "정형외과": "05",
    "orthopedics": "05",
    # 06 신경외과
    "신경외과": "06",
    "neurosurgery": "06",
    # 07 흉부외과
    "흉부외과": "07",
    "thoracic surgery": "07",
    # 08 성형외과
    "성형외과": "08",
    "plastic surgery": "08",
    # 09 마취통증의학과
    "마취통증의학과": "09",
    "마취과": "09",
    "통증의학과": "09",
    "anesthesiology": "09",
    # 10 산부인과
    "산부인과": "10",
    "obstetrics": "10",
    "gynecology": "10",
    "ob/gyn": "10",
    # 11 소아청소년과
    "소아청소년과": "11",
    "소아과": "11",
    "pediatrics": "11",
    # 12 안과
    "안과": "12",
    "ophthalmology": "12",
    # 13 이비인후과
    "이비인후과": "13",
    "ent": "13",
    "otolaryngology": "13",
    # 14 피부과
    "피부과": "14",
    "dermatology": "14",
    # 15 비뇨의학과
    "비뇨의학과": "15",
    "비뇨기과": "15",
    "urology": "15",
    # 16 영상의학과
    "영상의학과": "16",
    "방사선과": "16",
    "radiology": "16",
    # 17 방사선종양학과
    "방사선종양학과": "17",
    "radiation oncology": "17",
    # 18 병리과
    "병리과": "18",
    "pathology": "18",
    # 19 진단검사의학과
    "진단검사의학과": "19",
    "임상병리과": "19",
    "laboratory medicine": "19",
    # 20 결핵과
    "결핵과": "20",
    "tuberculosis": "20",
    # 21 재활의학과
    "재활의학과": "21",
    "rehabilitation": "21",
    # 22 핵의학과
    "핵의학과": "22",
    "nuclear medicine": "22",
    # 23 가정의학과
    "가정의학과": "23",
    "family medicine": "23",
    # 24 응급의학과
    "응급의학과": "24",
    "emergency medicine": "24",
    # 25 직업환경의학과
    "직업환경의학과": "25",
    "산업의학과": "25",
    "occupational medicine": "25",
    # 26 예방의학과
    "예방의학과": "26",
    "preventive medicine": "26",
    # 80 한방
    "한의원": "80",
    "한방": "80",
    "한의과": "80",
    "korean medicine": "80",
}

_DGSBJT_CODE_NAME_MAP: dict[str, str] = {
    "01": "내과",
    "02": "신경과",
    "03": "정신건강의학과",
    "04": "외과",
    "05": "정형외과",
    "06": "신경외과",
    "07": "흉부외과",
    "08": "성형외과",
    "09": "마취통증의학과",
    "10": "산부인과",
    "11": "소아청소년과",
    "12": "안과",
    "13": "이비인후과",
    "14": "피부과",
    "15": "비뇨의학과",
    "16": "영상의학과",
    "17": "방사선종양학과",
    "18": "병리과",
    "19": "진단검사의학과",
    "20": "결핵과",
    "21": "재활의학과",
    "22": "핵의학과",
    "23": "가정의학과",
    "24": "응급의학과",
    "25": "직업환경의학과",
    "26": "예방의학과",
    "80": "한방",
}

# 종별코드 — HIRA clCd. Source: HIRA 활용가이드 (병원정보서비스). Verified live
# 2026-05-04 with clCd=31 returning 673 / clCd=21 returning N (의원/병원 split).
_CLCD_CODE_MAP: dict[str, str] = {
    # 11 상급종합병원
    "상급종합": "11",
    "상급종합병원": "11",
    "tertiary hospital": "11",
    # 21 종합병원
    "종합병원": "21",
    "general hospital": "21",
    # 28 병원 (HIRA uses 21 for 종합병원 + 28 for 병원 in some tables; live API
    # accepts 21 broadly — keep canonical 21 for "병원").
    "병원": "21",
    "hospital": "21",
    # 29 치과병원
    "치과병원": "29",
    "dental hospital": "29",
    # 31 의원
    "의원": "31",
    "clinic": "31",
    # 41 조산원
    "조산원": "41",
    "midwifery clinic": "41",
    # 51 보건소
    "보건소": "51",
    "public health center": "51",
    # 81 한의원
    "한의원종별": "81",  # disambiguate from 진료과 한의원
    # 92 약국
    "약국": "92",
    "pharmacy": "92",
}

_DGSBJT_MULTI_SPLIT_RE = re.compile(r"\s*(?:,|/|\+|·|ㆍ|및|또는|\bor\b|\band\b)\s*")


def _split_dgsbjt_tokens(value: str) -> list[str]:
    """Split citizen/model multi-specialty strings into individual tokens."""
    normalized = re.sub(r"(?<=[가-힣])나\s+", ",", value.strip())
    return [part.strip() for part in _DGSBJT_MULTI_SPLIT_RE.split(normalized) if part.strip()]


def _resolve_dgsbjt_token(value: object) -> str:
    """Map one natural-language specialty/code token to HIRA's 2-digit code."""
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str):
        raise ValueError("Medical specialty must be a Korean name, English alias, or code.")

    token = value.strip()
    if not token:
        raise ValueError("Medical specialty must not be empty.")
    if token.isdigit():
        if len(token) == 1:
            token = f"0{token}"
        if len(token) == 2:
            return token

    lookup_key = token.lower()
    if lookup_key in _DGSBJT_CODE_MAP:
        return _DGSBJT_CODE_MAP[lookup_key]
    if token in _DGSBJT_CODE_MAP:
        return _DGSBJT_CODE_MAP[token]

    valid_examples = "내과 / 소아과 / 안과 / 이비인후과 / 정형외과 / 피부과"
    raise ValueError(
        f"Unknown medical specialty '{token}'. Pass either the Korean name "
        f"(e.g. {valid_examples}) or a 2-digit dgsbjtCd (01–26, 80)."
    )


def _append_matched_dgsbjt(item: dict[str, Any], dgsbjt_code: str | None) -> None:
    """Record which fan-out specialty call produced this item."""
    if dgsbjt_code is None:
        return

    codes = item.setdefault("matchedDgsbjtCds", [])
    if not isinstance(codes, list):
        codes = [str(codes)]
        item["matchedDgsbjtCds"] = codes
    if dgsbjt_code not in codes:
        codes.append(dgsbjt_code)

    name = _DGSBJT_CODE_NAME_MAP.get(dgsbjt_code)
    names = item.setdefault("matchedDgsbjtNms", [])
    if not isinstance(names, list):
        names = [str(names)]
        item["matchedDgsbjtNms"] = names
    if name and name not in names:
        names.append(name)

    item["matchedDgsbjtCd"] = ",".join(codes)
    if names:
        item["matchedDgsbjtNm"] = ",".join(names)


# ---------------------------------------------------------------------------
# Input schema (T054 — xPos + yPos + radius)
# ---------------------------------------------------------------------------


class HiraHospitalSearchInput(BaseModel):
    """Input schema for hira_hospital_search.

    Queries HIRA's hospital basis list endpoint by WGS84 coordinate and
    radius. All three parameters are required.

    Obtain xPos / yPos from a coordinate-producing locate adapter before calling
    this tool — never guess coordinate values from model memory.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    xPos: float = Field(  # noqa: N815
        ge=124.0,
        le=132.0,
        description=(
            "Longitude (WGS84, decimal degrees). Korean peninsula range: 124–132. "
            "Obtain from a coordinate-producing locate adapter. Never guess."
        ),
    )
    yPos: float = Field(  # noqa: N815
        ge=33.0,
        le=39.0,
        description=(
            "Latitude (WGS84, decimal degrees). Korean peninsula range: 33–39. "
            "Obtain from a coordinate-producing locate adapter. Never guess."
        ),
    )
    radius: int = Field(
        ge=1,
        le=10000,
        default=2000,
        description=(
            "Search radius in meters. Default 2000 m (2 km). Max 10 000 m. "
            "When the citizen gives an explicit numeric radius or distance, "
            "preserve that value. Otherwise use the default rather than guessing."
        ),
    )
    dgsbjt: str | None = Field(
        default=None,
        description=(
            "Optional medical-specialty filter (HIRA 진료과목코드). "
            "Accepts either the natural-language Korean name or the 2-digit "
            "code. Examples: '내과' → 01, '소아과' → 11, '안과' → 12, "
            "'이비인후과' → 13, '피부과' → 14, '정형외과' → 05, "
            "'산부인과' → 10, '치과' (use clCd=치과병원 instead). "
            "ENGLISH aliases: 'internal medicine' / 'pediatrics' / 'ENT' / "
            "'dermatology' / 'orthopedics'. WHEN TO USE: citizen mentions a "
            "specific 진료과 ('근처 내과 알려줘' → dgsbjt='내과'). When omitted, "
            "all specialties returned. Without this filter '근처 병원' returns "
            "mixed specialties. Do not invent a specialty code when the citizen "
            "did not state one clearly. "
            "If the citizen asks for multiple specialties, pass comma-separated "
            "names/codes (e.g. '피부과,내과'); UMMAYA will fan out and merge."
        ),
    )
    clCd: str | None = Field(  # noqa: N815
        default=None,
        description=(
            "Optional institution-type filter (HIRA 종별코드). "
            "Accepts natural-language Korean or the 2-digit code. "
            "'의원' / 'clinic' → 31 (small primary care, single-specialty), "
            "'병원' / 'hospital' → 21 (mid-size), '종합병원' → 21, "
            "'상급종합' / 'tertiary hospital' → 11, "
            "'치과병원' → 29, '한의원' → 81, "
            "'약국' / 'pharmacy' → 92, '보건소' → 51. WHEN TO USE: citizen "
            "specifies institution scale ('근처 종합병원', '큰 병원'). When "
            "omitted, all types returned mixed. Combine with dgsbjt for "
            "best precision when the citizen explicitly asks for both specialty "
            "and institution type."
        ),
    )
    pageNo: int = Field(  # noqa: N815
        default=1,
        ge=1,
        description="Page number for pagination (1-based). Default 1.",
    )
    numOfRows: int = Field(  # noqa: N815
        default=20,
        ge=1,
        le=100,
        description="Number of rows per page (1–100). Default 20.",
    )

    @field_validator("dgsbjt", mode="before")
    @classmethod
    def _resolve_dgsbjt(cls, v: object) -> str | None:
        """Map specialty input to one or more comma-separated dgsbjtCd values."""
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        raw_tokens: Sequence[object]
        if isinstance(v, list):
            raw_tokens = v
        elif isinstance(v, str):
            raw_tokens = _split_dgsbjt_tokens(v)
        else:
            raw_tokens = [v]

        codes: list[str] = []
        for token in raw_tokens:
            code = _resolve_dgsbjt_token(token)
            if code not in codes:
                codes.append(code)
        return ",".join(codes) if codes else None

    @field_validator("clCd")
    @classmethod
    def _resolve_clcd(cls, v: str | None) -> str | None:
        """Map natural-language institution type → 2-digit clCd, or pass through code."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if v.isdigit() and len(v) == 2:
            return v
        lookup_key = v.lower()
        if lookup_key in _CLCD_CODE_MAP:
            return _CLCD_CODE_MAP[lookup_key]
        if v in _CLCD_CODE_MAP:
            return _CLCD_CODE_MAP[v]
        valid_examples = "의원 / 병원 / 종합병원 / 상급종합 / 치과병원 / 약국"
        raise ValueError(
            f"Unknown institution type '{v}'. Pass either the Korean name "
            f"(e.g. {valid_examples}) or a 2-digit clCd."
        )

    @model_validator(mode="after")
    def _reject_rounded_coordinate_pair(self) -> HiraHospitalSearchInput:
        """Reject whole-degree coordinate pairs that lost locate precision."""
        if float(self.xPos).is_integer() and float(self.yPos).is_integer():
            raise ValueError(
                "xPos/yPos must preserve decimal WGS84 precision from locate; "
                "do not round both coordinates to whole degrees."
            )
        return self


# ---------------------------------------------------------------------------
# Async adapter handler
# ---------------------------------------------------------------------------


async def handle(  # noqa: C901
    inp: HiraHospitalSearchInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Invoke the HIRA hospital search endpoint and return a LookupCollection dict.

    FR-037: This is an async coroutine.
    FR-021: Returns LookupCollection with yadmNm, addr, telno, clCd, etc.

    Args:
        inp: Validated HiraHospitalSearchInput.
        client: Optional httpx.AsyncClient for test injection.

    Returns:
        A dict suitable for envelope normalization into LookupCollection.

    Raises:
        ConfigurationError: If UMMAYA_DATA_GO_KR_API_KEY is not set.
        RuntimeError: On upstream API errors (non-00 resultCode or HTTP error).
    """
    api_key = _require_env("UMMAYA_DATA_GO_KR_API_KEY")

    requested_num_rows = inp.numOfRows
    request_num_rows = requested_num_rows
    if inp.dgsbjt is not None:
        request_num_rows = min(100, max(request_num_rows, 50))

    params: dict[str, str | int | float] = {
        "serviceKey": api_key,
        "xPos": inp.xPos,
        "yPos": inp.yPos,
        "radius": inp.radius,
        "pageNo": inp.pageNo,
        "numOfRows": request_num_rows,
        "_type": "json",
    }
    dgsbjt_codes = inp.dgsbjt.split(",") if inp.dgsbjt else [None]
    effective_clcd = inp.clCd
    if effective_clcd is not None:
        params["clCd"] = effective_clcd

    logger.debug(
        "hira_hospital_search: xPos=%.5f yPos=%.5f radius=%d page=%d rows=%d "
        "request_rows=%d dgsbjt=%s clCd=%s",
        inp.xPos,
        inp.yPos,
        inp.radius,
        inp.pageNo,
        requested_num_rows,
        request_num_rows,
        inp.dgsbjt,
        effective_clcd,
    )

    own_client = client is None
    # Epic #2766 issue C — HIRA's `getHospBasisList` regularly takes 20-45 s
    # on cold-cache regional queries. The previous 30 s ceiling tripped on
    # second-attempt citizen flows ("Baked for 1m 5s" with no result, see
    # spec.md US3). Bump to 60 s so genuine slow upstreams complete; a real
    # network outage still surfaces as a clean timeout envelope (executor
    # _classify_adapter_exception → reason='upstream_unavailable').
    _client: httpx.AsyncClient = (
        traced_async_client(timeout=60.0) if own_client else client  # type: ignore[assignment]
    )

    async def _fetch_collection(
        request_params: dict[str, str | int | float],
    ) -> tuple[list[dict[str, Any]], int]:
        response = await _client.get(_BASE_URL, params=request_params)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "xml" in content_type.lower() and "json" not in content_type.lower():
            raise ToolExecutionError(
                "hira_hospital_search",
                f"HIRA API returned XML instead of JSON "
                f"(Content-Type: {content_type!r}). "
                "Ensure '_type=json' (underscore prefix) is in the request params.",
            )

        raw: dict[str, Any] = response.json()

        # HIRA uses a nested response envelope: response → body → items / totalCount
        response_body = raw.get("response", {})
        header = response_body.get("header", {})
        result_code = str(header.get("resultCode", ""))
        result_msg = str(header.get("resultMsg", "Unknown"))

        if result_code == "03":
            # NODATA_ERROR — return empty collection
            return [], 0

        if result_code != "00":
            raise ToolExecutionError(
                "hira_hospital_search",
                f"HIRA API error: resultCode={result_code!r} resultMsg={result_msg!r}",
            )

        body = response_body.get("body", {})
        total_count = int(body.get("totalCount", 0))
        raw_items = body.get("items", {})

        item_list: list[dict[str, Any]] = []
        if raw_items and not isinstance(raw_items, str):
            raw_item = raw_items.get("item", [])
            if isinstance(raw_item, dict):
                item_list = [raw_item]
            elif isinstance(raw_item, list):
                item_list = raw_item

        normalized_items: list[dict[str, Any]] = []
        for item in item_list:
            addr = str(item.get("addr", "") or "")
            sido = str(item.get("sidoCdNm", "") or "")
            normalized_items.append(
                {
                    "ykiho": item.get("ykiho", ""),
                    "yadmNm": item.get("yadmNm", ""),
                    "addr": addr,
                    "telno": _normalize_hira_telno(
                        item.get("telno", ""),
                        sido=sido,
                        addr=addr,
                    ),
                    "clCd": item.get("clCd", ""),
                    "clCdNm": item.get("clCdNm", ""),
                    "xPos": item.get("XPos"),
                    "yPos": item.get("YPos"),
                    "distance": item.get("distance"),
                    "sidoCdNm": sido,
                    "sgguCdNm": item.get("sgguCdNm", ""),
                }
            )

        return normalized_items, total_count

    try:
        items: list[dict[str, Any]] = []
        total_count = 0
        seen_items: dict[str, dict[str, Any]] = {}
        for dgsbjt_code in dgsbjt_codes:
            request_params = dict(params)
            if dgsbjt_code is not None:
                request_params["dgsbjtCd"] = dgsbjt_code
            fetched_items, fetched_total = await _fetch_collection(request_params)
            total_count += fetched_total
            for item in fetched_items:
                key = str(item.get("ykiho") or (item.get("yadmNm"), item.get("addr")))
                if key in seen_items:
                    _append_matched_dgsbjt(seen_items[key], dgsbjt_code)
                    continue
                _append_matched_dgsbjt(item, dgsbjt_code)
                seen_items[key] = item
                items.append(item)
    finally:
        if own_client:
            await _client.aclose()

    # D-fix: HIRA does NOT sort by distance server-side. Verified live
    # 2026-05-04: a coordinate-radius baseline call returned
    # d=829, 760, 479, 610, 757 (registration order). Citizens expect
    # "근처 X" to mean the actually-closest match. Sort ascending by the
    # `distance` string parsed as float. For specialty queries, HIRA returns
    # every institution that offers the specialty; prefer names that visibly
    # match the requested specialty before applying distance.
    def _distance_key(rec: dict[str, Any]) -> tuple[int, float]:
        raw = rec.get("distance")
        if raw is None or raw == "":
            return (1, 0.0)  # missing distance → sort last
        try:
            return (0, float(raw))
        except (TypeError, ValueError):
            return (1, 0.0)

    def _specialty_name_rank(rec: dict[str, Any]) -> int:
        display_name = str(rec.get("yadmNm") or "")
        matched_names = rec.get("matchedDgsbjtNms")
        if not isinstance(matched_names, list):
            return 1
        for matched_name in matched_names:
            if isinstance(matched_name, str) and matched_name and matched_name in display_name:
                return 0
        return 1

    items.sort(key=lambda rec: (_specialty_name_rank(rec), *_distance_key(rec)))
    items = items[:requested_num_rows]

    return {
        "kind": "collection",
        "items": items,
        "total_count": total_count,
    }


# ---------------------------------------------------------------------------
# Tool definition and registration helper (T054)
# ---------------------------------------------------------------------------


class _HiraHospitalSearchOutput(RootModel[dict[str, Any]]):
    """Placeholder output schema for GovAPITool registration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


_HIRA_DESCRIPTION = build_description_v4(
    purpose=(
        "Search HIRA (건강보험심사평가원) hospital registry for medical facilities "
        "within a WGS84 coordinate radius, optionally filtered by medical "
        "specialty (진료과목) and/or institution type (종별). Returns hospital "
        "name, address, phone, institution type, and distance — sorted by "
        "distance ascending (closest first). "
        "Use for: nearby hospitals, clinics, specialty-specific search "
        "(내과/소아과/안과/이비인후과/etc.), specific institution scale "
        "(의원 vs 종합병원 vs 상급종합)."
    ),
    input_quirk=(
        "xPos = longitude (124–132). yPos = latitude (33–39). "
        "Citizen location → locate(kakao_keyword_search 또는 kakao_address_search) first. "
        "radius is meters; preserve explicit numeric distance wording when present. "
        "dgsbjt + clCd are optional natural-language filters (see short_reference). "
        "For multiple specialties, pass comma-separated dgsbjt names/codes."
    ),
    short_reference=(
        "Lat/lon direct (no grid). Response: yadmNm, addr, telno, clCdNm, ykiho, distance, "
        "and matchedDgsbjtNm/Cd when dgsbjt was used.\n"
        "DGSBJT pass Korean: 내과→01, 신경과→02, 정신과→03, 외과→04, 정형외과→05, "
        "신경외과→06, 흉부외과→07, 성형외과→08, 산부인과→10, 소아과→11, 안과→12, "
        "이비인후과→13, 피부과→14, 비뇨기과→15, 영상의학과→16, 재활의학과→21, "
        "가정의학과→23, 응급의학과→24, 한의원→80. English: pediatrics/ENT/dermatology.\n"
        "CLCD: 의원→31, 병원/종합병원→21, 상급종합→11, 치과병원→29, 약국→92, 보건소→51.\n"
        "Multiple specialties: dgsbjt='피부과,내과' fans out and merges by distance; use "
        "matchedDgsbjtNms to group/list specialties correctly.\n"
        "Without dgsbjt, the result is an unfiltered mixed-specialty facility list."
    ),
    domain_quirk=(
        "JSON requires '_type=json' (underscore prefix). 'type=json' silently "
        "returns XML. Response coord fields uppercase: XPos/YPos. "
        "HIRA does NOT sort — UMMAYA sorts client-side by distance ASC, so the "
        "first item is the closest. Response does NOT echo dgsbjtCd back. "
        "This is not an emergency-room locator; for 응급실/야간 응급실 prefer "
        "nmc_emergency_search when an authenticated citizen session exists, "
        "or a location POI search when no authenticated NMC session is present."
    ),
    self_contained_decl=(
        "REQUIRED: xPos/yPos. Citizen location text needs "
        "locate(kakao_keyword_search 또는 kakao_address_search) first. "
        "ORDERING: turn1=locate adapter, "
        "turn2=this tool. When the citizen explicitly states a specialty or "
        "institution type, preserve it as dgsbjt / clCd in the same call. "
        "If multiple explicit specialties are stated, pass them comma-separated."
    ),
)

HIRA_HOSPITAL_SEARCH_TOOL = GovAPITool(
    id="hira_hospital_search",
    name_ko="병원 기본정보 조회 (좌표+반경)",
    ministry="HIRA",
    category=["의료", "병원", "의료기관", "진료"],
    endpoint=_BASE_URL,
    auth_type="api_key",
    input_schema=HiraHospitalSearchInput,
    output_schema=_HiraHospitalSearchOutput,
    llm_description=_HIRA_DESCRIPTION,
    search_hint=(
        "병원 검색 진료과목 의료기관 정보 근처 병원 내과 외과 소아과 "
        "이비인후과 가정의학과 의원 "
        "hospital search medical specialty "
        "clinic nearby HIRA healthcare Korea"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.hira.or.kr/bbs/informationNotice.do?pgmid=HIRAA030011000000",
        real_classification_text="건강보험심사평가원 공공데이터 이용약관 — 병원 정보 데이터 비상업적 공공 이용 허가",  # TODO: verify URL  # noqa: E501
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=0,
    rate_limit_per_minute=10,
    is_core=False,
    # Spec 031 T032/T033 dual-axis fields — None during pre-v1.2 compatibility window FR-028
    primitive="find",
    published_tier_minimum=None,
    nist_aal_hint=None,
    trigger_examples=[
        "근처 내과 병원",
        "근처 소아과",
        "이비인후과 추천",
        "근처 종합병원",
    ],
)


def register(registry: object, executor: object) -> None:
    """Register HIRA hospital search tool and its adapter.

    Call this from register_all.py (Stage 3 / T056) to wire the adapter
    into the global registry and executor. Do NOT call from this module
    directly — the global registry is managed by register_all.py.

    Args:
        registry: A ToolRegistry instance.
        executor: A ToolExecutor instance.
    """
    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.registry import ToolRegistry

    assert isinstance(registry, ToolRegistry)
    assert isinstance(executor, ToolExecutor)

    async def _adapter(inp: BaseModel) -> dict[str, Any]:
        assert isinstance(inp, HiraHospitalSearchInput)
        return await handle(inp)

    registry.register(HIRA_HOSPITAL_SEARCH_TOOL)
    executor.register_adapter("hira_hospital_search", _adapter)
    logger.info("Registered tool: hira_hospital_search")
