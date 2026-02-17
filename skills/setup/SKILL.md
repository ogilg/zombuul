---
name: setup
description: >
  Interactive onboarding for zombuul. Walks through prerequisites, API keys,
  .env creation, and verifies everything works. Run this after installing the plugin.
user_invocable: true
---

You are running the zombuul setup wizard. The philosophy is **detect first, ask only when something is missing**. Run all checks silently, then present a summary of what's already configured and what needs action.

## Phase 1: Silent detection

Run ALL of the following checks before presenting anything to the user:

1. **Package manager**: run `which uv` and `which pip`
2. **SSH key**: check if `~/.ssh/id_ed25519` exists
3. **runpod package**: run `uv pip show runpod 2>/dev/null` (or `pip show runpod`)
4. **RUNPOD_API_KEY**: check both `~/.claude/.env` and `.env` in the current working directory for a line matching `RUNPOD_API_KEY=`
5. **Claude Code credentials**: check if `~/.claude/.credentials.json` exists OR if macOS Keychain has the entry (`security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null`). These credentials are sent to pods so Claude Code works remotely.
6. **Repo .env**: check if `.env` exists in the current working directory and whether it contains: GH_TOKEN, GIT_USER_NAME, GIT_USER_EMAIL (required), and HF_TOKEN, SLACK_BOT_TOKEN, SLACK_CHANNEL_ID (optional)
7. **pyproject.toml**: check if it exists in the current working directory
8. **ralph-wiggum**: check if `launch-research-ralph` appears in the available skills list (it's in the system prompt)

## Phase 2: Status report

Present a checklist showing what was found:

```
Zombuul setup status:
  [x] uv available
  [x] SSH key at ~/.ssh/id_ed25519
  [x] runpod 1.8.1 installed
  [x] RUNPOD_API_KEY configured (in .env)
  [x] Claude Code credentials extractable
  [x] Repo .env — GH_TOKEN, GIT_USER_NAME, GIT_USER_EMAIL, HF_TOKEN, SLACK_BOT_TOKEN
  [x] pyproject.toml found
  [x] ralph-wiggum installed
```

Use `[ ]` for missing items. Only proceed to Phase 3 if there are missing items.

## Phase 3: Fix missing items (only if needed)

For each missing item, help the user fix it:

- **No package manager**: tell them to install uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **No SSH key**: `ssh-keygen -t ed25519`
- **No runpod**: install it with whichever package manager is available
- **No RUNPOD_API_KEY**: direct them to https://www.runpod.io/console/user/settings → API Keys, use AskUserQuestion to get the key, write to `~/.claude/.env`
- **No Claude Code credentials**: the user is already logged in (they're running this skill). Try extracting from Keychain: `security find-generic-password -s "Claude Code-credentials" -w > ~/.claude/.credentials.json && chmod 600 ~/.claude/.credentials.json`. If that fails, tell them to manually copy `~/.claude/.credentials.json` from wherever their system stores it. This file is sent to pods so Claude Code works remotely.
- **No .env file at all**: create a template `.env` with all required fields (GH_TOKEN, GIT_USER_NAME, GIT_USER_EMAIL) and optional fields (HF_TOKEN, SLACK_BOT_TOKEN, SLACK_CHANNEL_ID) as empty entries, then proceed to fill in the required ones via AskUserQuestion.
- **Missing .env fields**: use AskUserQuestion to collect only the missing required fields (GH_TOKEN, GIT_USER_NAME, GIT_USER_EMAIL). Mention optional fields but don't require them.
- **No pyproject.toml**: warn that pod setup expects one (`uv pip install -e .`)
- **No ralph-wiggum**: ask if they want it, if yes tell them to run `/plugin marketplace add anthropics/claude-code` then install ralph-loop

## Phase 4: Test API connection

Run this command to verify the RunPod API key works:
```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/runpod_ctl.py gpus
```

If it fails, help debug (wrong key, missing package, etc.).

## Phase 5: Summary

If everything is configured, tell the user they're ready and show:
```
/launch-research-pod experiments/<name>/spec.md
```

Tell them to create a spec.md first if they don't have one.
