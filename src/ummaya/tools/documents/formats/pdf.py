# SPDX-License-Identifier: Apache-2.0
"""PDF adapter and AcroForm-only mutation boundary."""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject

from ummaya.tools.documents.engines import (
    DocumentInspectionEngine,
    DocumentMutationBlockedError,
    DocumentMutationEngine,
)
from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    FieldType,
    FormField,
    ImageReference,
    KnownDocumentFormat,
    MetadataValue,
    OperationType,
    ParagraphBlock,
    ScalarValue,
)

if TYPE_CHECKING:
    from ummaya.tools.documents.tool_defs import DocumentFieldPatch

PDF_CANDIDATE_ENGINES: tuple[str, ...] = (
    "pypdf-acroform",
    "pypdfium2-render-oracle",
    "qpdf-structure-oracle",
)

_PDF_FIELD_PREFIX = "/acroform/fields/"
_PDF_KOREAN_FORM_FONT_RESOURCE = "/UMMAYA_KR"
_PDF_KOREAN_FORM_FONT_SIZE = 11.0
logger = logging.getLogger(__name__)
_PYPDF_APPEARANCE_LOGGER = "pypdf.generic._appearance_stream"
_PYPDF_UNSUPPORTED_FONT_WARNING = "characters not supported by font encoding"


class PdfDocumentKind(StrEnum):
    """PDF structure class used by the AcroForm-only promotion gate."""

    acroform = "acroform"
    static = "static"
    scanned = "scanned"
    xfa = "xfa"
    encrypted = "encrypted"
    signed = "signed"


@dataclass(frozen=True)
class PdfStructureProfile:
    """Local PDF structure decision used before any mutation is attempted."""

    kind: PdfDocumentKind
    page_count: int
    field_count: int
    text_length: int
    image_count: int
    field_names: tuple[str, ...] = ()
    blocked_reason: BlockedReason | None = None


class PdfDocumentAdapter:
    """PDF adapter boundary backed by pypdf for AcroForm work."""

    adapter_id: str = "pypdf-acroform-adapter"
    known_formats: tuple[KnownDocumentFormat, ...] = (
        KnownDocumentFormat.pdf,
        KnownDocumentFormat.pdfa,
    )

    def __init__(
        self,
        inspection_engine: DocumentInspectionEngine | None = None,
        *,
        promote_default: bool = True,
    ) -> None:
        if inspection_engine is None and promote_default:
            inspection_engine = PypdfAcroFormEngine()
        self.promoted_formats: tuple[DocumentFormat, ...] = (
            (DocumentFormat.pdf,) if inspection_engine is not None else ()
        )
        self._inspection_engine = (
            validate_pdf_engine(inspection_engine) if inspection_engine is not None else None
        )

    @property
    def engine_id(self) -> str:
        """Return the wrapped PDF engine id for diagnostics."""
        if self._inspection_engine is None:
            return self.adapter_id
        return self._inspection_engine.engine_id

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Inspect a PDF through the promoted engine or known-only classifier."""
        if self._inspection_engine is None:
            profile = classify_pdf_document(path)
            return _extraction_for_profile(
                artifact_id=artifact_id,
                profile=profile,
                engine_id=self.adapter_id,
                warnings=["PDF is registered as known-only because no engine is registered."],
            )
        return self._inspection_engine.inspect(path, artifact_id=artifact_id)

    def normalize_fill_patches(
        self,
        patches: tuple[DocumentFieldPatch, ...],
        *,
        extraction: DocumentExtraction | None,
    ) -> tuple[DocumentFieldPatch, ...]:
        """Map AcroForm labels to native field paths when the field is known."""
        if extraction is None:
            return patches

        field_path_by_label = {
            _field_key(field.label): field.path
            for field in extraction.fields
            if field.path.startswith(_PDF_FIELD_PREFIX)
        }
        field_path_by_name = {
            _field_key(field.path.removeprefix(_PDF_FIELD_PREFIX)): field.path
            for field in extraction.fields
            if field.path.startswith(_PDF_FIELD_PREFIX)
        }
        normalized: list[DocumentFieldPatch] = []
        for patch in patches:
            key = _field_key(patch.target_path)
            target_path = (
                patch.target_path
                if patch.target_path.startswith("/")
                else field_path_by_label.get(key)
                or field_path_by_name.get(key)
                or patch.target_path
            )
            normalized.append(patch.model_copy(update={"target_path": target_path}))
        return tuple(normalized)


class PypdfAcroFormEngine:
    """PDF AcroForm read/write engine backed by pypdf and pypdfium2 evidence."""

    document_format = DocumentFormat.pdf
    engine_id = "pypdf-acroform"
    render_engine_id = "pypdfium2"
    render_artifact_extension = "png"
    render_mime_type = "image/png"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract PDF structure, AcroForm fields, text, and image references."""
        profile = classify_pdf_document(path)
        if profile.kind is PdfDocumentKind.encrypted:
            return _extraction_for_profile(
                artifact_id=artifact_id,
                profile=profile,
                engine_id=self.engine_id,
                warnings=["Encrypted PDFs are blocked before page or field extraction."],
            )

        reader = PdfReader(str(path), strict=False)
        fields = _form_fields(reader)
        paragraphs = _paragraphs(reader, artifact_id=artifact_id)
        images = _image_references(reader)
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=paragraphs,
            images=images,
            fields=fields,
            metadata=_profile_metadata(profile, engine_id=self.engine_id),
            warnings=_profile_warnings(profile),
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        """Apply AcroForm field values only when the PDF is fillable and unsigned."""
        profile = classify_pdf_document(path)
        if profile.kind is not PdfDocumentKind.acroform:
            _raise_profile_block(profile)

        field_values = _field_values_from_patch(patch)
        missing = sorted(set(field_values) - set(profile.field_names))
        if missing:
            raise ValueError(f"PDF AcroForm field not found: {missing}")

        reader = PdfReader(str(path), strict=False)
        writer = PdfWriter()
        writer.append(reader)
        pypdf_field_values = _field_values_for_pypdf_update(writer, field_values)
        auto_regenerate = _needs_regenerated_acroform_appearance(pypdf_field_values)
        with _suppress_expected_pypdf_appearance_warning(enabled=auto_regenerate):
            for page in writer.pages:
                writer.update_page_form_field_values(
                    page,
                    pypdf_field_values,
                    auto_regenerate=auto_regenerate,
                )

        output = io.BytesIO()
        writer.write(output)
        payload = output.getvalue()
        _verify_acroform_values(payload, field_values)
        _verify_visible_render_change(path.read_bytes(), payload)
        return payload

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        """Render each PDF page to PNG reviewer evidence with annotations visible."""
        _ = artifact_id, output_dir
        return _render_pdf_pages(path.read_bytes())


