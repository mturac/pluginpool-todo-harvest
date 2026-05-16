"""Tests for harvest.py — hermetic temp git repos."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "harvest.py"


def _git(repo: Path, *args: str) -> None:
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": "Test User",
        "GIT_AUTHOR_EMAIL": "test@pluginpool.local",
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "test@pluginpool.local",
    })
    subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


def _init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@pluginpool.local")
    _git(repo, "config", "user.name", "Test User")


def _commit(repo: Path, message: str = "seed") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_works():
    r = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "marker" in r.stdout.lower()


def test_detects_default_markers(tmp_path):
    _init(tmp_path)
    (tmp_path / "a.py").write_text(
        "x = 1  # TODO: refactor this\n"
        "y = 2  # FIXME: handle edge case\n"
        "z = 3  # HACK temporary\n"
    )
    _commit(tmp_path)
    r = _run("--repo", str(tmp_path), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    markers = sorted(h["marker"] for h in data)
    assert markers == ["FIXME", "HACK", "TODO"]


def test_custom_marker_filter(tmp_path):
    _init(tmp_path)
    (tmp_path / "a.py").write_text("# TODO: x\n# FIXME: y\n# HACK: z\n")
    _commit(tmp_path)
    r = _run("--repo", str(tmp_path), "--markers", "FIXME", cwd=tmp_path)
    data = json.loads(r.stdout)
    assert len(data) == 1
    assert data[0]["marker"] == "FIXME"


def test_age_days_non_negative(tmp_path):
    _init(tmp_path)
    (tmp_path / "a.py").write_text("# TODO: soon\n")
    _commit(tmp_path)
    r = _run("--repo", str(tmp_path), cwd=tmp_path)
    data = json.loads(r.stdout)
    assert data
    assert data[0]["age_days"] >= 0
    assert data[0]["author"] == "Test User"


def test_markdown_render(tmp_path):
    _init(tmp_path)
    (tmp_path / "a.py").write_text("# TODO: refactor\n")
    _commit(tmp_path)
    r = _run("--repo", str(tmp_path), "--format", "md", cwd=tmp_path)
    assert "| age" in r.stdout
    assert "TODO" in r.stdout
    assert "a.py:1" in r.stdout


def test_min_age_filter(tmp_path):
    _init(tmp_path)
    (tmp_path / "a.py").write_text("# TODO: brand new\n")
    _commit(tmp_path)
    r = _run("--repo", str(tmp_path), "--min-age", "9999", cwd=tmp_path)
    data = json.loads(r.stdout)
    assert data == []


def test_binary_file_skipped(tmp_path):
    _init(tmp_path)
    (tmp_path / "bin.dat").write_bytes(b"\x00\x01TODO not a real todo\n")
    (tmp_path / "a.py").write_text("# TODO: real\n")
    _commit(tmp_path)
    r = _run("--repo", str(tmp_path), cwd=tmp_path)
    data = json.loads(r.stdout)
    paths = {h["path"] for h in data}
    assert "bin.dat" not in paths
    assert "a.py" in paths


def test_non_git_dir_returns_empty(tmp_path):
    r = _run("--repo", str(tmp_path), cwd=tmp_path)
    assert r.returncode == 0
    assert json.loads(r.stdout) == []


def test_worktree_with_gitdir_file(tmp_path):
    """In a git worktree the repo has a `.git` FILE pointing at the gitdir, not a dir.
    todo-harvest must still detect it as a repo."""
    main_repo = tmp_path / "main"
    _init(main_repo)
    (main_repo / "a.py").write_text("# TODO: x\n")
    _commit(main_repo, "init")
    wt = tmp_path / "wt"
    _git(main_repo, "worktree", "add", str(wt))
    # The worktree's `.git` is a file, not a directory
    assert (wt / ".git").is_file()
    (wt / "b.py").write_text("# FIXME: y\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "wt")
    r = _run("--repo", str(wt), cwd=wt)
    data = json.loads(r.stdout)
    paths = sorted(h["path"] for h in data)
    # a.py was committed in main, b.py in worktree — both should surface here
    assert "b.py" in paths
