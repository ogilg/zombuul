# Zombuul

Autonomous research loops on GPU pods with claude --dangerously-skip-permissions.

## Install

```
/plugin marketplace add ogilg/zombuul
/plugin install zombuul@ogilg-marketplace
/zombuul:setup
```

## Usage

1. Write an experiment spec — spend time making it good
2. Launch it:

```
/zombuul:launch-research-pod experiments/my_question/spec.md
```

This spins up a RunPod GPU, clones your repo, installs deps, then launches a headless Claude Code session with `--dangerously-skip-permissions` inside tmux. That agent reads your spec, runs the experiment autonomously (baseline, iterations, plots, report), pushes a branch with the results, and terminates the pod.

## Commands

| Command | What it does |
|---------|-------------|
| `/zombuul:launch-research-pod` | Pick a GPU, spin up a pod, launch a research loop on it. Syncs your `.env` and any data files referenced in the spec. Pod auto-terminates when done. |
| `/zombuul:launch-research-loop` | Run a research loop locally (no pod). Same autonomous agent — reads spec, runs baseline, iterates, writes report, pushes branch. |
| `/zombuul:launch-research-ralph` | Chain experiments. After each research loop completes, a ralph agent reads the report, decides what to investigate next, writes a follow-up spec, and launches another loop. Repeats until the research goal is met. |
| `/zombuul:launch-runpod` | Spin up a pod without launching an experiment. Gives you an SSH command and a ready Claude Code environment. |
| `/zombuul:stop-runpod` | List running pods and terminate one. |
| `/zombuul:check-slack` | Read the zombuul Slack channel. Agents post blocking issues and strong results there. |
| `/zombuul:setup` | Interactive onboarding — detects what's already configured, only asks for what's missing. |

## Setup details

`/zombuul:setup` handles all of this, but for reference:

- `pip install runpod` or `uv pip install runpod`
- SSH key at `~/.ssh/id_ed25519`
- RUNPOD_API_KEY in `.env` or `~/.claude/.env`
- A `.env` in your repo root with `GH_TOKEN`, `GIT_USER_NAME`, `GIT_USER_EMAIL`
- Your repo needs a `pyproject.toml` (the pod runs `uv pip install -e .`)

## How it works

```
You (local Claude Code)              Pod (RunPod GPU)
 │                                    │
 │  /launch-research-pod spec.md      │
 │  ─ pick GPU                        │
 │  ─ create pod ───────────────────> │ clone repo, install deps
 │  ─ SCP .env + data ─────────────> │
 │  ─ launch claude --dangerously-  > │
 │    skip-permissions in tmux        │
 │                                    │ read spec
 │                                    │ run baseline
 │                                    │ iterate (code, analysis, plots)
 │                                    │ write report.md
 │                                    │ push branch
 │                                    │ terminate pod
 │                                    │
 │  git pull
 │  experiments/my_question/report.md
```
