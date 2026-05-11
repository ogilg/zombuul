#!/bin/bash
# Usage: bash pod_setup.sh <repo_url> [branch] [python_version] [install_claude] [extras]
# Generic pod bootstrap for zombuul research loops.
# Tokens come from container env vars (/proc/1/environ), with .env as fallback.
#
# install_claude: "true" to install Claude Code + zombuul plugin (for remote-mode
# experiments where the pod itself runs an agent). Default "false" — local-mode
# setups only need the repo + Python env, not the agent.
#
# extras: which optional-dependency groups from pyproject.toml to install.
#   "auto"  (default) — install every group declared in [project.optional-dependencies].
#                       Convenient, but breaks for projects with mutually exclusive groups.
#   "none"            — install with no extras (`uv pip install -e .`).
#   "a,b,c"           — install only the listed groups (`uv pip install -e ".[a,b,c]"`).
set -o pipefail

REPO_URL="${1:?Usage: bash pod_setup.sh <repo_url> [branch] [python_version] [install_claude] [extras]}"
BRANCH="${2:-main}"
PYTHON_VERSION="${3:-3.11}"
INSTALL_CLAUDE="${4:-false}"
EXTRAS="${5:-auto}"
REPO_DIR="/workspace/repo"
SETUP_FAILURES=()

# --- helpers ---

retry() {
    local desc="$1" max_attempts="$2" delay="$3"
    shift 3
    local attempt=1
    while [ $attempt -le "$max_attempts" ]; do
        echo "[$desc] attempt $attempt/$max_attempts..."
        if "$@"; then
            echo "[$desc] succeeded."
            return 0
        fi
        echo "[$desc] failed (attempt $attempt/$max_attempts)."
        if [ $attempt -lt "$max_attempts" ]; then
            sleep "$delay"
        fi
        attempt=$((attempt + 1))
    done
    echo "[$desc] FAILED after $max_attempts attempts."
    SETUP_FAILURES+=("$desc")
    return 1
}

# --- env vars ---

# Import container env vars (not inherited when run via nohup over SSH)
if [ -f /proc/1/environ ]; then
    # shellcheck disable=SC2046
    export $(tr '\0' '\n' < /proc/1/environ | grep -E '^(HF_TOKEN|GH_TOKEN|SLACK_BOT_TOKEN|SLACK_CHANNEL_ID|RUNPOD_API_KEY|RUNPOD_POD_ID|GIT_USER_NAME|GIT_USER_EMAIL)=')
fi

# Fallback: check for .env synced by provision-pod.
for envfile in "$REPO_DIR/.env" /tmp/.env; do
    if [ -f "$envfile" ]; then
        echo "Found .env at $envfile — sourcing tokens."
        while IFS='=' read -r key value || [ -n "$key" ]; do
            case "$key" in
                GH_TOKEN|HF_TOKEN|SLACK_BOT_TOKEN|SLACK_CHANNEL_ID|RUNPOD_API_KEY|GIT_USER_NAME|GIT_USER_EMAIL)
                    value="${value%\"}"; value="${value#\"}"
                    value="${value%\'}"; value="${value#\'}"
                    export "$key=$value"
                    ;;
            esac
        done < "$envfile"
        break
    fi
done

# --- system tools ---

retry "apt-get update" 3 10 apt-get update

install_system_packages() {
    if command -v jq &>/dev/null && command -v rsync &>/dev/null && command -v tmux &>/dev/null; then
        echo "jq, rsync, and tmux already installed."
        return 0
    fi
    apt-get install -y jq rsync tmux
}
retry "install jq+rsync+tmux" 3 10 install_system_packages

# gh CLI (non-critical — used for PR operations but not essential)
install_gh() {
    if command -v gh &>/dev/null; then
        echo "gh already installed."
        return 0
    fi
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg 2>/dev/null \
        && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
        && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
            | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
        && apt-get update \
        && apt-get install -y gh
}
retry "install gh" 3 10 install_gh

# --- git auth (before any clone) ---
# Use gh CLI as credential helper instead of embedding token in URL.
# Embedding the token in the URL triggers GitHub push protection on push.

if [ -z "$GH_TOKEN" ]; then
    echo "FATAL: GH_TOKEN is empty. Set GH_TOKEN in the repo's .env (or in /proc/1/environ) before launching."
    echo "       Without it, gh auth login is skipped and any private clone / push will fail mid-experiment."
    exit 1
