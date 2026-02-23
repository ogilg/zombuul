#!/bin/bash
# Usage: bash pod_setup.sh <repo_url> [branch] [python_version]
# Generic pod bootstrap for zombuul research loops.
# Reads git identity and tokens from .env (SCP'd separately).
set -o pipefail

REPO_URL="${1:?Usage: bash pod_setup.sh <repo_url> [branch] [python_version]}"
BRANCH="${2:-main}"
PYTHON_VERSION="${3:-3.12}"
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
    export $(tr '\0' '\n' < /proc/1/environ | grep -E '^(HF_TOKEN|GH_TOKEN|SLACK_BOT_TOKEN|SLACK_CHANNEL_ID)=')
fi

# --- system tools ---

retry "apt-get update" 3 10 apt-get update
retry "install jq+rsync" 3 10 apt-get install -y jq rsync

# gh CLI (non-critical — used for PR operations but not essential)
install_gh() {
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
        echo "Repo already cloned."
        return 0
    fi
    rm -rf "$REPO_DIR"
    git clone "$REPO_URL" "$REPO_DIR"
}
retry "clone repo" 3 15 clone_repo
cd "$REPO_DIR" || exit 1
retry "git fetch" 3 10 git fetch origin
git checkout "$BRANCH" || git checkout -b "$BRANCH" "origin/$BRANCH"

# --- Claude Code ---

install_claude() {
    curl -fsSL https://claude.ai/install.sh | bash
}
retry "install Claude Code" 3 15 install_claude
export PATH="$HOME/.local/bin:$PATH"

if ! command -v claude &>/dev/null; then
    echo "FATAL: claude not found on PATH after install."
    SETUP_FAILURES+=("claude binary not found")
fi

# --- caches outside NFS ---

export UV_CACHE_DIR=/opt/uv_cache
export HF_HOME=/opt/hf_cache
mkdir -p /opt/uv_cache /opt/hf_cache

# --- Python environment ---

pip install uv
mkdir -p /opt/venvs
rm -rf /opt/venvs/research
retry "create venv" 3 5 uv venv --python "$PYTHON_VERSION" /opt/venvs/research
# shellcheck disable=SC1091
source /opt/venvs/research/bin/activate
cd "$REPO_DIR" || exit 1
retry "pip install project" 3 10 uv pip install -e .
uv cache clean

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

# --- zombuul plugin ---

install_zombuul() {
    # Remove stale marketplace if present (idempotent re-install)
    claude plugin marketplace remove ogilg-marketplace 2>/dev/null || true
    claude plugin marketplace add ogilg/zombuul || return 1
    claude plugin install zombuul@ogilg-marketplace || return 1
}
retry "install zombuul plugin" 3 10 install_zombuul

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
