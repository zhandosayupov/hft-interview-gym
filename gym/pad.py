"""Local coding pad: a CoderPad-like page for the CANDIDATE, served on localhost.

    python -m gym pad            ->  http://127.0.0.1:8765

The page shows problem.md, edits files in solution/ and runs Build & Test with the
same CMake presets the interviewer uses (results are recorded in session.json, so
the interviewer sees every run). It is the candidate's editor: it writes only
solution/** (Workspace.candidate_write) and is never exposed through MCP.

Security (it can write files and run builds, so it must not be reachable by other
sites in the browser or by other machines):
  * binds 127.0.0.1 by default;
  * rejects requests whose Host header is not an allowed local name (DNS rebinding);
  * POST requires Content-Type: application/json, the header X-Gym-Pad: 1 and a
    same-origin (or absent) Origin header, so a foreign page cannot trigger it.
"""
from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlsplit

from . import build, session
from .workspace import PolicyError, Workspace

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
LOOPBACK_NAMES = frozenset({"127.0.0.1", "localhost", "[::1]"})
MAX_BODY = 1_000_000
PAGE = Path(__file__).with_name("pad.html")
CSP = ("default-src 'self'; "
       "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
       "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
       "img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'")


class HTTPError(Exception):
    def __init__(self, status: HTTPStatus, message: str):
        super().__init__(message)
        self.status = status


def _session_files(ws: Workspace, sid: str, sub: str) -> list[str]:
    base = ws.session_dir(sid) / sub
    if not base.is_dir():
        return []
    return sorted(p.relative_to(ws.session_dir(sid)).as_posix()
                  for p in base.rglob("*") if p.is_file() and "build" not in p.parts)


def session_view(ws: Workspace, sid: str) -> dict:
    state = session.load_state(ws, sid)
    sdir = ws.session_dir(sid)
    problem = sdir / "problem.md"
    return {
        "state": {"id": state.id, "title": state.title, "track": state.track,
                  "difficulty": state.difficulty, "status": state.status,
                  "builds": state.builds[-5:]},
        "problem_md": problem.read_text(encoding="utf-8") if problem.is_file() else "",
        "solution_files": _session_files(ws, sid, "solution"),
        "test_files": _session_files(ws, sid, "tests"),
    }


def read_session_file(ws: Workspace, sid: str, rel: str) -> str:
    sdir = ws.session_dir(sid)
    target = ws.resolve(PurePosixPath("sessions") / sid / rel)
    if sdir not in target.parents:
        raise PolicyError(f"path escapes session: {rel}")
    if "build" in target.relative_to(sdir).parts:
        raise PolicyError("build/ is not served")
    return ws.read_text(target.relative_to(ws.root).as_posix())


class PadServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, ws: Workspace, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 allowed_hosts: set[str] | None = None):
        self.ws = ws
        self.build_lock = threading.Lock()
        names = set(LOOPBACK_NAMES) | set(allowed_hosts or ())
        if host not in {"0.0.0.0", "::", ""}:
            names.add(host)
        self.allowed_hosts = frozenset(names)
        super().__init__((host, port), PadHandler)

    @property
    def url(self) -> str:
        host, port = self.server_address[:2]
        shown = "127.0.0.1" if host in {"0.0.0.0", "::", ""} else host
        return f"http://{shown}:{port}/"


