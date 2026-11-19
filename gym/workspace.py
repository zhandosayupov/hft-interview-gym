"""Workspace sandbox: every path the interviewer touches goes through here.

Policy (enforced in code, not just in the prompt):
  * All paths must resolve inside the workspace root (symlinks resolved).
  * The interviewer may READ any file under sessions/ and the repo docs.
  * The interviewer may WRITE only: problem.md, tests/**, bench/**, and the
    session report/transcript files. It may never write into solution/**.
  * Nothing is ever deleted by the tools.
  * The local pad (gym/pad.py) is the CANDIDATE's editor: it may write only
    solution/** source files (candidate_write). It is never exposed via MCP.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Relative to a session directory.
WRITABLE_FILES = frozenset({"problem.md", "notes.md"})
WRITABLE_DIRS = ("tests", "bench")
SOLUTION_DIR = "solution"
CANDIDATE_SUFFIXES = frozenset({".hpp", ".h", ".hh", ".ipp", ".cpp", ".cc", ".cxx"})
MAX_WRITE_BYTES = 500_000
MAX_READ_BYTES = 200_000
TEXT_SUFFIXES = frozenset(
    {".md", ".txt", ".json", ".cpp", ".cc", ".cxx", ".hpp", ".h", ".hh", ".ipp",
     ".cmake", ".py", ".sh", ".yml", ".yaml", ".toml", ".log", ""}
)


class PolicyError(PermissionError):
    """Raised when a request violates the workspace policy."""


def default_root() -> Path:
    env = os.environ.get("GYM_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Workspace:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root).expanduser().resolve())

    @classmethod
    def from_env(cls) -> "Workspace":
        return cls(default_root())

    @property
    def sessions_dir(self) -> Path:
        return self.root / "sessions"

    def resolve(self, rel: str | os.PathLike[str]) -> Path:
        """Resolve a workspace-relative path; reject anything that escapes."""
        rel_str = os.fspath(rel)
        if "\x00" in rel_str:
            raise PolicyError("null byte in path")
        p = Path(rel_str)
        if p.is_absolute():
            candidate = p.resolve()
        else:
            candidate = (self.root / p).resolve()
        root = self.root.resolve()
        if candidate != root and root not in candidate.parents:
            raise PolicyError(f"path escapes workspace: {rel_str}")
        return candidate

    def session_dir(self, session_id: str) -> Path:
        if not session_id or "/" in session_id or "\\" in session_id or session_id in {".", ".."}:
            raise PolicyError(f"invalid session id: {session_id!r}")
        d = self.resolve(PurePosixPath("sessions") / session_id)
        if not d.is_dir():
            raise FileNotFoundError(f"no such session: {session_id}")
        return d

    def read_text(self, rel: str, max_bytes: int = MAX_READ_BYTES) -> str:
        p = self.resolve(rel)
        if not p.is_file():
            raise FileNotFoundError(rel)
        if p.suffix.lower() not in TEXT_SUFFIXES and p.name not in {"CMakeLists.txt"}:
            raise PolicyError(f"refusing to read non-text file: {rel}")
        data = p.read_bytes()
        truncated = len(data) > max_bytes
        text = data[:max_bytes].decode("utf-8", errors="replace")
        if truncated:
            text += f"\n\n[... truncated: {len(data) - max_bytes} more bytes ...]"
        return text

    def check_interviewer_write(self, session_id: str, rel_in_session: str) -> Path:
        """Return the absolute target path if the interviewer may write it."""
        sdir = self.session_dir(session_id)
        target = (sdir / rel_in_session).resolve()
        if sdir not in target.parents:
            raise PolicyError(f"path escapes session: {rel_in_session}")
        parts = target.relative_to(sdir).parts
        if parts[0] == SOLUTION_DIR:
            raise PolicyError(
                "solution/ belongs to the candidate; the interviewer must not write it"
            )
        if len(parts) == 1 and parts[0] in WRITABLE_FILES:
            return target
        if len(parts) >= 2 and parts[0] in WRITABLE_DIRS:
            return target
        raise PolicyError(
            f"interviewer may write only {sorted(WRITABLE_FILES)} or {list(WRITABLE_DIRS)}/**; got {rel_in_session}"
        )

    def interviewer_write(self, session_id: str, rel_in_session: str, content: str,
                          overwrite: bool = False) -> Path:
        target = self.check_interviewer_write(session_id, rel_in_session)
        if target.exists() and not overwrite:
            raise PolicyError(f"{rel_in_session} exists; pass overwrite=true to replace it")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def check_candidate_write(self, session_id: str, rel_in_session: str) -> Path:
        """Return the absolute target if the candidate's pad may write it: solution/** sources only."""
        sdir = self.session_dir(session_id)
        target = (sdir / rel_in_session).resolve()
        if sdir not in target.parents:
            raise PolicyError(f"path escapes session: {rel_in_session}")
        parts = target.relative_to(sdir).parts
        if len(parts) < 2 or parts[0] != SOLUTION_DIR:
            raise PolicyError(f"the pad writes only {SOLUTION_DIR}/**; got {rel_in_session}")
        if target.suffix.lower() not in CANDIDATE_SUFFIXES:
            raise PolicyError(f"only C++ sources {sorted(CANDIDATE_SUFFIXES)}; got {rel_in_session}")
        return target

    def candidate_write(self, session_id: str, rel_in_session: str, content: str) -> Path:
        target = self.check_candidate_write(session_id, rel_in_session)
        if len(content.encode()) > MAX_WRITE_BYTES:
            raise PolicyError(f"file too large (> {MAX_WRITE_BYTES} bytes)")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def list_files(self, rel: str = "sessions", max_entries: int = 500) -> list[str]:
        base = self.resolve(rel)
        if not base.is_dir():
            raise NotADirectoryError(rel)
        out: list[str] = []
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in {"build", ".git", "__pycache__"})
            for f in sorted(filenames):
                out.append(Path(dirpath, f).relative_to(self.root).as_posix())
                if len(out) >= max_entries:
                    return out
        return out
