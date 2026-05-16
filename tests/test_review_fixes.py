"""Regression tests for todo-harvest review findings."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import harvest  # noqa: E402


def test_marker_pattern_accepts_paren_decoration():
    pat = harvest._marker_pattern(("TODO",))
    m = pat.search("// TODO(user): rename this")
    assert m is not None
    assert m.group(1) == "TODO"
    assert m.group(2).strip() == "rename this"


def test_marker_pattern_accepts_bracket_decoration():
    pat = harvest._marker_pattern(("FIXME",))
    m = pat.search("// FIXME[ABC-123]: do not ship")
    assert m is not None
    assert m.group(1) == "FIXME"


def test_marker_pattern_accepts_exclamation():
    pat = harvest._marker_pattern(("HACK",))
    m = pat.search("/* HACK! avoid this in prod */")
    assert m is not None
    assert m.group(1) == "HACK"


def test_marker_pattern_still_matches_bare_form():
    pat = harvest._marker_pattern(("TODO",))
    assert pat.search("# TODO: write docs") is not None


def _setup_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "-c", "init.defaultBranch=main", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    return repo


def test_blame_runs_once_per_file(tmp_path, monkeypatch):
    """harvest() must call git blame at most once per file containing markers,
    not once per marker (review #1 critical perf finding)."""
    repo = _setup_repo(tmp_path)
    src = repo / "a.py"
    src.write_text("# TODO: a\n# TODO: b\n# TODO: c\n# TODO: d\n")
    subprocess.run(["git", "-C", str(repo), "add", "a.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "x"], check=True)

    blame_calls: list[list[str]] = []
    real_run = harvest._run

    def counting_run(args, cwd):
        if len(args) >= 2 and args[0] == "git" and args[1] == "blame":
            blame_calls.append(list(args))
        return real_run(args, cwd)

    monkeypatch.setattr(harvest, "_run", counting_run)
    hits = harvest.harvest(str(repo))
    assert len(hits) == 4
    assert len(blame_calls) == 1  # one file → one blame


def test_age_minus_one_renders_as_question_mark():
    hits = [{"age_days": -1, "marker": "TODO", "path": "x.py", "line": 1,
             "author": "u", "text": "note"}]
    md = harvest._render_markdown(hits)
    assert "| ? | TODO " in md
