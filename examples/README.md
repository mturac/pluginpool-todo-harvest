# todo-harvest — examples

Each scenario shows a real repo state, the exact command, and the table that `todo-harvest` produces — captured from a hermetic test repo, not hand-written.

---

## Scenario 1 — triage stale debt

**Setup:** A small repo with three TODOs of different ages — added across the years 2022, 2024, and 2026:

```
src/legacy.py:2  HACK    "special-case the demo account UA"       (Aug 2022)
src/db.py:2      FIXME   "this `n+1` lookup needs a join"          (Feb 2024)
src/auth.py:2    TODO    "wire to the new OAuth2 path"             (Apr 2026)
```

**Command:**

```sh
python3 scripts/harvest.py --format md
```

**Helper output (captured verbatim against a hermetic test repo on 2026-05-16):**

```
| age (d) | marker | file:line | author | note |
|---|---|---|---|---|
| 1369 | HACK | src/legacy.py:2 | Demo Dev | special-case the demo account UA — kept around since 2022 |
|  825 | FIXME | src/db.py:2 | Demo Dev | this `n+1` lookup needs a join |
|   44 | TODO | src/auth.py:2 | Demo Dev | wire to the new OAuth2 path |
```

Sorted oldest-first — the most-deferred work surfaces at the top.

**What Claude does next** (running `/todo-harvest`):

> The 1369-day HACK can almost certainly be deleted — it predates the user-agent
> registry rewrite (`src/ua.py`, Jan 2024). Suggest opening a one-line PR.
>
> The 825-day FIXME is real work — the n+1 was acknowledged but never scheduled.
> Suggest filing an issue and linking to `src/db.py:2`.
>
> The 44-day TODO is in-flight — see commit `0070d08`. Leave it.

---

## Scenario 2 — only show what's old

Skip the noise:

```sh
python3 scripts/harvest.py --min-age 365 --format md
```

Shows only TODOs that are at least one year old. Useful for "stale debt week" cleanups.

---

## Scenario 3 — narrow markers

`HACK` and `XXX` are usually higher-signal than `TODO`:

```sh
python3 scripts/harvest.py --markers HACK,XXX --format md
```

---

## Scenario 4 — JSON for further analysis

```sh
python3 scripts/harvest.py --format json | jq '[.[] | select(.age_days > 180)] | length'
# 2
```

---

## What `todo-harvest` does NOT do

- It doesn't rewrite or delete TODOs for you. Triage is a human decision.
- It doesn't follow renames or refactors — "age" is the age of the *current line*. A copy-paste resets it.
- It's slow on huge repos (one `git blame` per match). Use `--min-age` and `--markers` to narrow first.
