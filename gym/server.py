"""MCP stdio server. Run: python -m gym.server  (GYM_ROOT=<repo root> optional)."""
from __future__ import annotations

import functools

from . import tools

try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as _Server
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server
    from mcp.server.fastmcp.exceptions import ToolError

INSTRUCTIONS = (
    "Local tools for an HFT mock interview. Call get_interviewer_guide first. "
    "Never attempt to write the candidate's solution; no tool allows it."
)

# Expected failures: surface the message to the model instead of a generic error.
_EXPECTED = (PermissionError, ValueError, FileNotFoundError, FileExistsError,
             NotADirectoryError, RuntimeError, TypeError)


def _surface_errors(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except _EXPECTED as e:
            raise ToolError(f"{type(e).__name__}: {e}") from e
    return wrapper


def build_server():
    server = _Server(name="hft-gym", instructions=INSTRUCTIONS)
    for fn in tools.ALL_TOOLS:
        server.tool()(_surface_errors(fn))
    return server


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