fi
# gh CLI uses GH_TOKEN from env automatically when set; calling
# `gh auth login --with-token` in that case errors out ("To have GitHub CLI
# store credentials instead, first clear the value from the environment").
# Verify auth works via env instead — the credential helper below uses gh's
# auth regardless of whether it came from env or login store.
if gh auth status >/dev/null 2>&1; then
    echo "Logged into GitHub via GH_TOKEN env var."
else
    echo "FATAL: gh auth status failed despite GH_TOKEN being set — token may be invalid or expired."
    exit 1
fi
git config --global credential.helper '!gh auth git-credential'

# --- clone repo ---

clone_repo() {
    if [ -d "$REPO_DIR/.git" ]; then
        echo "Repo already cloned — fetching latest."
        git -C "$REPO_DIR" fetch origin
        return $?
    fi
    rm -rf "$REPO_DIR"
    git clone "$REPO_URL" "$REPO_DIR"
}
retry "clone repo" 3 15 clone_repo
cd "$REPO_DIR" || exit 1
git checkout "$BRANCH" || git checkout -b "$BRANCH" "origin/$BRANCH"

# --- Claude Code + zombuul plugin ---

if [ "$INSTALL_CLAUDE" = "true" ]; then
    install_claude() {
        if command -v claude &>/dev/null; then
            echo "Claude Code already installed."
            return 0
        fi
        curl -fsSL https://claude.ai/install.sh | bash
    }
    retry "install Claude Code" 3 15 install_claude
    export PATH="$HOME/.local/bin:$PATH"

    if ! command -v claude &>/dev/null; then
        echo "FATAL: claude not found on PATH after install."
        SETUP_FAILURES+=("claude binary not found")
    fi

    install_zombuul() {
        # Remove stale marketplace if present (idempotent re-install)
        claude plugin marketplace remove ogilg-marketplace 2>/dev/null || true
        claude plugin marketplace add oscar-gilg/zombuul || return 1
        claude plugin install zombuul@ogilg-marketplace || return 1
    }
    retry "install zombuul plugin" 3 10 install_zombuul
else
    echo "Skipping Claude Code install (INSTALL_CLAUDE=false)."
fi

# --- caches outside NFS ---

export UV_CACHE_DIR=/opt/uv_cache
export HF_HOME=/opt/hf_cache
mkdir -p /opt/uv_cache /opt/hf_cache
mkdir -p /root/.cache
# Only replace /root/.cache/huggingface if missing or a symlink; never rm a real cache dir.
if [ -L /root/.cache/huggingface ] || [ ! -e /root/.cache/huggingface ]; then
    ln -sfn /opt/hf_cache /root/.cache/huggingface
fi

# --- Python environment ---

if ! command -v uv &>/dev/null; then
    pip install uv
fi
mkdir -p /opt/venvs
if [ ! -d /opt/venvs/research/bin ]; then
    retry "create venv" 3 5 uv venv --python "$PYTHON_VERSION" /opt/venvs/research
fi
# Fail loudly if the venv didn't get built — otherwise we silently activate
# nothing and downstream `uv pip install` lands in the wrong interpreter.
if [ ! -x /opt/venvs/research/bin/python ]; then
    echo "FATAL: venv /opt/venvs/research not created. Requested Python $PYTHON_VERSION may be unavailable in this image."
    echo "       Check defaults.yaml python_version vs. the docker_image's bundled Python."
    exit 1
fi
ACTUAL_PY=$(/opt/venvs/research/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [ "$ACTUAL_PY" != "$PYTHON_VERSION" ]; then
    echo "FATAL: venv built with Python $ACTUAL_PY, but $PYTHON_VERSION was requested."
    exit 1
fi
# shellcheck disable=SC1091
source /opt/venvs/research/bin/activate
cd "$REPO_DIR" || exit 1
# Replace any existing .venv first: ln -sfn into an existing dir nests the symlink inside it.
if [ -L "$REPO_DIR/.venv" ] || [ ! -e "$REPO_DIR/.venv" ]; then
    ln -sfn /opt/venvs/research "$REPO_DIR/.venv"
else
    rm -rf "$REPO_DIR/.venv"
    ln -sfn /opt/venvs/research "$REPO_DIR/.venv"
fi
# Install project dependencies.
# Supports pyproject.toml (with optional extras), requirements.txt, or setup.py.
# Skips install if none are found.
if [ -f "$REPO_DIR/pyproject.toml" ]; then
    case "$EXTRAS" in
        auto)
            EXTRAS_RESOLVED=$(python3 -c "
import tomllib
with open('$REPO_DIR/pyproject.toml', 'rb') as f:
    groups = list(tomllib.load(f).get('project', {}).get('optional-dependencies', {}).keys())
if groups:
    print(','.join(groups))
" 2>/dev/null || true)
            ;;
        none|"")
            EXTRAS_RESOLVED=""
            ;;
        *)
            EXTRAS_RESOLVED="$EXTRAS"
            ;;
    esac
    if [ -n "$EXTRAS_RESOLVED" ]; then
        echo "Installing with extras: [$EXTRAS_RESOLVED]"
        retry "pip install project" 3 10 uv pip install -e ".[$EXTRAS_RESOLVED]"
    else
        echo "Installing with no extras."
        retry "pip install project" 3 10 uv pip install -e .
    fi
