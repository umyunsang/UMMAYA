# SPDX-License-Identifier: Apache-2.0
"""Contract helpers for the Public AX document harness."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, computed_field

DocumentPrimitive = Literal["find", "check", "send"]
DocumentPermission = Literal[
    "read_local_artifact",
    "write_derivative_artifact",
    "validate_local_artifact",
]
DocumentToolId = Literal[
    "document_inspect",
    "document_extract",
    "document_form_schema",
    "document_copy_for_edit",
    "document_apply_fill",
    "document_apply_style",
    "document_render",
    "document_validate_public_form",
    "document_save",
]

CONTRACT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "specs"
    / "2802-public-doc-harness"
    / "contracts"
    / "document-tools.schema.json"
)


class DocumentToolContract(BaseModel):
    """One model-visible document tool contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: DocumentToolId
    primitive: DocumentPrimitive
    input_schema: str = Field(pattern=r"^#/")
    output_schema: str = Field(pattern=r"^#/")
    permission: DocumentPermission


class DocumentToolContractCatalog(BaseModel):
    """Loaded catalog of document tool contracts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal["0.1.0"]
    tools: tuple[DocumentToolContract, ...] = Field(min_length=9)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tool_ids(self) -> tuple[str, ...]:
        """Return tool IDs in contract order."""
        return tuple(tool.tool_id for tool in self.tools)

    def by_tool_id(self, tool_id: DocumentToolId) -> DocumentToolContract:
        """Return the contract for one document tool ID."""
        for tool in self.tools:
            if tool.tool_id == tool_id:
                return tool
        raise KeyError(tool_id)


def load_contract_schema(path: Path = CONTRACT_SCHEMA_PATH) -> dict[str, object]:
    """Load the checked-in JSON Schema document."""
    raw = json.loads(_read_contract_schema_text(path))
    if not isinstance(raw, dict):
        raise ValueError(f"Contract schema must be an object: {path}")
    return cast(dict[str, object], raw)


def _read_contract_schema_text(path: Path) -> str:
    """Read the document contract schema from source tree or wheel resource."""
    if path.is_file():
        return path.read_text(encoding="utf-8")

    try:
        bundled = resources.files("ummaya._canonical").joinpath("document-tools.schema.json")
        with resources.as_file(bundled) as resource_path:
            if Path(resource_path).is_file():
                return Path(resource_path).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, AttributeError):
        pass

    raise FileNotFoundError(
        f"Document tool contract schema not found in source tree or bundled wheel resource: {path}"
    )


def load_document_tool_contracts(path: Path = CONTRACT_SCHEMA_PATH) -> DocumentToolContractCatalog:
    """Load UMMAYA document tool contracts from the checked-in schema extension."""
    schema = load_contract_schema(path)
    raw_tools = schema.get("x-ummaya-tools")
    if not isinstance(raw_tools, list):
        raise ValueError("Contract schema is missing x-ummaya-tools list")
    properties = schema.get("properties")
    version = "0.1.0"
    if isinstance(properties, dict):
        raw_version = properties.get("version")
        if isinstance(raw_version, dict) and raw_version.get("const") == "0.1.0":
            version = "0.1.0"
    return DocumentToolContractCatalog.model_validate(
        {
            "version": version,
            "tools": raw_tools,
        }
    )


def export_pydantic_schema(model: type[BaseModel]) -> dict[str, object]:
    """Export a Pydantic v2 model as a JSON Schema object."""
    return cast(dict[str, object], model.model_json_schema())
