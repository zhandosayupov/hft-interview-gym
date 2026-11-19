#include <gtest/gtest.h>

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <memory>
#include <string>
#include <thread>
#include <type_traits>
#include <utility>
#include <vector>

#include "solution.hpp"

namespace {

// Counts live instances. Not default-constructible, not copyable.
struct Tracked {
    static inline std::atomic<int> live{0};
    int v;
    explicit Tracked(int x) : v(x) { live.fetch_add(1, std::memory_order_relaxed); }
    Tracked(Tracked&& o) noexcept : v(o.v) {
        o.v = -1;
        live.fetch_add(1, std::memory_order_relaxed);
    }
    Tracked& operator=(Tracked&& o) noexcept {
        v = o.v;
        o.v = -1;
        return *this;
    }
    Tracked(const Tracked&) = delete;
    Tracked& operator=(const Tracked&) = delete;
    ~Tracked() { live.fetch_sub(1, std::memory_order_relaxed); }
};

struct Msg {
    std::uint64_t seq;
    std::uint64_t inv;
    std::uint64_t mul;
};

Msg make_msg(std::uint64_t s) { return Msg{s, ~s, s * 3u}; }
bool msg_ok(const Msg& m, std::uint64_t expected) {
    return m.seq == expected && m.inv == ~expected && m.mul == expected * 3u;
}

}  // namespace

// ---------------------------------------------------------------- interface

TEST(SpscQueue, NotCopyableNotMovable) {
    static_assert(!std::is_copy_constructible_v<SpscQueue<int>>);
    static_assert(!std::is_copy_assignable_v<SpscQueue<int>>);
    static_assert(!std::is_move_constructible_v<SpscQueue<int>>);
    static_assert(!std::is_move_assignable_v<SpscQueue<int>>);
    SUCCEED();
}

// ----------------------------------------------------------------- examples

TEST(SpscQueue, ExampleCapacity3) {
    SpscQueue<int> q(3);
    EXPECT_EQ(q.capacity(), 3u);
    int out = -1;
    EXPECT_FALSE(q.try_pop(out));
    EXPECT_TRUE(q.try_push(1));
    EXPECT_TRUE(q.try_push(2));
    EXPECT_TRUE(q.try_push(3));
    EXPECT_FALSE(q.try_push(4));
    EXPECT_EQ(q.size_approx(), 3u);
    ASSERT_TRUE(q.try_pop(out));
    EXPECT_EQ(out, 1);
    EXPECT_TRUE(q.try_push(4));
    ASSERT_TRUE(q.try_pop(out));
    EXPECT_EQ(out, 2);
    ASSERT_TRUE(q.try_pop(out));
    EXPECT_EQ(out, 3);
    ASSERT_TRUE(q.try_pop(out));
    EXPECT_EQ(out, 4);
    EXPECT_FALSE(q.try_pop(out));
    EXPECT_EQ(q.size_approx(), 0u);
}

TEST(SpscQueue, ExampleCapacity1Reusable) {
    SpscQueue<int> q(1);
    EXPECT_EQ(q.capacity(), 1u);
    int out = 0;
    for (int round = 0; round < 1000; ++round) {
        EXPECT_FALSE(q.try_pop(out));
        EXPECT_TRUE(q.try_push(round));
        EXPECT_FALSE(q.try_push(round + 1));
        EXPECT_EQ(q.size_approx(), 1u);
        ASSERT_TRUE(q.try_pop(out));
        EXPECT_EQ(out, round);
        EXPECT_FALSE(q.try_pop(out));
        EXPECT_EQ(q.size_approx(), 0u);
    }
}

TEST(SpscQueue, ExampleMoveOnlyUniquePtr) {
    SpscQueue<std::unique_ptr<int>> q(2);
    ASSERT_TRUE(q.try_push(std::make_unique<int>(7)));
    ASSERT_TRUE(q.try_push(std::make_unique<int>(8)));
    std::unique_ptr<int> out;
    ASSERT_TRUE(q.try_pop(out));
    ASSERT_NE(out, nullptr);
    EXPECT_EQ(*out, 7);
    ASSERT_TRUE(q.try_pop(out));
    ASSERT_NE(out, nullptr);
    EXPECT_EQ(*out, 8);
    EXPECT_FALSE(q.try_pop(out));
}

