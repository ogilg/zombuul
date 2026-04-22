# Zombuul

Run AI safety experiments end-to-end, from spec to report. Claude Code handles the GPU pod, orchestration, and writeup. Locally, or fully remote.

## Install

```
/plugin marketplace add ogilg/zombuul
/plugin install zombuul@ogilg-marketplace
```

Then run `/zombuul:setup`.

## Usage

1. **Write a spec.** A detailed markdown file covering the question, the data, the method, and the expected outputs. Spend time on it; everything downstream depends on it.

2. *(optional)* **Review the spec:** `/zombuul:review-spec path/to/spec.md`. Flags gaps before you burn GPU hours.

3. **Run it:** `/zombuul:run-experiment path/to/spec.md`. Pod, execution, plots, report all handled. Add `--remote` to run the agent *inside* the pod so you can close your laptop; it commits progress to a branch and auto-pauses the pod on exit.

4. *(optional)* **Babysit long runs:** `/zombuul:babysit <pod_name> <description>`. Polls progress every 5 min, reports back, handles crashes and wrap-up.

## What it handles for you

- **Pod lifecycle.** Spin up, pause, resume RunPod GPUs on demand.
- **Repo + env.** Clone your branch, auto-install deps, sync `.env` and gitignored data.
- **Orchestration.** Runs baseline + iterations, commits a running log, writes the final report with plots.
- **The prompts themselves.** `run-experiment`, `review-spec`, `review-experiment-report`, and `babysit` were refined over 3 months of MATS experiments. The opinionated loop (how to structure a spec, when to iterate, what a report should look like) is where most of the value lives.

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

## Commands

| Command | What it does |
|---------|-------------|
| `/zombuul:run-experiment` | Run an experiment from a spec. Pass `--remote` to run inside the pod. |
| `/zombuul:review-spec` | Review a spec for completeness before running. |
| `/zombuul:babysit` | Monitor a long-running job. Progress pings every 5 min, restarts on crash. |
| `/zombuul:review-experiment-report` | Rewrite a report for clarity. Called by `run-experiment` at the end. |
| `/zombuul:launch-runpod` | Spin up a pod without launching an experiment. `--remote` also installs Claude Code on it. |
| `/zombuul:provision-pod` | Configure SSH, sync `.env` and data. Called automatically by `run-experiment`. |
| `/zombuul:pause-runpod` / `/zombuul:resume-runpod` | Pause or resume a pod. |
| `/zombuul:setup` | Interactive onboarding. |

## Feedback

Bugs, questions, feature ideas, or just want to share what you're running: all welcome. Open an [issue](https://github.com/ogilg/zombuul/issues) or start a [discussion](https://github.com/ogilg/zombuul/discussions). I read everything.

Contact: `oscar.gilg18 [at] gmail [dot] com`
