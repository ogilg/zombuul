---
name: zombuul:babysit
description: >
  Monitor a long-running job on a RunPod GPU pod. Checks every 5 min, restarts on crash, and either
  pauses the pod or fires a follow-up prompt when done.
  Argument $ARGUMENTS — `<pod_name> <description> [--on-complete "<prompt>"]`.
  Use when a GPU job is expected to take >10 min and may crash (I/O errors, OOM, SSH timeouts).
  The description should say what's running and how to tell when it's done. Pass `--on-complete`
  to chain the next step (e.g. `/zombuul:finalize-experiment <spec> --pod <name>`) so the workflow
  resumes automatically when the job finishes.
argument-hint: <pod-name> <description> [--on-complete "<prompt>"]
user-invocable: true
---

Monitor a long-running GPU job on a RunPod pod, restarting on crash and either pausing the pod or handing off to a follow-up step when the job finishes.

## Arguments

`$ARGUMENTS` is `<pod_name> <description> [--on-complete "<prompt>"]`.

- `<pod_name>` (first whitespace-delimited token, required) — the pod name. The SSH alias is `runpod-<pod_name>`; strip a leading `runpod-` if the caller passed the alias verbatim (`runpod-foo` → `foo`).
- `<description>` (required) — natural-language description of what's running and how to tell when it's done. Used as the body of the cron's progress reporting.
- `--on-complete "<prompt>"` (optional) — a self-contained prompt to fire when the job finishes cleanly. Most often `/zombuul:finalize-experiment <spec_path> --pod <pod_name>`. When set, babysit does NOT pause the pod itself — the on-complete prompt is responsible for syncing results, pausing, etc. When not set, babysit pauses the pod itself on completion.

To parse: `--on-complete` is followed by a quoted string. Everything between the quotes after `--on-complete` is the on-complete prompt; everything before `--on-complete` (after the pod name) is the description.

## Process

1. **Parse arguments.** Split out `pod_name`, `description`, and optional `on_complete`. Strip a leading `runpod-` from `pod_name` if present. If pod_name or description is empty, show usage and stop.

2. **Snapshot the running command and its tmux session.** SSH to the pod and capture both:
   ```
   ssh runpod-<pod_name> 'tmux list-sessions 2>/dev/null; ps aux | grep python | grep -v grep'
   ```
   Save this output — it goes into the cron prompt so the babysitter agent knows the session name and exact command to restart.

3. **Create the cron job.** Use `CronCreate` with cron `*/5 * * * *` (every 5 min), recurring: true. For jobs >1 hour, also pass `durable: true` so the cron survives Claude session restarts (still requires Claude to be running and idle to fire — for fully unattended overnight runs, use `--remote` mode in `/zombuul:run-experiment` instead). The prompt must be **completely self-contained** — the cron agent has no conversation history. Build it from this template (omit the `--on-complete` block if not provided):

   ```
   You are babysitting a GPU job on pod "{pod_name}" (SSH: `runpod-{pod_name}`).

   **What's running:** {description}
   **Last known command:** {snapshot from step 2}
   {if on_complete: **On completion, fire this prompt:** {on_complete}}

   ## Check

   1. Liveness: `ssh runpod-{pod_name} 'tmux has-session -t <session> 2>/dev/null && echo alive || echo dead'`. If the job was launched without tmux, fall back to `ps aux | grep python | grep -v grep`.

   2. Disk: `ssh runpod-{pod_name} 'df -h / /workspace 2>/dev/null | tail -2'`. Surface usage as one line: `disk: / 67%, /workspace 42%`. If either is ≥ 85%, prefix the entire report with **DISK WARN** — disk-full causes silent corruption (xet IO errors, partial checkpoint writes, lost activations) and is a likely cause of crashes if dead.

   3. **If alive:** Check progress from the description (count output files, tail logs, etc.). Report one line: "{N}/{total} done" or similar.

   4. **If dead:**
      a. Check logs: `ssh runpod-{pod_name} 'tail -30 /workspace/repo/<likely_log_path>'`
      b. Diagnose (OOM? I/O error? disk full per step 2? completed successfully?).
      c. If completed successfully → go to step 5.
      d. If crashed → restart using the last known command above inside a new tmux session (`tmux new-session -d -s <session> '<cmd>'`). Report what happened.

   5. **If done** (all expected outputs exist per the description):
      a. Report completion (one line + total runtime if you can derive it).
      b. {if on_complete: Enqueue the follow-up via `CronCreate(cron="<minute+1> <hour> <day> <month> *", recurring=false, prompt="{on_complete}")` so it fires once, ~1 minute from now. Do NOT pause the pod — the follow-up is responsible for any syncing/pausing.}
         {else: Pause the pod by invoking `/zombuul:pause-runpod {pod_name}`.}
      c. Cancel this cron job: use `CronList` to find the job whose prompt mentions "{pod_name}", then `CronDelete <id>`.

   Keep output to 1-3 lines unless something went wrong.
   ```

4. **Run the first check immediately** — execute the same SSH process check inline so the user gets instant feedback. Don't wait for the first cron tick.

5. **Report:** Show the cron job ID, what it's monitoring, whether an on-complete is wired up, and `CronDelete <id>` to cancel.

## Why on-complete doesn't pause the pod

The follow-up prompt typically needs to rsync results from the pod before pausing — and you can't rsync from a paused pod (SSH is dead). So when `--on-complete` is set, babysit's success branch hands off to the follow-up with the pod still alive, and the follow-up handles its own pause as the final step. Without on-complete, babysit pauses immediately because no further work is queued.

## Report zombuul bugs

If anything went wrong this session that zombuul could plausibly have done better, follow `${CLAUDE_PLUGIN_ROOT}/REPORTING_BUGS.md` before ending.
