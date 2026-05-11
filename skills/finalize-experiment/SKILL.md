---
name: zombuul:finalize-experiment
description: >
  Finalize an experiment after the main work is done — sync pod results back, run analysis,
  spawn report review, commit and push. Argument $ARGUMENTS — `<spec_path> [--pod <pod_name>]`.
  Invoked automatically by `/zombuul:babysit --on-complete` when a long-running job finishes,
  or directly by you when an experiment doesn't use a babysitter (no pod, no cron).
argument-hint: <spec-path> [--pod <pod-name>]
user-invocable: true
---

You are finalizing an experiment that has finished running. The main work — generation, training, extraction, whatever the spec called for — is already done. Your job is to sync any remote results, analyze them, write or finish the report, get it reviewed, and commit/push the deliverable.

## Arguments

`$ARGUMENTS` is `<spec_path> [--pod <pod_name>]`.

- `spec_path` (required): path to the experiment spec, e.g. `experiments/foo/foo_spec.md`. The experiment directory is its parent.
- `--pod <pod_name>` (optional): if the experiment ran on a RunPod pod, pass its SSH alias name (matching `runpod-<pod_name>`). Triggers a pod-result sync followed by a pause. Omit for purely local experiments.

## Read history first — don't fly blind

Before doing anything, read these files in order. They are your only source of truth for what happened during the run:

1. `<spec_path>` — what the experiment was supposed to do.
2. `experiments/<name>/running_log.md` — what was actually done, what was decided mid-run, what was skipped, what surprised the kickoff agent. Read it end to end. If it references commits or git history, run `git log --oneline -20 -- experiments/<name>/` to fill in.
3. `experiments/<name>/<name>_report.md` if it already exists (the kickoff agent may have started it at major milestones).
4. The output files (whatever the spec said the experiment would produce — measurements, scores, JSONL, .npz, etc.).

You do not have the kickoff agent's working memory. The running log is how that memory was preserved for you. Treat any decision noted there (parameter changes, scope reductions, controls deferred) as load-bearing context that must be reflected in the report.

## Workflow

### F1: Sync results (pod-only)

If `--pod <pod_name>` was provided:

1. Verify the pod is alive: `ssh runpod-<pod_name> 'tmux ls 2>/dev/null; echo done'`. If it's paused (SSH fails), that's a problem — the babysitter was supposed to leave it running for you. Resume it once via `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py resume <pod_id>` (look up pod_id with `runpod_ctl.py list`).
2. Determine which directories to sync. The spec's "Output structure" / per-cell results path is the canonical source. Default for most experiments: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/safe_rsync.sh -az runpod-<pod_name>:/workspace/repo/experiments/<name>/results/ experiments/<name>/results/`. Add other gitignored output dirs the spec produced. Each invocation prints `[safe_rsync] EXIT=<code> FILES=<n>`; check both lines before proceeding — `EXIT=0 FILES=0` on a finalize sync usually means you're syncing the wrong path or the experiment didn't write what the spec said it would.
3. After sync, pause the pod: `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py pause <pod_id>` (or `/zombuul:pause-runpod <pod_name>` — equivalent).

