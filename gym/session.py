"""Session lifecycle: create a session directory from the template and track state."""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from .workspace import PolicyError, Workspace

TRACKS = ("dsa", "cpp", "concurrency", "low-latency", "systems", "networking", "system-design")
DIFFICULTIES = ("easy", "medium", "hard")
STATUSES = ("setup", "discussion", "coding", "review", "done")
STATE_FILE = "session.json"
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")


@dataclass
class SessionState:
    id: str
    title: str
    track: str
    difficulty: str
    created_at: str
    status: str = "setup"
    builds: list[dict] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def validate_slug(slug: str) -> str:
    if not _SLUG_RE.match(slug):
        raise PolicyError("slug must be lowercase [a-z0-9-], 1-48 chars, e.g. 'spsc-queue'")
    return slug


def create_session(ws: Workspace, slug: str, title: str, track: str, difficulty: str,
                   problem_md: str, now: datetime | None = None) -> SessionState:
    validate_slug(slug)
    if track not in TRACKS:
        raise ValueError(f"track must be one of {TRACKS}")
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"difficulty must be one of {DIFFICULTIES}")
    if not problem_md.strip():
        raise ValueError("problem_md must not be empty")
    now = now or _now()
    session_id = f"{now:%Y%m%d-%H%M}-{slug}"
    template = ws.root / "template" / "session"
    if not template.is_dir():
        raise FileNotFoundError(f"template missing: {template}")
    ws.sessions_dir.mkdir(parents=True, exist_ok=True)
    dest = ws.sessions_dir / session_id
    if dest.exists():
        raise FileExistsError(f"session already exists: {session_id}")
    shutil.copytree(template, dest)
    (dest / "problem.md").write_text(problem_md.rstrip() + "\n", encoding="utf-8")
    state = SessionState(session_id, title, track, difficulty, now.isoformat(timespec="seconds"))
    save_state(ws, state)
    return state


def load_state(ws: Workspace, session_id: str) -> SessionState:
    path = ws.session_dir(session_id) / STATE_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    return SessionState(**data)


def save_state(ws: Workspace, state: SessionState) -> None:
    path = ws.sessions_dir / state.id / STATE_FILE
    path.write_text(state.to_json(), encoding="utf-8")


def set_status(ws: Workspace, session_id: str, status: str) -> SessionState:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    state = load_state(ws, session_id)
    state.status = status
    save_state(ws, state)
    return state


def list_sessions(ws: Workspace) -> list[SessionState]:
    if not ws.sessions_dir.is_dir():
        return []
    out = []
    for d in sorted(ws.sessions_dir.iterdir()):
        if (d / STATE_FILE).is_file():
            out.append(load_state(ws, d.name))
    return out


def latest_session(ws: Workspace) -> SessionState | None:
    sessions = list_sessions(ws)
    return sessions[-1] if sessions else None