def validate_pdf_engine(engine: DocumentInspectionEngine) -> DocumentInspectionEngine:
    """Validate that an injected engine is scoped to PDF."""
    if engine.document_format is not DocumentFormat.pdf:
        raise ValueError("PDF adapter requires a pdf engine")
    return engine


def validate_pdf_mutation_engine(engine: DocumentInspectionEngine) -> DocumentMutationEngine:
    """Validate that an injected PDF engine can mutate fillable derivatives."""
    validate_pdf_engine(engine)
    if not isinstance(engine, DocumentMutationEngine):
        raise ValueError("PDF adapter requires a mutation-capable engine")
    return engine


def classify_pdf_document(path: Path) -> PdfStructureProfile:
    """Classify a local PDF without mutating it."""
    reader = PdfReader(str(path), strict=False)
    if reader.is_encrypted:
        return PdfStructureProfile(
            kind=PdfDocumentKind.encrypted,
            page_count=0,
            field_count=0,
            text_length=0,
            image_count=0,
            blocked_reason=BlockedReason.encrypted,
        )

    page_count = len(reader.pages)
    fields = _field_objects(reader)
    field_names = _field_names(reader)
    text_length = _text_length(reader)
    image_count = _image_count(reader)
    acroform = _acroform(reader)
    if acroform is not None and "/XFA" in acroform:
        return PdfStructureProfile(
            kind=PdfDocumentKind.xfa,
            page_count=page_count,
            field_count=len(fields),
            text_length=text_length,
            image_count=image_count,
            field_names=field_names,
            blocked_reason=BlockedReason.xfa_detected,
        )
    if "/Perms" in _root(reader) or _has_signature_field(fields):
        return PdfStructureProfile(
            kind=PdfDocumentKind.signed,
            page_count=page_count,
            field_count=len(fields),
            text_length=text_length,
            image_count=image_count,
            field_names=field_names,
            blocked_reason=BlockedReason.signature_detected,
        )
    if fields:
        return PdfStructureProfile(
            kind=PdfDocumentKind.acroform,
            page_count=page_count,
            field_count=len(fields),
            text_length=text_length,
            image_count=image_count,
            field_names=field_names,
        )
    if image_count > 0 and text_length == 0:
        return PdfStructureProfile(
            kind=PdfDocumentKind.scanned,
            page_count=page_count,
            field_count=0,
            text_length=text_length,
            image_count=image_count,
            blocked_reason=BlockedReason.scanned_pdf,
        )
    return PdfStructureProfile(
        kind=PdfDocumentKind.static,
        page_count=page_count,
        field_count=0,
        text_length=text_length,
        image_count=image_count,
        blocked_reason=BlockedReason.static_pdf,
    )


