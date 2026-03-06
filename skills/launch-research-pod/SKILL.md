---
name: zombuul:launch-research-pod
description: >
  Spin up a RunPod GPU pod and launch a research loop on it.
  Argument $ARGUMENTS — path to experiment spec (e.g. experiments/content_orthogonal_gemma2base.md).
user-invocable: true
allowed-tools: Bash, AskUserQuestion, Write, Read, Edit, Agent, Skill
---

Spin up a RunPod GPU pod and launch an autonomous research loop on it.

## Process

1. **Parallel recon**: Launch steps 1a, 1b, and 1c in parallel (three Agent tool calls in a single message):

   **1a. Check for dirty/unpushed experiment dependencies** (Agent, subagent_type=Explore): "Read the experiment spec at <spec_path>. Identify all referenced source modules, configs, and scripts. Then run `git status --porcelain` and `git log @{u}.. --name-only` and report which dirty or unpushed files are relevant to this experiment. Also suggest a short pod name (2-3 words, kebab-case) based on the experiment title."

   **1b. Find gitignored data to sync** (Agent, subagent_type=Explore): "Read the experiment spec at <spec_path>. Find all referenced data file paths (activations .npz, embeddings, topics .json, results directories, configs). Check which exist locally (follow symlinks) and report each with its size (`du -sh`). These are likely gitignored and will need syncing to the pod."

   **1c. List GPUs**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py gpus` (Bash tool, runs concurrently with the subagents).

2. **Act on recon results**: Once all three return:
   - If 1a found relevant dirty/unpushed files, commit and push them. Tell the user what you committed/pushed.
   - Use the GPU list from 1c and the data inventory from 1b to ask the user **three questions** in a single AskUserQuestion:
     - **GPU**: Which GPU they want. Offer 3-4 common options from the GPU list. Mention VRAM requirements from the spec if apparent.
     - **Mode**: (a) "Single experiment (/zombuul:launch-research-loop)" — runs one experiment and stops; (b) "Ralph mode (/zombuul:launch-research-ralph)" — iterates until the research goal is met.
     - **Data to sync**: Which data directories to sync (multiSelect), listed with sizes from 1b.

3. **Create the pod**: Use the pod name suggested by 1a (or pick one if it didn't). Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py create --name "<pod_name>" --gpu "<gpu_type_id>"` **in the background** (docker image, volume, and disk size come from config — `~/.claude/zombuul.yaml` or defaults). Parse the SSH IP and port from the output (line like `SSH: ssh root@<IP> -p <PORT> ...`), and the pod ID.

4. **Provision the pod**: Invoke `/zombuul:provision-pod` with JSON arguments: `{"pod_id": "<pod_id>", "pod_name": "<pod_name>", "ip": "<ip>", "port": "<port>", "spec_path": "<spec_path>", "data_dirs": [<dirs from step 2>]}`. The provision skill handles SSH config, wait-setup, .env sync, spec sync, and data directory sync. Wait for it to complete before proceeding.

5. **Launch the research loop**: Write a launch script locally, SCP it to the pod, then run it as a background process. Use the command the user chose in step 2 (`/zombuul:launch-research-loop` or `/zombuul:launch-research-ralph`). Pass the full path to the spec file (not `@` syntax):
   - Use the **Write tool** to create `/tmp/launch_research.sh` locally with this content (substitute the chosen command and spec path):
     ```
     source ~/.bash_profile
     cd /workspace/repo
     IS_SANDBOX=1 claude --dangerously-skip-permissions --effort high -p '/<chosen_command> <full_spec_path>'
     curl -s -H "Content-Type: application/json" -d "{\"query\": \"mutation { podStop(input: {podId: \\\"$RUNPOD_POD_ID\\\"}) { id desiredStatus } }\"}" "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY"
     ```
   - Copy it to the pod: `rsync -az --no-owner --no-group /tmp/launch_research.sh runpod-<pod_name>:/tmp/launch_research.sh`
   - Launch as background process: `ssh runpod-<pod_name> 'nohup bash /tmp/launch_research.sh </dev/null > /workspace/research.log 2>&1 & disown'`

6. **Verify**: Check that the claude process is running: `ssh runpod-<pod_name> 'ps aux | grep claude | grep -v grep'`

7. **Report to user**:
   - The research loop is running on the pod.
   - SSH command: `ssh runpod-<pod_name>`
   - To watch progress: `tail -f /workspace/research.log`
   - The pod will auto-pause after the research loop finishes (GPU billing stops, disk preserved). Run `/zombuul:pause-runpod` to pause early, or `/zombuul:stop-runpod` to terminate and delete.

8. **Friction check**: If anything went wrong or was harder than expected and Slack is configured, post a friction report: `{"channel": "$SLACK_CHANNEL_ID", "text": ":warning: *Friction report* (launch-research-pod)\n> <summary>\n> *Severity*: minor/moderate/major\n> *Details*: <1-3 sentences>", "username": "friction-log", "icon_url": "https://dummyimage.com/48x48/ff6b6b/ff6b6b.png"}`. Skip if nothing went wrong.
