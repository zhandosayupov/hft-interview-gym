"""Run CMake presets (configure/build/test/bench) for a session and summarise output.

The interviewer uses this to *observe* the candidate's build. It never edits code.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from .session import load_state, save_state
from .workspace import Workspace

PRESETS = ("asan", "tsan", "release", "debug")
TIMEOUTS = {"configure": 300, "build": 300, "test": 180, "bench": 120}
TAIL_CHARS = 6000

_CTEST_SUMMARY = re.compile(r"(\d+)% tests passed, (\d+) tests failed out of (\d+)")
_SANITIZER = re.compile(
    r"(ERROR: AddressSanitizer|runtime error:|WARNING: ThreadSanitizer|ERROR: LeakSanitizer)"
)
_COMPILER_DIAG = re.compile(r"^[^\s:][^:]*:\d+:\d+: (error|warning): ", re.MULTILINE)


@dataclass
class StepResult:
    step: str
    command: list[str]
    returncode: int | None
    duration_s: float
    output_tail: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


@dataclass
class RunSummary:
    session_id: str
    preset: str
    ok: bool
    steps: list[StepResult] = field(default_factory=list)
    tests_passed: int | None = None
    tests_total: int | None = None
    compiler_errors: int = 0
    compiler_warnings: int = 0
    sanitizer_reports: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        for s in d["steps"]:
            s["ok"] = s["returncode"] == 0 and not s["timed_out"]
        return d

    def brief(self) -> dict:
        return {
            "preset": self.preset,
            "ok": self.ok,
            "failed_step": next((s.step for s in self.steps if not s.ok), None),
            "tests_passed": self.tests_passed,
            "tests_total": self.tests_total,
            "compiler_errors": self.compiler_errors,
            "compiler_warnings": self.compiler_warnings,
            "sanitizer_reports": len(self.sanitizer_reports),
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }


def tail(text: str, n: int = TAIL_CHARS) -> str:
    if len(text) <= n:
        return text
    return f"[... {len(text) - n} chars omitted ...]\n" + text[-n:]


def parse_ctest(output: str) -> tuple[int | None, int | None]:
    m = _CTEST_SUMMARY.search(output)
    if not m:
        return None, None
    failed, total = int(m.group(2)), int(m.group(3))
    return total - failed, total


def count_diagnostics(output: str) -> tuple[int, int]:
    errors = warnings = 0
    for m in _COMPILER_DIAG.finditer(output):
        if m.group(1) == "error":
            errors += 1
        else:
            warnings += 1
    return errors, warnings


def sanitizer_lines(output: str, limit: int = 10) -> list[str]:
    out = []
    for line in output.splitlines():
        if _SANITIZER.search(line):
            out.append(line.strip())
            if len(out) >= limit:
                break
    return out


def run_step(step: str, cmd: list[str], cwd: str, timeout: int,
             env: dict[str, str] | None = None) -> StepResult:
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        errors="replace", start_new_session=True, env=env,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        # Kill the whole process group: a deadlocked test must not survive.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, _ = proc.communicate()
        out = (out or "") + f"\n[gym] {step} timed out after {timeout}s (deadlock or infinite loop?)"
        timed_out = True
    return StepResult(step, cmd, proc.returncode, round(time.monotonic() - start, 2),
                      out or "", timed_out)


def require_tools() -> list[str]:
    return [t for t in ("cmake", "ninja", "ctest") if shutil.which(t) is None]


def build_and_test(ws: Workspace, session_id: str, preset: str = "asan",
                   run_tests: bool = True, record: bool = True) -> RunSummary:
    if preset not in PRESETS:
        raise ValueError(f"preset must be one of {PRESETS}")
    missing = require_tools()
    if missing:
        raise RuntimeError(f"missing tools on PATH: {missing}")
    sdir = str(ws.session_dir(session_id))
    summary = RunSummary(session_id, preset, ok=False)
    plan = [("configure", ["cmake", "--preset", preset]),
            ("build", ["cmake", "--build", "--preset", preset])]
    if run_tests:
        plan.append(("test", ["ctest", "--preset", preset]))
    full_output = []
    for step, cmd in plan:
        r = run_step(step, cmd, sdir, TIMEOUTS[step])
        full_output.append(r.output_tail)
        if step == "build":
            summary.compiler_errors, summary.compiler_warnings = count_diagnostics(r.output_tail)
        if step == "test":
            summary.tests_passed, summary.tests_total = parse_ctest(r.output_tail)
        r.output_tail = tail(r.output_tail)
        summary.steps.append(r)
        if not r.ok:
            break
    summary.sanitizer_reports = sanitizer_lines("\n".join(full_output))
    summary.ok = all(s.ok for s in summary.steps) and len(summary.steps) == len(plan)
    if record:
        state = load_state(ws, session_id)
        state.builds.append(summary.brief())
        save_state(ws, state)
    return summary


def run_benchmark(ws: Workspace, session_id: str, filter_regex: str = "") -> StepResult:
    """Build the release preset and run bench/ (Google Benchmark)."""
    s = build_and_test(ws, session_id, "release", run_tests=False, record=False)
    sdir = ws.session_dir(session_id)
    if not s.ok:
        return s.steps[-1]
    exe = sdir / "build" / "release" / "bench"
    if not exe.is_file():
        return StepResult("bench", [str(exe)], None, 0.0,
                          "no bench binary: add bench/*.cpp and install libbenchmark-dev")
    cmd = [str(exe), "--benchmark_repetitions=3", "--benchmark_report_aggregates_only=true"]
    if filter_regex:
        cmd.append(f"--benchmark_filter={filter_regex}")
    r = run_step("bench", cmd, str(sdir), TIMEOUTS["bench"])
    r.output_tail = tail(r.output_tail)
    return r
