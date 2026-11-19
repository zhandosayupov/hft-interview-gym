# Order Book Price Levels

## Problem
Implement the passive side of a limit order book for a single instrument. The book stores resting orders, grouped by side and price, and answers market-data style queries. Orders never match each other: an order at a crossing price simply rests, so the book may be crossed.

## Requirements
Each order has a unique 64-bit id, a side, an integer price in ticks, and a quantity.

1. `add_order(id, side, price, qty)` inserts a new resting order. Returns `false` and changes nothing if `id` is already live in the book or `qty == 0`.
2. `cancel_order(id)` removes a live order. Returns `false` if the id is unknown (never added, or already cancelled).
3. `reduce_order(id, new_qty)` lowers the quantity of a live order. Returns `false` and changes nothing unless `0 < new_qty < current_qty`. A successful reduce keeps the order's time priority.
4. `best(side)` returns the best price on that side with its aggregate quantity, or `std::nullopt` if the side is empty. Best is the highest price for Buy and the lowest price for Sell.
5. `depth(side, n)` returns up to `n` price levels, best first, each with its aggregate quantity. Empty levels are never reported.
6. `qty_at(side, price)` returns the aggregate quantity at that exact price, or 0.
7. `front_order(side)` returns the id of the order with the highest time priority at the best price of that side (earliest added among the orders still live), or `std::nullopt` if the side is empty.

Ids are unique across both sides. An id that was cancelled may be added again later and then counts as a new order with new time priority.

## Constraints
- Single-threaded.
- Up to 10^7 operations in total; up to 10^6 live orders at any time.
- Prices are arbitrary `int64_t` values (they may be negative). In practice most activity is clustered near the best price, but your structure must stay correct for any price.
- Quantities fit in `uint32_t` per order. Aggregate quantity per level fits in `uint64_t`.
- Order ids are arbitrary `uint64_t` values, not dense.

## Interface
File: `solution/solution.hpp` (header only is fine; add a `.cpp` if you prefer).

```cpp
#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>

namespace gym {

enum class Side : std::uint8_t { Buy, Sell };

struct Level {
    std::int64_t  price;
    std::uint64_t qty;   // aggregate quantity at this price
};

class OrderBook {
public:
    bool add_order(std::uint64_t id, Side side, std::int64_t price, std::uint32_t qty);
    bool cancel_order(std::uint64_t id);
    bool reduce_order(std::uint64_t id, std::uint32_t new_qty);

    std::optional<Level>         best(Side side) const;
    std::vector<Level>           depth(Side side, std::size_t n) const;
    std::uint64_t                qty_at(Side side, std::int64_t price) const;
    std::optional<std::uint64_t> front_order(Side side) const;
};

}  // namespace gym
```

The tests only read `Level::price` and `Level::qty`. You may add members and helper types, but the public signatures above must not change.

## Examples
```
add_order(1, Buy, 100, 10)   -> true
add_order(2, Buy, 100, 5)    -> true
add_order(3, Buy,  99, 7)    -> true
best(Buy)                    -> {100, 15}
front_order(Buy)             -> 1
depth(Buy, 5)                -> [{100, 15}, {99, 7}]
cancel_order(1)              -> true
front_order(Buy)             -> 2
reduce_order(2, 5)           -> false   // not strictly smaller
reduce_order(2, 3)           -> true
qty_at(Buy, 100)             -> 3
cancel_order(2)              -> true
best(Buy)                    -> {99, 7}
add_order(3, Sell, 101, 1)   -> false   // id 3 is still live
```

## Complexity target
- `add_order`, `cancel_order`, `reduce_order`: at most O(log L) where L is the number of non-empty price levels; O(1) expected is better.
- `best`, `front_order`: O(1) or O(log L).
- `depth(side, n)`: O(n) plus the cost of locating the best level.
- You must be able to state and defend the complexity of every operation, including worst cases.

## Edge cases to consider
- Empty book and empty side.
- Duplicate or reused ids.
- Zero and boundary quantities.
- Removing the last order at a level, and removing the best level.
- Many orders at one price versus many distinct prices.
- Negative and extreme prices.
- Requests for more levels than exist, and `n == 0`.
- Time priority after cancels and reduces.

## Out of scope
- Order matching and trade generation.
- Thread safety.
- Order types other than plain limit orders.
- Persistence and serialization.
