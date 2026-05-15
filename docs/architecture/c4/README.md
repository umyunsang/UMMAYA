# UMMAYA C4 Architecture Model

This directory contains the canonical C4 model for the UMMAYA docs site.

Source of truth:

- `workspace.dsl`: Structurizr DSL model.

Generated artifacts:

- `out/dot/*.dot`: Structurizr CLI DOT export.
- `../../docs-site/public/architecture/c4/*.svg`: Graphviz-rendered SVGs embedded in the docs site.

Regenerate diagrams from the repository root:

```bash
bash scripts/render_c4_diagrams.sh
```

Local tools used:

- `structurizr-cli` for DSL validation and DOT export.
- `dot` from Graphviz for SVG rendering.

The model intentionally uses small C4 views rather than one large diagram:

- **National AX context** explains where UMMAYA sits.
- **Query loop** shows the first control loop after a user asks.
- **Query engine core** shows the internal control steps.
- **Public lookup flow** shows Live public evidence returning.
- **Protected Handoff flow** shows permission and Handoff boundaries.
- **Docs publish flow** shows the documentation CI/CD path.

Diagram rules:

- One diagram answers one reader question.
- Node names use short nouns; relationship labels use short verbs.
- Long explanations stay in prose, captions, tables, and trace examples.
- Do not force all runtime, adapter, permission, model, and deployment detail into
  one image.
