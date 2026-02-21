#!/usr/bin/env bash
# Touches /tmp/zombuul_session_active when a zombuul skill/command is invoked.
# Called from PreToolUse hook on the Skill tool.
# Try both field names in case the SDK uses either.
skill=$(echo "$CLAUDE_TOOL_INPUT" | jq -r '(.tool_input.skill // .tool_input.skill_name) // empty')
case "$skill" in
  zombuul:*)
    touch /tmp/zombuul_session_active
    ;;
esac
