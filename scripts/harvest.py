#!/usr/bin/env python3
"""Harvest TODO/FIXME/HACK markers from a git repo with author + age."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from typing import Iterable


DEFAULT_MARKERS = ("TODO", "FIXME", "HACK", "XXX", "NOTE")


def _run(args: list[str], cwd: str) -> str:
    res = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    return res.stdout


def _is_binary(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
        return b"\x00" in chunk
    except OSError:
        return True


def _list_files(repo: str) -> list[str]:
    out = _run(["git", "ls-files"], repo)
    return [line for line in out.splitlines() if line]


def _marker_pattern(markers: Iterable[str]) -> re.Pattern:
    """Match a marker word followed by common decorations.

    Accepts ``TODO:``, ``TODO foo``, ``TODO(user):``, ``FIXME[ABC-123]:``,
    ``HACK!`` and the bare standalone form. Previously only ``MARKER:`` or
    ``MARKER`` followed by whitespace would match — that lost a huge fraction
    of real-world annotations.
    """
    escaped = [re.escape(m) for m in markers]
    body = "(?:[(\\[][^)\\]]*[)\\]])?[:!\\s]?(.*)$"
    return re.compile(r"\b(" + "|".join(escaped) + r")\b" + body)


_HEADER_RE = re.compile(r"^([0-9a-f]{7,40}) (\d+) (\d+)(?: (\d+))?$")


def _blame_file(repo: str, path: str) -> dict[int, dict]:
    """Run ``git blame --porcelain`` once per file and return ``{line: blame}``.

    The original implementation spawned one subprocess per marker, which on a
    repo with 500 TODOs meant 500 ``git blame`` invocations. Batching by file
    drops the cost to N(files-with-markers) — typically <50 — and keeps the
    porcelain parsing trivial because every block is a single-line range
    starting with the commit-id header.
    """
    out = _run(["git", "blame", "--porcelain", "--", path], repo)
    commits: dict[str, dict[str, str | int]] = {}
    lines: dict[int, dict] = {}
    current_commit = ""
    current_lineno = 0

    for raw in out.splitlines():
        header = _HEADER_RE.match(raw)
        if header:
            current_commit = header.group(1)
            current_lineno = int(header.group(3))
            commits.setdefault(current_commit, {"author": "", "author_time": 0, "author_mail": ""})
            lines[current_lineno] = {"commit": current_commit}
            continue
        if not current_commit:
            continue
        record = commits[current_commit]
        if raw.startswith("author "):
            record["author"] = raw[len("author "):].strip()
        elif raw.startswith("author-mail "):
            record["author_mail"] = raw[len("author-mail "):].strip()
        elif raw.startswith("author-time "):
            try:
                record["author_time"] = int(raw[len("author-time "):].strip())
            except ValueError:
                record["author_time"] = 0
        # Lines starting with '\t' are the actual source content — we ignore them.

    # Flatten commit metadata into each line entry.
    for lineno, entry in lines.items():
        commit_meta = commits.get(entry["commit"], {"author": "", "author_time": 0})
        entry["author"] = commit_meta.get("author", "")
        entry["author_time"] = commit_meta.get("author_time", 0)
        entry["author_mail"] = commit_meta.get("author_mail", "")
    return lines


def _blame(repo: str, path: str, line: int, *, cache: dict[str, dict[int, dict]] | None = None) -> dict:
    """Single-line lookup that uses the file-level cache when supplied."""
    if cache is not None:
        if path not in cache:
            cache[path] = _blame_file(repo, path)
        entry = cache[path].get(line, {})
    else:
        entry = _blame_file(repo, path).get(line, {})
    return {
        "author": entry.get("author", ""),
        "commit": entry.get("commit", ""),
        "author_time": int(entry.get("author_time", 0) or 0),
    }


def _age_days(epoch: int, now: dt.datetime | None = None) -> int:
    if epoch <= 0:
        return -1
    now = now or dt.datetime.now(tz=dt.timezone.utc)
    delta = now - dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc)
    return max(0, delta.days)


def _is_git_repo(repo: str) -> bool:
    """A directory is a git repo if `.git` is a dir (normal) OR a file (worktree).
    Fall back to `git rev-parse --is-inside-work-tree` for edge cases like
    GIT_DIR overrides or bare checkouts."""
    git_path = os.path.join(repo, ".git")
    if os.path.exists(git_path):  # file (worktree pointer) or directory
        return True
    res = subprocess.run(
        ["git", "-C", repo, "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True, check=False,
    )
    return res.returncode == 0 and res.stdout.strip() == "true"


def harvest(repo: str, markers: tuple[str, ...] = DEFAULT_MARKERS, min_age: int = 0) -> list[dict]:
    if not _is_git_repo(repo):
        return []
    pat = _marker_pattern(markers)
    hits: list[dict] = []
    blame_cache: dict[str, dict[int, dict]] = {}
    for rel in _list_files(repo):
        abs_path = os.path.join(repo, rel)
        if not os.path.isfile(abs_path) or _is_binary(abs_path):
            continue
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                file_lines: list[tuple[int, str, str]] = []
                for n, line in enumerate(f, 1):
                    m = pat.search(line)
                    if m:
                        marker, text = m.group(1), m.group(2).strip()
                        file_lines.append((n, marker, text))
        except OSError:
            continue
        if not file_lines:
            continue
        # Single ``git blame`` call per file — O(files-with-markers) processes
        # rather than O(markers). See review #1 finding.
        blame_cache[rel] = _blame_file(repo, rel)
        for n, marker, text in file_lines:
            entry = blame_cache[rel].get(n, {})
            age = _age_days(int(entry.get("author_time", 0) or 0))
            if age >= 0 and age < min_age:
                continue
            hits.append({
                "path": rel,
                "line": n,
                "marker": marker,
                "text": text,
                "author": entry.get("author", ""),
                "age_days": age,
                "commit": entry.get("commit", ""),
            })
    hits.sort(key=lambda h: (-h["age_days"], h["path"], h["line"]))
    return hits


def _render_markdown(hits: list[dict]) -> str:
    if not hits:
        return "_No matching markers._\n"
    out = ["| age (d) | marker | file:line | author | note |", "|---|---|---|---|---|"]
    for h in hits:
        note = h["text"].replace("|", "\\|")
        age_cell = "?" if h["age_days"] < 0 else str(h["age_days"])
        out.append(
            f"| {age_cell} | {h['marker']} | {h['path']}:{h['line']} | {h['author']} | {note} |"
        )
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Harvest TODO/FIXME/HACK markers with git blame.")
    p.add_argument("--repo", default=os.getcwd())
    p.add_argument("--markers", default=",".join(DEFAULT_MARKERS),
                   help="Comma-separated marker words.")
    p.add_argument("--min-age", type=int, default=0)
    p.add_argument("--format", choices=["json", "md"], default="json")
    args = p.parse_args(argv)

    markers = tuple(m.strip() for m in args.markers.split(",") if m.strip())
    hits = harvest(args.repo, markers, args.min_age)
    if args.format == "md":
        sys.stdout.write(_render_markdown(hits))
    else:
        json.dump(hits, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
