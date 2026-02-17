Solve this research problem autonomously: $ARGUMENTS

## Slack

If `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` are set in the environment, you can communicate via Slack.

### Posting

Post to Slack at these moments:
- **Blocking issue** you cannot resolve after multiple attempts
- **Strong or surprising result** (e.g. significant accuracy jump, unexpected pattern)
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

Keep messages short and human-readable. Do not post routine progress — only things worth interrupting someone for.

### Reading

Check Slack for responses by reading recent channel history:

```
curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" "https://slack.com/api/conversations.history?channel=$SLACK_CHANNEL_ID&limit=10"
```

Messages from other agents or the user will have a different `username` field than yours. Look for messages that are relevant to you — replies to your questions, new instructions, or help from a supervisor agent.

**When to check:** After posting a question or asking for help, check periodically (e.g. every few minutes while working on other things). Do not block and poll — continue your work and check back between steps. If you haven't posted anything that needs a response, don't check.

## Rules

- **Work autonomously.** Do not stop and wait for help. If you're stuck, post to Slack, then keep trying other approaches while you wait. Check back for responses between steps.
- **Do not game the spec.** Solve the problem in spirit, not just technically.
- **Do not give up easily.** If something fails, debug it, try a different approach, read more code, re-examine assumptions. Iterate aggressively.
- **Do not cut corners.** If the problem requires running experiments, run them. If it requires reading papers or code, read them.
- **Pay attention to the instructions.** They should define the research space. They should also provide fallback options and different things to try. Do not do something that the instructions tell you not to.
- **Think about controls.** For each key result, think about what controls or sanity checks would strengthen the claim. Run them without being asked.
- **Pilot before scaling.** When running experiments at scale, always run a small pilot first to validate the pipeline, check for obvious issues, and get rough effect sizes. Use pilot results to decide what to iterate on before committing to full runs.
- **Results go in the experiment report only.** Do not write results anywhere else. The user will decide where to log them.

## Directory structure

The argument $ARGUMENTS points to an experiment spec at `experiments/{name}/spec.md`. All outputs for this experiment go inside `experiments/{name}/`:

```
experiments/{name}/
├── spec.md          # the experiment spec (input — already exists)
├── report.md        # your results report (output — you create this)
├── running_log.md   # detailed append-only working log (output — you create this)
└── assets/          # plots referenced from report.md
    └── plot_{mmddYY}_description.png
```

If this is a **follow-up** to an existing experiment (i.e. the spec lives in a subdirectory like `experiments/{name}/{follow_up}/spec.md`), write your report and assets inside that subdirectory. **Read the parent experiment's report.md first** — it contains context, baselines, and lessons learned that you should build on.

Image references in report.md use relative paths: `![description](assets/plot_foo.png)`.

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
