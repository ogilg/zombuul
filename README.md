# Zombuul

Autonomous research loops on GPU pods with Claude Code.

## Install

```
/plugin marketplace add ogilg/zombuul
/plugin install zombuul@ogilg-marketplace
/zombuul:setup
```

## Usage

1. Write an experiment spec — a markdown file describing your research question, methods, and success criteria
2. Launch it on a GPU pod:

```
/zombuul:launch-research-pod experiments/my_question/spec.md
```

Claude Code spins up a RunPod GPU, clones your repo, runs the experiment autonomously, pushes a report, and terminates the pod.

## Commands

| Command | What it does |
|---------|-------------|
| `/zombuul:launch-research-pod` | Launch an experiment on a GPU pod |
| `/zombuul:launch-research-loop` | Run an experiment locally (no pod) |
| `/zombuul:launch-research-ralph` | Chain experiments — each builds on the last |
| `/zombuul:launch-runpod` | Spin up a pod without launching an experiment |
| `/zombuul:stop-runpod` | List and terminate pods |
| `/zombuul:setup` | Interactive onboarding |

## Setup details

`/zombuul:setup` handles all of this, but for reference:

- `pip install runpod` or `uv pip install runpod`
- SSH key at `~/.ssh/id_ed25519`
- RUNPOD_API_KEY in `.env` or `~/.claude/.env`
- A `.env` in your repo root with `GH_TOKEN`, `GIT_USER_NAME`, `GIT_USER_EMAIL`
- Your repo needs a `pyproject.toml` (the pod runs `uv pip install -e .`)

## How it works

```
You                          Pod (RunPod GPU)
 │                            │
 │  /launch-research-pod      │
 │  spec.md ─────────────────>│ clone repo
 │                            │ install deps
 │                            │ read spec
 │                            │ run baseline
 │                            │ iterate (code, analysis, plots)
 │                            │ write report.md
 │                            │ push branch
 │  <─────────────────────────│ terminate
 │                            │
 │  git pull
 │  experiments/my_question/report.md
```
