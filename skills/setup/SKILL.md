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

1. **Package manager**: `which uv` and `which pip` (uv preferred, pip as fallback)
2. **SSH key**: Check the configured `ssh_key` path (from `~/.claude/zombuul.yaml`, default `~/.ssh/id_ed25519`). Does it exist?
3. **runpod package**: `uv pip show runpod 2>/dev/null` (or `pip show runpod`)
4. **RUNPOD_API_KEY**: check both `.env` and `~/.claude/.env` for `RUNPOD_API_KEY=`. It can live in either file.
5. **Claude Code credentials**: `~/.claude/.credentials.json` exists OR Keychain has `"Claude Code-credentials"` entry
6. **Repo .env**: `.env` contains GH_TOKEN, GIT_USER_NAME, GIT_USER_EMAIL (required); HF_TOKEN, SLACK_BOT_TOKEN, SLACK_CHANNEL_ID (optional). This file gets synced to pods, so pod-relevant tokens go here.
7. **Dependency file**: `pyproject.toml`, `requirements.txt`, or `setup.py` exists in cwd?
8. **ralph-wiggum**: `launch-research-ralph` in available skills?
9. **Config file**: `~/.claude/zombuul.yaml` exists?
10. **RunPod template** (optional): `template_id` set in config? (just note it if present, not a prerequisite)

## Phase 2: Status report

Present a checklist showing what was found:

```
Zombuul setup status:
  [x] uv available (pip also found)
  [x] SSH key found
  [x] runpod 1.8.1 installed
  [x] RUNPOD_API_KEY configured (in .env)
  [x] Claude Code credentials extractable
  [x] Repo .env — GH_TOKEN, GIT_USER_NAME, GIT_USER_EMAIL, HF_TOKEN, SLACK_BOT_TOKEN
  [x] Dependency file found (pyproject.toml)
  [x] ralph-wiggum installed
  [x] Config file at ~/.claude/zombuul.yaml
```

Use `[ ]` for missing items. Only proceed to Phase 3 if there are missing items.

## Phase 3: Fix missing items (only if needed)

For each missing item:

- **No package manager**: install uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`); if uv is unavailable, fall back to pip
- **No SSH key**: If they have a key at a different path (e.g. `~/.ssh/id_rsa`), set `ssh_key` in `~/.claude/zombuul.yaml`. Otherwise generate one: `ssh-keygen -t ed25519`
- **No runpod**: install with available package manager
- **No RUNPOD_API_KEY**: direct to https://www.runpod.io/console/user/settings → API Keys, collect via AskUserQuestion, write to the project `.env` (preferred, since it gets synced to pods) or `~/.claude/.env`
- **No Claude Code credentials**: try `security find-generic-password -s "Claude Code-credentials" -w > ~/.claude/.credentials.json && chmod 600 ~/.claude/.credentials.json`. On non-macOS or if the Keychain entry is missing, tell the user to copy `~/.claude/.credentials.json` from another logged-in machine, or to run `claude` and complete login first.
- **No .env / missing fields**: create template with required (GH_TOKEN, GIT_USER_NAME, GIT_USER_EMAIL) and optional (HF_TOKEN, SLACK_BOT_TOKEN, SLACK_CHANNEL_ID) fields. Collect missing required fields via AskUserQuestion.
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
