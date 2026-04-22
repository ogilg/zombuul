---
name: zombuul:babysit
description: >
  Monitor a long-running job on a RunPod GPU pod. Checks every 5 min, restarts on crash, pauses pod when done.
  Argument $ARGUMENTS — `<pod_name> <description of what's running>`.
  Use when a GPU job is expected to take >10 min and may crash (I/O errors, OOM, SSH timeouts).
  The description should say what's running and how to tell when it's done (e.g., "E1c extraction — 121 conditions in activations/qwen35_122b_ood/e1c/").
user-invocable: true
---

Monitor a long-running GPU job on a RunPod pod, restarting on crash and cleaning up when done.

## Arguments

`$ARGUMENTS` is `<pod_name> <description>`. The first whitespace-delimited token is the pod name (must match an SSH alias `runpod-<pod_name>`). Everything after it is a natural-language description of what's running and how to tell when it's done.

## Process

1. **Parse arguments.** Split into pod_name and description. If either is empty, show usage and stop.

2. **Snapshot the running command.** SSH to the pod and capture what's running:
   ```
   ssh runpod-<pod_name> 'ps aux | grep python | grep -v grep'
   ```
   Save this output — it goes into the cron prompt so the babysitter agent knows what to restart.

3. **Create the cron job.** Use `CronCreate` with cron `*/5 * * * *` (every 5 min), recurring: true. The prompt must be **completely self-contained** — the cron agent has no conversation history. Build it from this template:

   ```
   You are babysitting a GPU job on pod "{pod_name}" (SSH: `runpod-{pod_name}`).

   **What's running:** {description}
   **Last known command:** {snapshot from step 2}

   ## Check

   1. `ssh runpod-{pod_name} 'ps aux | grep python | grep -v grep'`

   2. **If alive:** Check progress from the description (count output files, tail logs, etc.). Report one line: "{N}/{total} done" or similar.

   3. **If dead:**
      a. Check logs: `ssh runpod-{pod_name} 'tail -30 /workspace/repo/<likely_log_path>'`
      b. Diagnose (OOM? I/O error? completed successfully?).
      c. If completed successfully → go to step 4.
      d. If crashed → restart using the last known command above (adjust working dir, log path as needed). Report what happened.

   4. **If done** (all expected outputs exist per the description):
      a. Report completion.
      b. Pause the pod: invoke `/zombuul:pause-runpod {pod_name}`.
      c. Cancel this cron job: use `CronList` to find the job whose prompt mentions "{pod_name}", then `CronDelete <id>`.

   Keep output to 1-3 lines unless something went wrong.
   ```

4. **Run the first check immediately** — execute the same SSH process check inline so the user gets instant feedback. Don't wait for the first cron tick.

5. **Report:** Show the cron job ID, what it's monitoring, and `CronDelete <id>` to cancel.
