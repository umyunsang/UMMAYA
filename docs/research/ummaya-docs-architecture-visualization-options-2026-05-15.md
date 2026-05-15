# UMMAYA Docs Architecture Visualization Options

Date: 2026-05-15

## Corrected Decision

UMMAYA architecture visuals should not try to prove the whole system in one image.
The docs site should use small C4/Structurizr-generated SVGs where each image answers
one reader question:

- context: where UMMAYA sits;
- loop: what happens first when a user asks;
- engine: which control steps exist inside the query engine;
- public lookup: how a Live public result returns;
- protected action: where permission and Handoff stop the flow;
- docs publishing: how the docs site is built and served.

The writing rule is the same as the visual rule: depth is not density. Put the
architecture explanation in prose, tables, and trace examples; keep the diagram as
the reader's orientation map.

## Sources Checked

- C4 model diagrams: https://c4model.com/diagrams
- Structurizr DSL: https://docs.structurizr.com/dsl
- U.S. Web Design System data visualization guidance: https://designsystem.digital.gov/components/data-visualizations/
- W3C WAI Images Tutorial: https://www.w3.org/WAI/tutorials/images/
- Nielsen Norman Group progressive disclosure: https://www.nngroup.com/articles/progressive-disclosure/
- Local UMMAYA writing skill: `.agents/skills/ummaya-doc-writing/SKILL.md`

## Findings

### One diagram should tell one story

The C4 model is useful because it separates abstraction levels. Context, container,
component, code, dynamic, and deployment views should not be collapsed into one
visual. The official C4 guidance says the zoom levels let authors tell different
stories to different audiences, and not every level is required. For UMMAYA, this
means the docs site should split context, query loop, query-engine internals, public
lookup, protected Handoff, and docs publishing into separate diagrams.

### Reduce cognitive load before adding detail

USWDS data visualization guidance is directly applicable even though these are
architecture diagrams, not charts: a visual should have one central theme and no
more than two or three concepts when possible. If colors, labels, and arrows need
long explanations inside the image, the image is carrying prose that should move
back into the page text.

### Use progressive disclosure across the page

Progressive disclosure supports UMMAYA's architecture page sequence. The first view
should show only the few concepts needed for the reader's current task. More
specialized details should appear later or on deeper pages. For UMMAYA, this avoids
the earlier overflow failure: a user can understand "ask -> route -> reason ->
answer" before seeing adapter retrieval, permission classification, and Handoff.

### Accessibility requires text equivalents

W3C WAI guidance treats diagrams as informative or complex images. The image should
have a useful text alternative, and the page should explain the intended meaning in
plain text. UMMAYA should not depend on tiny text inside SVG boxes to carry the only
meaning. Captions and nearby prose must state the point of each diagram.

## Applied Rules

- Maximize verbs and nouns, minimize sentences inside nodes.
- Prefer labels such as `ask`, `route`, `context`, `select`, `reason`, `answer`.
- Keep each diagram focused on one reader question.
- Use multiple small SVGs instead of one overloaded C4 view.
- Keep prose responsible for nuance: Live/Mock/Handoff, consent, citations, failure
  modes, and traceability belong in the surrounding documentation.
- Keep images responsive: no forced 960px minimum width, no horizontal overflow as
  the default reading path.

## Implementation

- `docs/architecture/c4/workspace.dsl` now defines six focused views.
- `docs-site/public/architecture/c4/structurizr-01-national-ax-context.svg`
  explains placement.
- `docs-site/public/architecture/c4/structurizr-02-query-loop.svg` explains the
  first user turn.
- `docs-site/public/architecture/c4/structurizr-03-query-engine-core.svg` explains
  the query engine control steps.
- `docs-site/public/architecture/c4/structurizr-04-public-lookup-flow.svg` explains
  Live public lookup.
- `docs-site/public/architecture/c4/structurizr-05-protected-handoff-flow.svg`
  explains protected Handoff.
- `docs-site/public/architecture/c4/structurizr-06-docs-publish-flow.svg` explains
  docs CI/CD publication.