class PadHandler(BaseHTTPRequestHandler):
    server: PadServer
    server_version = "gym-pad"

    def log_message(self, fmt: str, *args) -> None:  # quieter than the default
        if not str(args[0] if args else "").startswith(("GET /api/", "POST /api/save")):
            super().log_message(fmt, *args)

    # ---- helpers -----------------------------------------------------------------
    def _send(self, status: HTTPStatus, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        if ctype.startswith("text/html"):
            self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, obj) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json")

    def _check_host(self) -> None:
        host = self.headers.get("Host", "")
        name = host.rsplit(":", 1)[0] if not host.endswith("]") else host
        if name not in self.server.allowed_hosts:
            raise HTTPError(HTTPStatus.FORBIDDEN, f"host not allowed: {host!r}")

    def _check_post(self) -> dict:
        if self.headers.get("X-Gym-Pad") != "1":
            raise HTTPError(HTTPStatus.FORBIDDEN, "missing X-Gym-Pad header")
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            raise HTTPError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "expected application/json")
        origin = self.headers.get("Origin")
        if origin is not None and origin != f"http://{self.headers.get('Host', '')}":
            raise HTTPError(HTTPStatus.FORBIDDEN, f"cross-origin request refused: {origin}")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise HTTPError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body too large")
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as e:
            raise HTTPError(HTTPStatus.BAD_REQUEST, f"bad JSON: {e}") from e
        if not isinstance(data, dict):
            raise HTTPError(HTTPStatus.BAD_REQUEST, "expected a JSON object")
        return data

    def _dispatch(self, fn) -> None:
        try:
            self._check_host()
            fn()
        except HTTPError as e:
            self._json(e.status, {"error": str(e)})
        except PolicyError as e:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(e)})
        except (FileNotFoundError, NotADirectoryError) as e:
            self._json(HTTPStatus.NOT_FOUND, {"error": f"not found: {e}"})
        except (ValueError, KeyError, TypeError) as e:
            self._json(HTTPStatus.BAD_REQUEST, {"error": f"{type(e).__name__}: {e}"})
        except RuntimeError as e:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})

    # ---- routes ------------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        self._dispatch(self._get)

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch(self._post)

    def _get(self) -> None:
        url = urlsplit(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        ws = self.server.ws
        if url.path in {"/", "/index.html"}:
            self._send(HTTPStatus.OK, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/api/sessions":
            items = [{"id": s.id, "title": s.title, "track": s.track,
                      "difficulty": s.difficulty, "status": s.status}
                     for s in session.list_sessions(ws)]
            self._json(HTTPStatus.OK, {"sessions": items,
                                       "latest": items[-1]["id"] if items else None})
        elif url.path == "/api/session":
            self._json(HTTPStatus.OK, session_view(ws, q["id"]))
        elif url.path == "/api/file":
            self._json(HTTPStatus.OK, {"path": q["path"],
                                       "content": read_session_file(ws, q["session"], q["path"])})
        else:
            raise HTTPError(HTTPStatus.NOT_FOUND, f"no route: {url.path}")

    def _post(self) -> None:
        url = urlsplit(self.path)
        data = self._check_post()
        ws = self.server.ws
        if url.path == "/api/save":
            content = data["content"]
            if not isinstance(content, str):
                raise ValueError("content must be a string")
            p = ws.candidate_write(data["session"], data["path"], content)
            self._json(HTTPStatus.OK, {"saved": p.relative_to(ws.root).as_posix(),
                                       "bytes": len(content.encode())})
        elif url.path == "/api/build":
            preset = data.get("preset", "asan")
            if preset not in build.PRESETS:
                raise ValueError(f"preset must be one of {build.PRESETS}")
            ws.session_dir(data["session"])  # validate before taking the lock
            if not self.server.build_lock.acquire(blocking=False):
                raise HTTPError(HTTPStatus.CONFLICT, "a build is already running")
            try:
                s = build.build_and_test(ws, data["session"], preset)
            finally:
                self.server.build_lock.release()
            self._json(HTTPStatus.OK, {**s.to_dict(), "brief": s.brief()})
        else:
            raise HTTPError(HTTPStatus.NOT_FOUND, f"no route: {url.path}")


def serve(ws: Workspace, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
          allowed_hosts: set[str] | None = None) -> None:
    srv = PadServer(ws, host, port, allowed_hosts)
    print(f"gym pad: {srv.url}  (workspace {ws.root}; Ctrl+C to stop)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
