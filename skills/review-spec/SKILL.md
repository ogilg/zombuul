---
name: zombuul:review-spec
description: >
  Review an experiment spec for completeness before running it.
  Argument $ARGUMENTS — path to the experiment spec.
argument-hint: <spec-path>
user-invocable: true
---

Review this experiment spec for practical readiness: $ARGUMENTS

> Adapt these checks to your domain. Not every item applies to every spec — skip items that don't match the spec's methodology (e.g., the train/eval/test integrity check is irrelevant for a single-pass analysis).

## Proportionality

**Scale review depth to spec complexity.** A 25-line single-step spec does not need the same scrutiny as a 100-line multi-phase experiment. Before launching agents, read the spec and estimate complexity:

- **Simple** (~25–40 lines, single step, local execution, existing modules): run only Agent 2 (code pointer verification). Skip Agent 1 — its checklist adds noise for straightforward specs. Return a brief pass/fail on whether the referenced code exists and the parameters are specified.
- **Medium** (40–80 lines, 2–3 steps, may need GPU): run both agents but tell Agent 1 to keep output to pass/fail items only — no "suggested additions" unless something is actually missing.
- **Complex** (80+ lines, multi-phase, novel methodology): full review as described below.

## What to do

Read the spec, `README.md`, and `CLAUDE.md`. Then launch subagents as appropriate for the complexity level above. For medium and complex specs, launch **two parallel subagents** (Agent tool, subagent_type="general-purpose"). Agent 1 simulates reading the spec with zero prior context — pass only the spec + README + CLAUDE.md contents, nothing else. Agent 2 has access to the repo to verify code pointers.

### Agent 1: Spec quality (zero-context reviewer)

Append to the shared preamble:

```
You are reviewing an experiment spec that will be executed by local Claude Code, with optional GPU pod access for compute-heavy steps. The spec is the sole guide for the experiment.

Here is the spec:
<spec>
{spec contents}
</spec>

Here is the project README:
<readme>
{README.md contents}
</readme>

Here is the project CLAUDE.md:
<claude_md>
{CLAUDE.md contents}
</claude_md>

Review the spec across the sections below. Flag what's missing or unclear. Adapt items to the spec's domain — not every check applies to every spec.

### 1. Code reuse

This is the most important check. Without explicit code pointers, the executor will reimplement things that already exist — and get subtle details wrong.

- Does **every** pipeline step reference a specific module, function, or entry point? Vague references like "use the existing pipeline" or "the standard method" are not enough — the spec must name the exact module or function.
- Are there "do not reimplement" warnings for key pipeline infrastructure (e.g., data preprocessing, training, evaluation, analysis)?
- If the spec says "use X", check whether the README/CLAUDE.md confirms X exists.
- If a step could plausibly be done by existing code but the spec doesn't mention it, flag it — the executor will write new code instead of reusing what exists.

### 2. Data requirements

- Does the spec state which files are needed that aren't in the git repo (large data, model weights, etc.)?
- Or does it confirm that no extra data sync is needed?
- Are input file paths listed explicitly?

### 3. Parameter values

- Are all required parameters specified (model name, layers, batch sizes, sample counts, coefficient ranges, hyperparameters)?
- Are there ambiguous references ("the existing pipeline", "the standard method") without specific pointers?

### 4. Formats and conventions

This is where experiments most often go wrong silently. Flag any of these that are unspecified:

- File formats for inputs/outputs (JSON structure, NPZ keys, CSV columns)
- Prompt templates and response parsing methods — if the spec doesn't say which to use, the executor will invent one
- Scoring conventions (what scale? higher = better? how are ties handled?)
- Config file structure (if the step is config-driven, does the spec show the config or point to an example?)
- Naming conventions for output files

### 5. Compute / memory requirements

- Does the experiment involve model loading? If so, is VRAM likely sufficient for the described setup?
- Are there batch size / sequence length choices that might OOM?
- For non-GPU work: are wall-clock and memory expectations realistic?

### 6. Success criteria

- How do we know when the experiment is done?
- Are there clear metrics or thresholds?

### 7. Data integrity

- Are training, validation, and test sets explicitly defined as disjoint (if applicable)? If splits are mentioned, is the separation enforced at the right level (e.g., by group, not by individual observation)?
- If results from one stage feed into another (e.g., stage A → stage B), is the methodology (prompts, parameters, parsing, scoring) consistent across stages — or is the deviation documented?

### 8. Silent failure risks

- Steps that could fail silently (e.g., empty results, wrong tensor shapes, mismatched task IDs, mis-parsed responses)
- Missing sanity checks

### 9. Pre-mortem: what could go wrong?

Assume the experiment runs to completion but produces a useless or misleading result. Think adversarially:

- **Confounds**: Could the result be explained by something other than the intended variable? (e.g., topic/length/format artifacts, shared content between conditions)
- **Ceiling/floor effects**: Could the metric saturate before the manipulation has a chance to show an effect?
- **Wrong abstraction level**: Is the spec measuring the right thing? (e.g., measuring accuracy when the question is about calibration, or measuring average when the distribution is bimodal)
- **Null result ambiguity**: If the experiment finds no effect, can we distinguish "no effect exists" from "method wasn't sensitive enough"? Are there positive controls?

For each risk, suggest a concrete mitigation.

## Output

1. **Pass/fail** per section (one line each)
2. **Issues** — quote the problematic text and suggest a fix
3. **Suggested additions** — concrete text the user can paste into the spec
```

### Agent 2: Verify code pointers exist

This agent searches the actual repo — it does NOT get the zero-context constraint.

```
The following experiment spec references code modules and entry points. Your job is to verify that every referenced module, function, class, and entry point actually exists in the repo. Search the codebase for each one.

Here is the spec:
<spec>
{spec contents}
</spec>

For each code reference in the spec, report:
- **Found** — the module/function exists (give the file path)
- **Not found** — it doesn't exist, or the name is wrong (suggest the closest match if any)

Only report code references. Do not review anything else.
```

## After both agents return

Merge the results into a single review:

1. **Pass/fail summary** — one line per checklist item (code reuse, data requirements, parameters, formats/conventions, compute/memory, success criteria, data integrity, silent failures, pre-mortem risks)
2. **Code pointer verification** — which references exist, which don't
3. **Issues** — from Agent 1
4. **Suggested additions** — from Agent 1

Present to the user.
