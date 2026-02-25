---
name: zombuul:launch-research-loop
description: >
  Run an autonomous research loop for a single experiment.
  Argument $ARGUMENTS — path to experiment spec.
user-invocable: true
---

Solve this research problem autonomously: $ARGUMENTS

## Slack

If `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` are set, you can communicate via Slack.

### Posting

Post when: missing data (list what's missing, proceed with what you can), blocking issues after multiple attempts, noteworthy results, experiment complete, or asking for help. Do not post routine progress.

Write `/tmp/slack_msg.json` then post with `curl -s -X POST -H "Authorization: Bearer $SLACK_BOT_TOKEN" -H 'Content-type: application/json' -d @/tmp/slack_msg.json https://slack.com/api/chat.postMessage`.

```json
{
  "channel": "<SLACK_CHANNEL_ID env var>",
  "text": "<your message>",
  "username": "agent-<experiment_name>",
  "icon_url": "https://dummyimage.com/48x48/<color>/<color>.png"
}
```

Pick a hex color at the start and reuse it (remote agents: reds/pinks, local: blues/greens). If you know your GPU type, append it to the username.

**Formatting:** Slack markdown (`*bold*`, `>` quotes, `\n` newlines). Lead with a bold headline that captures the gist. Use `>` for data/numbers.

### Reading

`curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" "https://slack.com/api/conversations.history?channel=$SLACK_CHANNEL_ID&limit=10"`

Check periodically after posting questions — don't block and poll. Continue work and check between steps.

## Environment awareness

If `IS_SANDBOX=1` is set, you are running on a remote GPU pod. This means:
- **You are already on the GPU machine.** Do NOT create, launch, or SSH into other pods. Run experiments directly on this machine.
- **Data may be incomplete.** The pod was set up by cloning the git repo and optionally syncing some gitignored data. If the spec references data files that don't exist locally (activations, probe weights, embeddings, results JSONs), **post to Slack** listing the missing files and their expected paths. Do not try to work around missing data by provisioning infrastructure — just flag it and proceed with whatever steps you can do without it.

## Rules

- **Work autonomously.** If stuck, post to Slack and keep trying other approaches. Check back between steps.
- **Do not game the spec.** Solve the problem in spirit, not just technically.
- **Iterate aggressively.** If something fails, debug it, try a different approach, re-examine assumptions.
- **Follow the spec.** It defines the research space and fallback options. Do not deviate from it.
- **Think about controls.** Run sanity checks for key results without being asked.
- **Report honestly.** Null/negative results are informative. Do not spin or cherry-pick.
- **Pilot before scaling.** Validate the pipeline on a small run before committing to full runs.
- **Do not provision infrastructure.** Run experiments on the machine you're on.
- **Results go in the experiment report only.**

## Directory structure

The argument $ARGUMENTS points to an experiment spec at `experiments/{name}/{name}_spec.md`. All outputs for this experiment go inside `experiments/{name}/`:

```
experiments/{name}/
├── {name}_spec.md          # the experiment spec (input — already exists)
├── {name}_report.md        # your results report (output — you create this)
├── running_log.md          # detailed append-only working log (output — you create this)
└── assets/                 # plots referenced from {name}_report.md
    └── plot_{mmddYY}_description.png
```

If this is a **follow-up** to an existing experiment (i.e. the spec lives in a subdirectory like `experiments/{name}/{follow_up}/{follow_up}_spec.md`), write your report and assets inside that subdirectory. **Read the parent experiment's `{name}_report.md` first** — it contains context, baselines, and lessons learned that you should build on.

Image references in the report use relative paths: `![description](assets/plot_foo.png)`.

### Running log

Create `running_log.md` in the experiment directory. Append to this after every completed step — script outputs, intermediate numbers, observations, errors. This is for recovery if the session dies — do not re-read it during the session. Use your in-context memory for what you've done so far.

## Scripts workspace

Create a dedicated folder for this research loop's scripts:

```
scripts/{experiment_name}/
```

All scripts you write during this loop go here — experiment runners, analysis, plotting, etc.

**Plotting**: Delegate plot creation to subagents (Task tool, subagent_type="general-purpose"). Describe what to plot and where to save it — the subagent writes the script and runs it. This keeps plotting code out of your context.

## Report style guide

Scannable — someone should grasp the full arc in 30 seconds. Headlines over prose, tables over text, dead ends in one line each. Include plots at key checkpoints (save to `assets/`). Include enough detail to reproduce (parameters, prompts, configs) but stay concise. The `/review-experiment-report` subagent will catch clarity issues — focus on content first.

## Workflow

1. **Do not ask clarification questions.** Make reasonable assumptions and note them.
2. **Branch once.** If you're already on a `research-loop/` branch, stay on it. Otherwise, create one: `git checkout -b research-loop/{experiment_name}`.
3. Read prior work (parent experiment's `report.md` if this is a follow-up). Create scripts workspace, report, and running log.
4. Run baseline, then iterate. Log each step to the running log. Update the report at major milestones with plots. If an approach fails, log it and pivot.
5. **Review the report.** Launch a subagent (Task tool, subagent_type="general-purpose") with `/review-experiment-report`, passing the path to `report.md`. Do not skip this step.
6. **Push results.** Commit all outputs — reports, plots, scripts, data files (scores, configs, JSON results) — and push: `git push -u origin research-loop/{experiment_name}`. Check `.gitignore` before committing large files. If you generate data files that exceed ~50MB and aren't already gitignored, add them to `.gitignore` rather than committing.
7. **Friction check**: If anything went wrong or was harder than expected (script failures, confusing instructions, missing files, etc.) and Slack is configured, post a friction report using the Slack posting pattern above with `"username": "friction-log"` and format: `:warning: *Friction report* (launch-research-loop)\n> <summary>\n> *Severity*: minor/moderate/major\n> *Details*: <1-3 sentences>`. Skip if nothing went wrong.
