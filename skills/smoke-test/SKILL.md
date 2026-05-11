---
name: zombuul:smoke-test
description: >
  End-to-end smoke test of zombuul. Pre-flight, then 3 parallel agents (API, pod list,
  full pod lifecycle), then a serial e2e step that runs /zombuul:run-experiment on a
  tiny canned spec to exercise the orchestration + PR flow. Use before publishing a
  release. Takes ~10–15 minutes and costs roughly $0.10 in RunPod GPU time.
user-invocable: true
allowed-tools: Bash, Agent, Read, Skill
---

Run a pre-release smoke test of zombuul. Goal: confirm the basic plumbing (API key, scripts, pod lifecycle) still works end-to-end before shipping to other users. Not a substitute for real testing — but catches the obvious "everything is broken" cases in under 10 minutes.

## Pre-flight (serial, fast)

Run these checks before launching anything. Abort with a clear message if any fail.

1. **API key present**: Check that `RUNPOD_API_KEY` is set in either `.env` (in the current working directory) or `~/.claude/.env`.
   - If missing: stop. Tell the user to run `/zombuul:setup` first.

2. **Scripts importable**: Run `${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py --help` and confirm exit code 0.
   - If non-zero: stop. The likely cause is a missing `runpod` Python package or a broken script. Tell the user to re-run `/zombuul:setup`.

3. **SSH key present**: Read `ssh_key` path from `~/.claude/zombuul.yaml` (default `~/.ssh/id_ed25519`). Confirm the file exists.
   - If missing: stop. Tell the user to run `/zombuul:setup`.

If all three pass, announce that smoke test is starting and report the unique smoke-test pod name you'll use (e.g., `smoke-<unix_timestamp>`).

## Parallel agents

Spawn three subagents in parallel using the Agent tool (`subagent_type="general-purpose"`, `run_in_background=true`). Each agent gets a self-contained prompt with the exact bash commands and pass criterion below. **Do not have agents invoke any `/zombuul:*` slash command** — they call `runpod_ctl.py` directly. This isolates the smoke test from skill orchestration logic.

### Agent A — API connectivity

Prompt:

> Run `${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py gpus` and capture stdout.
>
> **Pass criterion**: command exits 0 AND the output lists at least one GPU type (look for substring patterns like "RTX" or "A100" or "H100" or a non-empty line that looks like a GPU id).
>
> Report a single-line result: `A (API) PASS — <one-sentence summary>` or `A (API) FAIL — <reason>` with the command output included if it failed.

### Agent B — Pod listing

Prompt:

> Run `${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py list` and capture stdout.
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
> 1. Read `~/.claude/zombuul.yaml` for default GPU type. If a `gpu_type` field is set, use it. Otherwise default to `NVIDIA RTX A4000` — any cheap GPU works, we just need a CUDA device. If create fails with `no instances available`, retry once with `NVIDIA RTX A5000`.
>
> 2. Create the pod:
>    `${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py create --name <smoke_pod_name> --gpu <gpu_type>`.
>    Capture the pod_id from the output.
>
> 3. Wait for setup:
>    `${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py wait-setup <pod_id> --timeout 600`.
>
> 4. Run the GPU sanity check over SSH:
>    `ssh runpod-<smoke_pod_name> 'nvidia-smi --query-gpu=name --format=csv,noheader'`.
>    Capture the output.
>
> 5. Pause the pod:
>    `${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py pause <pod_id>`.
>
> **Pass criterion**: step 4 returns a non-empty GPU name AND step 5 exits 0.
>
> **Cleanup on failure**: if any step fails, attempt `${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py pause <pod_id>` (idempotent — pause is safe even mid-setup). If pause also fails, attempt `${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py terminate <pod_id> --yes`. Report any leaked pods in the failure message.
>
> Report a single-line result: `C (pod e2e) PASS — <gpu_name>, paused as <smoke_pod_name>` or `C (pod e2e) FAIL — <step> — <reason>`. Include any leaked-pod warning.

