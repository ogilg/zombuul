Solve this research problem autonomously: $ARGUMENTS

## Rules

- **Do not ask the user for help.** Work continuously until you solve it or exhaust all reasonable approaches.
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
6. **Push results.** Commit all outputs and push: `git push -u origin research-loop/{experiment_name}`.
