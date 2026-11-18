"""Read-only git views. No command here mutates the repository."""
from __future__ import annotations

import subprocess

from .build import tail
from .workspace import Workspace

_READ_ONLY = {"status", "diff", "log"}


def _git(ws: Workspace, *args: str, timeout: int = 20) -> str:
    if not args or args[0] not in _READ_ONLY:
        raise PermissionError(f"git subcommand not allowed: {args[:1]}")
    r = subprocess.run(["git", "-C", str(ws.root), "--no-pager", *args], capture_output=True,
                       text=True, errors="replace", timeout=timeout)
    if r.returncode != 0:
        return f"[git exited {r.returncode}] {r.stderr.strip()}"
    return r.stdout


def status(ws: Workspace) -> str:
    return _git(ws, "status", "--short", "--branch")


def diff(ws: Workspace, path: str = "sessions", staged: bool = False, max_chars: int = 20000) -> str:
    ws.resolve(path)  # policy check
    args = ["diff", "--stat", "--patch", "--no-color"]
    if staged:
        args.append("--cached")
    out = _git(ws, *args, "--", path)
    untracked = _git(ws, "status", "--porcelain", "--untracked-files=all", "--", path)
    new_files = [l[3:] for l in untracked.splitlines() if l.startswith("??")]
    if new_files:
        out += "\n# untracked files (not in diff; read them with read_file):\n" + "\n".join(new_files)
    return tail(out, max_chars) if out.strip() else "(no changes)"


def log(ws: Workspace, n: int = 10) -> str:
    return _git(ws, "log", f"-{max(1, min(n, 50))}", "--oneline", "--decorate")
