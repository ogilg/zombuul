Review and rewrite this research report for clarity: $ARGUMENTS

You are reviewing a research report as a **naive reader** — someone who understands ML but has not seen the code, the running log, or any implementation details. Your only inputs are the report itself and the experiment spec.

## Setup

1. Read the experiment spec (the `spec.md` in the same directory as the report, or the parent experiment's spec if this is a follow-up).
2. Read the report.
3. Do NOT read any code, scripts, running logs, or other implementation files. The whole point is to evaluate the report as a standalone document.

## Review criteria

Flag and fix each of these:

### 1. Straight to the point

Short sentences. No filler. Lead every section with the main result, then give supporting detail. If a reader has to wade through methodology to find out what happened, restructure. Cut any sentence that doesn't add information.

Interpretation/discussion sections should be a bulleted list of one-liners, not paragraphs. Each bullet is one claim with its key supporting number. If it takes more than two sentences, it's too long.

- Bad: "We tried alpha values from 0.1 to 10000 using 5-fold CV. The best alpha was 2154. This gave R²=0.86."
- Good: "Ridge probes achieve R²=0.86 (best alpha=2154 via 5-fold CV)."
- Bad interpretation: A paragraph discussing what a technique does, why a gap is small, and what it implies.
- Good interpretation: "**Augmentation closes the train-test gap** (82% → 79%), confirming the model isn't overfitting to source-specific artifacts."

### 2. Naming

Find good names for everything — metrics, conditions, groups, axes. A reader should immediately understand what something refers to without needing to look anything up. This goes beyond just avoiding code-internal names: even "plain English" names can be bad if they're vague or ambiguous. Spend time finding the clearest, most precise short name for each concept.

- Bad: `cv_r2_mean`, `demean_confounds`, `hoo_acc`
- Also bad: "the adjusted score", "condition A vs B", "the main metric"
- Good: "cross-validated R²", "topic-demeaned Thurstonian scores", "held-one-out accuracy"

Exception: model names, dataset names, and well-known method names (Ridge, Bradley-Terry, etc.) are fine as-is.

### 3. Examples give intuition

When introducing a concept, condition, or category, give a concrete example. Examples make abstract descriptions tangible and also disambiguate naming. Present examples in tables when showing multiple items.

- Bad: "We test 6 target categories with persona-style system prompts."
- Good:

  | Category | Example prompt |
  |----------|---------------|
  | math | "You find math tedious and draining" |
  | coding | "Writing code feels mechanical and unpleasant" |

### 4. Choosing the right presentation

Think about whether each piece of information is best shown as a table, a plot, or inline text. Don't default to tables — sometimes a bar chart or scatter plot communicates the pattern faster. Consider what the reader needs to see: exact numbers → table; trends or comparisons → plot; one or two values → inline. When referencing a plot, say what the reader should see in it — describe the pattern, don't just point to it.

Every table column name should be understandable without context. If abbreviations are necessary, add a note below. If a metric is non-standard, define it on first use.

### 5. Missing context

If a number is presented without a comparison point (baseline, chance level, ceiling), add one. Isolated numbers are hard to interpret.

## Process

1. Read the spec, then the report.
2. Make a list of all issues found (grouped by criterion above).
3. Rewrite the report in place, fixing all issues. Preserve all factual content — you're editing for clarity, not changing results.
4. After rewriting, briefly summarize what you changed.
