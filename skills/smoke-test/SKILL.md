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

## Wait for parallel agents

Wait for A, B, C to complete. Capture their pass/fail results for the final summary; don't print yet — the E step still needs to run.

## E (experiment e2e, serial, in this session)

Run in the main session — subagents can't invoke skills recursively. Slow tail: ~5–8 min.

The test runs against `oscar-gilg/zombuul-smoke-bed` — never opens PRs on zombuul itself.

1. Save the current cwd. Clone `oscar-gilg/zombuul-smoke-bed` into a fresh tmp dir and cd in.
2. Invoke `Skill` with `skill="zombuul:run-experiment"`, `args="experiments/smoke_e2e/smoke_e2e_spec.md"`. Capture the PR number when run-experiment announces it.
3. Wait for it to return.
4. **Verify**: read `experiments/smoke_e2e/results.json` in the worktree. All must hold:
   - `no_nans == true`
   - `device` starts with `cuda`
   - `" dog"` is in `top3_token_strs` (canonical pangram completion — confirms the model knows English)
   - `ce_for_dog < 3.0` (random weights would give ~10.8; correct gpt-2 < 1.0)
   - `max_minus_mean > 5.0` (confident prediction, not flat distribution)
   - `entropy` in `[0.5, 5.0]` (no delta, no uniform)

   Also confirm the captured PR is no longer draft: `gh pr view <num> --repo oscar-gilg/zombuul-smoke-bed --json isDraft -q .isDraft` returns `false`.
5. **Always run cleanup, even if verification failed.** Idempotent:
   - `gh pr close <num> --repo oscar-gilg/zombuul-smoke-bed`.
   - `git push origin --delete <branch>` from inside the clone.
   - `ExitWorktree`.
   - `python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py terminate <pod_id> --yes`. Get pod_id from the experiment's running_log.
6. Return to the saved cwd and remove the tmp dir.

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
