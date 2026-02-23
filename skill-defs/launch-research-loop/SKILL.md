---
name: zombuul:launch-research-loop
description: >
  Run an autonomous research loop for a single experiment.
  Argument $ARGUMENTS — path to experiment spec.
user-invocable: true
---

Solve this research problem autonomously: $ARGUMENTS

## Slack

If `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` are set in the environment, you can communicate via Slack.

### Posting

Post to Slack at these moments:
- **Missing data** — if the spec references files that don't exist on this machine (activations, probe weights, etc.), post immediately listing what's missing and what steps are blocked. Then proceed with whatever steps you can.
- **Blocking issue** you cannot resolve after multiple attempts
- **Noteworthy result** — positive, negative, or null — that updates our understanding
- **Experiment complete** (one-line summary of outcome)
- **Asking for help** — if you're stuck and want human or supervisor input, describe what you need

Write a JSON file `/tmp/slack_msg.json` with your message, then post it. At the start of the experiment, pick a hex color for your icon and reuse it for every message — remote agents (on a GPU pod) pick from reds/pinks, local agents pick from blues/greens.

```json
{
  "channel": "<SLACK_CHANNEL_ID env var>",
  "text": "<your message>",
  "username": "agent-<experiment_name>",
  "icon_url": "https://dummyimage.com/48x48/<color>/<color>.png"
}
```

If you know your GPU type (e.g. from the pod), use `"username": "agent-<experiment_name> (<gpu_type>)"`.

Post with: `curl -s -X POST -H "Authorization: Bearer $SLACK_BOT_TOKEN" -H 'Content-type: application/json' -d @/tmp/slack_msg.json https://slack.com/api/chat.postMessage`

**Message formatting:** Use Slack markdown (`*bold*`, `>` quotes, `\n` newlines) to make messages scannable. Start with a bold headline that captures the gist (e.g. `*Experiment complete: exp3c*` or `*Stuck: OOM during extraction*`), then key details on separate lines. Use `>` block quotes for data/numbers. A reader glancing at the channel should get the point from the headline alone, and can read further for details. Do not post routine progress — only things worth interrupting someone for.

### Reading

Check Slack for responses by reading recent channel history:

```
curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" "https://slack.com/api/conversations.history?channel=$SLACK_CHANNEL_ID&limit=10"
```

Messages from other agents or the user will have a different `username` field than yours. Look for messages that are relevant to you — replies to your questions, new instructions, or help from a supervisor agent.

**When to check:** After posting a question or asking for help, check periodically (e.g. every few minutes while working on other things). Do not block and poll — continue your work and check back between steps. If you haven't posted anything that needs a response, don't check.

## Environment awareness

If `IS_SANDBOX=1` is set, you are running on a remote GPU pod. This means:
- **You are already on the GPU machine.** Do NOT create, launch, or SSH into other pods. Run experiments directly on this machine.
- **Data may be incomplete.** The pod was set up by cloning the git repo and optionally syncing some gitignored data. If the spec references data files that don't exist locally (activations, probe weights, embeddings, results JSONs), **post to Slack** listing the missing files and their expected paths. Do not try to work around missing data by provisioning infrastructure — just flag it and proceed with whatever steps you can do without it.

## Rules

- **Work autonomously.** Do not stop and wait for help. If you're stuck, post to Slack, then keep trying other approaches while you wait. Check back for responses between steps.
- **Do not game the spec.** Solve the problem in spirit, not just technically.
- **Do not give up easily.** If something fails, debug it, try a different approach, read more code, re-examine assumptions. Iterate aggressively.
- **Do not cut corners.** If the problem requires running experiments, run them. If it requires reading papers or code, read them.
- **Pay attention to the instructions.** They should define the research space. They should also provide fallback options and different things to try. Do not do something that the instructions tell you not to.
- **Think about controls.** For each key result, think about what controls or sanity checks would test the claim. Run them without being asked.
- **Report what you find, not what you hoped to find.** A null or negative result is just as informative as a positive one — often more so. Do not spin results, cherry-pick coefficients, or frame ambiguous evidence as support for the hypothesis. If the data doesn't show an effect, say so plainly.
- **Pilot before scaling.** When running experiments at scale, always run a small pilot first to validate the pipeline, check for obvious issues, and get rough effect sizes. Use pilot results to decide what to iterate on before committing to full runs.
- **Do not provision infrastructure.** Never create pods, VMs, or cloud resources. You run experiments on the machine you're on.
- **Results go in the experiment report only.** Do not write results anywhere else. The user will decide where to log them.

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
7. **Friction check**: Before finishing, reflect on whether anything went wrong or was harder than expected during this research loop (script failures, confusing spec instructions, missing files, API errors, tools that didn't work, etc.). If there was friction and `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` are set, post a short friction report to Slack for each issue:
   `curl -s -X POST -H "Authorization: Bearer $SLACK_BOT_TOKEN" -H 'Content-type: application/json' -d '{"channel": "'$SLACK_CHANNEL_ID'", "text": ":warning: *Friction report* (launch-research-loop)\n> <one-line summary>\n> *Severity*: minor/moderate/major\n> *Details*: <1-3 sentences>", "username": "friction-log", "icon_url": "https://dummyimage.com/48x48/ff6b6b/ff6b6b.png"}' https://slack.com/api/chat.postMessage`
   If nothing went wrong, skip this step.
