#!/bin/bash
# Usage: bash pod_setup.sh <repo_url> [branch] [python_version] [install_claude]
# Generic pod bootstrap for zombuul research loops.
# Tokens come from container env vars (/proc/1/environ), with .env as fallback.
#
# install_claude: "true" to install Claude Code + zombuul plugin (for remote-mode
# experiments where the pod itself runs an agent). Default "false" — local-mode
# setups only need the repo + Python env, not the agent.
set -o pipefail

REPO_URL="${1:?Usage: bash pod_setup.sh <repo_url> [branch] [python_version] [install_claude]}"
BRANCH="${2:-main}"
PYTHON_VERSION="${3:-3.12}"
INSTALL_CLAUDE="${4:-false}"
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
    export $(tr '\0' '\n' < /proc/1/environ | grep -E '^(HF_TOKEN|GH_TOKEN|SLACK_BOT_TOKEN|SLACK_CHANNEL_ID|RUNPOD_API_KEY|RUNPOD_POD_ID)=')
fi

# Fallback: check for .env synced by provision-pod
for envfile in "$REPO_DIR/.env" /tmp/.env; do
    if [ -f "$envfile" ]; then
        echo "Found .env at $envfile — sourcing tokens."
        # shellcheck disable=SC2046
        export $(grep -E '^(GH_TOKEN|HF_TOKEN|SLACK_BOT_TOKEN|SLACK_CHANNEL_ID|RUNPOD_API_KEY)=' "$envfile" | xargs)
        break
    fi
done

# --- system tools ---

retry "apt-get update" 3 10 apt-get update

install_system_packages() {
    if command -v jq &>/dev/null && command -v rsync &>/dev/null; then
        echo "jq and rsync already installed."
        return 0
    fi
    apt-get install -y jq rsync
}
retry "install jq+rsync" 3 10 install_system_packages

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

if [ -n "$GH_TOKEN" ]; then
    echo "$GH_TOKEN" | gh auth login --with-token 2>/dev/null && echo "Logged into GitHub (for git auth)." || echo "WARNING: gh login failed."
    git config --global credential.helper '!gh auth git-credential'
fi

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
        claude plugin marketplace add ogilg/zombuul || return 1
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

# --- Python environment ---

if ! command -v uv &>/dev/null; then
    pip install uv
fi
mkdir -p /opt/venvs
if [ ! -d /opt/venvs/research/bin ]; then
    retry "create venv" 3 5 uv venv --python "$PYTHON_VERSION" /opt/venvs/research
fi
# shellcheck disable=SC1091
source /opt/venvs/research/bin/activate
cd "$REPO_DIR" || exit 1
# Install project dependencies.
# Supports pyproject.toml (with optional extras), requirements.txt, or setup.py.
# Skips install if none are found.
if [ -f "$REPO_DIR/pyproject.toml" ]; then
    EXTRAS=$(python3 -c "
import tomllib, sys
with open('$REPO_DIR/pyproject.toml', 'rb') as f:
    groups = list(tomllib.load(f).get('project', {}).get('optional-dependencies', {}).keys())
if groups:
    print(','.join(groups))
" 2>/dev/null || true)
    if [ -n "$EXTRAS" ]; then
        echo "Installing with extras: [$EXTRAS]"
        retry "pip install project" 3 10 uv pip install -e ".[$EXTRAS]"
    else
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

if [ -f "$REPO_DIR/.env" ]; then
    GIT_USER_NAME=$(grep '^GIT_USER_NAME=' "$REPO_DIR/.env" | cut -d= -f2-)
    GIT_USER_EMAIL=$(grep '^GIT_USER_EMAIL=' "$REPO_DIR/.env" | cut -d= -f2-)
fi
if [ -n "$GIT_USER_NAME" ]; then
    git config --global user.name "$GIT_USER_NAME"
fi
if [ -n "$GIT_USER_EMAIL" ]; then
    git config --global user.email "$GIT_USER_EMAIL"
fi

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