If no `--pod` flag (purely local experiment, or `IS_SANDBOX=1` meaning you're already on the pod): skip F1.

### F2: Analyze

Run any analysis script the spec or running_log point to (typically `scripts/<name>/analyze.py` or similar). The kickoff agent should have left analysis code in place; if not, write it. Sanity-check outputs (counts, magnitudes, no NaNs) before building the report on top of them.

If results look wrong (counts off, magnitudes implausible, refusal rates that suggest a broken cell), do NOT paper over it in the report. Flag it in the report and, if needed, re-run the affected piece.

### F3: Write or finish the report

Path: `experiments/<name>/<name>_report.md`. Plots go in `experiments/<name>/assets/` and are referenced with relative paths: `![desc](assets/plot_<mmddyy>_<short_desc>.png)`.

**Report style.** Scannable — someone should grasp the full arc in 30 seconds. Headlines over prose, tables over text, dead ends in one line each. Include plots at key checkpoints. Include enough detail to reproduce (parameters, prompts, configs) but stay concise. Favor results (numbers, tables, plots) over interpretive prose — keep interpretation to short inline remarks or a few bullets, not dedicated sections. The reviewer subagent (next step) will catch clarity issues — focus on content first.

**Plotting.** Delegate plot creation to subagents (Agent tool, subagent_type="general-purpose", model="opus"). Describe what to plot, where the data is, and where to save it. The subagent writes the script (under `scripts/<name>/`) and runs it. Keeps plotting code out of your context.

**Compute, don't transcribe.** Never hand-write numbers in the report. Generate tables and metrics programmatically from the data files. If a number changes after a re-run, the report should pick it up automatically.

**Report honestly.** Null and negative results are informative. Spec deviations (parameter changes, scope reductions, controls deferred) recorded in the running log must appear in the report as a "deviations from spec" or similar paragraph.

### F4: Review

Spawn an Agent (subagent_type="general-purpose", model="opus") with `/zombuul:review-experiment-report`, passing the path to the report. Apply the feedback. Do not skip this — even a one-pass review catches missing context, ambiguous claims, and unsupported conclusions.

### F5: Data inventory + outside-code-changes (in the report)

Before final commit, append two short sections to the report.

**Data used.** From the spec's input paths, run `du -sh <path>` on each and list:

```
## Data used
- activations/<dir>/ (2.3G)
- probe_data/<dir>/ (45M)
```

Skip the section entirely if the experiment has no gitignored inputs.

**Code changes outside this experiment.** Run `git diff <pr-base-branch>...HEAD --name-only -- ':!experiments/<name>/' ':!scripts/<name>/'`. If non-empty, append:

```
## Code changes outside this experiment
Modified while running. These are not in this PR — open a separate one:
- <path>
- <path>
```

The user uses this list to spin off a follow-up PR with just the code changes. Don't include diffs, just paths.

### F6: Commit and push (experiment folder is the deliverable)

The deliverable is `experiments/<name>/` (spec, report, assets, running log). Order commits so the experiment-folder diff is clean and self-contained — easy to read in the PR UI.

1. Commit code/scripts/data artifacts in separate, meaningfully-labeled commits. Respect `.gitignore`. Files >50 MB that aren't already gitignored should be added to `.gitignore` rather than committed.
2. A final commit containing only `experiments/<name>/` — the deliverable.
3. `git push origin HEAD`.

### F7: Mark draft PR ready

Find the draft PR for this branch: `gh pr list --head <branch> --state open --json number,isDraft -q '.[] | select(.isDraft)'`. If one exists:

1. Mark it ready: `gh pr ready <number>`.
2. Rewrite the body: 2-3 sentence summary of findings, link to the report (`experiments/<name>/<name>_report.md`), mention "see § Code changes outside this experiment in the report" if F5 found any.

Skip silently if no draft PR exists (e.g. user invoked with `--no-pr` or the launcher couldn't open one). The deliverable is still on the branch and pushed.

## Rules

- **Read the running log first.** Without it, you are guessing about decisions made during the run.
- **Reuse existing analysis code** under `scripts/<name>/` rather than writing new analyses. If the kickoff agent already drafted `analyze.py`, use it; only extend it for things it didn't cover.
- **Compute, don't transcribe.** Numbers in the report come from data files via code, not from your context.
- **Report honestly.** Spec deviations, null results, surprising findings all belong in the report. Do not spin or omit.
- **Don't game the spec.** If a metric in the spec is unmeasurable from the data you have, say so in the report — don't substitute a similar-looking metric without flagging the swap.
- **Do not ask the user.** Make reasonable choices and note them. The user invoked finalize expecting it to run to completion.

## Report zombuul bugs

If anything went wrong this session that zombuul could plausibly have done better, follow `${CLAUDE_PLUGIN_ROOT}/REPORTING_BUGS.md` before ending.
