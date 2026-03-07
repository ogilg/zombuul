---
name: zombuul:review-spec
description: >
  Review an experiment spec for completeness before launching a research loop.
  Argument $ARGUMENTS — path to the experiment spec.
user-invocable: true
---

Review this experiment spec for research-loop readiness: $ARGUMENTS

## What to do

Launch a **subagent** (Task tool, subagent_type="general-purpose") with the prompt below. The subagent simulates a research agent with zero prior context — it only reads what you give it.

Pass the subagent:
1. The contents of the experiment spec
2. The project's `README.md` and `CLAUDE.md`

Do NOT pass any other context. The point is to test whether the spec stands on its own.

### Subagent prompt

```
You are reviewing an experiment spec that will be handed to an autonomous research agent running on a GPU pod. The agent has only the git repo and whatever data is synced to the pod. The spec is its sole guide.

## Inputs

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

## Review checklist

For each item, flag what's missing or unclear.

### 1. Code pointers

The spec must tell the agent which existing code to use for each pipeline step. Without this, agents reimplement things that already exist.

- Does each pipeline phase reference specific modules, functions, or entry points?
- Are there "do not reimplement" warnings for key infrastructure?
- If the spec says "use X", check whether the README/CLAUDE.md confirms X exists.

### 2. Data requirements

- Does the spec state which files are needed that aren't in the git repo (large data, model weights, etc.)?
- Or does it confirm that no extra data sync is needed?
- Are input file paths listed explicitly?

### 3. Commit guidance

- If the experiment produces large artifacts that shouldn't be committed, is that noted?

### 4. Clarity for a context-free agent

Read the spec as if you know nothing beyond these three documents. Flag:

- Ambiguous references ("the existing pipeline", "the standard method") without specific pointers
- Missing parameter values (model name, layers, batch sizes, sample counts, coefficient ranges)
- Unclear success criteria — how does the agent know when it's done?
- Missing output paths — where do results, plots, and the report go?

## Output

1. **Pass/fail** per checklist item (one line each)
2. **Issues** — quote the problematic text and suggest a fix
3. **Suggested additions** — concrete text the user can paste into the spec
```

## After the subagent returns

Present its review to the user. If the subagent flagged code pointers to modules it couldn't verify (since it only had README/CLAUDE.md), do a quick check yourself — confirm the referenced modules actually exist in the repo and note any that don't.
