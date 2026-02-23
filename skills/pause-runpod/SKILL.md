---
name: pause-runpod
description: Pause a RunPod pod (stop GPU billing, keep disk).
user-invocable: true
allowed-tools: Bash, AskUserQuestion
---

Pause a running RunPod pod without terminating it. The disk is preserved and GPU billing stops.

## Process

1. **List pods**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py list`.

2. If there are multiple pods, **ask the user** which one to pause using AskUserQuestion.

3. **Pause**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py pause <pod_id>`.

4. If no pods are running, tell the user.