// ------------------------------------------------------- single-thread logic

TEST(SpscQueue, ExactCapacityForManySizes) {
    std::vector<std::size_t> caps;
    for (std::size_t c = 1; c <= 40; ++c) caps.push_back(c);
    for (std::size_t c : {63u, 64u, 65u, 1000u, 1023u, 1024u, 1025u}) caps.push_back(c);

    for (std::size_t cap : caps) {
        SpscQueue<std::uint64_t> q(cap);
        ASSERT_EQ(q.capacity(), cap);
        std::uint64_t next = 0;
        std::uint64_t expect = 0;
        // Three rounds so that the indices wrap at least a few times for small caps.
        for (int round = 0; round < 3; ++round) {
            for (std::size_t i = 0; i < cap; ++i) {
                ASSERT_TRUE(q.try_push(std::uint64_t{next})) << "cap=" << cap << " i=" << i;
                ++next;
            }
            EXPECT_EQ(q.size_approx(), cap) << "cap=" << cap;
            ASSERT_FALSE(q.try_push(std::uint64_t{999999})) << "cap=" << cap;
            EXPECT_EQ(q.size_approx(), cap) << "cap=" << cap;
            std::uint64_t out = 0;
            for (std::size_t i = 0; i < cap; ++i) {
                ASSERT_TRUE(q.try_pop(out)) << "cap=" << cap << " i=" << i;
                ASSERT_EQ(out, expect) << "cap=" << cap;
                ++expect;
            }
            ASSERT_FALSE(q.try_pop(out)) << "cap=" << cap;
            EXPECT_EQ(q.size_approx(), 0u) << "cap=" << cap;
        }
    }
}

TEST(SpscQueue, RandomisedAgainstDequeModel) {
    for (std::size_t cap : {1u, 2u, 3u, 5u, 7u, 8u, 13u}) {
        SpscQueue<std::uint64_t> q(cap);
        std::deque<std::uint64_t> model;
        std::uint64_t rng = 0x9E3779B97F4A7C15ull + cap;
        std::uint64_t next = 0;
        for (int step = 0; step < 300000; ++step) {
            rng ^= rng << 13;
            rng ^= rng >> 7;
            rng ^= rng << 17;
            if (rng & 1u) {
                bool ok = q.try_push(std::uint64_t{next});
                ASSERT_EQ(ok, model.size() < cap) << "cap=" << cap << " step=" << step;
                if (ok) model.push_back(next++);
            } else {
                std::uint64_t out = ~0ull;
                bool ok = q.try_pop(out);
                ASSERT_EQ(ok, !model.empty()) << "cap=" << cap << " step=" << step;
                if (ok) {
                    ASSERT_EQ(out, model.front()) << "cap=" << cap << " step=" << step;
                    model.pop_front();
                }
            }
            ASSERT_EQ(q.size_approx(), model.size()) << "cap=" << cap << " step=" << step;
        }
    }
}

TEST(SpscQueue, NonTrivialStrings) {
    SpscQueue<std::string> q(5);
    for (int round = 0; round < 50; ++round) {
        for (int i = 0; i < 5; ++i) {
            ASSERT_TRUE(q.try_push(std::string(100, static_cast<char>('a' + i)) + std::to_string(round)));
        }
        ASSERT_FALSE(q.try_push(std::string(200, 'x')));
        std::string out;
        for (int i = 0; i < 5; ++i) {
            ASSERT_TRUE(q.try_pop(out));
            EXPECT_EQ(out, std::string(100, static_cast<char>('a' + i)) + std::to_string(round));
        }
        ASSERT_FALSE(q.try_pop(out));
    }
}

// --------------------------------------------------------------- lifetimes

