---
name: zombuul:stop-runpod
description: List and terminate RunPod pods.
user-invocable: true
allowed-tools: Bash, AskUserQuestion, Read, Edit
---

List running RunPod pods and terminate one.

## Process

1. **List pods**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py list`.

2. If there are multiple pods, **ask the user** which one to terminate using AskUserQuestion.

3. **Terminate**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py stop <pod_id>`.

4. **Clean up SSH config**: Read `~/.ssh/config` and remove the `Host runpod-<pod_name>` block (the Host line plus the indented lines that follow it) for the terminated pod. Use the Edit tool to replace the block with empty string. The pod name from the `list` output should match the SSH config alias.

5. If no pods are running, tell the user.