elif [ -f "$REPO_DIR/requirements.txt" ]; then
    echo "No pyproject.toml found; installing from requirements.txt"
    retry "pip install requirements" 3 10 uv pip install -r requirements.txt
elif [ -f "$REPO_DIR/setup.py" ]; then
    echo "No pyproject.toml found; installing from setup.py"
    retry "pip install project" 3 10 uv pip install -e .
else
    echo "WARNING: No pyproject.toml, requirements.txt, or setup.py found. Skipping dependency install."
fi

# --- git identity ---
# GIT_USER_NAME / GIT_USER_EMAIL are forwarded by runpod_ctl.py, which reads
# them from the launching user's env / .env / `git config --global user.*`.
# So on-pod commits are attributed to the real human, not a generic pod user.

if [ -z "$GIT_USER_NAME" ] || [ -z "$GIT_USER_EMAIL" ]; then
    echo "FATAL: GIT_USER_NAME and/or GIT_USER_EMAIL not forwarded to the pod."
    echo "       runpod_ctl.py reads these from env, .env, or 'git config --global user.{name,email}'."
    echo "       Set one of those on the launching machine, or commits will fail with 'Author identity unknown' mid-experiment."
    exit 1
fi
git config --global user.name "$GIT_USER_NAME"
git config --global user.email "$GIT_USER_EMAIL"

# --- auth (tokens passed via environment) ---

if [ -n "$HF_TOKEN" ]; then
    hf auth login --token "$HF_TOKEN" 2>/dev/null && echo "Logged into Hugging Face." || echo "WARNING: HF login failed (non-critical)."
fi

# gh auth already done above (before clone)

# --- .bash_profile ---

cat > ~/.bash_profile << 'PROFILE'
export PATH="$HOME/.local/bin:$PATH"
export UV_CACHE_DIR=/opt/uv_cache
export HF_HOME=/opt/hf_cache
source /opt/venvs/research/bin/activate
PROFILE

if [ -n "$HF_TOKEN" ]; then
    echo "export HF_TOKEN=$HF_TOKEN" >> ~/.bash_profile
fi
if [ -n "$GH_TOKEN" ]; then
    echo "export GH_TOKEN=$GH_TOKEN" >> ~/.bash_profile
fi
if [ -n "$SLACK_BOT_TOKEN" ]; then
    echo "export SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN" >> ~/.bash_profile
fi
if [ -n "$SLACK_CHANNEL_ID" ]; then
    echo "export SLACK_CHANNEL_ID=$SLACK_CHANNEL_ID" >> ~/.bash_profile
fi
if [ -n "$RUNPOD_API_KEY" ]; then
    echo "export RUNPOD_API_KEY=$RUNPOD_API_KEY" >> ~/.bash_profile
fi
if [ -n "$RUNPOD_POD_ID" ]; then
    echo "export RUNPOD_POD_ID=$RUNPOD_POD_ID" >> ~/.bash_profile
fi

# --- summary ---

echo ""
if [ ${#SETUP_FAILURES[@]} -gt 0 ]; then
    echo "=== Setup complete with ${#SETUP_FAILURES[@]} failure(s) ==="
    for f in "${SETUP_FAILURES[@]}"; do
        echo "  FAILED: $f"
    done
else
    echo "=== Setup complete ==="
fi
echo "Research venv: /opt/venvs/research/bin/python (also symlinked at $REPO_DIR/.venv)"
echo "HF cache: /opt/hf_cache  UV cache: /opt/uv_cache"
