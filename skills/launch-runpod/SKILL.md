---
name: zombuul:launch-runpod
description: >
  Spin up a RunPod GPU pod. Argument $ARGUMENTS — optional pod name, optionally
  followed by `--remote` to install Claude Code + zombuul plugin on the pod
  (needed when the pod itself will run an agent, not just receive SSH commands).
argument-hint: "[pod-name] [--remote] [--disk-gb N] [--volume-gb N] [--extras LIST]"
user-invocable: true
allowed-tools: Bash, AskUserQuestion, Read, Edit, Skill
---

Spin up a RunPod GPU pod interactively.

## Arguments

`$ARGUMENTS` is a whitespace-separated list: `[pod_name] [--remote] [--disk-gb N] [--volume-gb N] [--extras LIST]`.

- `pod_name` (optional): short kebab-case pod name. Default `research`.
- `--remote` (optional flag): if present, pass `--install-claude` to the create command. This installs Claude Code and the zombuul plugin on the pod so an agent can run *inside* the pod (used by `/zombuul:run-experiment <spec> --remote`). Omit for the default case where your local Claude drives the pod over SSH.
- `--disk-gb N` (optional): container disk (local NVMe; HF cache, venv, regenerable intermediates). **WIPED on pause/resume** — do not store persistent experiment outputs here. Default 100 from config; size up for larger models.
- `--volume-gb N` (optional): network volume (MooseFS; durable outputs that survive pause). Default 50 from config. Has a hidden per-user quota — keep small unless the experiment specifically needs it.
- `--extras LIST` (optional): `[project.optional-dependencies]` groups to install. Default `auto` installs all declared groups; pass `none` or a comma-separated list (e.g. `dev,viz,gpu`) when groups are mutually exclusive (unsloth vs vllm) or have unresolvable pins on this hardware. Failure is recoverable post-setup with `uv pip install -e ".[<list>]"`.

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

5. **Create the pod** **in the background** (docker image defaults from config; disk/volume come from flags or config):
   - GPU: `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py create --name <name> --gpu "<gpu_type_id>" --gpu-count <n>`
   - CPU: `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py create --name <name> --cpu`
   - Add `--image "<image>"` only if the user specified a non-default image.
   - Add `--install-claude` if the caller passed `--remote` in `$ARGUMENTS`.
   - Add `--disk-gb <N>` if the caller passed `--disk-gb` in `$ARGUMENTS`; same for `--volume-gb`. Omit both flags to fall back to config defaults.
   - Add `--extras <LIST>` if the caller passed `--extras` in `$ARGUMENTS`; otherwise omit (defaults to `auto` server-side, which installs every declared group).
   Use the pod name from $ARGUMENTS if provided, otherwise default to "research". The script auto-detects the repo URL and branch from the current working directory, creates the pod, waits for SSH, and SCPs `pod_setup.sh`. Claude Code credentials are only copied and installed when `--install-claude` is set.

6. **Ask about provisioning**: After getting the pod ID, IP, and port from the create output, ask the user via AskUserQuestion:
   - **"Provision pod"** (Recommended) — waits for setup to complete, configures SSH alias, syncs .env
   - **"Raw pod"** — just prints SSH info, no provisioning

   If the user chooses **Provision**: invoke `/zombuul:provision-pod` with JSON arguments: `{"pod_id": "<pod_id>", "pod_name": "<name>", "ip": "<ip>", "port": "<port>"}`. The provision skill handles SSH config, wait-setup, and .env sync.

   If the user chooses **Raw pod**: report to the user:
   - SSH command: `ssh root@<ip> -p <port> -i <ssh_key from config>`
   - The setup script is running in the background on the pod (clones repo, installs deps). Check `/var/log/pod_setup.log` on the pod for progress.
   - If setup fails, don't debug individual steps — just re-run `pod_setup.sh`: `ssh runpod-<name> 'nohup bash /pod_setup.sh <repo_url> <branch> </dev/null > /var/log/pod_setup.log 2>&1 & disown'`. It's idempotent (skips clone if repo exists).
   - They can run `/zombuul:pause-runpod` to pause the pod when done (GPU billing stops, disk preserved).

## Report zombuul bugs

If anything went wrong this session that zombuul could plausibly have done better, follow `${CLAUDE_PLUGIN_ROOT}/REPORTING_BUGS.md` before ending.
