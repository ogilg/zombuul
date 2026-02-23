---
name: zombuul:launch-research-ralph
description: >
  Run a multi-experiment research program that iterates until the research goal is met.
  Argument $ARGUMENTS — path to top-level experiment directory.
user-invocable: true
---

You are running a research program — a sequence of experiments that build on each other. This prompt will be re-invoked after each experiment completes.

The argument $ARGUMENTS points to a top-level experiment directory: `experiments/{name}/`.

## Every iteration

1. **Read the research goal.** Read `experiments/{name}/{name}_spec.md`.
2. **Find all completed experiments.** List all `*_report.md` files in `experiments/{name}/` and its subdirectories. Order them chronologically (by file modification time or by the sequence implied by parent→child relationships).
3. **Synthesize older reports.** If there are 2+ reports, launch a subagent (Task tool, subagent_type="general-purpose"): "Read these reports in order: {list all but the latest}. Write a synthesis to `experiments/{name}/synthesis.md` with: (a) what's been established, (b) what failed and why, (c) open questions. Be concise — this is background context, not the focus." Then read `synthesis.md`.
4. **Read the latest report in full.** This is the most important input — read it directly, not via summary.
5. **Check if done.** If the overall goal is convincingly addressed — whether by positive results, null results, or negative evidence that closes the question — output <promise>RESEARCH_COMPLETE</promise> and stop.
6. **Design the next experiment.** Write a focused spec at `experiments/{name}/{follow_up_name}/{follow_up_name}_spec.md`.
7. **Run the experiment.** Invoke `/zombuul:launch-research-loop experiments/{name}/{follow_up_name}/{follow_up_name}_spec.md`.
8. **Push synthesis.** If you wrote or updated `synthesis.md`, commit and push it.
9. **Stop.** You will be re-invoked automatically.

## Designing follow-up experiments

Think critically about what to do next:

- **Positive result?** What confounders could explain it? Is the baseline strong enough? Does it replicate?
- **Negative result?** Was the hypothesis wrong, or was the approach flawed? What else could we try?
- **Ambiguous result?** What would disambiguate it?
- **Always ask:** What's the most informative experiment — the one that updates our beliefs the most, regardless of outcome?

Keep specs focused. One clear question per experiment. Reference the parent report's findings briefly in the spec.

## Rules

- **Do not repeat a failed experiment** unless you have a specific reason to believe the outcome will differ.
- **Keep the experiment tree manageable.** Prefer breadth (sibling experiments) over depth when questions are independent.
