# Zombuul

## Branch workflow

Two long-lived branches:

- **`main`** — production. Tracked by other users' plugin installs (`ogilg-marketplace`). Moves only on deliberate release PRs. Branch-protected (PR required, no force-pushes, no deletions). The `version-bump.yml` workflow opens an auto-merging bump PR after every merge to main; that PR bumps the patch in `plugin.json` and tags the release.
- **`dev`** — integration branch for the maintainer's own testing. Tracked by the maintainer's local install via `ogilg-marketplace-dev` (git URL source with `ref: dev`). Branch-protected identically to main (PR required, no force-pushes, no deletions). The `version-bump-dev.yml` workflow opens an auto-merging bump PR after every merge to dev, incrementing the `-dev.N` counter — this is what makes `claude plugin update zombuul@ogilg-marketplace-dev` see new commits without manual cache-clearing.

**Making edits — always:**
1. `git checkout dev && git pull`
2. `git checkout -b feat/<name>` (feature branch off dev)
3. Edit, commit, push, `gh pr create --base dev`. Never target `main` from a feature branch.
4. Merge PR → dev. Refresh local install: `claude plugin marketplace update ogilg-marketplace-dev && claude plugin update zombuul@ogilg-marketplace-dev`, restart Claude Code.

**Releasing dev → main** (periodic, when dev has shippable changes):
1. `git checkout main && git pull`
2. `git checkout -b release/<yyyy-mm-dd>`
3. `git merge dev --no-commit --no-ff`
4. `git checkout main -- .claude-plugin/marketplace.json .claude-plugin/plugin.json` — keep main's versions of these two files; dev's rename (`ogilg-marketplace-dev`) and `-dev` version suffix must NOT leak to main.
5. `git commit -m "release: <summary>"`
6. `gh pr create --base main`. Merge → `version-bump.yml` bumps patch version, tags, publishes to other users.

**Dev-only files that must not merge to main:**
- `.claude-plugin/marketplace.json` — `name` is `ogilg-marketplace-dev` on dev, `ogilg-marketplace` on main
- `.claude-plugin/plugin.json` — `version` has `-dev` suffix on dev (format `X.Y.Z-dev` or `X.Y.Z-dev.N`)

When syncing main → dev, resolve the `plugin.json` conflict to `<main-patch>-dev` (no counter) — the next dev push auto-bumps to `<main-patch>-dev.1`.

**Never:**
- PR a feature branch directly to main (go through dev).
- Change GitHub's default branch away from main — the plugin marketplace for other users resolves the default branch.

## Skills

Skills are auto-discovered from `skills/`. Each skill is a directory with a `SKILL.md` file containing YAML frontmatter. No manual registration needed — just create the directory and file.

## Agent-authored issues

The main user-invocable skills point agents at `REPORTING_BUGS.md`, which tells them to file GitHub issues autonomously when zombuul itself hits friction, even in someone else's repo. Expect a steady stream at https://github.com/oscar-gilg/zombuul/issues — treat them as field telemetry, close/dedupe liberally.
