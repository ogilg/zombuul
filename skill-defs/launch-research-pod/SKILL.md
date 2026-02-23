---
name: zombuul:launch-research-pod
description: >
  Spin up a RunPod GPU pod and launch a research loop on it.
  Argument $ARGUMENTS — path to experiment spec (e.g. experiments/content_orthogonal_gemma2base.md).
user-invocable: true
allowed-tools: Bash, AskUserQuestion, Write, Read, Edit
---

Spin up a RunPod GPU pod and launch an autonomous research loop on it.

## Process

1. **Check for uncommitted/unpushed changes relevant to this experiment**: The pod clones the repo from git, so local changes that aren't committed and pushed will be missing. Read the experiment spec first, then:
   - Identify which source files, configs, and modules the experiment depends on (e.g. referenced scripts, imported modules, config files).
   - Run `git status` and `git log @{u}.. --oneline` to find uncommitted changes and unpushed commits.
   - Filter to only the files relevant to this experiment. If any are dirty or unpushed, commit and push them automatically. Tell the user what you committed/pushed.
   - If none of the experiment-relevant files are affected, proceed silently.

2. **List available GPUs**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py gpus` and show the user the options.

3. **Ask the user two questions** using AskUserQuestion:
   - **GPU**: Which GPU they want. Offer 3-4 common options from the list plus an "Other" escape hatch.
   - **Mode**: Which research mode to use. Options: (a) "Single experiment (/launch-research-loop)" — runs one experiment and stops; (b) "Ralph mode (/launch-research-ralph)" — runs experiments in a loop, each building on the last, until the research goal is met.

4. **Sync gitignored data**: Read the experiment spec and check for references to data files (activations, embeddings, results, etc.) that are likely gitignored. Look for those files locally (follow symlinks). If any exist, ask the user which ones to sync to the pod using AskUserQuestion — list the files with their sizes as options (multiSelect). Sync the selected files after setup completes (step 5) using rsync.

5. **Create the pod**: Read the experiment spec and pick a short, descriptive pod name (2-3 words, kebab-case, e.g. `probe-generalization` or `steering-math`). Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py create --name "<pod_name>" --gpu "<gpu_type_id>"` **in the background** (docker image, volume, and disk size come from config — `~/.claude/zombuul.yaml` or defaults). Parse the SSH IP and port from the output (line like `SSH: ssh root@<IP> -p <PORT> ...`).

6. **Update SSH config**: After getting the IP and port, add a `Host runpod-<pod_name>` alias to `~/.ssh/config` (where `<pod_name>` is the pod name from step 5). Use the Edit tool to append this block to the end of the file:
     ```
     Host runpod-<pod_name>
         HostName <IP>
         User root
         Port <PORT>
         IdentityFile ~/.ssh/id_ed25519
         StrictHostKeyChecking no
     ```

7. **Wait for setup to complete**: Poll every 15 seconds by running `ssh runpod-<pod_name> bash -c 'grep -c "Setup complete" /var/log/pod_setup.log'`. Once it returns "1", setup is done. Show the last line of the log each poll for progress. Timeout after 15 minutes. If setup fails, **do not manually run individual steps** — just re-run `pod_setup.sh` on the pod: `ssh runpod-<pod_name> "nohup bash /pod_setup.sh <repo_url> <branch> <python_version> > /var/log/pod_setup.log 2>&1 &"`. The script is idempotent (skips clone if repo exists).

   **IMPORTANT — SSH exit codes**: RunPod pods often have terminal escape codes in their shell profile that cause SSH commands to return exit code 1 even when the command succeeded. Always wrap remote commands with `bash -c '...'` to get a clean exit code. For example: `ssh runpod-<pod_name> bash -c 'mkdir -p /workspace/repo/foo'` instead of `ssh runpod-<pod_name> "mkdir -p /workspace/repo/foo"`.

8. **Sync the experiment spec (REQUIRED)**: The spec file is often not committed/pushed. You MUST SCP it to the pod — never assume it exists from the git clone:
   - Create the parent directory: `ssh runpod-<pod_name> bash -c 'mkdir -p /workspace/repo/<spec_parent_dir>'`
   - Copy the spec: `scp <local_spec_path> runpod-<pod_name>:/workspace/repo/<spec_path>`

9. **Sync data**: Use rsync to sync directories the user selected in step 3. This avoids the nesting issues of `scp -r` and handles large transfers cleanly. Use this pattern:
   `rsync -az --no-owner --no-group <local_dir>/ runpod-<pod_name>:/workspace/repo/<remote_dir>/`
   Note the trailing slashes — this copies *contents* of `local_dir` into `remote_dir`. This can be done in parallel with .env copy.

10. **Copy .env**: If a `.env` file exists in the current working directory:
   `scp .env runpod-<pod_name>:/workspace/repo/.env`

11. **Launch the research loop**: Write a launch script locally, SCP it to the pod, then run it with `nohup`. Use the command the user chose in step 3 (`/launch-research-loop` or `/launch-research-ralph`). Pass the full path to the spec file (not `@` syntax):
   - Use the **Write tool** to create `/tmp/launch_research.sh` locally with this content (substitute the chosen command and spec path):
     ```
     source ~/.bash_profile
     cd /workspace/repo
     IS_SANDBOX=1 claude --dangerously-skip-permissions --effort high -p '/<chosen_command> <full_spec_path>'
     runpodctl stop pod $RUNPOD_POD_ID
     ```
   - SCP it to the pod: `scp /tmp/launch_research.sh runpod-<pod_name>:/tmp/launch_research.sh`
   - Launch with nohup: `ssh runpod-<pod_name> bash -c 'nohup bash /tmp/launch_research.sh > /workspace/research.log 2>&1 &'`

12. **Verify**: Check that the claude process is running: `ssh runpod-<pod_name> bash -c 'ps aux | grep claude | grep -v grep'`

13. **Report to user**:
   - The research loop is running on the pod.
   - SSH command: `ssh runpod-<pod_name>`
   - To watch progress: `tail -f /workspace/research.log`
   - The pod will auto-terminate after the research loop finishes. Run `/stop-runpod` to terminate early if needed.

14. **Friction check**: Before finishing, reflect on whether anything went wrong or was harder than expected during this command (SSH failures, RunPod API issues, wrong paths, pod setup errors, confusing instructions, etc.). If there was friction and `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` are set, post a short friction report to Slack for each issue:
   `curl -s -X POST -H "Authorization: Bearer $SLACK_BOT_TOKEN" -H 'Content-type: application/json' -d '{"channel": "'$SLACK_CHANNEL_ID'", "text": ":warning: *Friction report* (launch-research-pod)\n> <one-line summary>\n> *Severity*: minor/moderate/major\n> *Details*: <1-3 sentences>", "username": "friction-log", "icon_url": "https://dummyimage.com/48x48/ff6b6b/ff6b6b.png"}' https://slack.com/api/chat.postMessage`
   If nothing went wrong, skip this step.
