---
name: zombuul:launch-research-pod
description: >
  Spin up a RunPod GPU pod and launch a research loop on it.
  Argument $ARGUMENTS — path to experiment spec (e.g. experiments/content_orthogonal_gemma2base.md).
user-invocable: true
allowed-tools: Bash, AskUserQuestion, Write, Read, Edit, Task
---

Spin up a RunPod GPU pod and launch an autonomous research loop on it.

## Process

1. **Parallel recon**: Launch steps 1a, 1b, and 1c in parallel (three Task tool calls in a single message):

   **1a. Check for dirty/unpushed experiment dependencies** (Task, subagent_type=Explore): "Read the experiment spec at <spec_path>. Identify all referenced source modules, configs, and scripts. Then run `git status --porcelain` and `git log @{u}.. --name-only` and report which dirty or unpushed files are relevant to this experiment. Also suggest a short pod name (2-3 words, kebab-case) based on the experiment title."

   **1b. Find gitignored data to sync** (Task, subagent_type=Explore): "Read the experiment spec at <spec_path>. Find all referenced data file paths (activations .npz, embeddings, topics .json, results directories, configs). Check which exist locally (follow symlinks) and report each with its size (`du -sh`). These are likely gitignored and will need syncing to the pod."

   **1c. List GPUs**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py gpus` (Bash tool, runs concurrently with the subagents).

2. **Act on recon results**: Once all three return:
   - If 1a found relevant dirty/unpushed files, commit and push them. Tell the user what you committed/pushed.
   - Use the GPU list from 1c and the data inventory from 1b to ask the user **three questions** in a single AskUserQuestion:
     - **GPU**: Which GPU they want. Offer 3-4 common options from the GPU list. Mention VRAM requirements from the spec if apparent.
     - **Mode**: (a) "Single experiment (/zombuul:launch-research-loop)" — runs one experiment and stops; (b) "Ralph mode (/zombuul:launch-research-ralph)" — iterates until the research goal is met.
     - **Data to sync**: Which data directories to sync (multiSelect), listed with sizes from 1b.

3. **Create the pod**: Use the pod name suggested by 1a (or pick one if it didn't). Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py create --name "<pod_name>" --gpu "<gpu_type_id>"` **in the background** (docker image, volume, and disk size come from config — `~/.claude/zombuul.yaml` or defaults). Parse the SSH IP and port from the output (line like `SSH: ssh root@<IP> -p <PORT> ...`).

4. **Update SSH config**: After getting the IP and port, add a `Host runpod-<pod_name>` alias to `~/.ssh/config` (where `<pod_name>` is the pod name from step 3). Use the Edit tool to append this block to the end of the file:
     ```
     Host runpod-<pod_name>
         HostName <IP>
         User root
         Port <PORT>
         IdentityFile ~/.ssh/id_ed25519
         StrictHostKeyChecking no
     ```

5. **Wait for setup + sync data in parallel**: Launch these concurrently — SSH is available before setup finishes, so data transfer overlaps with package installation. Use `run_in_background` for all of them, then wait for all to complete before proceeding.

   - **Wait for setup** (background): `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py wait-setup <pod_id>` (use pod ID from step 3). If setup fails, **do not manually run individual steps** — just re-run `pod_setup.sh` on the pod (it's idempotent).
   - **Sync experiment spec** (background, REQUIRED — the spec is often not committed/pushed):
     `ssh runpod-<pod_name> 'mkdir -p /workspace/repo/<spec_parent_dir>' && rsync -az --no-owner --no-group <local_spec_path> runpod-<pod_name>:/workspace/repo/<spec_path>`
   - **Sync data directories** (background, one per directory from step 2):
     `rsync -az --no-owner --no-group <local_dir>/ runpod-<pod_name>:/workspace/repo/<remote_dir>/`
     Note the trailing slashes — this copies *contents* of `local_dir` into `remote_dir`.
   - **Sync .env** (background, if `.env` exists in working directory):
     `rsync -az --no-owner --no-group .env runpod-<pod_name>:/workspace/repo/.env`

   **Background processes on the pod** — all four pieces required (`nohup`, `</dev/null`, `&`, `disown`):
   ```
   ssh runpod-<pod_name> 'nohup bash /path/to/script.sh </dev/null > /var/log/output.log 2>&1 & disown'
   ```

6. **Launch the research loop**: Write a launch script locally, SCP it to the pod, then run it as a background process. Use the command the user chose in step 2 (`/zombuul:launch-research-loop` or `/zombuul:launch-research-ralph`). Pass the full path to the spec file (not `@` syntax):
   - Use the **Write tool** to create `/tmp/launch_research.sh` locally with this content (substitute the chosen command and spec path):
     ```
     source ~/.bash_profile
     cd /workspace/repo
     IS_SANDBOX=1 claude --dangerously-skip-permissions --effort high -p '/<chosen_command> <full_spec_path>'
     runpodctl stop pod $RUNPOD_POD_ID
     ```
   - Copy it to the pod: `rsync -az --no-owner --no-group /tmp/launch_research.sh runpod-<pod_name>:/tmp/launch_research.sh`
   - Launch as background process: `ssh runpod-<pod_name> 'nohup bash /tmp/launch_research.sh </dev/null > /workspace/research.log 2>&1 & disown'`

7. **Verify**: Check that the claude process is running: `ssh runpod-<pod_name> 'ps aux | grep claude | grep -v grep'`

8. **Report to user**:
   - The research loop is running on the pod.
   - SSH command: `ssh runpod-<pod_name>`
   - To watch progress: `tail -f /workspace/research.log`
   - The pod will auto-terminate after the research loop finishes. Run `/zombuul:stop-runpod` to terminate early if needed.

9. **Friction check**: If anything went wrong or was harder than expected and Slack is configured, post a friction report: `{"channel": "$SLACK_CHANNEL_ID", "text": ":warning: *Friction report* (launch-research-pod)\n> <summary>\n> *Severity*: minor/moderate/major\n> *Details*: <1-3 sentences>", "username": "friction-log", "icon_url": "https://dummyimage.com/48x48/ff6b6b/ff6b6b.png"}`. Skip if nothing went wrong.
