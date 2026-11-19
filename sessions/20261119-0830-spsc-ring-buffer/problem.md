# Bounded Lock-Free Queue for Two Threads

## Problem
In a market-data pipeline, one thread decodes packets and hands messages to exactly one strategy thread. Implement a fixed-capacity, wait-free queue for this one-producer, one-consumer hand-off. The producer must never block on the consumer, and the consumer must never block on the producer.

## Requirements
- Exactly one producer thread calls `try_push`; exactly one consumer thread calls `try_pop`. Roles never change during the lifetime of the queue.
- `try_push` returns `false` when the queue is full and leaves the queue unchanged. `try_pop` returns `false` when the queue is empty.
- Elements are delivered in FIFO order, each exactly once, with no loss and no duplication.
- The element type `T` may be move-only and non-trivially destructible. Every element that was pushed and not popped must be destroyed exactly once when the queue is destroyed; popped elements must not be destroyed twice.
- No mutex, no `std::condition_variable`, no syscalls on the hot path.
- The queue stores elements in storage owned by the queue itself. After construction, push and pop must not allocate.
- `size_approx()` may be called from either thread and must be safe to call concurrently (no data race), but may return a stale value.

## Constraints
- C++20, GCC or Clang on x86-64. Must be clean under AddressSanitizer and ThreadSanitizer.
- The capacity passed to the constructor is at least 1 and at most 2^20. It is not necessarily a power of two. The queue must be able to hold exactly `capacity` elements at the same time.
- `T` is not required to be default-constructible or copyable.
- The queue object itself is neither copyable nor movable.

## Interface
```cpp
// solution/solution.hpp
#pragma once
#include <cstddef>

template <typename T>
class SpscQueue {
public:
    explicit SpscQueue(std::size_t capacity);
    ~SpscQueue();

    SpscQueue(const SpscQueue&) = delete;
    SpscQueue& operator=(const SpscQueue&) = delete;

    bool try_push(T&& value);        // producer thread only
    bool try_pop(T& out);            // consumer thread only; moves the element into `out`
    std::size_t size_approx() const; // any thread
    std::size_t capacity() const;    // any thread
};
```

## Examples
- Capacity 3: push 1, 2, 3 succeed; push 4 fails; pop returns 1; push 4 now succeeds; pops return 2, 3, 4; the next pop fails.
- Capacity 1: push succeeds, second push fails; pop succeeds, second pop fails; the queue is reusable afterwards.
- `SpscQueue<std::unique_ptr<int>>` works with `try_push(std::make_unique<int>(7))`.

## Complexity target
- `try_push` and `try_pop`: O(1) worst case, wait-free.
- No heap allocation after construction.
- Memory: O(capacity) plus a constant amount of bookkeeping.

## Edge cases to consider
- Capacity extremes and non-power-of-two capacities
- Index wrap-around, including after a very large number of operations
- Distinguishing full from empty
- Move-only and non-trivially destructible element types, and their lifetimes
- Destruction of a non-empty queue
- Memory ordering between producer and consumer
- Cache-line interaction between the two threads' state

## Out of scope
- Multiple producers or multiple consumers
- Blocking or waiting variants, batching APIs, bulk operations
- Resizing, iteration, or peeking at elements
- Cross-process or shared-memory placement
