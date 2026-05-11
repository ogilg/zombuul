---
name: zombuul:resume-runpod
description: Resume a paused RunPod pod.
user-invocable: true
allowed-tools: Bash, AskUserQuestion
---

Resume a previously paused RunPod pod. Waits for SSH to be ready.

## Process

1. **List pods**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py list`. Look for pods with EXITED status (these are paused).

2. If there are multiple paused pods, **ask the user** which one to resume using AskUserQuestion.

3. **Resume**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py resume <pod_id>`.

4. If no paused pods are found, tell the user.
