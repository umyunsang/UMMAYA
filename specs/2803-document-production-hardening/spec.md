# Feature Specification: Document Production Hardening

**Feature Branch**: `2803-document-production-hardening`  
**Created**: 2026-06-11  
**Status**: Draft - awaiting user approval before planning  
**Input**: User description: "Delete the prior public document harness spec and create a new production-grade document work epic. The system must handle real document authoring requests such as filling institutional forms, self-introduction forms, and business plans; ask the user for missing evidence through a Socratic loop; never fabricate unsupported content; support HWP/HWPX/DOCX/PDF; preserve and compare visual formatting; use rhwp as the initial HWP direct-edit candidate if it passes promotion gates; and execute future work through the LazyCodex planning/execution/review pipeline."

## Clarifications

### Session 2026-06-11

- Q: Who decides that the Socratic clarification loop may end? -> A: Agent checklist plus user approval.
- Q: What must the Socratic clarification loop closure checklist cover? -> A: User intent, spec completeness, and verification readiness.
- Q: Which remaining ambiguities may be accepted at Socratic clarification closure? -> A: Only engineering parameters that LazyCodex planning can decide from evidence.
- Q: What happens if a blocking ambiguity remains and the user asks to proceed anyway? -> A: Escalate to a LazyCodex reviewer verdict.
- Q: What format makes a LazyCodex reviewer verdict valid? -> A: Structured verdict with ambiguity id, classification, evidence path, proceed or block decision, and required next question.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Evidence-Bound Form Completion (Priority: P1)

A user provides an official or institutional form and asks UMMAYA to fill it so the user can submit the completed copy. UMMAYA identifies all required fields, determines which values can be filled from supplied evidence, asks targeted questions for missing information, drafts field values only from user-approved evidence, preserves the original file, writes a modified copy, and presents diff, render, re-read, provenance, and final approval evidence.

**Why this priority**: This is the minimum production behavior for common public, school, company, and institutional forms where users receive a template and must submit a completed artifact.

**Independent Test**: Use one representative public form fixture. The test passes only when UMMAYA produces an original-preserving modified copy, records missing fields, blocks unsupported content, shows render/diff evidence, re-reads the saved artifact, and obtains user approval before finalizing.

**Acceptance Scenarios**:

1. **Given** a supported blank form and user-supplied evidence for every required field, **When** the user asks UMMAYA to fill it, **Then** UMMAYA writes a completed copy, preserves the source, records provenance for each filled field, renders the result, re-reads the saved bytes, and asks for final confirmation before treating the artifact as complete.
2. **Given** a supported blank form with missing required evidence, **When** the user asks UMMAYA to fill it, **Then** UMMAYA asks targeted questions and leaves the affected fields unfilled until the user supplies evidence and approves the proposed content.
3. **Given** the user asks "대충 그럴듯하게 써줘" without supporting facts, **When** the document requires factual content, **Then** UMMAYA refuses fabrication, lists the missing evidence, and keeps the document unchanged.

---

### User Story 2 - Socratic Narrative Document Authoring (Priority: P1)

A user provides a self-introduction form, business plan, application form, proposal, or similar document whose sections require written answers. UMMAYA extracts the questions and section constraints, runs a Socratic question loop per section, drafts intermediate answers from supplied evidence, asks for approval, and inserts only approved text into the document.

**Why this priority**: Narrative forms are a major real-use document category, and they cannot be safely completed from a template alone.

**Independent Test**: Use one self-introduction fixture and one business-plan fixture. The test passes only when each required section follows ask -> draft -> approval -> insert, and no unsupported claim appears in the saved document.

**Acceptance Scenarios**:

1. **Given** a self-introduction template with multiple prompts, **When** the user provides background facts for only one prompt, **Then** UMMAYA drafts and inserts only that approved answer and asks for evidence before drafting the remaining prompts.
2. **Given** a business-plan section requiring market size, budget, schedule, or performance claims, **When** the user provides no numeric basis or source, **Then** UMMAYA blocks drafting that claim and asks for concrete evidence.
3. **Given** the user edits the intermediate draft, **When** the edited text is approved, **Then** UMMAYA records the approval and inserts the edited version, not the previous draft.