TEST(SpscQueue, LifetimeTracking) {
    ASSERT_EQ(Tracked::live.load(), 0);
    {
        SpscQueue<Tracked> q(8);
        EXPECT_EQ(Tracked::live.load(), 0) << "construction must not create T objects";
        for (int i = 0; i < 5; ++i) ASSERT_TRUE(q.try_push(Tracked(i)));
        EXPECT_EQ(Tracked::live.load(), 5);
        Tracked out(-100);
        EXPECT_EQ(Tracked::live.load(), 6);
        ASSERT_TRUE(q.try_pop(out));
        EXPECT_EQ(out.v, 0);
        ASSERT_TRUE(q.try_pop(out));
        EXPECT_EQ(out.v, 1);
        // 3 still in the queue + `out`; popped slots must have been destroyed.
        EXPECT_EQ(Tracked::live.load(), 4);
    }
    EXPECT_EQ(Tracked::live.load(), 0);
}

TEST(SpscQueue, FailedPushDoesNotChangeLiveObjects) {
    ASSERT_EQ(Tracked::live.load(), 0);
    {
        SpscQueue<Tracked> q(2);
        ASSERT_TRUE(q.try_push(Tracked(1)));
        ASSERT_TRUE(q.try_push(Tracked(2)));
        EXPECT_EQ(Tracked::live.load(), 2);
        EXPECT_FALSE(q.try_push(Tracked(3)));
        EXPECT_EQ(Tracked::live.load(), 2);
        Tracked out(0);
        ASSERT_TRUE(q.try_pop(out));
        EXPECT_EQ(out.v, 1);
    }
    EXPECT_EQ(Tracked::live.load(), 0);
}

TEST(SpscQueue, DestroyingWrappedNonEmptyQueueDestroysEachElementOnce) {
    ASSERT_EQ(Tracked::live.load(), 0);
    {
        SpscQueue<Tracked> q(4);
        for (int i = 0; i < 4; ++i) ASSERT_TRUE(q.try_push(Tracked(i)));
        Tracked out(0);
        for (int i = 0; i < 3; ++i) ASSERT_TRUE(q.try_pop(out));
        for (int i = 4; i < 7; ++i) ASSERT_TRUE(q.try_push(Tracked(i)));  // wraps
        EXPECT_EQ(q.size_approx(), 4u);
        EXPECT_EQ(Tracked::live.load(), 5);  // 4 in queue + out
    }
    EXPECT_EQ(Tracked::live.load(), 0);
}

TEST(SpscQueue, DestroyingEmptyAndNeverUsedQueue) {
    ASSERT_EQ(Tracked::live.load(), 0);
    { SpscQueue<Tracked> q(16); }
    {
        SpscQueue<Tracked> q(3);
        ASSERT_TRUE(q.try_push(Tracked(1)));
        Tracked out(0);
        ASSERT_TRUE(q.try_pop(out));
    }
    EXPECT_EQ(Tracked::live.load(), 0);
}

// ---------------------------------------------------- two-thread stress (TSan)

namespace {

struct StressResult {
    std::atomic<std::uint64_t> errors{0};
    std::atomic<std::uint64_t> first_bad{~0ull};
};

void note_error(StressResult& r, std::uint64_t at) {
    std::uint64_t expected = ~0ull;
    r.first_bad.compare_exchange_strong(expected, at);
    r.errors.fetch_add(1, std::memory_order_relaxed);
}

void run_msg_stress(std::size_t cap, std::uint64_t n) {
    SpscQueue<Msg> q(cap);
    StressResult res;
    std::atomic<bool> go{false};

    std::thread consumer([&] {
        while (!go.load(std::memory_order_acquire)) std::this_thread::yield();
        Msg out{};
        std::uint64_t expected = 0;
        while (expected < n) {
            if (q.try_pop(out)) {
                if (!msg_ok(out, expected)) {
                    note_error(res, expected);
                    return;
                }
                ++expected;
            } else {
                std::this_thread::yield();
            }
            if ((expected & 0xFFu) == 0 && q.size_approx() > cap) {
                note_error(res, expected);
                return;
            }
        }
    });

    std::thread producer([&] {
        while (!go.load(std::memory_order_acquire)) std::this_thread::yield();
        for (std::uint64_t i = 0; i < n; ++i) {
            while (!q.try_push(make_msg(i))) {
                if (res.errors.load(std::memory_order_relaxed) != 0) return;
                std::this_thread::yield();
            }
            if ((i & 0xFFu) == 0 && q.size_approx() > cap) {
                note_error(res, i);
                return;
            }
        }
    });

    go.store(true, std::memory_order_release);
    producer.join();
    consumer.join();
    EXPECT_EQ(res.errors.load(), 0u) << "cap=" << cap << " first bad index=" << res.first_bad.load();
    EXPECT_EQ(q.size_approx(), 0u) << "cap=" << cap;
}

}  // namespace

