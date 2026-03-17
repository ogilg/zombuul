---
name: zombuul:run-experiment
description: >
  Run an experiment from a spec. Handles pod creation, data sync, execution, and reporting.
  Argument $ARGUMENTS — path to experiment spec.
user-invocable: true
---

Run this experiment: $ARGUMENTS

## Infrastructure setup

1. Read the spec. Determine if GPU is needed (look for references to GPU, CUDA, model loading, extraction, training on large models, steering).
2. If GPU needed:
   - Check for running pods: `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py list`
   - If a suitable pod is already running (and spec/context suggests using it), use it.
   - Otherwise: invoke `/zombuul:launch-runpod` to create and provision a pod. The launch-runpod skill handles GPU selection, pod creation, and provisioning. After it completes, sync experiment data via `/zombuul:provision-pod`, passing `data_dirs` explicitly (inferred from the spec) to skip interactive recon.
   - Do NOT ask the user for GPU choice, data dirs, etc. Make reasonable choices. Only ask if truly blocked (e.g., no GPUs available).
3. If no GPU needed: run everything locally.

## Execution model

**Remote vs local execution awareness:**
- GPU-bound commands (model loading, extraction, training, steering) → SSH to pod: `ssh runpod-<name> 'cd /workspace/repo && python -m ...'`
- CPU-bound commands (analysis, plotting, fitting) → run locally
- Results from pod need to be synced back: `rsync -az runpod-<name>:/workspace/repo/<results_path> <local_path>`

**Non-blocking execution:**
- Long-running scripts (training, extraction, generation) should use `run_in_background` on the Bash tool
- Remote execution via SSH also uses `run_in_background`
- While waiting: prepare next steps, write analysis code, set up plotting scripts
- You get notified when background tasks complete — process results then

## Rules

- **Work autonomously.** Do not ask the user for anything unless completely blocked. Make reasonable assumptions and note them in the running log.
- **Reuse existing code.** Before writing anything, check the README and CLAUDE.md for existing modules, entry points, and utilities. The spec should reference them — use what it points to. Do NOT reimplement extraction, probe training, steering, measurement, or any other pipeline step that already exists. If the spec is vague about which code to use, search the repo before writing new code.
- **Follow the spec exactly.** The spec defines formats, parameters, methods, and conventions. Pay close attention to subtle details — specific file formats, prompt templates, response parsing methods, scoring conventions, config structures. Getting these wrong silently produces garbage results. If the spec says "use X format" or "use X method", do exactly that.
- **Do not game the spec.** Solve the problem in spirit, not just technically.
- **Iterate aggressively.** If something fails, debug it, try a different approach, re-examine assumptions.
- **Think about controls.** Run sanity checks for key results without being asked.
- **Report honestly.** Null/negative results are informative. Do not spin or cherry-pick.
- **Pilot before scaling.** Validate the pipeline on a small run before committing to full runs.
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

Create a dedicated folder for this experiment's scripts:

```
scripts/{experiment_name}/
```

All scripts you write during this experiment go here — experiment runners, analysis, plotting, etc.

**Plotting**: Delegate plot creation to subagents (Agent tool, subagent_type="general-purpose"). Describe what to plot and where to save it — the subagent writes the script and runs it. This keeps plotting code out of your context.

## Report style guide

Scannable — someone should grasp the full arc in 30 seconds. Headlines over prose, tables over text, dead ends in one line each. Include plots at key checkpoints (save to `assets/`). Include enough detail to reproduce (parameters, prompts, configs) but stay concise. Favor results (numbers, tables, plots) over interpretive prose — keep interpretation to short inline remarks or a few bullets, not dedicated sections. The `/zombuul:review-experiment-report` subagent will catch clarity issues — focus on content first.

## Workflow

1. **Read the spec.** Set up infrastructure (see above).
2. **Branch once.** If you're already on a `research-loop/` branch, stay on it. Otherwise, create one: `git checkout -b research-loop/{experiment_name}`.
3. Create scripts workspace, report skeleton, and running log.
4. Run baseline, then iterate. Log each step to the running log. Update the report at major milestones with plots. If an approach fails, log it and pivot.
5. **Review the report.** Launch a subagent (Agent tool, subagent_type="general-purpose") with `/zombuul:review-experiment-report`, passing the path to `report.md`. Do not skip this step.
6. **Sync results.** If a pod was used: sync all results back locally. Pause the pod via `/zombuul:pause-runpod`.
7. **Push results.** Commit all outputs — reports, plots, scripts, data files (scores, configs, JSON results) — and push: `git push -u origin research-loop/{experiment_name}`. Check `.gitignore` before committing large files. If you generate data files that exceed ~50MB and aren't already gitignored, add them to `.gitignore` rather than committing.
