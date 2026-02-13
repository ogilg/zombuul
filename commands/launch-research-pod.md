---
description: Spin up a RunPod GPU pod and launch a research loop on it. Argument $ARGUMENTS — path to experiment spec (e.g. experiments/content_orthogonal_gemma2base.md).
allowed-tools: Bash, AskUserQuestion
---

Spin up a RunPod GPU pod and launch an autonomous research loop on it.

## Process

1. **List available GPUs**: Run `python /Users/oscargilg/Dev/zombuul/scripts/runpod_ctl.py gpus` and show the user the options.

2. **Ask the user two questions** using AskUserQuestion:
   - **GPU**: Which GPU they want. Offer 3-4 common options from the list plus an "Other" escape hatch.
   - **Mode**: Which research mode to use. Options: (a) "Single experiment (/launch-research-loop)" — runs one experiment and stops; (b) "Ralph mode (/launch-research-ralph)" — runs experiments in a loop, each building on the last, until the research goal is met.

3. **Sync gitignored data**: Read the experiment spec and check for references to data files (activations, embeddings, results, etc.) that are likely gitignored. Look for those files locally (follow symlinks). If any exist, ask the user which ones to SCP to the pod using AskUserQuestion — list the files with their sizes as options (multiSelect). SCP the selected files after setup completes (step 4), creating target directories on the pod first with `ssh ... "mkdir -p /workspace/repo/<dir>"`.

4. **Create the pod**: Run `python /Users/oscargilg/Dev/zombuul/scripts/runpod_ctl.py create --name "research" --gpu "<gpu_type_id>" --image "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"` **in the background**. Parse the SSH IP and port from the output (line like `SSH: ssh root@<IP> -p <PORT> ...`).

5. **Wait for setup to complete**: Poll every 15 seconds by running `ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no grep -c 'Setup complete' /var/log/pod_setup.log`. Once it returns "1", setup is done. Show the last line of the log each poll for progress. Timeout after 15 minutes. If something seems wrong, check the full log and debug.

6. **Sync data**: SCP the files the user selected in step 3. Create target directories first, then copy. This can be done in parallel with .env copy.

7. **Copy .env**: If a `.env` file exists in the current working directory:
   `scp -P <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no .env root@<IP>:/workspace/repo/.env`

8. **Launch the research loop**: To avoid quoting issues, write a launch script to the pod, then run it. Use the command the user chose in step 2 (`/launch-research-loop` or `/launch-research-ralph`):
   - Use `ssh` to write a script on the pod: `ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no "cat > /tmp/launch_research.sh << 'SCRIPT'\ncd /workspace/repo && claude --dangerously-skip-permissions --effort high -p '/<chosen_command> $ARGUMENTS'\nrunpodctl stop pod $RUNPOD_POD_ID\nSCRIPT"`
   - Then launch it in tmux as zombuul: `ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no "su - zombuul -c 'tmux new-session -d -s research \"bash /tmp/launch_research.sh\"'"`
   - If the tmux launch fails, debug and retry with adjusted commands. The goal is a detached tmux session named `research` running as `zombuul`.

9. **Verify**: Check that the tmux session is running: `ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no "su - zombuul -c 'tmux list-sessions'"`

10. **Report to user**:
   - The research loop is running in tmux session `research` on the pod.
   - SSH command: `ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519`
   - To watch progress: `su - zombuul -c 'tmux attach -t research'`
   - The pod will auto-terminate after the research loop finishes. Run `/stop-runpod` to terminate early if needed.
