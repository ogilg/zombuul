---
name: zombuul:provision-pod
description: >
  Provision a RunPod pod: wait for setup, configure SSH, sync .env and data.
  Argument $ARGUMENTS — JSON with keys: pod_id, pod_name, ip, port, and optionally spec_path and data_dirs.
user-invocable: true
allowed-tools: Bash, AskUserQuestion, Read, Agent
---

Provision a RunPod pod after creation. Handles SSH config, waits for setup to complete, and syncs project files.

## Arguments

`$ARGUMENTS` is a JSON string with these keys:

| Key | Required | Description |
|-----|----------|-------------|
| `pod_id` | yes | RunPod pod ID |
| `pod_name` | yes | Pod name (used for SSH alias) |
| `ip` | yes | SSH IP address |
| `port` | yes | SSH port |
| `spec_path` | no | Experiment spec path (triggers spec sync; triggers data recon if `data_dirs` absent) |
| `data_dirs` | no | Explicit list of local directories to sync (skips recon) |

## Process

1. **Parse arguments**: Parse the JSON from `$ARGUMENTS`. Validate that `pod_id`, `pod_name`, `ip`, and `port` are present.

2. **SSH alias**: the `Host runpod-<pod_name>` alias is already written to `~/.ssh/config` by `runpod_ctl.py create` (called from `/zombuul:launch-runpod`). Verify with `ssh -o ConnectTimeout=5 runpod-<pod_name> 'echo ok'`. If the alias is missing or stale (rare — happens when the pod was created outside zombuul, or its IP/port changed after a manual pause/resume), run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py refresh-ssh <pod_name>` to refresh it.

3. **Phase A — concurrent setup + early sync**: Launch all of the following concurrently using `run_in_background`, then wait for ALL to complete before proceeding to Phase B:

   - **Wait for setup**: `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py wait-setup <pod_id>` — polls until pod setup is done. If setup fails, re-run `pod_setup.sh` (it's idempotent).
   - **Sync .env to /tmp** (if `.env` exists in current working directory): `scp .env runpod-<pod_name>:/tmp/.env` — this is safe before repo clone completes since `/tmp` always exists.
   - **Data recon** (if `spec_path` is provided but `data_dirs` is NOT): Launch an Explore agent: "Read the experiment spec at <spec_path>. Find all referenced data file paths (activations .npz, embeddings, topics .json, results directories, configs). Check which exist locally (follow symlinks) and report each with its size (`du -sh`). These are likely gitignored and will need syncing to the pod." Once the agent returns, ask the user via AskUserQuestion (multiSelect) which data directories to sync, listed with sizes. Use the user's selection as `data_dirs` for Phase B.

4. **Phase B — sync to repo** (only after Phase A completes, so `/workspace/repo/` exists):

   Launch all of the following concurrently using `run_in_background`, then wait for all to complete:

   - **Sync .env to repo** (if `.env` exists in current working directory): `rsync -az --no-owner --no-group .env runpod-<pod_name>:/workspace/repo/.env`
   - **Sync experiment spec** (if `spec_path` provided): `ssh runpod-<pod_name> 'mkdir -p /workspace/repo/<spec_parent_dir>' && rsync -az --no-owner --no-group <spec_path> runpod-<pod_name>:/workspace/repo/<spec_path>`
   - **Sync data directories** (one per directory from `data_dirs`): `rsync -az --no-owner --no-group <local_dir>/ runpod-<pod_name>:/workspace/repo/<remote_dir>/` — note trailing slashes to copy contents.

5. **Report**: Once all background tasks complete, report:
   - SSH command: `ssh runpod-<pod_name>`
   - What was synced (list .env, spec, data dirs as applicable)
   - Setup status (success or failure with instructions to check `/var/log/pod_setup.log`)

## Note on `/workspace` capacity

The pod's `/workspace` lives on a MooseFS network volume with a hidden per-user quota. `df` reports the full pool (often tens of TB) but writes fail well before that. If an experiment needs to download large model weights, keep them off `/workspace` — `pod_setup.sh` already points `HF_HOME` at `/opt/hf_cache` on container disk for this reason. Flag to the user if the spec implies large writes to `/workspace`.

Flip side: pause preserves `/workspace/` but wipes container disk. The two filesystems have opposite tradeoffs — experiment outputs that must survive pause belong on `/workspace/`; caches and venvs belong on container disk.

## Report zombuul bugs

If anything went wrong this session that zombuul could plausibly have done better, follow `${CLAUDE_PLUGIN_ROOT}/REPORTING_BUGS.md` before ending.
