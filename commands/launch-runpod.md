---
description: Spin up a RunPod GPU pod. Argument $ARGUMENTS — optional pod name.
allowed-tools: Bash, AskUserQuestion, Read, Edit
---

Spin up a RunPod GPU pod interactively.

## Process

1. **Check permissions**: Read `~/.claude/settings.json` and check that the `permissions.allow` array contains all of these:
   - `Bash(python *)`
   - `Bash(ssh *)`
   - `Bash(scp *)`
   - `Bash(sleep *)`

   If any are missing, tell the user which ones are needed and ask (via AskUserQuestion) if you can add them. If they agree, read the current settings.json, add the missing entries to `permissions.allow`, and write it back. If they decline, warn that the command will require manual permission approvals and continue.

2. **List available GPUs**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py gpus` and show the user the options.

3. **Ask the user** which GPU they want using AskUserQuestion. Offer 3-4 common GPU options from the list, plus a "CPU-only" option. Also ask how many GPUs (default 1).

4. **Ask for docker image** if not obvious. Default comes from config (`~/.claude/zombuul.yaml` or shipped defaults). Only ask if the user might want a different image.

5. **Create the pod** **in the background** (docker image, volume, and disk size default from config):
   - GPU: `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py create --name <name> --gpu "<gpu_type_id>" --gpu-count <n>`
   - CPU: `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py create --name <name> --cpu`
   - Add `--image "<image>"` only if the user specified a non-default image.
   Use $ARGUMENTS as the pod name if provided, otherwise default to "research". The script auto-detects the repo URL and branch from the current working directory, creates the pod, waits for SSH, extracts Claude Code credentials from Keychain, then SCPs and runs `pod_setup.sh`.

6. **SCP the project .env**: If a `.env` file exists in the current working directory, copy it to the pod:
   `scp -P <port> -i ~/.ssh/id_ed25519 .env root@<ip>:/workspace/repo/.env`

7. **Report to the user**:
   - SSH command: `ssh root@<ip> -p <port> -i ~/.ssh/id_ed25519`
   - The setup script is running in the background on the pod (clones repo, installs deps). Check `/var/log/pod_setup.log` on the pod for progress.
   - Once setup is done, run `source ~/.bash_profile && cd /workspace/repo && IS_SANDBOX=1 claude --dangerously-skip-permissions --effort high`.
   - If setup fails, don't debug individual steps — just re-run `pod_setup.sh`: `ssh ... "nohup bash /pod_setup.sh <repo_url> <branch> > /var/log/pod_setup.log 2>&1 &"`. It's idempotent (skips clone if repo exists).
   - They can run `/stop-runpod` to terminate the pod when done.
