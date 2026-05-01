"""Replay asciinema cast → per-frame plain-text cell-grid snapshots.

Spec 2521 — TUI Layer 5 LLM-readable frame capture.

The agent-debug methodology (AGENTS.md § TUI verification methodology)
mandates byte-grepable text snapshots of every distinct cell-grid state
the user actually saw. asciinema records every PTY byte with sub-ms
timestamps; pyte emulates VT-100 + xterm subset with full wide-char (CJK)
support; this script glues them so an LLM agent can `Read` and `grep`
deterministic frames instead of OCR'ing PNG keyframes.

Usage::

    uv run python scripts/cast_to_frames.py <input.cast> <output-dir>

Input  : asciinema v2 or v3 cast (auto-detected via header `version`).
Output : output-dir/frame_NNNN_t<seconds>.txt — one file per *distinct*
         cell-grid state. Consecutive duplicate states are deduped so the
         agent reads only meaningful transitions. timeline.txt indexes
         every frame by (idx, t, sha1, label).

The script intentionally has zero deps beyond stdlib + pyte (already a
dev dep per pyproject.toml § project.optional-dependencies). It is
test-only — never imported by KOSMOS production code.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pyte


def _parse_header(line: str) -> tuple[int, int, int]:
    """Return (cols, rows, version) from cast header. Supports v2 + v3.

    v2 events use ABSOLUTE timestamps (seconds since session start).
    v3 events use RELATIVE deltas (seconds since previous event).
    The caller must accumulate v3 deltas to compute absolute t.
    """
    hdr = json.loads(line)
    version = hdr.get("version")
    if version == 2:
        return int(hdr["width"]), int(hdr["height"]), 2
    if version == 3:
        term = hdr.get("term", {})
        return int(term.get("cols", 80)), int(term.get("rows", 24)), 3
    raise ValueError(f"Unsupported asciicast version: {version!r}")


def _snap_text(screen: pyte.Screen) -> str:
    """Render screen as plain text — strip trailing whitespace per row."""
    return "\n".join(row.rstrip() for row in screen.display).rstrip("\n") + "\n"


def replay(cast_path: Path, out_dir: Path) -> int:
    """Replay cast and dump per-frame text to out_dir. Return frame count."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("frame_*.txt"):
        stale.unlink()
    timeline = out_dir / "timeline.txt"
    timeline.write_text("# idx\tt_seconds\tsha1\tlabel\n")

    lines = cast_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"empty cast: {cast_path}")

    cols, rows, version = _parse_header(lines[0])
    screen = pyte.Screen(cols, rows)
    stream = pyte.ByteStream(screen)

    prev_hash: str | None = None
    idx = 0
    initial_label = "boot"
    abs_t = 0.0  # absolute time accumulator for v3 deltas

    # Capture the empty pre-replay frame so the agent can diff against it.
    snap = _snap_text(screen)
    sha = hashlib.sha1(snap.encode("utf-8")).hexdigest()[:12]
    fpath = out_dir / f"frame_{idx:04d}_t0.000_{sha}.txt"
    fpath.write_text(snap)
    with timeline.open("a") as fh:
        fh.write(f"{idx:04d}\t0.000\t{sha}\t{initial_label}\n")
    prev_hash = sha
    idx = 1

    for ln in lines[1:]:
        ln = ln.strip()
        if not ln:
            continue
        try:
            event = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, list) or len(event) < 3:
            continue
        t_field, kind, data = event[0], event[1], event[2]
        # v3: t is delta since previous event; v2: t is absolute.
        if version == 3:
            abs_t += float(t_field)
        else:
            abs_t = float(t_field)
        if kind != "o":
            continue
        if isinstance(data, str):
            stream.feed(data.encode("utf-8"))
        elif isinstance(data, bytes):
            stream.feed(data)
        else:
            continue
        snap = _snap_text(screen)
        sha = hashlib.sha1(snap.encode("utf-8")).hexdigest()[:12]
        if sha == prev_hash:
            continue
        fpath = out_dir / f"frame_{idx:04d}_t{abs_t:.3f}_{sha}.txt"
        fpath.write_text(snap)
        with timeline.open("a") as fh:
            fh.write(f"{idx:04d}\t{abs_t:.3f}\t{sha}\tdelta\n")
        prev_hash = sha
        idx += 1

    return idx


def _emit_summary(out_dir: Path, count: int, cast_path: Path) -> None:
    summary = out_dir / "summary.txt"
    frames = sorted(out_dir.glob("frame_*.txt"))
    final = frames[-1].read_text() if frames else "(no frames)"
    summary.write_text(
        "TUI text-debug summary (asciinema → pyte)\n"
        f"  source   : {cast_path}\n"
        f"  outdir   : {out_dir}\n"
        f"  frames   : {count}\n"
        f"  timeline : {out_dir / 'timeline.txt'}\n"
        f"\n=== final frame ===\n{final}"
    )


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: cast_to_frames.py <input.cast> <output-dir>",
            file=sys.stderr,
        )
        return 2
    cast = Path(sys.argv[1]).expanduser().resolve()
    out = Path(sys.argv[2]).expanduser().resolve()
    if not cast.is_file():
        print(f"::error::cast not found: {cast}", file=sys.stderr)
        return 1
    count = replay(cast, out)
    _emit_summary(out, count, cast)
    print(f"wrote {count} unique frames to {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
