# Legacy Office Promotion Deep Research

Date: 2026-06-03

## Local Position

UMMAYA does not provide native in-place write/render/save for legacy Microsoft
Office binary extensions `.doc`, `.xls`, and `.ppt`. The promoted direction is a
local derivative bridge into OOXML working copies.

Current code boundary:

- `src/ummaya/tools/documents/models.py` classifies `doc`, `xls`, and `ppt` as
  `KnownDocumentFormat` values in the `legacy_office` family and as
  `DocumentFormat` source formats.
- `PROMOTED_RUNTIME_DOCUMENT_FORMATS` excludes these legacy binary formats;
  they are not directly mutable runtime formats.
- `src/ummaya/tools/documents/formats/passive.py` routes them to
  `LegacyOfficeDocumentAdapter`, which is metadata-only with
  `conversion_required_legacy_office`.
- `src/ummaya/tools/documents/conversion.py` registers a default
  LibreOffice/soffice converter from legacy Office originals into
  DOCX/XLSX/PPTX working derivatives when a local executable is discoverable.
- Local runtime probe on 2026-06-03 found no `soffice` or `libreoffice`
  executable, so this workstation still reports the live bridge as unavailable
  until installed.

## 2026-Current Sources

| Source | Signal | UMMAYA impact |
|---|---|---|
| Microsoft Open Specifications archive, <https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-offfflp/7b95d465-d508-4213-a403-38f745e63d96> | Microsoft identifies `.doc`, `.xls`, and `.ppt` as Office 97-2003 binary file formats and warns the archived documents are convenience copies. | Direct binary mutation should stay blocked unless a dedicated engine passes very strong gates. |
| Microsoft Support, Open XML file extensions, <https://support.microsoft.com/en-us/office/open-xml-formats-and-file-name-extensions-5200d93c-3449-4380-8e11-31ef14555b18> | Current Office defaults are `.docx`, `.xlsx`, and `.pptx`; converting old binary files creates a new modern-format copy. | The safe write target for legacy Office originals is an explicit OOXML derivative, not in-place `.doc/.xls/.ppt` editing. |
| LibreOffice Help, starting parameters, <https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html> | `--convert-to` can export files to target formats and supports `--outdir`; official examples include converting `.doc` files. | Best local-only bridge candidate for legacy Office conversion, but must be explicit and absent from CI live dependencies. |
| LibreOffice conversion filter table, <https://help.libreoffice.org/latest/en-US/text/shared/guide/convertfilters.html> | Filter table includes `MS Word 2007 XML`, `Calc MS Excel 2007 XML`, and `Impress MS PowerPoint 2007 XML` output filters. | Recommended derivative targets are DOCX/XLSX/PPTX using explicit filter names. |
| Apache POI HWPF/XWPF docs, <https://poi.apache.org/components/document/> | POI documents legacy Word support as moderately functional, with strong extraction but limited/incomplete areas and risky invalid-file generation paths. | Java POI is useful as comparative extraction evidence, not a primary mutation runtime for UMMAYA's Python/TUI stack. |

## Candidate Scorecard

Weights: format fidelity 25, write safety 25, render/reread evidence 15,
local-only execution 15, license/maintenance 10, implementation cost 10.

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Direct `.doc/.xls/.ppt` binary mutation | 22 | Reject | High corruption risk and no current UMMAYA engine. |
| Metadata-only forever | 66 | Partial | Safe, but users with legacy attachments cannot author derivatives. |
| Java POI bridge for direct legacy mutation | 58 | Reject as primary | Heavy runtime boundary and upstream docs warn about incomplete/risky areas. |
| LibreOffice headless conversion to OOXML derivative | 84 | Adopt after gates | Aligns with Microsoft modern-format direction and UMMAYA's existing DOCX/XLSX/PPTX writers. |
| Cloud conversion service | 18 | Reject | Violates local-only document privacy and CI/no-live-channel constraints. |

## Final Direction

Legacy Office should be promoted only as an explicit derivative path:

1. `.doc` -> `.docx`
2. `.xls` -> `.xlsx`
3. `.ppt` -> `.pptx`

The original binary document remains immutable. The generated OOXML derivative
must carry source SHA-256, converter id, output SHA-256, and conversion lineage,
then run through the existing promoted DOCX/XLSX/PPTX inspect, fill, render,
save, re-read, diff, and TUI evidence path.

## Implemented Loop 1 - Readiness Probe

This loop added the fail-closed readiness probe:

- `src/ummaya/tools/documents/legacy_office_promotion_probe.py`
  - Reports `.doc/.xls/.ppt` derivative readiness.
  - Detects local `soffice`/`libreoffice` availability.
  - Emits explicit target OOXML formats and recommended `--convert-to` args.
  - Keeps `legacy_office_runtime_not_promoted` and
    `direct_legacy_office_write_blocked` in reasons even when the candidate is
    available.
- `tests/tools/documents/test_legacy_office_promotion_probe.py`
  - Verifies missing local LibreOffice blocks promotion.
  - Verifies a fake local LibreOffice executable becomes `candidate_available`
    and is reported as a default derivative-bridge candidate rather than a
    direct legacy binary writer.
- `src/ummaya/evidence/runner.py`
  - Emits `document_legacy_office_probe_records` alongside HWP and ODF probe
    records.

## Implemented Loop 2 - Derivative Bridge

This loop added the single-primitive derivative execution path:

- `docs/adr/ADR-012-legacy-office-libreoffice-bridge.md`
  - Defines LibreOffice as an optional local conversion bridge, not a direct
    legacy binary writer.
- `src/ummaya/tools/documents/models.py`
  - Adds `doc`, `xls`, and `ppt` to `DocumentFormat` as source formats while
    keeping them out of `PROMOTED_RUNTIME_DOCUMENT_FORMATS`.
- `src/ummaya/tools/documents/conversion.py`
  - Discovers local `soffice`/`libreoffice` and registers `.doc -> .docx`,
    `.xls -> .xlsx`, and `.ppt -> .pptx` conversion engines.
  - Supports `{outdir}` output discovery and validates OOXML package markers.
- `src/ummaya/tools/documents/registry.py`
  - Routes top-level `document(fill/save, legacy Office)` through immutable
    source artifact lineage and editable OOXML working derivatives.
- `tests/tools/documents/test_legacy_office_derivative_bridge.py`
  - Proves a `.doc` source is preserved, a `.docx` working derivative is
    patched, and a user-visible `.docx` export is saved.

## Next Gates

- Add owned `.doc`, `.xls`, and `.ppt` fixtures or generated binary fixtures
  with clear redistribution safety.
- Run real local LibreOffice fixture conversions in CI-compatible or developer
  evidence mode.
- Mark legacy Office complete in the all-format audit only after all three
  conversion families pass lineage, save/re-read, visible render, structured
  diff, and source-immutability gates.
