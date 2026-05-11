---
name: zombuul:setup
description: >
  Interactive onboarding for zombuul. Walks through prerequisites, API keys,
  .env creation, and verifies everything works. Run this after installing the plugin.
user-invocable: true
---

You are running the zombuul setup wizard. The philosophy is **detect first, ask only when something is missing**. Run all checks silently, then present a summary of what's already configured and what needs action.

## Phase 1: Silent detection

Run ALL checks before presenting anything to the user:

1. **uv installed**: `which uv` (hard requirement — `scripts/runpod_ctl.py` declares its deps via PEP 723 and is invoked through `uv run --script` via its shebang).
2. **SSH key**: Check the configured `ssh_key` path from `~/.claude/zombuul.yaml`, or auto-detect a usable key under `~/.ssh/`.
3. **RUNPOD_API_KEY**: check both `.env` (cwd) and `~/.claude/.env` for a non-empty `RUNPOD_API_KEY=`. Either works; `~/.claude/.env` is preferred so the key doesn't get synced into pods.
4. **Claude Code credentials**: `~/.claude/.credentials.json` exists OR Keychain has `"Claude Code-credentials"` entry
5. **Repo .env**: `.env` contains non-empty `GH_TOKEN`, `GIT_USER_NAME`, `GIT_USER_EMAIL` (all required — empty values count as missing); HF_TOKEN, SLACK_BOT_TOKEN, SLACK_CHANNEL_ID (optional). This file gets synced to pods, so pod-relevant tokens go here.
6. **Dependency file**: `pyproject.toml`, `requirements.txt`, or `setup.py` exists in cwd?
7. **ralph-wiggum**: `launch-research-ralph` in available skills?
8. **Config file**: `~/.claude/zombuul.yaml` exists?
9. **RunPod template** (optional): `template_id` set in config? (just note it if present, not a prerequisite)

## Phase 2: Status report

Present a checklist showing what was found:

```
Zombuul setup status:
  [x] uv available
  [x] SSH key found (~/.ssh/id_ed25519)
  [x] RUNPOD_API_KEY configured (in ~/.claude/.env)
  [x] Claude Code credentials extractable
  [x] Repo .env — GH_TOKEN, GIT_USER_NAME, GIT_USER_EMAIL, HF_TOKEN, SLACK_BOT_TOKEN
  [x] Dependency file found (pyproject.toml)
  [x] ralph-wiggum installed
  [x] Config file at ~/.claude/zombuul.yaml
```

Use `[ ]` for missing items. Only proceed to Phase 3 if there are missing items.

**Required items** (must be `[x]` before pod work is reliable): uv, SSH key, RUNPOD_API_KEY, Claude Code credentials, and the three repo-`.env` required fields (`GH_TOKEN`, `GIT_USER_NAME`, `GIT_USER_EMAIL`). If any of these is `[ ]` after Phase 3, refuse to proceed to Phase 4 and surface the gap to the user — silent missing values here cause confusing mid-experiment failures on the pod (auth declined, `Author identity unknown`, etc.).

## Phase 3: Fix missing items (only if needed)

For each missing item:

- **No uv**: install via `curl -LsSf https://astral.sh/uv/install.sh | sh`. Required — there's no pip fallback (the controller script self-installs deps through `uv run --script`).
- **No SSH key**: pick an existing key under `~/.ssh/` and write its path to `ssh_key` in `~/.claude/zombuul.yaml`. If none, generate one (`ssh-keygen -t ed25519`).
- **No RUNPOD_API_KEY**: direct to https://www.runpod.io/console/user/settings → API Keys, collect via AskUserQuestion, write to `~/.claude/.env` (preferred — it's a local controller credential, no reason to ship it to pods). The project `.env` also works as a fallback.
- **No Claude Code credentials**: try `security find-generic-password -s "Claude Code-credentials" -w > ~/.claude/.credentials.json && chmod 600 ~/.claude/.credentials.json`. On non-macOS or if the Keychain entry is missing, tell the user to copy `~/.claude/.credentials.json` from another logged-in machine, or to run `claude` and complete login first.
- **No .env / missing/empty required fields**: create or amend a template with required (`GH_TOKEN`, `GIT_USER_NAME`, `GIT_USER_EMAIL`) and optional (HF_TOKEN, SLACK_BOT_TOKEN, SLACK_CHANNEL_ID) fields. Collect missing required values via AskUserQuestion. Empty values count as missing.
- **No dependency file**: warn that pod setup expects a `pyproject.toml`, `requirements.txt`, or `setup.py` in the repo root. Dependencies will be skipped on the pod if none are present.
- **No ralph-wiggum**: ask if wanted; if yes, `/plugin marketplace add anthropics/claude-code` then install ralph-loop
- **No config file**: copy `${CLAUDE_PLUGIN_ROOT}/defaults.yaml` to `~/.claude/zombuul.yaml`

## Phase 4: Customize pod defaults

After all prerequisites are resolved, read the current config from `~/.claude/zombuul.yaml` and the defaults from `${CLAUDE_PLUGIN_ROOT}/defaults.yaml`. Use AskUserQuestion to ask the user if they want to customize their pod defaults.

If the user says **no**, skip to Phase 5.

If the user says **yes**, ask about all settings in a single AskUserQuestion call with multiple questions:

1. **Volume size** (persistent storage in GB) — offer the current value as "(current)", plus 2-3 reasonable alternatives. Common values: 50, 100, 200, 500.
2. **Disk size** (container disk in GB) — offer the current value as "(current)", plus alternatives. Common values: 100, 200, 400.
3. **GPU count** — offer 1, 2, 4.
4. **Docker image** — offer the current image as "(current)", plus any newer PyTorch images you know of. The "Other" option (auto-provided by AskUserQuestion) lets them paste a custom image.
5. **Python version** — offer the current value as "(current)", plus alternatives like 3.11, 3.12, 3.13. This controls the venv Python version on the pod.

Skip `cpu_instance_id` — it's too niche for the interactive flow.

After the user answers, only update `~/.claude/zombuul.yaml` if any values actually changed. Write the full config file (all fields, not just changed ones) using the Write tool.

### RunPod template (optional)

Ask whether the user has a custom RunPod template. If yes, collect the template ID and write it to `~/.claude/zombuul.yaml`. Mention they can change it later in that file.

## Phase 5: Test API connection

Run this command to verify the RunPod API key works:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py gpus
```

If it fails, debug from the error output. Note that the env var can live in `.env` (cwd) or `~/.claude/.env` — confirm the file actually used was picked up.

## Phase 6: Summary

If everything is configured, tell the user they're ready and show:
```
/zombuul:run-experiment experiments/<name>/<name>_spec.md
```

Tell them to create a `{name}_spec.md` first if they don't have one.
