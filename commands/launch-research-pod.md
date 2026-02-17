---
description: Spin up a RunPod GPU pod and launch a research loop on it. Argument $ARGUMENTS — path to experiment spec (e.g. experiments/content_orthogonal_gemma2base.md).
allowed-tools: Bash, AskUserQuestion
---

Spin up a RunPod GPU pod and launch an autonomous research loop on it.

## Process

1. **List available GPUs**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py gpus` and show the user the options.

2. **Ask the user two questions** using AskUserQuestion:
   - **GPU**: Which GPU they want. Offer 3-4 common options from the list plus an "Other" escape hatch.
   - **Mode**: Which research mode to use. Options: (a) "Single experiment (/launch-research-loop)" — runs one experiment and stops; (b) "Ralph mode (/launch-research-ralph)" — runs experiments in a loop, each building on the last, until the research goal is met.

3. **Sync gitignored data**: Read the experiment spec and check for references to data files (activations, embeddings, results, etc.) that are likely gitignored. Look for those files locally (follow symlinks). If any exist, ask the user which ones to SCP to the pod using AskUserQuestion — list the files with their sizes as options (multiSelect). SCP the selected files after setup completes (step 4), creating target directories on the pod first with `ssh ... "mkdir -p /workspace/repo/<dir>"`.

4. **Create the pod**: Read the experiment spec and pick a short, descriptive pod name (2-3 words, kebab-case, e.g. `probe-generalization` or `steering-math`). Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py create --name "<pod_name>" --gpu "<gpu_type_id>" --image "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"` **in the background**. Parse the SSH IP and port from the output (line like `SSH: ssh root@<IP> -p <PORT> ...`).

5. **Wait for setup to complete**: Poll every 15 seconds by running `ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no grep -c 'Setup complete' /var/log/pod_setup.log`. Once it returns "1", setup is done. Show the last line of the log each poll for progress. Timeout after 15 minutes. If something seems wrong, check the full log and debug.

6. **Sync the experiment spec**: The spec file may not be committed/pushed yet. Always SCP it to the pod to guarantee it exists:
   - Create the parent directory: `ssh ... "mkdir -p /workspace/repo/<spec_parent_dir>"`
   - Copy the spec: `scp -P <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no <local_spec_path> root@<IP>:/workspace/repo/<spec_path>`

7. **Sync data**: SCP the files the user selected in step 3. Create target directories first, then copy. This can be done in parallel with .env copy.

8. **Copy .env**: If a `.env` file exists in the current working directory:
   `scp -P <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no .env root@<IP>:/workspace/repo/.env`

9. **Launch the research loop**: To avoid quoting issues, write a launch script to the pod, then run it. Use the command the user chose in step 2 (`/launch-research-loop` or `/launch-research-ralph`):
   - Use `ssh` to write a script on the pod. The script must set git config from `.env` (since `.env` was SCP'd after pod_setup.sh ran): `ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no "cat > /tmp/launch_research.sh << 'SCRIPT'\nsource ~/.bash_profile && cd /workspace/repo && if [ -f .env ]; then git config --global user.name \"$(grep '^GIT_USER_NAME=' .env | cut -d= -f2-)\"; git config --global user.email \"$(grep '^GIT_USER_EMAIL=' .env | cut -d= -f2-)\"; fi && IS_SANDBOX=1 claude --dangerously-skip-permissions --effort high -p '/<chosen_command> $ARGUMENTS'\nrunpodctl stop pod $RUNPOD_POD_ID\nSCRIPT"`
   - Then launch it in tmux: `ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no "tmux new-session -d -s research 'bash /tmp/launch_research.sh'"`
   - If the tmux launch fails, debug and retry with adjusted commands. The goal is a detached tmux session named `research`.

10. **Verify**: Check that the tmux session is running: `ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no "tmux list-sessions"`

11. **Report to user**:
   - The research loop is running in tmux session `research` on the pod.
   - SSH command: `ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519`
   - To watch progress: `tmux attach -t research`
   - The pod will auto-terminate after the research loop finishes. Run `/stop-runpod` to terminate early if needed.