---

### User Story 3 - Visual Formatting and Render Comparison (Priority: P1)

A user needs the submitted copy to retain or intentionally adjust fonts, font sizes, tables, colors, styles, page layout, and official form structure. UMMAYA preserves source formatting by default, applies only approved style changes, and provides render comparison artifacts that make layout regressions visible.

**Why this priority**: A filled document that loses official layout, table structure, fonts, or visual conformance is not submission-ready.

**Independent Test**: Use fixtures containing tables, styled runs, colored cells, mixed font sizes, and constrained fields. The test passes only when unchanged regions remain visually equivalent and changed regions are localized, explainable, and reviewable.

**Acceptance Scenarios**:

1. **Given** a form with tables, colors, and specified font sizes, **When** UMMAYA fills text fields, **Then** unchanged visual regions remain within the accepted render-comparison threshold and changed field bounding boxes are highlighted.
2. **Given** a proposal or report where style improvement is allowed, **When** UMMAYA proposes a design change, **Then** the change is presented for approval before mutation and is recorded separately from content changes.
3. **Given** a field value overflows its original space, **When** UMMAYA prepares the modified copy, **Then** it either adjusts within allowed layout rules with render evidence or asks the user whether to shorten, resize, or leave the field blank.

---

### User Story 4 - Direct HWP Editing Candidate Promotion (Priority: P2)

UMMAYA treats direct HWP read, edit, save, re-read, and render comparison as the target behavior when a candidate engine proves it can safely handle real fixtures. The initial candidate selected for evaluation is `edwardkim/rhwp`; it must remain unpromoted until UMMAYA evidence proves direct HWP mutation is safe for the required fixture set.

**Why this priority**: Korean public and institutional workflows still use HWP. A production harness cannot depend only on HWPX derivatives if a safe direct HWP engine can be promoted, but direct HWP write must be earned by evidence.

**Independent Test**: Use real HWP fixtures with body text, fields, tables, styles, and saved-byte re-read. The test passes only when the edited HWP saves successfully, re-opens with expected structure/content/style, and render comparison is reviewable.

**Acceptance Scenarios**:

1. **Given** a HWP fixture with fillable content and tables, **When** the candidate engine edits and saves the file, **Then** the saved HWP re-reads with expected content, table structure, style metadata, and render comparison evidence.
2. **Given** a HWP fixture using unsupported constructs, **When** the candidate engine cannot preserve the document safely, **Then** UMMAYA returns a typed blocked result and does not silently fallback to a lossy conversion path.
3. **Given** a promoted HWP path, **When** a later regression breaks render or re-read equivalence, **Then** the promotion gate fails and the capability is removed from model-visible success paths until repaired.

---

### User Story 5 - Real TUI Multi-Turn Verification (Priority: P2)

A reviewer exercises the feature through the real UMMAYA TUI using ordinary Korean requests. The visible flow must show document analysis, Socratic questions, user answers, intermediate drafts, approvals, insertion, render/diff/re-read artifacts, result cards, and the final answer in the correct order.

**Why this priority**: The user-facing contract is the real conversational tool loop, not only isolated document-library tests.

**Independent Test**: Drive `bun run tui` with a tmux-captured multi-turn Korean scenario. The test passes only when the captured artifact proves progress, tool calls, questions, approvals, document mutation, and final answer boundaries.

**Acceptance Scenarios**:

1. **Given** a narrative document fixture, **When** a Korean user asks UMMAYA to complete it, **Then** the TUI asks for missing evidence before drafting and does not present unsupported content as final.
2. **Given** a completed approved draft, **When** UMMAYA inserts it into the document, **Then** the TUI shows the insertion result, render/diff/re-read evidence, and final confirmation request before completion.

### Edge Cases

