---
description: Spin up a RunPod GPU pod. Argument $ARGUMENTS — optional pod name.
allowed-tools: Bash, AskUserQuestion
---

Spin up a RunPod GPU pod interactively.

## Process

1. **List available GPUs**: Run `python /Users/oscargilg/Dev/zombuul/scripts/runpod_ctl.py gpus` and show the user the options.

2. **Ask the user** which GPU they want using AskUserQuestion. Offer 3-4 common options from the list plus an "Other" escape hatch.

3. **Ask for docker image** if not obvious. Default to `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`.

4. **Create the pod**: Run `python /Users/oscargilg/Dev/zombuul/scripts/runpod_ctl.py create --name <name> --gpu "<gpu_type_id>" --image "<image>"` **in the background**. Use $ARGUMENTS as the pod name if provided, otherwise default to "research". The script auto-detects the repo URL and branch from the current working directory, creates the pod, waits for SSH, extracts Claude Code credentials from Keychain, then SCPs and runs `pod_setup.sh`.

5. **SCP the project .env**: If a `.env` file exists in the current working directory, copy it to the pod:
   `scp -P <port> -i ~/.ssh/id_ed25519 .env root@<ip>:/workspace/repo/.env`

6. **Report to the user**:
   - SSH command: `ssh root@<ip> -p <port> -i ~/.ssh/id_ed25519`
   - The setup script is running in the background on the pod (clones repo, installs deps). Check `/var/log/pod_setup.log` on the pod for progress.
   - Once setup is done, run `source ~/.bash_profile && cd /workspace/repo && IS_SANDBOX=1 claude --dangerously-skip-permissions --effort high`.
   - They can run `/stop-runpod` to terminate the pod when done.
