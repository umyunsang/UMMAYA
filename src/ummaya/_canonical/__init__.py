# SPDX-License-Identifier: Apache-2.0
"""Wheel-bundled canonical artifacts.

Sec H-1 (Spec 1636 review re-eval): hatch's ``force-include`` ships the
following files into installed wheels so canonical_acknowledgment.py +
checks.framework can resolve them via :mod:`importlib.resources` without
depending on the source-tree layout:

* ``security-review.md`` — PIPA §26 trustee acknowledgment canonical
  text. Hashed at import time by
  :mod:`ummaya.plugins.canonical_acknowledgment`.
* ``checklist_manifest.yaml`` — 50-row plugin validation checklist.
  Loaded by :mod:`ummaya.plugins.checks.framework` and the
  ``ummaya-plugin-validate`` CLI.
* ``document-tools.schema.json`` — Public AX document harness tool
  contract. Loaded by :mod:`ummaya.tools.documents.contracts`.

The mapping is in pyproject.toml under
``[tool.hatch.build.targets.wheel.force-include]``.

In editable installs this directory is empty and the loaders fall back
to the source-tree paths. Production wheels populate this directory
deterministically from the canonical sources.
"""