- Encrypted, corrupted, password-protected, scanned-only, XFA-only, malformed, or unsupported-version documents must fail closed with typed reasons and no claimed successful write.
- Documents containing prompt injection text must be treated as untrusted document content; injected instructions must not override system, tool, provenance, or approval policy.
- User-provided private or sensitive documents may be used only as local evidence and must not be committed as fixtures.
- Content with no user-provided basis must remain blank or marked as missing; it must not be invented to improve fluency.
- The system must distinguish user-approved style changes from automatic layout preservation.
- The system must preserve source files and write modified copies only.
- A partial completion is allowed only when missing fields are explicitly listed and approved by the user as intentionally blank.
- Long-running render, comparison, or TUI proof runs must be resumable and must not leave stale temporary files, tmux sessions, browser sessions, or artifact-store entries without cleanup receipts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: UMMAYA MUST preserve the original source document bytes and write any mutation to a separate modified copy.
- **FR-002**: UMMAYA MUST support HWP, HWPX, DOCX, and PDF as first-class scope targets for inspection, authoring decisions, render evidence, and blocked-capability reporting.
- **FR-003**: UMMAYA MUST detect document fields, questions, tables, sections, required blanks, constraints, and visible layout regions before proposing content insertion.
- **FR-004**: UMMAYA MUST run a Socratic evidence-collection loop when required content cannot be derived from the document and user-provided facts.
- **FR-005**: UMMAYA MUST NOT draft or insert factual, autobiographical, business, financial, institutional, legal, academic, or performance claims unless the user supplies supporting evidence or explicitly approves the exact claim as their own supplied statement.
- **FR-006**: UMMAYA MUST treat "대충 그럴듯하게 써줘", "알아서 채워줘", and similar requests as requests to begin document analysis and evidence collection, not as permission to fabricate.
- **FR-007**: UMMAYA MUST generate intermediate drafts per field, question, or section and obtain user approval before inserting each approved unit into the document.
- **FR-008**: UMMAYA MUST leave fields blank or mark them as unresolved when the user does not provide required evidence.
- **FR-009**: UMMAYA MUST record field-level provenance including source, confidence, evidence span or user answer reference, edit operation, reviewer note, timestamp, and approval state.
- **FR-010**: UMMAYA MUST present a final confirmation gate that supports approve, edit, leave blank, and cancel for document content changes.
- **FR-011**: UMMAYA MUST apply a stronger confirmation gate for risky fields such as identity, payment, tax, welfare, legal, health, immigration, signature, or submission-certification fields.
- **FR-012**: UMMAYA MUST preserve fonts, font sizes, tables, colors, styles, paragraph layout, page structure, and official form structure by default.
- **FR-013**: UMMAYA MUST separate content edits from visual/design edits and require explicit approval before applying style improvements outside required layout preservation.
- **FR-014**: UMMAYA MUST produce render comparison artifacts including changed-field bounding boxes, full-page similarity scoring, and reviewer-readable overlay or side-by-side output.
- **FR-015**: UMMAYA MUST re-read saved modified documents and compare saved content, structure, style metadata, and render output against the approved edit plan before reporting success.
- **FR-016**: UMMAYA MUST return typed blocked results for unsupported or unsafe document operations instead of silently routing to a lossy fallback.
- **FR-017**: UMMAYA MUST evaluate `edwardkim/rhwp` as the initial direct HWP edit/save candidate and keep it unpromoted until real HWP fixtures prove read, edit, save, re-read, style preservation, and render comparison.
- **FR-018**: UMMAYA MUST fail the HWP direct-edit path if the candidate engine cannot preserve required content, tables, style, layout, or saved-byte re-read evidence.
- **FR-019**: UMMAYA MUST include at least three public/agency submit-form fixtures and at least three narrative document fixtures before the feature can pass acceptance.
- **FR-020**: UMMAYA MUST keep private user documents local-only and out of committed fixtures, logs, and evidence artifacts.
- **FR-021**: UMMAYA MUST verify the feature through deterministic/fake LLM paths for CI and live K-EXAONE/FriendliAI manual acceptance for final user-visible behavior.
- **FR-022**: UMMAYA MUST verify the real TUI path with a natural Korean multi-turn scenario covering analysis, questions, answers, draft approval, insertion, diff/render/re-read evidence, result card, and final answer.
- **FR-023**: UMMAYA MUST measure both document correctness and Socratic loop quality, including unsupported-content blocking, question relevance, ambiguity reduction, approval compliance, and evidence sufficiency.
- **FR-024**: UMMAYA MUST define Ralph completion as automated tests, fake-LLM TUI scenario, live K-EXAONE manual TUI acceptance, independent reviewer PASS, and attached evidence artifacts.
- **FR-025**: UMMAYA MUST use the LazyCodex workflow for implementation execution after this spec is approved: `$ulw-plan` for decision-complete planning, `$start-work` for durable checklist execution, `$ulw-loop` where open-ended verification must continue until evidence-backed completion, and `review-work` for final multi-lane review.
- **FR-026**: UMMAYA MUST NOT begin implementation from this spec until the user approves the spec and the resulting LazyCodex/Prometheus plan.
- **FR-027**: UMMAYA MUST treat the deleted `specs/2802-public-doc-harness/` artifacts as retired and must not use them as the active source of truth for new planning.
- **FR-028**: UMMAYA MUST end the Socratic clarification loop only after the agent presents a checklist-backed closure rationale and the user explicitly approves that the remaining ambiguity is acceptable for planning.
- **FR-029**: The Socratic clarification closure checklist MUST cover user intent, spec completeness, and verification readiness before the agent may request user approval to stop asking clarification questions.
- **FR-030**: The Socratic clarification closure checklist MUST classify any remaining ambiguity as either blocking or non-blocking; only engineering parameters that the LazyCodex planning workflow can decide from repository, fixture, research, or verification evidence may be marked non-blocking.
- **FR-031**: User intent, safety constraints, fabrication policy, approval gates, scope boundaries, acceptance criteria, and Ralph completion conditions MUST NOT remain ambiguous at Socratic clarification closure.
- **FR-032**: If the agent classifies an ambiguity as blocking and the user asks to proceed anyway, UMMAYA MUST escalate to an independent LazyCodex reviewer verdict before planning or implementation starts.
- **FR-033**: A LazyCodex reviewer may allow progress only by either reclassifying the ambiguity as a non-blocking engineering parameter with an evidence path, or by confirming that the ambiguity is blocking and requiring another Socratic clarification question.
- **FR-034**: A LazyCodex reviewer verdict for disputed ambiguity MUST be structured with ambiguity id, classification, evidence path, proceed-or-block decision, and required next question when the decision is block.