## Wait for parallel agents

Wait for A, B, C to complete. Capture their pass/fail results for the final summary; don't print yet — the E step still needs to run.

## E (experiment e2e, serial, in this session)

Run in the main session — subagents can't invoke skills recursively. Slow tail: ~5–8 min.

The test runs against `oscar-gilg/zombuul-smoke-bed` — never opens PRs on zombuul itself.

**Adaptation notes** (smoke-test specific — these are NOT how a real experiment would run):

- The Claude Code session's cwd is fixed to the user's dev repo (e.g. `~/Dev/zombuul`), not the smoke-bed clone. `EnterWorktree` operates on the session's git repo and would create a worktree of zombuul, not smoke-bed.
- So: clone smoke-bed to a fixed absolute path (`/tmp/zombuul-smoke/zombuul-smoke-bed`), **skip `EnterWorktree`** (the clone is already an isolated workspace), and chain `cd /tmp/zombuul-smoke/zombuul-smoke-bed && ...` in every Bash call (cwd doesn't persist between Bash calls). Pass an **absolute spec path** to `/zombuul:run-experiment`.
- When `/zombuul:run-experiment` tells you to use `EnterWorktree`, ignore it and work directly in the clone.
- `pod_setup.sh` on the pod will clone the user's dev repo (it reads the caller's cwd git origin). That's fine here: the smoke test never reads the cloned repo on the pod, it just `scp`s `scripts/$NAME/forward.py` over.

Steps:

1. Clone `oscar-gilg/zombuul-smoke-bed` to `/tmp/zombuul-smoke/zombuul-smoke-bed` (delete any existing path first).
2. Rename the experiment dir to include a timestamp so each run has a unique branch/PR on the fixture repo:
   ```
   cd /tmp/zombuul-smoke/zombuul-smoke-bed
   NAME=smoke_e2e_$(date +%Y%m%d_%H%M%S)
   mv experiments/smoke_e2e experiments/$NAME
   mv experiments/$NAME/smoke_e2e_spec.md experiments/$NAME/${NAME}_spec.md
   ```
3. Invoke `Skill` with `skill="zombuul:run-experiment"`, `args="/tmp/zombuul-smoke/zombuul-smoke-bed/experiments/$NAME/${NAME}_spec.md"` (absolute path). Capture the PR number when run-experiment announces it.
4. Wait for it to return.
5. **Verify**: `cd /tmp/zombuul-smoke/zombuul-smoke-bed && experiments/$NAME/verify.py experiments/$NAME/results.json`. Exit 0 = pass. The thresholds and assertions live in that script — do not re-implement them here. Also confirm the captured PR is no longer draft: `gh pr view <num> --repo oscar-gilg/zombuul-smoke-bed --json isDraft -q .isDraft` returns `false`.
6. **Always run cleanup, even if verification failed.** Idempotent:
   - `gh pr close <num> --repo oscar-gilg/zombuul-smoke-bed`.
   - `cd /tmp/zombuul-smoke/zombuul-smoke-bed && git push origin --delete <branch>`.
   - `${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py terminate <pod_id> --yes`. Get pod_id from the experiment's running_log.
7. `rm -rf /tmp/zombuul-smoke`.

**Pass criterion**: results.json verifies AND PR was opened+marked-ready AND cleanup succeeded.

## Final report

Print:

```
Zombuul smoke test results:
  A (API)      PASS/FAIL — ...
  B (list)     PASS/FAIL — ...
  C (pod e2e)  PASS/FAIL — ...
  E (experiment e2e)  PASS/FAIL — ...

Overall: PASS/FAIL
```

If any step looks like a zombuul bug (not user-environment), follow `${CLAUDE_PLUGIN_ROOT}/REPORTING_BUGS.md` before ending.

If anything was leaked (pod still running, PR still open, branch still on origin), call it out explicitly with the cleanup commands so the user can finish manually.
