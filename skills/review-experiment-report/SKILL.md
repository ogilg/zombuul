---
name: zombuul:review-experiment-report
description: >
  Review and rewrite a research report for clarity.
  Argument $ARGUMENTS — path to the report markdown file.
argument-hint: <report-path>
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

### 4. Framing and mental models

For every key result, ask: "Would someone who hasn't been staring at this experiment for hours understand what this means?" The concepts, conditions, and metrics the author invented during the experiment often make perfect sense to them but are opaque to readers.

- **Question every abstract label.** If a condition is called "condition A vs B", "orig vs swap", or "Direction 1 vs 2", ask: what do these actually mean in plain language? Replace with descriptive names that convey the mechanism being tested. The name should tell the reader *why* the conditions differ, not just *that* they differ.
- **Question the framing itself.** Is the author presenting results in the most intuitive frame? There's often a better way to slice the same data. A plot titled "metric X by variable Y" is almost always worse than a plot titled with the question being answered. Reframe around the question, not the variable.
- **Check that plot axes, legends, and titles are self-explanatory.** If you need to read 2 paragraphs of report text to understand what a plot shows, the plot has failed. Every axis label, legend entry, and title should make sense on its own. Legend entries like "Group A (x / y)" that overload two naming schemes are a red flag.
- **Check color consistency.** If conditions are color-coded in one plot, the same colors should mean the same things across all plots. New colors should not appear without explanation.

### 5. Diagrams for non-obvious setups

If the experiment involves a multi-step procedure, pipeline, or setup where multiple entities interact, check whether a **setup diagram** would help. The procedure may be obvious to the author but readers need to see the flow.

- If the report describes a non-standard experimental setup (not just "train model, evaluate"), a diagram is strongly recommended.
- The diagram should use concrete examples (specific values, not abstract placeholders) so the reader can trace through what happens step by step.
- If a diagram already exists, check that it covers all conditions mentioned in the report and uses consistent colors with the results plots.

### 6. Prefer plots over tables

Default to plots. Tables with more than ~4 rows of numeric results should be a plot instead. Use tables only when exact numbers matter more than patterns (e.g., final metrics, hyperparameter configs).

### 7. Plot consistency across reports

Check sibling/parent experiment directories for related reports. If found, read their plots and match the format: same chart type, axis ranges, color mapping, condition ordering, and legend style.

### 8. Missing context

If a number is presented without a comparison point (baseline, chance level, ceiling), add one. Isolated numbers are hard to interpret.

## Process

1. Read the spec, then the report.
2. Check for related reports in sibling or parent experiment directories. If found, read their plots to establish the visual style to match (criterion 7).
3. For each plot referenced in the report, read the image file and evaluate it against criteria 4-5 and 7 above. Plots are the most common source of confusion — axis labels, legends, and color choices that made sense during analysis often don't survive first contact with a reader.
4. Flag any tables that should be plots (criterion 6). When replacing a table with a plot, preserve all the data — the plot should convey strictly more than the table did.
5. Make a list of all issues found (grouped by criterion above).
6. Rewrite the report in place, fixing all text issues. Preserve all factual content — you're editing for clarity, not changing results.
7. For plots that need fixing (bad labels, inconsistent colors, missing context) or tables that should become plots, write and run a replacement plotting script. For missing diagrams (criterion 5), create them.
8. After rewriting, briefly summarize what you changed.