def _field_values_from_patch(patch: DocumentPatch) -> dict[str, str]:
    values: dict[str, str] = {}
    for operation in patch.operations:
        if operation.operation_type is not OperationType.set_field_value:
            raise ValueError(
                "PDF mutation supports AcroForm set_field_value operations only: "
                f"{operation.operation_type.value}"
            )
        if not operation.target_path.startswith(_PDF_FIELD_PREFIX):
            raise ValueError(f"PDF field target must start with {_PDF_FIELD_PREFIX}")
        field_name = operation.target_path.removeprefix(_PDF_FIELD_PREFIX)
        if not field_name:
            raise ValueError("PDF field target is missing the AcroForm field name")
        values[field_name] = "" if operation.value is None else str(operation.value)
    return values


def _verify_acroform_values(payload: bytes, field_values: dict[str, str]) -> None:
    reader = PdfReader(io.BytesIO(payload), strict=False)
    observed = reader.get_form_text_fields() or {}
    mismatches = {
        field_name: {"expected": expected, "observed": observed.get(field_name)}
        for field_name, expected in field_values.items()
        if observed.get(field_name) != expected
    }
    if mismatches:
        raise ValueError(f"PDF AcroForm re-read mismatch: {mismatches}")


def _field_values_for_pypdf_update(
    writer: PdfWriter,
    field_values: dict[str, str],
) -> dict[str, str | tuple[str, str, float]]:
    if not _has_non_ascii_field_value(field_values):
        return dict(field_values)
    font_resource = _register_embedded_unicode_form_font(writer)
    if font_resource is None:
        return dict(field_values)
    return {
        field_name: (
            (value, font_resource, _PDF_KOREAN_FORM_FONT_SIZE)
            if _has_non_ascii_text(value)
            else value
        )
        for field_name, value in field_values.items()
    }


def _needs_regenerated_acroform_appearance(
    field_values: dict[str, str | tuple[str, str, float]],
) -> bool:
    for value in field_values.values():
        if isinstance(value, tuple):
            continue
        if _has_non_ascii_text(value):
            return True
    return False


def _has_non_ascii_field_value(field_values: dict[str, str]) -> bool:
    return any(_has_non_ascii_text(value) for value in field_values.values())


def _has_non_ascii_text(value: str) -> bool:
    return any(ord(character) > 0x7F for character in value)


def _register_embedded_unicode_form_font(writer: PdfWriter) -> str | None:
    acroform = _dict_object(writer._root_object.get("/AcroForm"))  # noqa: SLF001
    if acroform is None:
        return None
    font_ref = _first_embedded_unicode_page_font(writer)
    if font_ref is None:
        return None

    default_resources = _dict_object(acroform.get("/DR"))
    if default_resources is None:
        default_resources = DictionaryObject()
        acroform[NameObject("/DR")] = default_resources
    default_fonts = _dict_object(default_resources.get("/Font"))
    if default_fonts is None:
        default_fonts = DictionaryObject()
        default_resources[NameObject("/Font")] = default_fonts
    font_name = NameObject(_PDF_KOREAN_FORM_FONT_RESOURCE)
    default_fonts[font_name] = font_ref
    return _PDF_KOREAN_FORM_FONT_RESOURCE


def _first_embedded_unicode_page_font(writer: PdfWriter) -> object | None:
    for page in writer.pages:
        resources = _dict_object(page.get("/Resources"))
        fonts = _dict_object(resources.get("/Font")) if resources is not None else None
        if fonts is None:
            continue
        for font_ref in fonts.values():
            font = _dict_object(font_ref)
            if font is None:
                continue
            if _is_embedded_unicode_font(font):
                return cast(object, font_ref)
    return None


def _is_embedded_unicode_font(font: DictionaryObject) -> bool:
    subtype = str(font.get("/Subtype", ""))
    return (
        subtype in {"/TrueType", "/Type0"}
        and "/ToUnicode" in font
        and ("/FontDescriptor" in font or "/DescendantFonts" in font)
    )


