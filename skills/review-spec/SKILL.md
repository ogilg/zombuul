---
name: zombuul:review-spec
description: >
  Review an experiment spec for completeness before running it.
  Argument $ARGUMENTS — path to the experiment spec.
user-invocable: true
---

Review this experiment spec for practical readiness: $ARGUMENTS

## What to do

Read the spec, `README.md`, and `CLAUDE.md`. Then launch **three parallel subagents** (Agent tool, subagent_type="general-purpose"). Each simulates reading the spec with zero prior context — pass only the spec + README + CLAUDE.md contents, nothing else.

### Shared preamble (include in all three prompts)

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
```

### Agent 1: Code & data validation

Append to the shared preamble:

```
Review ONLY the following two aspects. Flag what's missing or unclear.

### 1. Code reuse

This is the most important check. Without explicit code pointers, the executor will reimplement things that already exist — and get subtle details wrong.

- Does **every** pipeline step reference a specific module, function, or entry point? Vague references like "use the existing pipeline" or "the standard method" are not enough — the spec must name the exact module or function.
- Are there "do not reimplement" warnings for key infrastructure (extraction, probe training, steering, measurement, elicitation)?
- If the spec says "use X", check whether the README/CLAUDE.md confirms X exists.
- If a step could plausibly be done by existing code but the spec doesn't mention it, flag it — the executor will write new code instead of reusing what exists.

### 2. Data requirements

- Does the spec state which files are needed that aren't in the git repo (large data, model weights, etc.)?
- Or does it confirm that no extra data sync is needed?
- Are input file paths listed explicitly?

## Output

1. **Pass/fail** per item (one line each)
2. **Issues** — quote the problematic text and suggest a fix
3. **Suggested additions** — concrete text the user can paste into the spec
```

### Agent 2: Practical pitfalls

Append to the shared preamble:

```
Review ONLY the following aspects. Flag what's missing or unclear.

### 1. Missing parameter values

- Are all required parameters specified (model name, layers, batch sizes, sample counts, coefficient ranges)?
- Are there ambiguous references ("the existing pipeline", "the standard method") without specific pointers?

### 2. Formats and conventions

This is where experiments most often go wrong silently. Flag any of these that are unspecified:

- File formats for inputs/outputs (JSON structure, NPZ keys, CSV columns)
- Prompt templates and response parsing methods — if the spec doesn't say which to use, the executor will invent one
- Scoring conventions (what scale? higher = better? how are ties handled?)
- Config file structure (if the step is config-driven, does the spec show the config or point to an example?)
- Naming conventions for output files

### 3. GPU memory requirements

- Does the experiment involve model loading? If so, is VRAM likely sufficient for the described setup?
- Are there batch size / sequence length choices that might OOM?

### 4. Success criteria

- How do we know when the experiment is done?
- Are there clear metrics or thresholds?

### 5. Silent failure risks

- Steps that could fail silently (e.g., empty results, wrong tensor shapes, mismatched task IDs)
- Missing sanity checks

## Output

1. **Pass/fail** per item (one line each)
2. **Issues** — quote the problematic text and suggest a fix
3. **Suggested additions** — concrete text the user can paste into the spec
```

### Agent 3: Verify code pointers exist

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

## After all three agents return

Merge the results into a single review:

1. **Pass/fail summary** — one line per checklist item (code reuse, data requirements, parameters, formats/conventions, GPU memory, success criteria, silent failures)
2. **Code pointer verification** — which references exist, which don't
3. **Issues** — combined from agents 1 and 2, deduplicated
4. **Suggested additions** — combined from agents 1 and 2

Present to the user.
