# SPDX-License-Identifier: Apache-2.0
"""Fixture parser tests for verified public-data responses."""

from __future__ import annotations

from pathlib import Path

import pytest

from ummaya.tools.verified_data_go_kr._models import ResponseFormat
from ummaya.tools.verified_data_go_kr._parsing import (
    VerifiedUpstreamError,
    parse_verified_payload,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = ROOT / "docs/api/data-go-kr-candidate-docs"


def _read(relpath: str) -> bytes:
    return (FIXTURES / relpath).read_bytes()


def test_parse_data_go_kr_common_json_items() -> None:
    parsed = parse_verified_payload(
        _read("15043459/probes/live-2026-05-16/corporate-finance-summary.body.json"),
        response_format="json",
    )

    assert parsed.kind == "collection"
    assert parsed.total_count == 2
    assert parsed.items
    assert parsed.items[0].record["crno"] == "1746110000741"


def test_parse_data_go_kr_common_xml_zero_result_shape() -> None:
    parsed = parse_verified_payload(
        _read("15098530/probes/live-2026-05-16/tago-bus-arrival.body.xml"),
        response_format="xml",
    )

    assert parsed.kind == "collection"
    assert parsed.total_count == 0
    assert parsed.items == []


def test_parse_xml_with_nonstandard_repeating_record_tag() -> None:
    parsed = parse_verified_payload(
        _read("15091886/probes/live-2026-05-16/ftc-large-group.body.xml"),
        response_format="xml",
        record_tag="appnGroupSttus",
    )

    assert parsed.total_count == 71
    assert parsed.items[0].record["unityGrupNm"] == "삼성"


def test_parse_xml_preserves_repeated_child_elements_as_lists() -> None:
    parsed = parse_verified_payload(
        b"""
        <response>
          <header><resultCode>00</resultCode><resultMsg>NORMAL_CODE</resultMsg></header>
          <body>
            <items>
              <item>
                <subject>notice</subject>
                <files>
                  <file><fileName>a.hwp</fileName></file>
                  <file><fileName>b.odt</fileName></file>
                </files>
              </item>
            </items>
          </body>
        </response>
        """,
        response_format="xml",
    )

    files = parsed.items[0].record["files"]
    assert isinstance(files, dict)
    assert files["file"] == [{"fileName": "a.hwp"}, {"fileName": "b.odt"}]


def test_parse_msit_fixture_preserves_all_attachment_entries() -> None:
    parsed = parse_verified_payload(
        _read("15074634/probes/live-2026-05-16-blocker-resolution/msit-rawkey-ua-only.body"),
        response_format="xml",
    )

    files = parsed.items[1].record["files"]
    assert isinstance(files, dict)
    attachment_entries = files["file"]
    assert isinstance(attachment_entries, list)
    assert len(attachment_entries) == 5
    assert attachment_entries[0]["fileName"].endswith(".hwp")
    assert attachment_entries[-1]["fileName"].endswith(".zip")


def test_parse_reb_openapi_json_rows() -> None:
    parsed = parse_verified_payload(
        _read("15134761/probes/live-2026-05-16/reb-stat-table.body.json"),
        response_format="json",
    )

    assert parsed.total_count == 738
    assert parsed.items[0].record["STATBL_ID"] == "A_2024_00900"


@pytest.mark.parametrize("response_format", ["json", "xml"])
def test_non_success_result_code_raises(response_format: ResponseFormat) -> None:
    payload = (
        b'{"response":{"header":{"resultCode":"30","resultMsg":"SERVICE KEY ERROR"}}}'
        if response_format == "json"
        else (
            b"<response><header><resultCode>30</resultCode>"
            b"<resultMsg>SERVICE KEY ERROR</resultMsg></header></response>"
        )
    )

    with pytest.raises(VerifiedUpstreamError) as exc_info:
        parse_verified_payload(payload, response_format=response_format)

    assert exc_info.value.upstream_code == "30"
    assert "SERVICE KEY ERROR" in exc_info.value.upstream_message


def test_parse_pps_response_error_envelope_raises() -> None:
    """PPS can return an nkoneps ResponseError envelope instead of response.header."""

    payload = b"""
    {
      "nkoneps.com.response.ResponseError": {
        "header": {
          "resultCode": "07",
          "resultMsg": "input range exceeded"
        }
      }
    }
    """

    with pytest.raises(VerifiedUpstreamError) as exc_info:
        parse_verified_payload(payload, response_format="json")

    assert exc_info.value.upstream_code == "07"
    assert "input range exceeded" in exc_info.value.upstream_message
