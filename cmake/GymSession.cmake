# Shared build logic for every interview session.
# A session's CMakeLists.txt includes this file and calls gym_session().
#
# GYM_CONFIG selects the build flavour (set by CMakePresets.json):
#   asan    - Debug, AddressSanitizer + UndefinedBehaviorSanitizer
#   tsan    - RelWithDebInfo, ThreadSanitizer (concurrency problems)
#   release - Release, -O3 -march=native (benchmarks)
#   debug   - plain Debug, no sanitizers (for gdb/lldb)

include_guard(GLOBAL)

set(GYM_CONFIG "asan" CACHE STRING "asan|tsan|release|debug")
set_property(CACHE GYM_CONFIG PROPERTY STRINGS asan tsan release debug)

if(NOT DEFINED CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 23)
endif()
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Must run at directory scope (inside a function it does not create CTestTestfile).
enable_testing()

function(_gym_apply_flags target)
  target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Wshadow -Wconversion
                                           -Wno-sign-conversion)
  if(GYM_CONFIG STREQUAL "asan")
    target_compile_options(${target} PRIVATE -O1 -g -fno-omit-frame-pointer
                           -fsanitize=address,undefined -fno-sanitize-recover=all)
    target_link_options(${target} PRIVATE -fsanitize=address,undefined)
  elseif(GYM_CONFIG STREQUAL "tsan")
    target_compile_options(${target} PRIVATE -O1 -g -fno-omit-frame-pointer -fsanitize=thread)
    target_link_options(${target} PRIVATE -fsanitize=thread)
  elseif(GYM_CONFIG STREQUAL "release")
    target_compile_options(${target} PRIVATE -O3 -march=native -DNDEBUG)
  elseif(GYM_CONFIG STREQUAL "debug")
    target_compile_options(${target} PRIVATE -O0 -g)
  else()
    message(FATAL_ERROR "Unknown GYM_CONFIG='${GYM_CONFIG}'")
  endif()
endfunction()

function(_gym_find_gtest)
  find_package(GTest CONFIG QUIET)
  if(NOT GTest_FOUND)
    message(STATUS "gym: system GoogleTest not found, fetching v1.15.2 (prefer: apt install libgtest-dev)")
    include(FetchContent)
    FetchContent_Declare(googletest
      GIT_REPOSITORY https://github.com/google/googletest.git
      GIT_TAG v1.15.2
      GIT_SHALLOW TRUE)
    set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
    set(BUILD_GMOCK OFF CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(googletest)
    if(NOT TARGET GTest::gtest_main)
      add_library(GTest::gtest_main ALIAS gtest_main)
    endif()
  endif()
endfunction()

# gym_session(): builds
#   solution  - INTERFACE or STATIC lib from solution/ (candidate's code)
#   tests     - GoogleTest binary from tests/*.cpp, registered with CTest
#   bench     - Google Benchmark binary from bench/*.cpp (only if the library exists)
function(gym_session)
  set(SDIR ${CMAKE_CURRENT_SOURCE_DIR})
  file(GLOB SOLUTION_SRC CONFIGURE_DEPENDS ${SDIR}/solution/*.cpp ${SDIR}/solution/*.cc)
  if(SOLUTION_SRC)
    add_library(solution STATIC ${SOLUTION_SRC})
    target_include_directories(solution PUBLIC ${SDIR}/solution)
    _gym_apply_flags(solution)
    find_package(Threads REQUIRED)
    target_link_libraries(solution PUBLIC Threads::Threads)
  else()
    add_library(solution INTERFACE)
    target_include_directories(solution INTERFACE ${SDIR}/solution)
    find_package(Threads REQUIRED)
    target_link_libraries(solution INTERFACE Threads::Threads)
  endif()

  file(GLOB TEST_SRC CONFIGURE_DEPENDS ${SDIR}/tests/*.cpp)
  if(TEST_SRC)
    _gym_find_gtest()
    add_executable(tests ${TEST_SRC})
    _gym_apply_flags(tests)
    target_link_libraries(tests PRIVATE solution GTest::gtest_main)
    include(GoogleTest)
    gtest_discover_tests(tests DISCOVERY_TIMEOUT 30 PROPERTIES TIMEOUT 60)
  endif()

  file(GLOB BENCH_SRC CONFIGURE_DEPENDS ${SDIR}/bench/*.cpp)
  if(BENCH_SRC)
    find_package(benchmark CONFIG QUIET)
    if(benchmark_FOUND)
      add_executable(bench ${BENCH_SRC})
      _gym_apply_flags(bench)
      target_link_libraries(bench PRIVATE solution benchmark::benchmark_main)
    else()
      message(STATUS "gym: Google Benchmark not found; bench/ skipped (apt install libbenchmark-dev)")
    endif()
  endif()
endfunction()
