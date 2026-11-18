"""Real CMake/Ninja/GoogleTest builds. These write solution/ files directly because
the *test* plays the candidate; the interviewer tools never can."""
import shutil

import pytest

from gym import build, session

from .conftest import PROBLEM

pytestmark = [
    pytest.mark.cpp,
    pytest.mark.skipif(build.require_tools() or not (shutil.which("c++") or shutil.which("clang++")),
                       reason="cmake/ninja/compiler not installed"),
]

TESTS = """#include <gtest/gtest.h>
#include "solution.hpp"
TEST(Add, Basic) { EXPECT_EQ(add(2, 3), 5); }
TEST(Add, Negative) { EXPECT_EQ(add(-2, -3), -5); }
"""


def _session(ws, slug, solution, tests=TESTS):
    sid = session.create_session(ws, slug, slug, "dsa", "easy", PROBLEM).id
    sdir = ws.session_dir(sid)
    (sdir / "solution" / "solution.hpp").write_text(solution)
    ws.interviewer_write(sid, "tests/test_solution.cpp", tests, overwrite=True)
    return sid


def test_correct_solution_passes_asan(ws):
    sid = _session(ws, "ok", "#pragma once\ninline int add(int a, int b) { return a + b; }\n")
    s = build.build_and_test(ws, sid, "asan")
    assert s.ok, [st.output_tail for st in s.steps]
    assert (s.tests_passed, s.tests_total) == (2, 2)
    assert session.load_state(ws, sid).builds[-1]["ok"] is True


def test_wrong_answer_reported(ws):
    sid = _session(ws, "wrong", "#pragma once\ninline int add(int a, int b) { return a - b; }\n")
    s = build.build_and_test(ws, sid, "asan")
    assert not s.ok and s.steps[-1].step == "test"
    assert s.tests_total == 2 and s.tests_passed < 2


def test_compile_error_counted(ws):
    sid = _session(ws, "cerr", "#pragma once\ninline int add(int a, int b) { return a + b }\n")
    s = build.build_and_test(ws, sid, "asan")
    assert not s.ok and s.steps[-1].step == "build" and s.compiler_errors >= 1
    assert s.brief()["failed_step"] == "build"


def test_asan_catches_heap_overflow(ws):
    sol = """#pragma once
#include <vector>
inline int add(int a, int b) {
    std::vector<int> v{a, b};
    volatile int i = 2;
    return v.data()[i] == 42 ? 0 : a + b;  // reads one past the end
}
"""
    s = build.build_and_test(ws, _session(ws, "oob", sol), "asan")
    assert not s.ok
    assert any("AddressSanitizer" in line for line in s.sanitizer_reports)


def test_ubsan_catches_signed_overflow(ws):
    sol = "#pragma once\n#include <climits>\ninline int add(int a, int b) { return a + b; }\n"
    tests = TESTS + "TEST(Add, Overflow) { volatile int m = INT_MAX; EXPECT_NE(add(m, 1), 0); }\n"
    s = build.build_and_test(ws, _session(ws, "ub", sol, tests), "asan")
    assert not s.ok
    assert any("runtime error" in line for line in s.sanitizer_reports)


def test_tsan_catches_data_race(ws):
    sol = """#pragma once
#include <thread>
inline int add(int a, int b) {
    int counter = 0;  // shared, unsynchronised
    std::thread t1([&] { for (int i = 0; i < 100000; ++i) ++counter; });
    std::thread t2([&] { for (int i = 0; i < 100000; ++i) ++counter; });
    t1.join(); t2.join();
    return a + b + (counter - counter);
}
"""
    s = build.build_and_test(ws, _session(ws, "race", sol), "tsan")
    if not s.ok and s.steps[-1].step == "test" and "unexpected memory mapping" in s.steps[-1].output_tail:
        pytest.skip("TSan unsupported by this kernel's ASLR settings (vm.mmap_rnd_bits)")
    assert not s.ok
    assert any("ThreadSanitizer" in line for line in s.sanitizer_reports)


def test_deadlock_is_killed(ws, monkeypatch):
    sol = """#pragma once
#include <mutex>
inline int add(int a, int b) {
    static std::mutex m;
    std::lock_guard g1(m);
    std::lock_guard g2(m);  // self-deadlock
    return a + b;
}
"""
    sid = _session(ws, "deadlock", sol)
    monkeypatch.setitem(build.TIMEOUTS, "test", 8)
    s = build.build_and_test(ws, sid, "debug")
    assert not s.ok and s.steps[-1].step == "test"
    assert s.steps[-1].timed_out or "Timeout" in s.steps[-1].output_tail


def test_benchmark_runs_in_release(ws):
    if not shutil.which("c++"):
        pytest.skip("no compiler")
    sid = _session(ws, "bench", "#pragma once\ninline int add(int a, int b) { return a + b; }\n")
    ws.interviewer_write(sid, "bench/bench_solution.cpp", """#include <benchmark/benchmark.h>
#include "solution.hpp"
static void BM_Add(benchmark::State& s) { int x = 0; for (auto _ : s) benchmark::DoNotOptimize(x = add(x, 1)); }
BENCHMARK(BM_Add);
""")
    r = build.run_benchmark(ws, sid)
    if "no bench binary" in r.output_tail:
        pytest.skip("Google Benchmark not installed")
    assert r.ok and "BM_Add" in r.output_tail


def test_solution_cpp_builds_static_lib(ws):
    sid = _session(ws, "lib", "#pragma once\nint add(int a, int b);\n")
    (ws.session_dir(sid) / "solution" / "solution.cpp").write_text(
        '#include "solution.hpp"\nint add(int a, int b) { return a + b; }\n')
    s = build.build_and_test(ws, sid, "asan")
    assert s.ok, [st.output_tail for st in s.steps]
