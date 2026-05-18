#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate UMMAYA docs-site machine-readable surfaces.

Outputs:
  - docs-site/public/llms.txt
  - docs-site/public/llms-full.txt
  - docs-site/public/_llm/index.json
  - docs-site/public/_llm/pages.jsonl
  - docs-site/public/_llm/pages/*.md
  - docs-site/public/_llm/generated/*.json
  - docs-site/src/data/generated/*.json

Use --check in CI to fail when generated docs are stale.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_SITE = REPO_ROOT / "docs-site"
CONTENT_ROOT = DOCS_SITE / "src" / "content" / "docs"
PUBLIC_ROOT = DOCS_SITE / "public"
DATA_ROOT = DOCS_SITE / "src" / "data" / "generated"
PRIMITIVE_RENAMES = {
    "lookup": "find",
    "resolve_location": "locate",
    "verify": "check",
    "submit": "send",
    "subscribe": "send",
}


@dataclass(frozen=True)
class Page:
    path: Path
    slug: str
    title: str
    description: str
    frontmatter: dict[str, Any]
    body: str

    @property
    def raw_path(self) -> str:
        return f"/_llm/pages/{self.slug or 'index'}.md"

    @property
    def url_path(self) -> str:
        return "/" if self.slug == "" else f"/{self.slug}/"


def _read_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError(f"Unclosed front matter: {path}")
    raw = text[4:end]
    body = text[end + 5 :]
    loaded = yaml.safe_load(raw) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Front matter must be a mapping: {path}")
    return loaded, body


def _slug_for(path: Path) -> str:
    rel = path.relative_to(CONTENT_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts == ["index"]:
        return ""
    if parts[-1] == "index":
        parts = parts[:-1]
    return "/".join(parts)


def _collect_pages() -> list[Page]:
    pages: list[Page] = []
    for path in sorted(CONTENT_ROOT.rglob("*.md")):
        fm, body = _read_frontmatter(path)
        if fm.get("llm_index", True) is False:
            continue
        title = str(fm.get("title") or _slug_for(path) or "UMMAYA Docs")
        description = str(fm.get("description") or "")
        pages.append(
            Page(
                path=path,
                slug=_slug_for(path),
                title=title,
                description=description,
                frontmatter=fm,
                body=body.strip() + "\n",
            )
        )
    return pages


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _normalize_primitives(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if key == "primitive":
                normalized[key] = PRIMITIVE_RENAMES.get(str(item), item)
            else:
                normalized[key] = _normalize_primitives(item)
        return normalized
    if isinstance(value, list):
        return [_normalize_primitives(item) for item in value]
    return value


def _markdown_table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _strip_code_span(value: str) -> str:
    match = re.fullmatch(r"`([^`]+)`", value.strip())
    return match.group(1) if match else value.strip()


def _extract_markdown_link_path(value: str) -> str | None:
    match = re.search(r"\]\(([^)]+)\)", value)
    return match.group(1) if match else None


def _api_catalog_path(link_path: str | None) -> str | None:
    if not link_path:
        return None
    clean = link_path.split("#", 1)[0]
    if clean.startswith("./"):
        return str((Path("docs") / "api" / clean[2:]).as_posix())
    if clean.startswith("../"):
        return str((Path("docs") / "api" / clean).as_posix())
    return clean


def _permission_tier(value: str) -> int | str | None:
    match = re.search(r"\d+", value)
    if match:
        return int(match.group(0))
    clean = value.strip()
    return clean or None


def _adapter_catalog_rows() -> list[dict[str, Any]]:
    path = REPO_ROOT / "docs" / "api" / "README.md"
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        if "`" not in line or "](" not in line:
            continue
        cells = _markdown_table_cells(line)
        if len(cells) != 7:
            continue
        (
            source,
            tool_cell,
            primitive_cell,
            tier_cell,
            permission_cell,
            spec_cell,
            schema_cell,
        ) = cells
        tool_match = re.search(r"`([^`]+)`", tool_cell)
        if not tool_match:
            continue
        rows.append(
            {
                "tool_id": tool_match.group(1),
                "primitive": _strip_code_span(primitive_cell),
                "tier": _strip_code_span(tier_cell),
                "permission_tier": _permission_tier(permission_cell),
                "docs_path": _api_catalog_path(_extract_markdown_link_path(spec_cell)),
                "schema_path": _api_catalog_path(_extract_markdown_link_path(schema_cell)),
                "source": source,
            }
        )
    return rows


def _adapter_frontmatter() -> list[dict[str, Any]]:
    adapters_by_id: dict[str, dict[str, Any]] = {}
    for path in sorted((REPO_ROOT / "docs" / "api").rglob("*.md")):
        fm, _ = _read_frontmatter(path)
        tool_id = fm.get("tool_id")
        if not tool_id:
            continue
        schema = REPO_ROOT / "docs" / "api" / "schemas" / f"{tool_id}.json"
        adapters_by_id[str(tool_id)] = {
            "tool_id": str(tool_id),
            "primitive": fm.get("primitive"),
            "tier": fm.get("tier"),
            "permission_tier": fm.get("permission_tier"),
            "docs_path": str(path.relative_to(REPO_ROOT)),
            "schema_path": (str(schema.relative_to(REPO_ROOT)) if schema.exists() else None),
        }

    for row in _adapter_catalog_rows():
        existing = adapters_by_id.get(row["tool_id"], {})
        adapters_by_id[row["tool_id"]] = {**existing, **row}

    return [adapters_by_id[key] for key in sorted(adapters_by_id)]


def _workflow_cards() -> list[dict[str, Any]]:
    path = REPO_ROOT / "eval" / "scenarios" / "national_ax_citizen_requests_v1.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    scenarios = payload.get("scenarios", [])
    cards: list[dict[str, Any]] = []
    for item in scenarios[:24]:
        if not isinstance(item, dict):
            continue
        cards.append(
            {
                "id": item.get("id"),
                "priority": item.get("priority"),
                "domain": item.get("lifecycle_domain"),
                "request_ko": item.get("request_ko"),
                "agencies_or_infrastructure": item.get("agencies_or_infrastructure", []),
                "expected_ax_chain": _normalize_primitives(
                    copy.deepcopy(item.get("expected_ax_chain", []))
                ),
                "evaluation_focus": item.get("evaluation_focus", []),
            }
        )
    return cards


def _env_vars() -> list[dict[str, str]]:
    path = REPO_ROOT / "docs" / "configuration.md"
    rows: list[dict[str, str]] = []
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("| Variable | Required |"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("|----------"):
            continue
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        rows.append(
            {
                "variable": cells[0].strip("`"),
                "required": cells[1],
                "default": cells[2],
                "range": cells[3],
                "consumed_by": cells[4],
                "source_doc": cells[5],
            }
        )
    return rows


def _prompt_manifest() -> dict[str, Any]:
    path = REPO_ROOT / "prompts" / "manifest.yaml"
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _render_llms_txt(pages: list[Page]) -> str:
    lines = [
        "# UMMAYA Documentation",
        "",
        "> Machine-readable index for UMMAYA docs. Generated from docs-site content.",
        "",
        "## Pages",
        "",
    ]
    for page in pages:
        label = page.title
        detail = f" — {page.description}" if page.description else ""
        lines.append(f"- [{label}]({page.raw_path}){detail}")
    lines.extend(
        [
            "",
            "## Generated Data",
            "",
            "- [Adapter metadata](/_llm/generated/adapters.json)",
            "- [Citizen workflow cards](/_llm/generated/workflows.json)",
            "- [Environment variables](/_llm/generated/env-vars.json)",
            "- [Prompt manifest summary](/_llm/generated/prompt-manifest.json)",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _render_llms_full(pages: list[Page]) -> str:
    chunks = ["# UMMAYA Documentation Full Text", ""]
    for page in pages:
        chunks.extend(
            [
                f"## {page.title}",
                "",
                f"Path: {page.url_path}",
                f"Raw: {page.raw_path}",
                "",
                page.body,
                "",
            ]
        )
    return "\n".join(chunks).rstrip() + "\n"


def _render_raw_page(page: Page) -> str:
    metadata = {
        "title": page.title,
        "description": page.description,
        "source_of_truth": page.frontmatter.get("source_of_truth", []),
        "audience": page.frontmatter.get("audience", []),
    }
    return (
        "---\n"
        + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
        + "---\n\n"
        + page.body
    ).rstrip() + "\n"


def _generate(output_public: Path = PUBLIC_ROOT, output_data: Path = DATA_ROOT) -> None:
    pages = _collect_pages()
    llm_root = output_public / "_llm"
    raw_pages = llm_root / "pages"
    generated_public = llm_root / "generated"

    if llm_root.exists():
        shutil.rmtree(llm_root)
    raw_pages.mkdir(parents=True, exist_ok=True)
    generated_public.mkdir(parents=True, exist_ok=True)
    output_data.mkdir(parents=True, exist_ok=True)

    (output_public / "llms.txt").write_text(_render_llms_txt(pages), encoding="utf-8")
    (output_public / "llms-full.txt").write_text(_render_llms_full(pages), encoding="utf-8")

    index = []
    pages_jsonl: list[str] = []
    for page in pages:
        raw_path = raw_pages / f"{page.slug or 'index'}.md"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(_render_raw_page(page), encoding="utf-8")
        entry = {
            "title": page.title,
            "description": page.description,
            "url_path": page.url_path,
            "raw_path": page.raw_path,
            "source_path": str(page.path.relative_to(REPO_ROOT)),
            "audience": page.frontmatter.get("audience", []),
            "source_of_truth": page.frontmatter.get("source_of_truth", []),
        }
        index.append(entry)
        pages_jsonl.append(json.dumps({**entry, "body": page.body}, ensure_ascii=False))

    _write_json(llm_root / "index.json", {"pages": index})
    (llm_root / "pages.jsonl").write_text("\n".join(pages_jsonl) + "\n", encoding="utf-8")

    generated = {
        "adapters.json": _adapter_frontmatter(),
        "workflows.json": _workflow_cards(),
        "env-vars.json": _env_vars(),
        "prompt-manifest.json": _prompt_manifest(),
    }
    for name, payload in generated.items():
        _write_json(generated_public / name, payload)
        _write_json(output_data / name, payload)


def _snapshot(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[str(path.relative_to(root))] = path.read_text(encoding="utf-8")
    return result


def _snapshot_public_generated(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for rel in ("llms.txt", "llms-full.txt"):
        path = root / rel
        if path.exists():
            result[rel] = path.read_text(encoding="utf-8")
    llm_root = root / "_llm"
    for path in sorted(llm_root.rglob("*")) if llm_root.exists() else []:
        if path.is_file():
            result[str(path.relative_to(root))] = path.read_text(encoding="utf-8")
    return result


def _check() -> int:
    before_public = _snapshot_public_generated(PUBLIC_ROOT)
    before_data = _snapshot(DATA_ROOT)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        tmp_public = tmp_root / "public"
        tmp_data = tmp_root / "data"
        _generate(tmp_public, tmp_data)
        after_public = _snapshot_public_generated(tmp_public)
        after_data = _snapshot(tmp_data)
    if before_public != after_public or before_data != after_data:
        sys.stderr.write(
            "Generated docs artifacts are stale. Run: uv run python scripts/docs_generate.py\n"
        )
        return 1
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docs_generate")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        return _check()
    _generate()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
