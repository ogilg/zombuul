---
name: zombuul:pause-runpod
description: "Pause a RunPod pod: stop GPU billing; keep /workspace only (container disk is wiped on resume)."
user-invocable: true
allowed-tools: Bash, AskUserQuestion
---

Pause a running RunPod pod without terminating it. Only the `/workspace` MooseFS volume is preserved across pause — container disk (`/`, `/opt/`, `/root/`) is wiped on resume.

## Process

1. **List pods**: Run `${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py list`.

2. If there are multiple pods, **ask the user** which one to pause using AskUserQuestion.

3. **Remind the user about data loss risk.** Before pausing, note in the chat that pausing wipes container disk (`/`, `/opt/`, `/root/`) and only `/workspace/` survives. Suggest they rsync important experiment outputs off-pod or to `/workspace/` first. This is a reminder, not a hard block — continue to the pause command.

4. **Pause**: Run `${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py pause <pod_id>`.

5. If no pods are running, tell the user.