@contextmanager
def _suppress_expected_pypdf_appearance_warning(*, enabled: bool) -> Iterator[None]:
    if not enabled:
        yield
        return
    pypdf_logger = logging.getLogger(_PYPDF_APPEARANCE_LOGGER)
    warning_filter = _ExpectedPypdfAppearanceWarningFilter()
    pypdf_logger.addFilter(warning_filter)
    try:
        yield
    finally:
        pypdf_logger.removeFilter(warning_filter)


class _ExpectedPypdfAppearanceWarningFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return _PYPDF_UNSUPPORTED_FONT_WARNING not in record.getMessage()


def _verify_visible_render_change(before_payload: bytes, after_payload: bytes) -> None:
    before_pages = _render_pdf_pages(before_payload)
    after_pages = _render_pdf_pages(after_payload)
    if before_pages == after_pages:
        raise DocumentMutationBlockedError(
            BlockedReason.validation_failed,
            "PDF AcroForm fill did not change visible page rendering.",
        )


def _render_pdf_pages(payload: bytes) -> tuple[bytes, ...]:
    import pypdfium2 as pdfium  # type: ignore[import-untyped]  # noqa: PLC0415

    document = pdfium.PdfDocument(payload)
    try:
        document.init_forms()
        rendered: list[bytes] = []
        for page in document:
            try:
                bitmap = page.render(scale=2)
                try:
                    image = bitmap.to_pil()
                    output = io.BytesIO()
                    image.save(output, format="PNG")
                    rendered.append(output.getvalue())
                finally:
                    bitmap.close()
            finally:
                page.close()
        return tuple(rendered)
    finally:
        document.close()


def _raise_profile_block(profile: PdfStructureProfile) -> None:
    reason = profile.blocked_reason or BlockedReason.validation_failed
    raise DocumentMutationBlockedError(
        reason,
        f"PDF mutation blocked: {profile.kind.value} PDF cannot be edited through AcroForm fill.",
    )


def _extraction_for_profile(
    *,
    artifact_id: str,
    profile: PdfStructureProfile,
    engine_id: str,
    warnings: list[str],
) -> DocumentExtraction:
    return DocumentExtraction(
        artifact_id=artifact_id,
        metadata=_profile_metadata(profile, engine_id=engine_id),
        warnings=[*warnings, *_profile_warnings(profile)],
    )


def _profile_metadata(
    profile: PdfStructureProfile,
    *,
    engine_id: str,
) -> dict[str, MetadataValue]:
    return {
        "format": DocumentFormat.pdf.value,
        "engine_id": engine_id,
        "pdf_kind": profile.kind.value,
        "page_count": profile.page_count,
        "field_count": profile.field_count,
        "text_length": profile.text_length,
        "image_count": profile.image_count,
        "mutation_policy": "acroform_only",
        "render_oracle": PypdfAcroFormEngine.render_engine_id,
        "template_overlay_capability": "requires_template_baseline",
        "template_overlay_available": False,
        "template_overlay_required_evidence": (
            "baseline_bounding_boxes_and_pypdfium2_render_comparison"
        ),
    }


def _profile_warnings(profile: PdfStructureProfile) -> list[str]:
    if profile.kind is PdfDocumentKind.acroform:
        return [
            "PDF AcroForm fill is promoted; static, XFA, encrypted, and signed mutation is blocked."
        ]
    if profile.kind is PdfDocumentKind.encrypted:
        return ["Encrypted PDFs are blocked for inspection and mutation."]
    warnings = [f"{profile.kind.value} PDF mutation is blocked by the AcroForm-only gate."]
    if profile.kind in {PdfDocumentKind.static, PdfDocumentKind.scanned}:
        warnings.append(
            "PDF template overlay is deferred until a public-form baseline provides "
            "field bounding boxes and pypdfium2 render-comparison evidence."
        )
    return warnings


def _form_fields(reader: PdfReader) -> list[FormField]:
    extracted_fields = reader.get_fields() or {}
    text_fields = reader.get_form_text_fields() or {}
    fields: list[FormField] = []
    for field_name, raw_field in extracted_fields.items():
        field = cast(dict[str, Any], raw_field)
        field_type = _field_type(field.get("/FT"))
        fields.append(
            FormField(
                field_id=f"pdf-field-{_safe_field_id(field_name)}",
                label=str(field.get("/TU") or field.get("/T") or field_name),
                path=f"{_PDF_FIELD_PREFIX}{field_name}",
                field_type=field_type,
                required=False,
                current_value=text_fields.get(field_name, _scalar_field_value(field.get("/V"))),
                allowed_values=_allowed_values(field.get("/Opt")),
                source_confidence=Decimal("1"),
            )
        )
    return fields


