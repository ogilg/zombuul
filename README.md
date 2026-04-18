# Zombuul

Run experiments on GPU pods from local Claude Code.

## Install

```
/plugin marketplace add ogilg/zombuul
/plugin install zombuul@ogilg-marketplace
```
And then ask claude to set it up.


## Usage

1. Write an experiment spec — spend time making it good
2. Run it:

```
/zombuul:run-experiment experiments/my_question/my_question_spec.md
```

Your local Claude Code reads the spec, decides if a GPU pod is needed, sets one up if so, then runs the experiment — baseline, iterations, plots, report. GPU-bound work (extraction, training, steering) runs on the pod via SSH; analysis and plotting run locally. Results are synced back, the pod is paused, and the branch is pushed.

### Remote mode (survive local disconnects)

Pass `--remote` to run the agent *inside* the pod instead of orchestrating from your laptop:

```
/zombuul:run-experiment experiments/my_question/my_question_spec.md --remote
```

Your local Claude pushes the branch, spins up a pod with Claude Code + the zombuul plugin installed, syncs the spec and any gitignored data the spec reads, kicks off `claude -p '/zombuul:run-experiment <spec>'` inside the pod under `nohup ... & disown`, and hands off. The on-pod agent commits and pushes `experiments/<name>/running_log.md` after each step so you can `git fetch` to see progress. When the agent exits, the pod auto-pauses.

Claude Code is **only** installed on the pod in remote mode. Default (local) mode uses the pod as a dumb SSH target.

## Commands

| Command | What it does |
|---------|-------------|
| `/zombuul:run-experiment` | Run an experiment from a spec. Handles pod creation, data sync, remote/local execution, and reporting. Pass `--remote` to run the agent inside the pod. |
| `/zombuul:review-spec` | Review an experiment spec for completeness before running it. |
| `/zombuul:launch-runpod` | Spin up a pod without launching an experiment. Pass `--remote` as a second arg to also install Claude Code + the zombuul plugin on the pod. |
| `/zombuul:provision-pod` | Provision a pod: configure SSH, sync .env and data. Called by `run-experiment` automatically. |
| `/zombuul:pause-runpod` | Pause a pod (stop GPU billing, keep disk). |
| `/zombuul:resume-runpod` | Resume a paused pod. |
| `/zombuul:review-experiment-report` | Review and rewrite a research report for clarity. Called by `run-experiment` at the end. |
| `/zombuul:setup` | Interactive onboarding — detects what's already configured, only asks for what's missing. |

## Setup details

`/zombuul:setup` handles all of this, but for reference:

- `pip install runpod` or `uv pip install runpod`
- SSH key at `~/.ssh/id_ed25519`
- A `.env` in your repo root with `RUNPOD_API_KEY`, `GH_TOKEN`, `GIT_USER_NAME`, `GIT_USER_EMAIL`
- Your repo needs a `pyproject.toml`, `requirements.txt`, or `setup.py` (the pod auto-detects and installs deps)

## How it works

```
You (local Claude Code)              Pod (RunPod GPU)
 │                                    │
 │  /run-experiment spec.md           │
 │  ─ read spec                       │
 │  ─ GPU needed? create pod ──────> │ clone repo, install deps
 │  ─ sync .env + data ────────────> │
 │  ─ add ssh alias (runpod-<name>)  │
 │                                    │
 │  ssh runpod-<name> 'python -m ..' │ run GPU-bound work
 │  (run locally: analysis, plots)    │
 │  rsync results back <──────────── │
 │                                    │
 │  write report, push branch         │
 │  pause pod                         │
```
