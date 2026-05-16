# todo-harvest

**Find the oldest, most-forgotten TODOs and put their authors on blast (constructively).**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Claude Code Plugin](https://img.shields.io/badge/claude--code-plugin-7c3aed.svg)](https://docs.claude.com/en/docs/claude-code/overview)
[![Tests: 9 passing](https://img.shields.io/badge/tests-9%20passing-success.svg)](./tests)

> **TL;DR:** `/todo-harvest` → markdown table of every `TODO/FIXME/HACK` with `git blame` author + age in days, sorted oldest-first.

## Why this exists

`TODO` comments are how engineers say "future me will deal with this." Future me never does. Worse, future-me-the-new-hire doesn't even know who wrote them or whether they still apply. `todo-harvest` runs `git blame` for each match so you can triage: 800-day-old TODOs from a dev who left the company three years ago are deletable; 12-day-old ones from this sprint are real work.

## Install (Claude Code)

```sh
git clone https://github.com/mturac/pluginpool-todo-harvest ~/.claude/plugins/todo-harvest
```

Restart Claude Code; the slash command `/todo-harvest` appears.

## Quick start

```sh
/todo-harvest
```

Or directly:

```sh
python3 scripts/harvest.py --format md
python3 scripts/harvest.py --min-age 180 --format md     # only stuff older than 6 months
python3 scripts/harvest.py --markers TODO,FIXME --format json
```

## Flags

| Flag | Default | Description |
|---|---|---|
| `--repo` | cwd | Repo path |
| `--markers` | `TODO,FIXME,HACK,XXX,NOTE` | Comma-separated marker words |
| `--min-age` | `0` | Only show markers ≥ N days old |
| `--format` | `json` | `json` or `md` |

## Example output (markdown)

```
| age (d) | marker | file:line | author | note |
|---|---|---|---|---|
| 1247 | HACK | src/legacy/login.py:42 | Alice (left in 2022) | special-case the demo-account UA |
| 412 | FIXME | src/db.py:81 | Bob | this `n+1` lookup needs a join |
| 88 | TODO | src/auth.py:17 | Cara | wire to the new OAuth2 path |
```

## How it works

1. Uses `git ls-files` so untracked + `.gitignore`d files are skipped.
2. Detects worktrees correctly (`.git` can be a file pointer, not a directory).
3. Skips binary files (null byte in first 1 KB).
4. Matches markers as whole words: `TODO`, `TODO:`, `# TODO …`.
5. Runs `git blame --porcelain -L N,N -- <file>` per match for the original author + author-time.

## Limitations

- One `git blame` call per match means it's slow on huge repos — use `--min-age` or `--markers` to narrow.
- "Age" is the age of the *current* line. Renames and reformats reset the clock.
- Unicode-safe (decodes with `errors="replace"`).

## Part of the pluginpool family

Ten focused Claude Code plugins for everyday productivity:
[commit-narrator](https://github.com/mturac/pluginpool-commit-narrator) ·
[pr-storyteller](https://github.com/mturac/pluginpool-pr-storyteller) ·
[test-gap](https://github.com/mturac/pluginpool-test-gap) ·
[deps-doctor](https://github.com/mturac/pluginpool-deps-doctor) ·
[env-lint](https://github.com/mturac/pluginpool-env-lint) ·
[secret-guard](https://github.com/mturac/pluginpool-secret-guard) ·
[standup-gen](https://github.com/mturac/pluginpool-standup-gen) ·
[todo-harvest](https://github.com/mturac/pluginpool-todo-harvest) ·
[flaky-detector](https://github.com/mturac/pluginpool-flaky-detector) ·
[changelog-forge](https://github.com/mturac/pluginpool-changelog-forge)

## License

MIT — see [`LICENSE`](./LICENSE). Contributions welcome.