def _paragraphs(reader: PdfReader, *, artifact_id: str) -> list[ParagraphBlock]:
    paragraphs: list[ParagraphBlock] = []
    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for line_index, line in enumerate(_non_empty_lines(text), start=1):
            paragraphs.append(
                ParagraphBlock(
                    block_id=f"pdf-page-{page_index:03d}-line-{line_index:03d}",
                    text=line,
                    source_path=f"{artifact_id}/pages/{page_index}/text[{line_index}]",
                )
            )
    return paragraphs


def _image_references(reader: PdfReader) -> list[ImageReference]:
    images: list[ImageReference] = []
    for page_index, page in enumerate(reader.pages, start=1):
        resources = _dict_object(page.get("/Resources"))
        xobjects = _dict_object(resources.get("/XObject")) if resources is not None else None
        if xobjects is None:
            continue
        for name, value in xobjects.items():
            image = _dict_object(value)
            if image is None or str(image.get("/Subtype")) != "/Image":
                continue
            images.append(
                ImageReference(
                    image_id=f"pdf-page-{page_index:03d}-{_safe_field_id(str(name))}",
                    source_path=f"/pages/{page_index}/resources/xobject/{name}",
                    content_type="application/pdf-image-xobject",
                )
            )
    return images


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _root(reader: PdfReader) -> DictionaryObject:
    return cast(DictionaryObject, _resolve(reader.trailer["/Root"]))


def _acroform(reader: PdfReader) -> DictionaryObject | None:
    return _dict_object(_root(reader).get("/AcroForm"))


def _field_objects(reader: PdfReader) -> tuple[DictionaryObject, ...]:
    acroform = _acroform(reader)
    if acroform is None:
        return ()
    fields = acroform.get("/Fields", ())
    return tuple(_walk_field_objects(fields))


def _walk_field_objects(fields: object) -> list[DictionaryObject]:
    field_objects: list[DictionaryObject] = []
    for field_ref in cast(Any, fields):
        field = _dict_object(field_ref)
        if field is None:
            continue
        field_objects.append(field)
        kids = field.get("/Kids")
        if kids is not None:
            field_objects.extend(_walk_field_objects(kids))
    return field_objects


def _field_names(reader: PdfReader) -> tuple[str, ...]:
    fields = reader.get_fields() or {}
    return tuple(str(field_name) for field_name in fields)


def _has_signature_field(fields: tuple[DictionaryObject, ...]) -> bool:
    return any(str(field.get("/FT")) == "/Sig" for field in fields)


def _text_length(reader: PdfReader) -> int:
    total = 0
    for page in reader.pages:
        try:
            total += len(page.extract_text() or "")
        except Exception as exc:  # pragma: no cover - malformed page evidence path.
            logger.warning("PDF page text extraction failed during classification: %s", exc)
            continue
    return total


def _image_count(reader: PdfReader) -> int:
    return len(_image_references(reader))


def _dict_object(value: object) -> DictionaryObject | None:
    resolved = _resolve(value)
    if isinstance(resolved, DictionaryObject):
        return resolved
    if isinstance(resolved, dict):
        return cast(DictionaryObject, resolved)
    return None


def _resolve(value: object) -> object:
    if hasattr(value, "get_object"):
        return cast(Any, value).get_object()
    return value


def _field_type(raw_type: object) -> FieldType:
    field_type = str(raw_type)
    if field_type == "/Tx":
        return "text"
    if field_type == "/Btn":
        return "checkbox"
    if field_type == "/Ch":
        return "choice"
    if field_type == "/Sig":
        return "signature"
    return "unknown"


def _scalar_field_value(value: object) -> str | int | bool | None:
    if value is None:
        return None
    if isinstance(value, str | int | bool):
        return value
    return str(value)


def _allowed_values(value: object) -> list[ScalarValue]:
    if value is None:
        return []
    if isinstance(value, str | int | bool):
        return [value]
    if isinstance(value, list | tuple):
        return [_scalar_field_value(item) for item in value]
    return [str(value)]


def _field_key(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def _safe_field_id(value: str) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")
    return safe or "field"
