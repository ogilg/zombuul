---
name: zombuul:smoke-test
description: >
  End-to-end smoke test of zombuul. Runs pre-flight checks, then spawns 3 parallel
  agents that exercise API connectivity, pod listing, and full pod lifecycle (launch,
  SSH, GPU sanity check, pause). Use before publishing a release. Takes ~5–10 minutes
  and costs roughly $0.05 in RunPod GPU time.
user-invocable: true
allowed-tools: Bash, Agent, Read
---

Run a pre-release smoke test of zombuul. Goal: confirm the basic plumbing (API key, scripts, pod lifecycle) still works end-to-end before shipping to other users. Not a substitute for real testing — but catches the obvious "everything is broken" cases in under 10 minutes.

## Pre-flight (serial, fast)

Run these checks before launching anything. Abort with a clear message if any fail.

1. **API key present**: Check that `RUNPOD_API_KEY` is set in either `.env` (in the current working directory) or `~/.claude/.env`.
   - If missing: stop. Tell the user to run `/zombuul:setup` first.

2. **Scripts importable**: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py --help` and confirm exit code 0.
   - If non-zero: stop. The likely cause is a missing `runpod` Python package or a broken script. Tell the user to re-run `/zombuul:setup`.

3. **SSH key present**: Read `ssh_key` path from `~/.claude/zombuul.yaml` (default `~/.ssh/id_ed25519`). Confirm the file exists.
   - If missing: stop. Tell the user to run `/zombuul:setup`.

If all three pass, announce that smoke test is starting and report the unique smoke-test pod name you'll use (e.g., `smoke-<unix_timestamp>`).

## Parallel agents

Spawn three subagents in parallel using the Agent tool (`subagent_type="general-purpose"`, `run_in_background=true`). Each agent gets a self-contained prompt with the exact bash commands and pass criterion below. **Do not have agents invoke any `/zombuul:*` slash command** — they call `runpod_ctl.py` directly. This isolates the smoke test from skill orchestration logic.

### Agent A — API connectivity

Prompt:

> Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py gpus` and capture stdout.
>
> **Pass criterion**: command exits 0 AND the output lists at least one GPU type (look for substring patterns like "RTX" or "A100" or "H100" or a non-empty line that looks like a GPU id).
>
> Report a single-line result: `A (API) PASS — <one-sentence summary>` or `A (API) FAIL — <reason>` with the command output included if it failed.

### Agent B — Pod listing

Prompt:

> Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py list` and capture stdout.
>
> **Pass criterion**: command exits 0. Output is allowed to say "no pods running" or list pods — either is fine.
>
> Report a single-line result: `B (list) PASS — <count> pods` or `B (list) FAIL — <reason>` with the command output included if it failed.

### Agent C — Full pod lifecycle (GPU)

Prompt:

> You are running a full pod lifecycle smoke test. Use the unique pod name `<smoke_pod_name>` (passed in below). Do NOT reuse an existing pod.
>
> **Steps:**
>
> 1. Read `~/.claude/zombuul.yaml` for default GPU type. If a `gpu_type` field is set, use it. Otherwise call `runpod_ctl.py gpus` and pick the cheapest GPU type (lowest `$/hr`).
>
> 2. Create the pod:
>    `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py create --name <smoke_pod_name> --gpu <gpu_type>`.
>    Capture the pod_id from the output.
>
> 3. Wait for setup:
>    `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py wait-setup <pod_id> --timeout 600`.
>
> 4. Run the GPU sanity check over SSH:
>    `ssh runpod-<smoke_pod_name> 'nvidia-smi --query-gpu=name --format=csv,noheader'`.
>    Capture the output.
>
> 5. Pause the pod:
>    `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py pause <pod_id>`.
>
> **Pass criterion**: step 4 returns a non-empty GPU name AND step 5 exits 0.
>
> **Cleanup on failure**: if any step fails, attempt `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py pause <pod_id>` (idempotent — pause is safe even mid-setup). If pause also fails, attempt `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py terminate <pod_id> --yes`. Report any leaked pods in the failure message.
>
> Report a single-line result: `C (pod e2e) PASS — <gpu_name>, paused as <smoke_pod_name>` or `C (pod e2e) FAIL — <step> — <reason>`. Include any leaked-pod warning.

## Wait, then report

Wait for all three agents to complete. Print a summary block:

```
Zombuul smoke test results:
  A (API)      PASS/FAIL — ...
  B (list)     PASS/FAIL — ...
  C (pod e2e)  PASS/FAIL — ...

Overall: PASS/FAIL
```

If any test failed AND the failure looks like a zombuul bug (not a user-environment issue), follow `${CLAUDE_PLUGIN_ROOT}/REPORTING_BUGS.md` to file an issue before ending.

If C left a pod running (cleanup couldn't pause it), call this out loudly in the final report so the user can terminate it manually.
