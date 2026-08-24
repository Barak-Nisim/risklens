# Scoring Methodology

RiskLens scores security maturity on a 0-4 scale per question, then rolls that up into category, function, and overall scores. This document explains the math in plain terms. The full implementation is in `risklens/scoring.py` and is unit-tested in `tests/test_scoring.py`.

## The maturity scale

Every question is answered on the same 5-point scale:

| Score | Meaning |
|---|---|
| 0 | Not started: no defined practice |
| 1 | Ad hoc: practiced inconsistently, not documented |
| 2 | Defined: documented policy/process exists |
| 3 | Managed: consistently followed and measured |
| 4 | Optimized: continuously improved, integrated into operations |

An **unanswered question is scored 0**, not skipped. Silently excluding unanswered questions would let an organization improve its score just by leaving hard questions blank. Missing evidence of a control is itself the worst case, not a neutral one.

## Rolling scores up

Each question, category, and function has a `weight` reflecting its relative importance (defined in the framework YAML, e.g. `frameworks/nist_csf.yaml`). Scores roll up as a weighted average:

```
category_score = Σ(question_score × question_weight) / Σ(question_weight)
function_score = Σ(category_score × category_weight) / Σ(category_weight)
overall_score  = Σ(function_score × function_weight) / Σ(function_weight)
```

This is a plain weighted average at every level, with no hidden curve and no black-box model. A question with weight 1.3 (e.g. "Is MFA enforced?") pulls its category's score twice as hard as a question with weight 0.6.

## Maturity tiers

The overall score (0-4) maps to a named tier for readability:

| Score range | Tier |
|---|---|
| 0.0 – 0.8 | Initial |
| 0.8 – 1.6 | Developing |
| 1.6 – 2.4 | Defined |
| 2.4 – 3.2 | Managed |
| 3.2 – 4.0 | Optimized |

## Findings and prioritization

A question scoring below a configurable threshold (default: **2.0**) becomes a **finding**. Findings are ranked by:

```
priority = question_weight × (4 − question_score)
```

This rewards findings that are both high-weight (important) and low-scoring (immature). A weight-1.3 question scored 0 outranks a weight-0.6 question scored 1, because it represents a bigger, more important gap. This is deliberately simple and explainable rather than a machine-learned ranking: anyone reading a RiskLens report can recompute the priority order by hand from the numbers already on the page.

## What the AI layer does and doesn't do

The AI narrator (`ai/narrator.py`) receives the fully-computed `ScoreResult` as structured JSON (scores, tier, and ranked findings) and is explicitly instructed to narrate and prioritize that data for a leadership audience, not to recompute or second-guess it. If you disagree with a finding's priority, the fix is in the scoring math above, not in the AI layer.