### Key Entities *(include if feature involves data)*

- **Document Artifact**: Immutable source copy, modified copy, working derivative when needed, hashes, file format, capability profile, and storage location.
- **Document Field**: A fillable blank, detected question, table cell, paragraph slot, checkbox, or visual region requiring content or confirmation.
- **Evidence Item**: User answer, uploaded source, document excerpt, numeric basis, citation, or reviewer note that supports a draft or field value.
- **Socratic Loop State**: Per-field or per-section question history, missing information, ambiguity status, intermediate draft, approval state, and termination reason.
- **Edit Plan**: Ordered content and style operations approved for insertion, including target locations, layout constraints, risk level, and rollback behavior.
- **Render Evidence**: Page images, changed bounding boxes, similarity scores, overlays, and reviewer-readable comparison artifacts.
- **Provenance Ledger**: Field-level audit trail linking evidence, drafts, approvals, edit operations, saved bytes, re-read output, and final confirmation.
- **Promotion Gate**: Candidate-engine evidence package proving that a document format operation is safe to expose as a successful model-visible capability.
- **Clarification Closure Record**: Agent-produced summary of answered questions, remaining uncertainties classified as blocking or non-blocking, evidence path for each non-blocking engineering parameter, structured LazyCodex reviewer verdict for any disputed blocking ambiguity, user-intent checklist status, spec-completeness checklist status, verification-readiness checklist status, and the user's explicit approval to stop clarification and begin planning.
- **LazyCodex Reviewer Verdict**: Structured disputed-ambiguity decision containing ambiguity id, classification, evidence path, proceed-or-block decision, and required next question when blocked.
- **LazyCodex Work Plan**: Approved Prometheus plan and Boulder ledger that drive implementation, verification, review, and completion evidence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across the required fixture set, 100% of saved successful documents preserve the original source artifact and produce a separate modified copy.
- **SC-002**: Across the required fixture set, 0 unsupported factual claims are drafted or inserted without user-provided evidence and explicit approval.
- **SC-003**: For every successful document mutation, 100% of changed fields include provenance, approval state, re-read evidence, and render comparison evidence.
- **SC-004**: For unchanged visual regions in accepted fixtures, render comparison stays within the documented similarity threshold; every threshold breach is either approved as an intentional style change or blocks completion.
- **SC-005**: The Socratic loop resolves or explicitly marks 100% of required fields and narrative prompts as approved, edited, intentionally blank, canceled, or blocked.
- **SC-006**: The HWP direct-edit path is not promoted unless all selected HWP fixtures pass read, edit, save, re-read, style preservation, table preservation, and render comparison gates.
- **SC-007**: The real TUI proof captures at least one complete Korean multi-turn form scenario and one complete Korean multi-turn narrative scenario through final confirmation.
- **SC-008**: CI uses deterministic/fake LLM verification for repeatability, while final acceptance includes a manually reviewed live K-EXAONE/FriendliAI run.
- **SC-009**: The feature is not marked complete until LazyCodex execution records an approved plan, completed checklist, independent review PASS, and cleanup receipts.
- **SC-010**: Planning does not begin until the spec contains a clarification closure record showing agent checklist completion and explicit user approval to end the Socratic clarification loop.
- **SC-011**: The clarification closure record is accepted only when user intent, spec completeness, and verification readiness are each marked complete or explicitly blocked with a user-approved reason.
- **SC-012**: No clarification closure record is accepted if it leaves unresolved user intent, safety policy, fabrication policy, approval policy, scope, acceptance, or Ralph completion ambiguity.
- **SC-013**: When a blocking ambiguity is disputed, planning begins only after the closure record includes the LazyCodex reviewer verdict and the verdict either reclassifies the item as non-blocking with evidence or requires more clarification.
- **SC-014**: A disputed ambiguity cannot be considered resolved by reviewer escalation unless the reviewer verdict includes all required structured fields.

