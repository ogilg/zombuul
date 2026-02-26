---
name: zombuul:review-experiment-report
description: >
  Review and rewrite a research report for clarity.
  Argument $ARGUMENTS — path to the report markdown file.
user-invocable: true
---

Review and rewrite this research report for clarity: $ARGUMENTS

You are reviewing a research report as a **naive reader** — someone who understands ML but has not seen the code, the running log, or any implementation details. Your only inputs are the report itself and the experiment spec.

## Setup

1. Read the experiment spec (the `*_spec.md` in the same directory as the report, or the parent experiment's spec if this is a follow-up).
2. Read the report.
3. Do NOT read any code, scripts, running logs, or other implementation files. The whole point is to evaluate the report as a standalone document.

## Review criteria

Flag and fix each of these:

### 1. Straight to the point

Lead every section with the main result. Cut filler. The report should be dominated by results (numbers, tables, plots), not interpretation. Where interpretation is needed, keep it to short inline remarks or a few bullets — not dedicated Discussion or Implications sections. If a section is mostly prose explaining what results mean, condense it.

- Bad: "We tried alpha values from 0.1 to 10000 using 5-fold CV. The best alpha was 2154. This gave R²=0.86."
- Good: "Ridge probes achieve R²=0.86 (best alpha=2154 via 5-fold CV)."
- Bad: A paragraph discussing what a technique does, why a gap is small, and what it implies.
- Good: "**Augmentation closes the train-test gap** (82% → 79%), suggesting no overfitting to source-specific artifacts."

### 2. Naming

Find clear, precise short names for metrics, conditions, groups, axes. A reader should understand what something refers to without looking anything up.

- Bad: `cv_r2_mean`, `demean_confounds`, "the adjusted score", "condition A vs B"
- Good: "cross-validated R²", "topic-demeaned Thurstonian scores", "held-one-out accuracy"

Model names, dataset names, and well-known methods (Ridge, Bradley-Terry, etc.) are fine as-is.

### 3. Examples give intuition

When introducing a concept, condition, or category, give a concrete example. Examples make abstract descriptions tangible and also disambiguate naming. Present examples in tables when showing multiple items.

- Bad: "We test 6 target categories with persona-style system prompts."
- Good:

  | Category | Example prompt |
  |----------|---------------|
  | math | "You find math tedious and draining" |
  | coding | "Writing code feels mechanical and unpleasant" |

### 4. Choosing the right presentation

Pick the best format: exact numbers → table; trends/comparisons → plot; one or two values → inline. When referencing a plot, describe the pattern. Table column names should be understandable without context. Define non-standard metrics on first use.

### 5. Missing context

If a number is presented without a comparison point (baseline, chance level, ceiling), add one. Isolated numbers are hard to interpret.

## Process

1. Read the spec, then the report.
2. Make a list of all issues found (grouped by criterion above).
3. Rewrite the report in place, fixing all issues. Preserve all factual content — you're editing for clarity, not changing results.
4. After rewriting, briefly summarize what you changed.
