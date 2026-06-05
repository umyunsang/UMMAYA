# ADR-012: Legacy Office LibreOffice Derivative Bridge

**Status**: Accepted
**Date**: 2026-06-03
**Initiative**: #2290
**Affected**:
- `src/ummaya/tools/documents/conversion.py`
- `src/ummaya/tools/documents/registry.py`
- `src/ummaya/tools/documents/models.py`
- `src/ummaya/tools/documents/legacy_office_promotion_probe.py`
- `tests/tools/documents/test_legacy_office_derivative_bridge.py`

## Context

Korean public-infrastructure document bundles still include Microsoft Office
97-2003 binary files: `.doc`, `.xls`, and `.ppt`. UMMAYA must let a citizen ask
for document work through the single `document` primitive, but direct binary
mutation is unsafe and does not match the existing promoted OOXML adapters.

The document harness already has the required safe shape:

1. source bytes are copied into immutable artifact storage;
2. writing happens only against a working derivative;
3. render, diff, save, and re-read evidence attach to the derivative;
4. user-visible export writes are explicit and permission-scoped.

## Current Sources

- `docs/vision.md`: UMMAYA keeps the Claude Code harness structure and swaps in
  Korean public-service tools.
- `docs/adr/ADR-010-workspace-bash-permission-boundary.md`: file mutation must
  remain under the appropriate primitive boundary.
- `docs/adr/ADR-011-hwp-conversion-bridge.md`: legacy binary public-document
  sources may be converted into editable derivatives, but original bytes remain
  immutable.
- Microsoft Open Specifications archive: `.doc`, `.xls`, and `.ppt` are legacy
  Office binary formats.
  <https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-offfflp/7b95d465-d508-4213-a403-38f745e63d96>
- Microsoft Support: modern Office documents use Open XML extensions such as
  `.docx`, `.xlsx`, and `.pptx`.
  <https://support.microsoft.com/en-us/office/open-xml-formats-and-file-name-extensions-5200d93c-3449-4380-8e11-31ef14555b18>
- LibreOffice Help: `soffice --convert-to ... --outdir ...` is the documented
  command-line conversion boundary, and the filter table exposes OOXML export
  filters for Writer, Calc, and Impress.
  <https://help.libreoffice.org/latest/en-US/text/shared/guide/convertfilters.html>

## Decision

UMMAYA supports legacy Office authoring only as a local derivative bridge:

- `.doc` source -> `.docx` working derivative
- `.xls` source -> `.xlsx` working derivative
- `.ppt` source -> `.pptx` working derivative

`DocumentFormat` includes `doc`, `xls`, and `ppt` so the single `document`
primitive can receive them as source formats. `PROMOTED_RUNTIME_DOCUMENT_FORMATS`
continues to exclude them because they are not directly mutable runtime formats.

When a real local `soffice` or `libreoffice` executable is discoverable, the
default conversion registry registers `LocalCliDocumentConversionEngine` entries
for the three derivative conversions. The bridge validates the executable,
requires `{source}` plus `{outdir}` or `{output}`, runs headlessly, verifies that
source SHA-256 is unchanged, and validates the OOXML package markers before the
derivative can be used.

## Permission Boundary

The bridge is allowed only through the `document` primitive. It must not be
called through `workspace_bash`, generic file adapters, or hidden fallback
routes. Successful mutation means:

1. original `.doc/.xls/.ppt` source artifact unchanged;
2. editable `.docx/.xlsx/.pptx` working derivative created;
3. promoted OOXML engine applies the patch;
4. render/diff/save evidence is attached to the derivative;
5. the user-visible export has the OOXML extension.

## Alternatives Considered

- **Direct legacy binary mutation**: rejected. It has high corruption risk and
  no promoted UMMAYA runtime.
- **Metadata-only forever**: rejected as the final path because users still need
  safe editable derivatives from legacy attachments.
- **Apache POI direct mutation bridge**: rejected as primary. It adds a Java
  boundary and upstream legacy write support is not a stronger fit than
  LibreOffice conversion followed by existing OOXML writers.
- **Remote conversion service**: rejected. User documents must remain local.

## Consequences

Positive:

- Natural `document(fill/save, legacy Office)` requests can proceed when the
  local bridge exists.
- The existing DOCX/XLSX/PPTX mutation, render, diff, save, and re-read gates
  remain the write authority.
- The audit can distinguish `derivative bridge implemented` from `direct binary
  promotion complete`.

Risks:

- Completion still depends on a real local LibreOffice executable and fixture
  conversions.
- LibreOffice filter output can vary by installed version, so promotion cannot
  be claimed without fixture evidence.

Mitigations:

- The registry is fail-closed when no executable exists.
- The conversion engine rejects empty output, missing output, source mutation,
  non-zero exit, timeout, and invalid OOXML containers.
- Evidence Fabric keeps `document_legacy_office_probe_records` so missing local
  bridge capability is visible instead of being counted as success.

## Verification

Focused gates:

```bash
uv run pytest tests/tools/documents/test_legacy_office_derivative_bridge.py tests/tools/documents/test_conversion_registry.py -q
uv run pytest tests/tools/documents/test_legacy_office_promotion_probe.py tests/tools/documents/test_intake_security.py -q
uv run pytest tests/tools/documents -q
uv run pytest tests/evidence tests/ci -q
```

The all-format audit remains incomplete until real `.doc`, `.xls`, and `.ppt`
fixtures pass local conversion, OOXML save/re-read, visible render, structured
diff, and source-immutability gates in this runtime.