## Assumptions

- The active product surface remains UMMAYA's conversational TUI and document tool loop, not a standalone web editor or cloud document service.
- Supported document operations are local/offline; no live government, institution, identity, payment, certificate, or submission channel is called by this feature.
- HWP direct edit is a target capability, but promotion depends on evidence rather than the existence of a promising OSS project.
- User-provided private documents may be used during local manual acceptance only when sensitive content is redacted from durable artifacts.
- Public official or institution-published blank forms are the preferred committed fixtures when licensing and privacy allow.
- Narrative document authoring must prioritize truthful, evidence-bound drafting over fluency or persuasive polish.
- LazyCodex is the execution harness for implementation after spec approval; Spec Kit artifacts are the requirements input and not the execution engine.

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- Actual online submission, receipt lookup, payment, identity verification, certificate issuance, or agency-side transaction completion - this feature creates local submission-ready documents only.
- Mobile app, web app, or cloud document-processing API - this feature is for the local UMMAYA conversational harness.
- Remote upload to proprietary document-conversion services - document processing must remain local/offline for this feature.
- Fabricating user history, credentials, business facts, financial numbers, institutional claims, or autobiographical evidence - unsupported content must stay blank or blocked.
- Committing private user documents or sensitive personal data as fixtures - only public or sanitized fixtures may be versioned.

### Deferred to Future Work

| Item | Reason for Deferral | Target Epic/Phase | Tracking Issue |
|------|---------------------|-------------------|----------------|
| Actual agency/institution submission after document generation | Requires separate live-channel policy, credential, permission, and receipt handling | Future submit/check channel epic | NEEDS TRACKING |
| Cloud collaboration or browser-based document editing UI | Outside the TUI-first UMMAYA harness scope | Future UI product epic | NEEDS TRACKING |
| Full visual redesign assistant for arbitrary reports and proposals | This epic allows constrained approved style changes only; broad design generation requires separate UX policy and evaluation | Future document design epic | NEEDS TRACKING |
| New live public API adapters related to forms | This epic is local document processing only and must not call live citizen-infrastructure APIs | Future public-service adapter epic | NEEDS TRACKING |
