from __future__ import annotations

from pathlib import Path

from brain_mcp.scope.project_id import resolve_project_id


def test_mcp_roots_wins(tmp_path: Path) -> None:
    (tmp_path / "my-app").mkdir()
    got = resolve_project_id(mcp_roots=[str(tmp_path / "my-app")], cwd=tmp_path)
    assert got == "my-app"


def test_empty_mcp_roots_falls_through(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    got = resolve_project_id(mcp_roots=[], cwd=tmp_path)
    assert got == resolve_project_id(mcp_roots=None, cwd=tmp_path)


def test_git_walk_finds_repo_root(tmp_path: Path) -> None:
    repo = tmp_path / "alpha-repo"
    (repo / ".git").mkdir(parents=True)
    nested = repo / "src" / "inner"
    nested.mkdir(parents=True)
    got = resolve_project_id(mcp_roots=None, cwd=nested)
    assert got == "alpha-repo"


def test_git_file_worktree_is_equivalent_to_dir(tmp_path: Path) -> None:
    repo = tmp_path / "beta"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: ../main/.git\n")
    got = resolve_project_id(mcp_roots=None, cwd=repo)
    assert got == "beta"


def test_no_git_falls_back_to_cwd_basename(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    got = resolve_project_id(mcp_roots=None, cwd=plain)
    assert got == "plain"


def test_unknown_when_everything_fails(tmp_path: Path) -> None:
    weird = tmp_path / "!!!"
    weird.mkdir()
    got = resolve_project_id(mcp_roots=None, cwd=weird)
    assert got == "unknown"


def test_uppercase_and_spaces_slugified(tmp_path: Path) -> None:
    repo = tmp_path / "My Cool App"
    repo.mkdir()
    (repo / ".git").mkdir()
    got = resolve_project_id(mcp_roots=None, cwd=repo)
    assert got == "my-cool-app"
