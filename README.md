# RiskLens

[![CI](https://github.com/Barak-Nisim/risklens/actions/workflows/ci.yml/badge.svg)](https://github.com/Barak-Nisim/risklens/actions/workflows/ci.yml)

AI-assisted enterprise security readiness assessment tool. Scores a filled-out security questionnaire against NIST CSF 2.0, ranks the gaps by business impact, and (optionally) uses Claude to turn that into a leadership-facing executive summary, remediation plan, and Jira-importable backlog.

The scoring engine is deterministic, unit-tested, and has zero dependency on any AI service. The AI layer is a separate, optional piece bolted on top of it. See [`docs/architecture.md`](docs/architecture.md) for why it's split that way, and [`docs/scoring_methodology.md`](docs/scoring_methodology.md) for the scoring math.

## Quickstart

```bash
pip install -e ".[dev]"

# Deterministic report, no API key needed
risklens assess examples/sample_answers.yaml --no-ai
```

Sample output (excerpt):

```
# RiskLens Security Readiness Report: Acme Financial Services

**Date:** 2026-08-24
**Framework:** NIST Cybersecurity Framework 2.0
**Overall Score:** 2.04 / 4.0 (Defined)

## Function Scores

| Function | Score | Tier |
|---|---|---|
| Govern | 2.03 | Defined |
| Protect | 3.01 | Managed |
| Detect | 1.53 | Developing |
...

## Findings (prioritized)

| # | Question | Function / Category | Score | Weight |
|---|---|---|---|---|
| 1 | Can evidence for control effectiveness be produced on demand for an auditor? | Govern / Audit Readiness | 1/4 | 1.1 |
| 2 | Are existing vendors periodically reassessed for security and compliance risk? | Govern / Supply Chain / Vendor Risk | 1/4 | 1.0 |
...
```

### With AI narration

Copy `.env.example` to `.env`, add an `ANTHROPIC_API_KEY`, then drop `--no-ai`:

```bash
risklens assess examples/sample_answers.yaml
```

This adds an executive summary, a prioritized remediation plan, and a risk register to the report, generated from the same scored findings above (the AI narrates them, it doesn't recompute them).

### Export a Jira backlog

```bash
risklens assess examples/sample_answers.yaml --no-ai --jira-export backlog.csv
```

Produces a CSV with Summary / Issue Type / Priority / Description / Labels columns, ready to drag into Jira's CSV importer.

## Running your own assessment

Write an answers file in the same shape as `examples/sample_answers.yaml`: an org name, a date, and a score (0-4) plus optional notes for each question in `risklens/frameworks/nist_csf.yaml`.

## Web UI

```bash
risklens serve
```

Opens a small product site at `http://127.0.0.1:8000`:

- `/` -- a landing page explaining what RiskLens does, why it matters, and how it's different
- `/how-it-works` -- a walkthrough of the actual scoring methodology (not a simplified version of it)
- `/app` -- the live demo: an actual questionnaire (grouped by NIST CSF function, pre-filled with the sample data), not a YAML textarea. Submitting it scores the answers, renders the report, and shows a collapsed "View as YAML" section for anyone who wants to see the underlying data

All three pages sit on top of the same scoring engine, loader, and AI narrator the CLI uses. Not deployed publicly yet.

## Development

```bash
pytest      # 31 tests, all mocked where they touch the AI layer -- no network calls, no cost
ruff check .
```

## Status

Core scoring engine, CLI, deterministic and AI-narrated reports, Jira export, and a local web UI are all working end to end. A public live deploy is the remaining item on the roadmap. See [open issues](https://github.com/Barak-Nisim/risklens/issues).

## License

MIT