TEST(SpscQueueStress, Capacity1) { run_msg_stress(1, 100000); }
TEST(SpscQueueStress, Capacity2) { run_msg_stress(2, 150000); }
TEST(SpscQueueStress, Capacity7NonPowerOfTwo) { run_msg_stress(7, 300000); }
TEST(SpscQueueStress, Capacity1000NonPowerOfTwo) { run_msg_stress(1000, 300000); }
TEST(SpscQueueStress, Capacity1024) { run_msg_stress(1024, 300000); }

TEST(SpscQueueStress, MoveOnlyHeapPayloadUnderAsanAndTsan) {
    constexpr std::uint64_t n = 100000;
    SpscQueue<std::unique_ptr<std::uint64_t>> q(64);
    StressResult res;
    std::atomic<bool> go{false};

    std::thread consumer([&] {
        while (!go.load(std::memory_order_acquire)) std::this_thread::yield();
        std::unique_ptr<std::uint64_t> out;
        std::uint64_t expected = 0;
        while (expected < n) {
            if (q.try_pop(out)) {
                if (!out || *out != expected) {
                    note_error(res, expected);
                    return;
                }
                out.reset();
                ++expected;
            } else {
                std::this_thread::yield();
            }
        }
    });

    std::thread producer([&] {
        while (!go.load(std::memory_order_acquire)) std::this_thread::yield();
        for (std::uint64_t i = 0; i < n; ++i) {
            auto p = std::make_unique<std::uint64_t>(i);
            while (!q.try_push(std::move(p))) {
                if (res.errors.load(std::memory_order_relaxed) != 0) return;
                std::this_thread::yield();
            }
        }
    });

    go.store(true, std::memory_order_release);
    producer.join();
    consumer.join();
    EXPECT_EQ(res.errors.load(), 0u) << "first bad index=" << res.first_bad.load();
}

TEST(SpscQueueStress, TrackedLifetimesAcrossThreads) {
    ASSERT_EQ(Tracked::live.load(), 0);
    constexpr int n = 50000;
    {
        SpscQueue<Tracked> q(16);
        std::atomic<bool> go{false};
        std::atomic<int> bad{0};

        std::thread consumer([&] {
            while (!go.load(std::memory_order_acquire)) std::this_thread::yield();
            Tracked out(-1);
            // Consume only part of the stream: the queue is destroyed non-empty.
            for (int expected = 0; expected < n - 100;) {
                if (q.try_pop(out)) {
                    if (out.v != expected) {
                        bad.fetch_add(1);
                        return;
                    }
                    ++expected;
                } else {
                    std::this_thread::yield();
                }
            }
        });

        std::thread producer([&] {
            while (!go.load(std::memory_order_acquire)) std::this_thread::yield();
            for (int i = 0; i < n; ++i) {
                // Stop once the consumer is done and the queue stays full.
                int spins = 0;
                while (!q.try_push(Tracked(i))) {
                    if (bad.load() != 0) return;
                    if (++spins > 2000000) return;
                    std::this_thread::yield();
                }
            }
        });

        go.store(true, std::memory_order_release);
        producer.join();
        consumer.join();
        EXPECT_EQ(bad.load(), 0);
    }
    EXPECT_EQ(Tracked::live.load(), 0);
}
