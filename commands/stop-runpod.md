---
description: List and terminate RunPod pods.
allowed-tools: Bash, AskUserQuestion
---

List running RunPod pods and terminate one.

## Process

1. **List pods**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py list`.

2. If there are multiple pods, **ask the user** which one to terminate using AskUserQuestion.

3. **Terminate**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py stop <pod_id>`.

4. If no pods are running, tell the user.
