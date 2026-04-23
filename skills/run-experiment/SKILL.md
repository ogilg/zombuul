---
name: zombuul:run-experiment
description: >
  Run an experiment from a spec or description. If given a path to an existing spec, runs it directly.
  If given a natural language description, synthesizes a spec first, then runs it.
  Argument $ARGUMENTS — `<spec_path_or_description> [--remote]`. Pass `--remote` to execute
  autonomously on a GPU pod (survives local disconnects); otherwise runs local-first.
user-invocable: true
---

Run this experiment: $ARGUMENTS

## Execution modes (pick one before starting)

Check `$IS_SANDBOX` and `$ARGUMENTS`:

- **On-pod mode** — if the `IS_SANDBOX=1` env var is set, you are already inside a GPU pod that was launched by a remote-mode invocation. Jump to [On-pod execution](#on-pod-execution). Do not read the rest of this document first.
- **Remote-launcher mode** — if `$ARGUMENTS` contains the flag `--remote` (strip it before treating the remainder as the spec path/description), go to [Remote-launcher execution](#remote-launcher-execution).
- **Local mode** — default. `$ARGUMENTS` has no `--remote` flag and `IS_SANDBOX` is unset. Go to [Local execution](#local-execution).

## Phase 0: Determine input type (all modes)

After identifying the mode, parse what's left of `$ARGUMENTS`:

- Ends in `.md` and the file exists → spec path. Skip spec synthesis.
- Otherwise → natural language description. Spawn a **spec synthesis subagent** (Agent tool, subagent_type="general-purpose", model="opus") with the following prompt:

> Write a concise experiment spec from this description and the conversation context.
>
> **Description:** {$ARGUMENTS (minus `--remote`)}
>
> **Instructions:**
> - Read `README.md` and `CLAUDE.md` for codebase conventions and available modules.
> - Read 2-3 short existing specs under `experiments/` for format reference (the shortest specs are ~25 lines — match that brevity for simple experiments).
> - Derive an experiment name and path. Nest under an existing experiment if it's a follow-up; otherwise create a new directory.
> - The spec should include: title, core question, models/data, code pointers to existing modules, parameter values, and steps. Omit background, justification, or anything the executing agent can find in the README.
> - Scale length to complexity. A single-step analysis or extraction needs ~25 lines. A multi-phase experiment with GPU needs more. Never pad.
> - Write the spec to `experiments/{name}/{name}_spec.md`.
> - Return the spec path and a one-paragraph summary of key decisions/assumptions.

When the subagent returns, show the user the spec path and summary. Ask: "Want me to run `/zombuul:review-spec` on this, or proceed?" Do not proceed until the user confirms.

## Local execution

### Phase 1: Read spec and launch setup agents

1. **Read the spec** (at the confirmed spec path). Determine whether GPU is needed (references to GPU, CUDA, model loading, extraction, training on large models, steering).
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

### Phase 2: Enter worktree and set up

1. **Enter a worktree**: use the `EnterWorktree` tool with name `{experiment_name}` (derived from the spec path, e.g., `experiments/foo/foo_spec.md` → name `foo`).
2. **Run the symlink commands** returned by the symlink discovery agent. Verify the experiment's input files are accessible.
3. **Set up infrastructure** if GPU needed:
   - If the infrastructure agent found a running pod, use it.
   - Otherwise: **size the pod based on the spec before invoking launch-runpod.** See [Sizing a pod from the spec](#sizing-a-pod-from-the-spec) below. Then invoke `/zombuul:launch-runpod <pod_name> --disk-gb <N> --volume-gb <N>` (local mode — do NOT pass `--remote`, the pod is just an SSH target). After it completes, sync experiment data via `/zombuul:provision-pod`, passing `data_dirs` explicitly (inferred from the spec) to skip interactive recon.
   - Do NOT ask the user for GPU choice, data dirs, etc. Make reasonable choices. Only ask if truly blocked.

Continue to [Execution model](#execution-model) and [Workflow](#workflow).

## Remote-launcher execution

You are **not** running the experiment — you are setting up a pod that will run it autonomously, then handing off. The user wants this because their laptop may go offline.

**Do not ask for confirmation at any step in R1–R4.** Invoking `--remote` is the user pre-authorizing the full pod-launch + handoff flow: pushing the branch, launching/reusing a pod, provisioning, copying the launch script, and kicking off the on-pod agent. Make reasonable choices (pod name, data_dirs) and proceed. The only acceptable stop is if something is actually broken (e.g. push fails, pod setup errors). Run tool calls back-to-back; no "shall I proceed?" checkpoints.

### R1: Read spec, recon data, push branch (concurrent)

1. **Read the spec** at the confirmed spec path.
2. **Launch in parallel** (one `run_in_background` Bash call for the push, one Agent call for the recon):
   - **Data recon subagent** (Agent, subagent_type="general-purpose", model="opus"): "Read the experiment spec at <spec_path>. Find every data path it references (activations .npz, embeddings, topics .json, results directories, configs, probe weights, concept vectors). For each: check whether it exists locally (follow symlinks), whether it's gitignored, and report size (`du -sh`). Return a structured list: `path | exists? | gitignored? | size`. The experiment will run on a GPU pod with only what git provides plus what we explicitly sync — anything gitignored that the spec reads must appear in the sync list."
   - **Push the branch**: commit any relevant unstaged changes (ask before broad commits), then `git push -u origin HEAD`. The pod clones from the remote, so unpushed work is invisible.
3. **Wait for both**, then **decide `data_dirs`**: gitignored paths the spec reads (not writes) are the default sync set. Do not ask the user; err toward including ambiguous directories — a too-small sync is a silent failure on the pod. Capture the branch name.

### R2: Pod setup

1. **Reuse or create**: `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py list`. If a suitable pod is already running with claude installed (verify with `ssh runpod-<name> 'command -v claude'`), reuse it. Otherwise, **size the pod from the spec** (see [Sizing a pod from the spec](#sizing-a-pod-from-the-spec)) and invoke `/zombuul:launch-runpod <pod_name> --remote --disk-gb <N> --volume-gb <N>` — the `--remote` flag causes Claude Code + the zombuul plugin to be installed on the pod. Pick a distinctive 2-3 word kebab-case name based on the experiment.
2. **Provision**: invoke `/zombuul:provision-pod` with `{"pod_id": ..., "pod_name": ..., "ip": ..., "port": ..., "spec_path": "<spec_path>", "data_dirs": [<from R1>]}`. Wait for completion. `provision-pod`'s `wait-setup` surfaces any setup failures — if it reports `claude binary not found`, re-run setup in remote mode via `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py create --name <same> ... --install-claude` (or re-invoke `/zombuul:launch-runpod <pod_name> --remote`).

### R3: Launch the on-pod agent

Execute all three steps without pausing to confirm — this is the whole point of remote mode.

1. **Copy the launch script to the pod**: `scp ${CLAUDE_PLUGIN_ROOT}/scripts/launch_on_pod.sh runpod-<name>:/tmp/launch_on_pod.sh`
2. **Launch under nohup + disown** with branch and spec path as positional args:
   `ssh runpod-<name> 'chmod +x /tmp/launch_on_pod.sh && nohup /tmp/launch_on_pod.sh <branch> <spec_path> </dev/null > /workspace/launch.log 2>&1 & disown'`
3. **Verify the claude process is running**: `ssh runpod-<name> 'ps aux | grep claude | grep -v grep'`.

The script sources `~/.bash_profile` (for tokens), registers a `trap pause_pod EXIT` so the pod auto-pauses on any agent exit including crashes, then runs `claude -p '/zombuul:run-experiment <spec>'` with `IS_SANDBOX=1`. See `scripts/launch_on_pod.sh` for the full script.

### R4: Hand off to the user

Report:
- Pod name, SSH command, branch name.
- Monitoring commands:
  - `git fetch origin <branch> && git log origin/<branch> --oneline -- experiments/<name>/` — see running-log commits as they land.
  - `ssh runpod-<name> 'tail -f /workspace/agent.log'` — live stdout of the on-pod agent.
- Expected behavior: pod auto-pauses when the agent exits (trap handles crashes too). Results land on the `<branch>` branch as commits. `experiments/<name>/running_log.md` is the legible progress log.

Then stop. Do NOT enter any monitoring loop — the user's explicit motivation for remote mode is that they may be offline.

## On-pod execution

You are inside a GPU pod. `IS_SANDBOX=1` is set. Everything you need to run the experiment is already here: the repo is cloned at `/workspace/repo`, `.env` is synced, the spec is at `$ARGUMENTS`, and `data_dirs` specified at launch time have been synced under `/workspace/repo/`. Do NOT:

- Create pods or call any `runpod_ctl.py` command.
- Invoke `/zombuul:launch-runpod`, `/zombuul:provision-pod`, or `/zombuul:run-experiment` recursively (no `remote` token handling — you're the terminal point).
- Use `EnterWorktree`. Work directly in `/workspace/repo` on the current branch.

### OP1: Setup

1. **Confirm context**: `pwd` should be `/workspace/repo`. `git branch --show-current` should show the experiment branch. If not, `git checkout <branch>`.
2. **Read the spec** at the path passed in `$ARGUMENTS`.
3. **Verify data presence**: for every gitignored data path the spec references, check it exists on the pod (`ls -la <path>`). If anything critical is missing, append a MISSING DATA block to `experiments/<name>/running_log.md`, commit+push, and stop — don't try to work around missing data by provisioning more infrastructure.
4. **Create scripts workspace, report skeleton, and running log** (see [Directory structure](#directory-structure) below).

### OP2: Run + log + push

Execute the experiment workflow ([Workflow](#workflow) steps 3–5) with two differences:

- **Every step appends to `running_log.md`** (you'd do this in any mode). Additionally, after each step:
  `git add experiments/<name>/ && git diff --cached --quiet || (git commit -m "log: <brief>" && git push origin HEAD)`
  The `--quiet` check skips empty commits when no files actually changed (e.g., a no-op step). `git add experiments/<name>/` picks up anything under the experiment dir, including newly-created subdirs. This is what lets the user's local Claude check progress from a fresh fetch. Squash noise later — clarity now beats tidy history.
- **GPU-bound and CPU-bound commands both run locally on the pod.** No SSH. No rsync-back. Everything lives here.

Keep commits small and labeled (`log: <step>`, `result: <step>`, `fix: <what>`). Do not force-push.

### OP3: Finish

1. Run `/zombuul:review-experiment-report` via an Agent subagent on the report path.
2. Final commit + push of report, plots, scripts, data artifacts (respect `.gitignore`; large files that aren't already gitignored should be added to `.gitignore` rather than committed).
3. Exit cleanly. The launch script will pause the pod automatically.

## Execution model

**Local mode — remote vs local command awareness:**
- GPU-bound commands (model loading, extraction, training, steering) → SSH to pod: `ssh runpod-<name> 'cd /workspace/repo && python -m ...'`
- CPU-bound commands (analysis, plotting, fitting) → run locally
- Results from pod need to be synced back: `rsync -az runpod-<name>:/workspace/repo/<results_path> <local_path>`

**On-pod mode:** everything runs locally on the pod. No SSH, no rsync.

**Non-blocking execution (local mode):**
- Short commands (<10 min): use `run_in_background` on the Bash tool. You get notified when they complete.
- While waiting: prepare next steps, write analysis code, set up plotting scripts.

**Babysitting long GPU jobs (local mode only):**
For GPU jobs expected to take more than ~10 minutes, use nohup + babysit instead of `run_in_background`. This handles crash recovery automatically.

1. Launch the job so it survives SSH disconnect:
   `ssh runpod-<name> 'cd /workspace/repo && nohup python -u -m <module> > <log_path> 2>&1 & disown'`
2. Invoke `/zombuul:babysit <pod_name> <description>` — this sets up a cron job that checks every 5 min, restarts on crash, and pauses the pod when done.
3. You are free to work on other tasks while the babysitter monitors. It will report progress and any issues to the conversation.

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

Create `running_log.md` in the experiment directory. Append to this after every completed step — script outputs, intermediate numbers, observations, errors. In on-pod mode, this is also the user's only real-time progress window, so append aggressively (every command, every result) and commit+push after each append. This is for recovery if the session dies — do not re-read it during the session. Use your in-context memory for what you've done so far.

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

1. **Setup** (Phase 1 + Phase 2 for local mode; R1–R4 for remote-launcher; OP1 for on-pod).
2. **Read the spec.** Set up infrastructure.
3. Create scripts workspace, report skeleton, and running log.
4. Run baseline, then iterate. Log each step to the running log. Update the report at major milestones with plots. If an approach fails, log it and pivot.
5. **Review the report.** Launch a subagent (Agent tool, subagent_type="general-purpose", model="opus") with `/zombuul:review-experiment-report`, passing the path to `report.md`. Do not skip this step.
6. **Sync results** (local mode only, if a pod was used): sync all results back locally. Pause the pod via `/zombuul:pause-runpod`.
7. **Commit and push.** Commit all outputs — reports, plots, scripts, data files (scores, configs, JSON results). Push: `git push -u origin HEAD`. Check `.gitignore` before committing large files. If you generate data files that exceed ~50MB and aren't already gitignored, add them to `.gitignore` rather than committing. (In on-pod mode you've already been pushing incrementally — this final push just tops it off.)

## Sizing a pod from the spec

Defaults (100 GB disk / 50 GB volume) only fit small models (≤13B). Derive `--disk-gb` and `--volume-gb` from the spec before launching — undersized pods fail mid-run and cost a full restart.

- **`--disk-gb`** (container NVMe; HF cache + venv + local outputs): `model_params_B × 2.5 + 30 + local_outputs_gb`. Anchors: 27B → 100, 70B → 210, 122B → 400. When unsure, round up.
- **`--volume-gb`** (MooseFS; durable outputs that must survive pod deletion): default 50 is usually fine. Note: MooseFS has a hidden per-user quota; `df` reports the pool, not the limit.

Note the chosen sizes in the running log.

## Report zombuul bugs

If anything went wrong this session that zombuul could plausibly have done better, follow `${CLAUDE_PLUGIN_ROOT}/REPORTING_BUGS.md` before ending.
