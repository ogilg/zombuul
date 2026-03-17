---
name: zombuul:run-experiment
description: >
  Run an experiment from a spec. Handles pod creation, data sync, execution, and reporting.
  Argument $ARGUMENTS — path to experiment spec.
user-invocable: true
---

Run this experiment: $ARGUMENTS

## Phase 1: Read spec and launch setup agents

1. **Read the spec** at `$ARGUMENTS`. Determine whether GPU is needed (references to GPU, CUDA, model loading, extraction, training on large models, steering).
2. **Save the main repo root**: `MAIN_REPO=$(pwd)`.
3. **Launch two background subagents in parallel** (both with `model: "opus"`, `run_in_background: true`):

   **a) Symlink discovery agent** — reads the spec, scans all data paths it references, cross-checks against `.gitignore`, and returns the exact shell commands to create symlinks. The agent should:
   - Find every path the spec references (activations dirs, results dirs, probe_data, concept_vectors, config files, score files, etc.)
   - For each path, check whether it exists in the main repo and whether it's gitignored
   - Produce a list of symlink commands following these rules:
     - `activations/`, `probe_data/`, `concept_vectors/` have no tracked files — symlink the entire directory: `rm -rf <dir> && ln -s $MAIN_REPO/<dir> <dir>`
     - `results/` has tracked files — symlink only specific gitignored files (completions.json, measurements.yaml, steering_results.json) within the subdirectories the spec needs
     - Only symlink things the experiment READs. Directories it WRITEs to should remain in the worktree.
   - Return the commands as a newline-separated list, nothing else.

   **b) Infrastructure agent** (only if GPU needed) — checks for running pods and determines what infrastructure is available. The agent should:
   - Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py list`
   - If a suitable pod is already running, return its name and connection details
   - If no suitable pod exists, return that a new pod is needed (do NOT launch one yet — the main agent will invoke `/zombuul:launch-runpod` after entering the worktree)

4. **Wait for both agents to complete** before proceeding.

## Phase 2: Enter worktree and set up

1. **Enter a worktree**: use the `EnterWorktree` tool with name `{experiment_name}` (derived from the spec path, e.g., `experiments/foo/foo_spec.md` → name `foo`).
2. **Run the symlink commands** returned by the symlink discovery agent. Verify the experiment's input files are accessible.
3. **Set up infrastructure** if GPU needed:
   - If the infrastructure agent found a running pod, use it.
   - Otherwise: invoke `/zombuul:launch-runpod` to create and provision a pod. After it completes, sync experiment data via `/zombuul:provision-pod`, passing `data_dirs` explicitly (inferred from the spec) to skip interactive recon.
   - Do NOT ask the user for GPU choice, data dirs, etc. Make reasonable choices. Only ask if truly blocked.

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

**Audit on launch:**
When you launch a long-running job (extraction, training, generation, steering), immediately spawn an audit subagent (Agent tool, subagent_type="general-purpose", model="opus") in the background. The subagent checks the setup independently — it should not trust your assumptions. Pass it the spec and the paths to all data/config files being used. The subagent should:

1. **Data separation.** There should never be any overlap between train, eval, and test data. Load the actual files, extract IDs, and verify.
2. **Spec compliance.** For each parameter the spec prescribes, find the corresponding value in the config file or script and confirm it matches exactly. List each parameter, the spec value, and the actual value side by side.
3. **Input sanity.** For each input file the pipeline reads: confirm it exists, is non-empty, and has the expected format (parses correctly, has the expected keys/columns, sample counts match what the spec says). If the spec says "N samples", count them.
4. **Cross-stage consistency.** If the experiment has multiple stages that should use the same methodology, compare the actual parameters used in each stage (prompts, temperatures, response formats, parsing logic, scoring conventions). Flag any difference — even if it looks intentional, the spec should document it.

If the audit finds problems, kill the running job, fix the issue, and restart. Do not wait for a failed run to complete.

**Data validation between pipeline steps:**
After each pipeline step completes (extraction, training, evaluation, etc.), spawn a background validation subagent (Agent tool, subagent_type="general-purpose", model="opus") to verify the outputs while you prepare the next step. The subagent should:

1. **File presence.** All expected output files exist and are non-empty.
2. **Counts.** Sample/row/entry counts match what is expected (from spec or from the input that produced them).
3. **Format.** Files parse correctly (JSON loads, NPZ loads, YAML loads). Spot-check a few entries for expected structure.
4. **Magnitude.** Numeric outputs are in reasonable ranges (no NaNs, no wildly out-of-range values). For probe R² values, loss curves, steering coefficients — flag anything suspicious.
5. **Consistency.** If this step's output feeds the next step, confirm the IDs/keys/shapes are compatible.

Report back a pass/fail summary. If anything fails, flag it immediately — do not let the main agent build on bad outputs.

## Rules

- **Work autonomously.** Do not ask the user for anything unless completely blocked. Make reasonable assumptions and note them in the running log.
- **Reuse existing code.** Before writing anything, check the README and CLAUDE.md for existing modules, entry points, and utilities. The spec should reference them — use what it points to. Do NOT reimplement extraction, probe training, steering, measurement, or any other pipeline step that already exists. If the spec is vague about which code to use, search the repo before writing new code.
- **Follow the spec exactly.** The spec defines formats, parameters, methods, and conventions. Pay close attention to subtle details — specific file formats, prompt templates, response parsing methods, scoring conventions, config structures. Getting these wrong silently produces garbage results. If the spec says "use X format" or "use X method", do exactly that.
- **Do not game the spec.** Solve the problem in spirit, not just technically.
- **Iterate aggressively.** If something fails, debug it, try a different approach, re-examine assumptions.
- **Verify data separation.** Before training or evaluating, confirm no sample appears in both the training and evaluation sets. Check at the level that matters — if samples are grouped, split by group, not by individual observation.
- **Check consistency across stages.** If comparing or combining results from different pipeline stages, verify the methodology (prompts, parameters, parsing, scoring) is identical — or document the deviation and justify it.
- **Sanity-check before building on results.** After each step, verify the output makes sense (expected counts, reasonable magnitudes, non-empty files) before using it as input to the next step.
- **Compute, don't transcribe.** Never hand-write numbers in reports. Generate all figures, tables, and examples programmatically from the data.
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

**Plotting**: Delegate plot creation to subagents (Agent tool, subagent_type="general-purpose", model="opus"). Describe what to plot and where to save it — the subagent writes the script and runs it. This keeps plotting code out of your context.

## Report style guide

Scannable — someone should grasp the full arc in 30 seconds. Headlines over prose, tables over text, dead ends in one line each. Include plots at key checkpoints (save to `assets/`). Include enough detail to reproduce (parameters, prompts, configs) but stay concise. Favor results (numbers, tables, plots) over interpretive prose — keep interpretation to short inline remarks or a few bullets, not dedicated sections. The `/zombuul:review-experiment-report` subagent will catch clarity issues — focus on content first.

## Workflow

1. **Setup** (Phase 1 + Phase 2 above).
2. **Read the spec.** Set up infrastructure.
3. Create scripts workspace, report skeleton, and running log.
4. Run baseline, then iterate. Log each step to the running log. Update the report at major milestones with plots. If an approach fails, log it and pivot.
5. **Review the report.** Launch a subagent (Agent tool, subagent_type="general-purpose", model="opus") with `/zombuul:review-experiment-report`, passing the path to `report.md`. Do not skip this step.
6. **Sync results.** If a pod was used: sync all results back locally. Pause the pod via `/zombuul:pause-runpod`.
7. **Commit and push.** Commit all outputs — reports, plots, scripts, data files (scores, configs, JSON results). Push: `git push -u origin HEAD`. Check `.gitignore` before committing large files. If you generate data files that exceed ~50MB and aren't already gitignored, add them to `.gitignore` rather than committing.
