#!/bin/bash
# Usage: launch_on_pod.sh <branch> <spec_path>
#
# Runs an on-pod zombuul agent for a single experiment and pauses the pod
# when the agent exits (success, failure, or signal). Trap fires on any EXIT
# except SIGKILL, so the pod won't keep billing if the agent crashes.
set -u

BRANCH="${1:?Usage: launch_on_pod.sh <branch> <spec_path>}"
SPEC_PATH="${2:?Usage: launch_on_pod.sh <branch> <spec_path>}"

# Load env (RUNPOD_POD_ID, RUNPOD_API_KEY, HF_TOKEN, GH_TOKEN, etc.) before
# registering the trap so pause_pod has access to them.
# shellcheck source=/dev/null
source ~/.bash_profile

pause_pod() {
    curl -s -H "Content-Type: application/json" \
        -d "{\"query\": \"mutation { podStop(input: {podId: \\\"$RUNPOD_POD_ID\\\"}) { id desiredStatus } }\"}" \
        "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY"
}
trap pause_pod EXIT

cd /workspace/repo || exit 1
git checkout "$BRANCH"
git pull origin "$BRANCH"

export IS_SANDBOX=1
claude --dangerously-skip-permissions -p "/zombuul:run-experiment $SPEC_PATH" > /workspace/agent.log 2>&1
