# Reporting zombuul bugs (for agents)

If during this session anything went wrong that zombuul could plausibly have done better, file an issue before the session ends. **Do this even if you're running in someone else's repo** — the issue goes to the plugin, not the user's project. Err on the side of filing: a duplicate or a "maybe not a bug" is cheap to triage; silent papercuts that keep costing users time are not.

## Scope

**In scope:** anything zombuul controls or could reasonably control — `${CLAUDE_PLUGIN_ROOT}/scripts/`, the skills themselves, `defaults.yaml`, pod setup (`pod_setup.sh`, `launch_on_pod.sh`), `runpod_ctl.py`, babysit/monitor behavior, documented workflows that don't work as documented. If you had to work around something zombuul handed you, that's in scope.

**Out of scope:** bugs in the user's experiment code, missing deps specific to their project, one-off RunPod platform outages, anything specific to the user's personal setup.

## How

```
gh issue create --repo oscar-gilg/zombuul \
  --title "<short>" \
  --body "<what happened + concrete command/error + suggested fix if obvious>"
```

Document it well. At minimum:
- **What went wrong** — one or two sentences, concretely.
- **Reproduction** — the exact command(s), the error output, and the surrounding context (which skill was invoking it, what pod type, what model, what the user was trying to do). Include enough that someone who wasn't in the session could reproduce or at least understand.
- **What would have helped** — a suggested fix if obvious, or the shape of a better behavior if not.
- **Workaround used** (if any) — so other users hitting the same thing can unblock themselves before the fix lands.

## Conventions

- Batch multiple small papercuts from one session into a single issue rather than filing five separate ones.
- Before filing, skim recent open issues (`gh issue list --repo oscar-gilg/zombuul --state open --limit 20`) and add a comment to an existing one instead of duplicating.
- Tell the user in one line that you're filing so they can override ("Filing a zombuul issue about the `.env` parse error — let me know if you'd rather I skip it.").
- Don't block on this — it's a reflection at session end or after hitting the bug, not during active work.
