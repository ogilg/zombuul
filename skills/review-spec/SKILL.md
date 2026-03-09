---
name: zombuul:review-spec
description: >
  Review an experiment spec for completeness before launching a research loop.
  Argument $ARGUMENTS — path to the experiment spec.
user-invocable: true
---

Review this experiment spec for research-loop readiness: $ARGUMENTS

## What to do

Read the spec, `README.md`, and `CLAUDE.md`. Then launch **three parallel subagents** (Agent tool, subagent_type="general-purpose"). Each simulates a research agent with zero prior context — pass only the spec + README + CLAUDE.md contents, nothing else.

### Shared preamble (include in all three prompts)

```
You are reviewing an experiment spec that will be handed to an autonomous research agent running on a GPU pod. The agent has only the git repo and whatever data is synced to the pod. The spec is its sole guide.

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

### Agent 1: Code pointers & data requirements

Append to the shared preamble:

```
Review ONLY the following two aspects. Flag what's missing or unclear.

### 1. Code pointers

The spec must tell the agent which existing code to use for each pipeline step. Without this, agents reimplement things that already exist.

- Does each pipeline phase reference specific modules, functions, or entry points?
- Are there "do not reimplement" warnings for key infrastructure?
- If the spec says "use X", check whether the README/CLAUDE.md confirms X exists.

### 2. Data requirements

- Does the spec state which files are needed that aren't in the git repo (large data, model weights, etc.)?
- Or does it confirm that no extra data sync is needed?
- Are input file paths listed explicitly?

## Output

1. **Pass/fail** per item (one line each)
2. **Issues** — quote the problematic text and suggest a fix
3. **Suggested additions** — concrete text the user can paste into the spec
```

### Agent 2: Commit guidance & clarity

Append to the shared preamble:

```
Review ONLY the following two aspects. Flag what's missing or unclear.

### 1. Commit guidance

- If the experiment produces large artifacts that shouldn't be committed, is that noted?

### 2. Clarity for a context-free agent

Read the spec as if you know nothing beyond these three documents. Flag:

- Ambiguous references ("the existing pipeline", "the standard method") without specific pointers
- Missing parameter values (model name, layers, batch sizes, sample counts, coefficient ranges)
- Unclear success criteria — how does the agent know when it's done?
- Missing output paths — where do results, plots, and the report go?

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

1. **Pass/fail summary** — one line per checklist item (code pointers, data requirements, commit guidance, clarity)
2. **Code pointer verification** — which references exist, which don't
3. **Issues** — combined from agents 1 and 2, deduplicated
4. **Suggested additions** — combined from agents 1 and 2

Present to the user.
