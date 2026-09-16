# Enhancement Roadmap

RiskLens v1 is stable: scoring engine, CLI, AI narrator, Jira export, and a local web UI (marketing site + real questionnaire) are all working and tested. This document is the parking lot for what could come next, ranked by effort, not by priority. Nothing here is committed to; it's a menu, not a schedule.

Effort tags: **Minor** (an evening), **Moderate** (a focused day or two), **Major** (a real feature, spans multiple files/decisions).

## Framework & scoring

1. **[Major]** Support additional frameworks beyond NIST CSF (CIS Controls v8, ISO 27001, SOC 2 Trust Services Criteria), with a framework picker on the form.
2. **[Moderate]** Let users upload a custom framework YAML instead of only the two built-ins, with schema validation and a clear error if it's malformed.
3. **[Shipped]** ~~Historical trend tracking: save assessments over time and show score delta between runs.~~ Shipped via `history.py`; see the "Posture over time" section on the report page.
4. **[Moderate]** Industry-specific weight profiles (a fintech org and a healthcare org shouldn't necessarily weight the same questions identically).
5. **[Shipped]** ~~Expose `--threshold` (finding sensitivity) as a form field in the web UI.~~ Shipped: `Assessment.finding_threshold` is now a real field (default preserved, older answer files and YAML round-trip unaffected), so the value chosen on the questionnaire survives every later re-score -- recording/clearing a decision, simulating a fix, exporting to Jira -- instead of silently resetting to the default. The web form offers four presets (Lenient/Standard/Strict/Very strict, each labeled against `MATURITY_LEVELS` via the new `finding_sensitivity_label()`); the CLI's `--threshold` keeps accepting any float. Fixed a real bug caught while wiring this up: the CLI's report showed the *file's* threshold, not the one `--threshold` had actually scored with, whenever they differed.
6. **[Shipped]** ~~Add an "evidence type" tag to notes (policy doc / audit log / verbal confirmation) so findings can be sorted by how well-supported they are.~~ Shipped: `Answer.evidence_type` is a sibling of `Answer.notes` -- the note says what was found, this says how solidly it was established -- with four values ranked weakest to strongest in `EVIDENCE_TYPES` (unspecified, verbal confirmation, policy doc, audit log; the log outranks the policy because a policy says what is supposed to happen and a log shows it did). The questionnaire puts a dropdown beside each note field, the value round-trips through `dump_assessment()`/`parse_assessment()`, and the findings table renders it as a badge under the note, reusing the existing `.band-badge` styling and colored by strength rather than by name. A sort control above the table regroups findings by weakest or strongest support; ties hold their priority order and the "Priority (default)" option restores the original ranking exactly, since both sort keys stay on the row. Default is "unspecified" everywhere: answer files written before this field load unchanged (as does the bare-score shorthand), an unrecognized value normalizes to the default instead of raising, and `dump_assessment()` writes the key only when it is set, so a file with no evidence types dumps exactly as it did before. The Jira CSV and Markdown report never carried note text, so both ignore the new field untouched; `simulate.py` now carries the whole `Answer` forward with `replace()` rather than rebuilding it, which had been quietly dropping anything recorded alongside the score. `examples/sample_answers.yaml` gained a realistic spread of evidence types (and one answer deliberately left untagged) so the live demo shows the badge and the sort doing something.

## Web UI / UX

7. **[Moderate]** Save/load assessments to a local file (or browser `localStorage`) so a half-finished questionnaire survives a page refresh.
8. **[Major]** Side-by-side comparison view: two orgs, or the same org at two points in time.
9. **[Shipped]** ~~Live progress indicator on the questionnaire.~~ Shipped.
10. **[Moderate]** PDF export of the report, in addition to the existing Markdown/HTML/CSV outputs.
11. **[Shipped]** ~~Print-friendly stylesheet for the report page (`@media print`).~~ Shipped: an `@media print` block in `static/style.css`, scoped to `body.report-page` (new `body_class` block in `base.html`) so the marketing pages and questionnaire print unchanged. Nav, footer, theme toggle, the simulate/decision/Jira controls, the checkbox column and the raw-YAML section drop out; the collapsed "engineering view" `<details>` prints expanded; the palette is re-pointed to black-on-white inside the block so a dark-theme session still prints legibly; severity and decision badges lose their tinted fill and print as outlined text labels, so nothing depends on color; `thead` repeats per page and rows, cards and the trend box use `break-inside: avoid`. Verified by printing a rendered report to PDF with headless Chrome.
12. **[Minor]** Mobile polish pass specifically on the pill-row radio controls; they're usable but not optimized for small touch targets.
13. **[Shipped]** ~~Manual dark/light theme toggle.~~ Shipped.
14. **[Moderate]** Autosave draft answers to `localStorage` as the user fills out the form.
15. **[Shipped]** ~~Highlight unanswered questions before submit instead of silently scoring them as 0.~~ Shipped: unanswered questions still score as 0 (unchanged, intentional), but the first submit with gaps is caught client-side, highlights each unanswered question and its "Unanswered" tag, and shows a banner explaining they'll score as 0 -- submitting again goes through. Editing any answer after that clears its highlight and re-arms the check for any gaps still remaining.

## AI layer

16. **[Moderate]** Stream the AI narrative token-by-token instead of waiting for the full response before rendering.
17. **[Minor]** Toggle for narrative tone/audience (board-level vs. technical-team summary).
18. **[Moderate]** Let the AI suggest a remediation owner based on an org-chart-shaped input, instead of a generic role placeholder.
19. **[Major]** Multi-turn follow-up chat about a finding ("why is this priority one?") grounded in the same structured findings the narrator already receives.
20. **[Minor]** Cache AI narratives for identical assessments so re-running the same submission doesn't re-spend tokens.

## Integrations

21. **[Major]** Direct Jira API integration (create tickets via API using a Jira token) as an alternative to the CSV export.
22. **[Moderate]** Slack/Teams webhook to post the executive summary to a channel.
23. **[Moderate]** Export to PowerPoint for board presentations, matching the "leadership-ready" positioning on the landing page.
24. **[Major]** Formalize a JSON API endpoint (not just HTML routes) so RiskLens could be called programmatically by other tooling.
25. **[Major]** A GitHub Action that runs a RiskLens assessment against a repo's security posture as part of CI.

## Engineering & quality

26. **[Minor]** Structured logging for the web app (local-only, no external telemetry).
27. **[Minor]** Basic rate limiting / request size caps on the web form: defensive hardening, relevant only if this is ever made public (see [issue #7](https://github.com/Barak-Nisim/risklens/issues/7) discussion on why it currently isn't).
28. **[Moderate]** Dockerfile + docker-compose as an alternative to `pip install` for local setup.
29. **[Minor]** Add `mypy` or `pyright` to CI alongside the existing `ruff` lint step.
30. **[Moderate]** Snapshot/golden-file tests for the rendered HTML report and CSV output, to catch unintended template regressions that content-substring tests might miss.

## Shipped since this list was written (2026-08-25)

Not originally on this list, added as they were built:

31. **[Shipped]** What-if scenario simulation: checkboxes on the findings table, "simulate fixing this" against a hypothetical target score, before/after comparison. See `risklens/simulate.py`.
32. **[Shipped]** Risk acceptance workflow: accept/mitigate/transfer/defer a finding with a rationale, persisted per org. See `risklens/decisions.py`.

## Bigger bets (real architecture decisions, plan formally before building)

33. **[Major]** Executive risk dashboard: turn the report into "Top 5 risks, business impact, owner, recommended action, residual risk" instead of the current full findings table -- a genuine information-architecture redesign of the report, not just an addition to it.
