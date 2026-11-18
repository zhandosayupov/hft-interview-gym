import sys

from gym import build


def test_parse_ctest():
    out = "...\n75% tests passed, 1 tests failed out of 4\n"
    assert build.parse_ctest(out) == (3, 4)
    assert build.parse_ctest("100% tests passed, 0 tests failed out of 2") == (2, 2)
    assert build.parse_ctest("no summary") == (None, None)


def test_count_diagnostics():
    out = ("/s/solution/solution.hpp:3:5: error: expected ';'\n"
           "/s/tests/t.cpp:10:1: warning: unused variable 'x' [-Wunused-variable]\n"
           "/s/tests/t.cpp:11:1: warning: shadow\n"
           "In file included from x.cpp:1:\n")
    assert build.count_diagnostics(out) == (1, 2)


def test_sanitizer_lines():
    out = ("==1==ERROR: AddressSanitizer: heap-buffer-overflow on address\n"
           "solution.hpp:4:12: runtime error: signed integer overflow\n"
           "WARNING: ThreadSanitizer: data race (pid=1)\nplain line\n")
    assert len(build.sanitizer_lines(out)) == 3
    assert len(build.sanitizer_lines(out, limit=1)) == 1


def test_tail():
    assert build.tail("abc", 10) == "abc"
    t = build.tail("x" * 100, 10)
    assert t.endswith("x" * 10) and "90 chars omitted" in t


def test_run_step_ok_and_fail(tmp_path):
    ok = build.run_step("s", [sys.executable, "-c", "print('hi')"], str(tmp_path), 10)
    assert ok.ok and "hi" in ok.output_tail
    bad = build.run_step("s", [sys.executable, "-c", "import sys; sys.exit(3)"], str(tmp_path), 10)
    assert not bad.ok and bad.returncode == 3


def test_run_step_timeout_kills_process_group(tmp_path):
    # A child that spawns a grandchild sleeping forever: both must die.
    code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); time.sleep(60)"
    r = build.run_step("test", [sys.executable, "-c", code], str(tmp_path), 1)
    assert r.timed_out and not r.ok
    assert "timed out" in r.output_tail
    assert r.duration_s < 10


def test_bad_preset(ws, session_id):
    import pytest
    with pytest.raises(ValueError):
        build.build_and_test(ws, session_id, "msan")
