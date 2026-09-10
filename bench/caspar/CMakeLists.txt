cmake_minimum_required(VERSION 3.20)
project(caspar_bal LANGUAGES CXX CUDA)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CUDA_STANDARD 17)
set(CASPAR_GENERATED_DIR "" CACHE PATH "COLMAP generated/f64 directory")
if(NOT EXISTS "${CASPAR_GENERATED_DIR}/CMakeLists.txt")
  message(FATAL_ERROR "Set CASPAR_GENERATED_DIR to COLMAP generated/f64")
endif()
add_subdirectory("${CASPAR_GENERATED_DIR}" caspar)
# Upstream declares initial_score but does not assign it at this pinned revision.
# Instrument a build-local copy; leave the algorithm and upstream checkout intact.
file(READ "${CASPAR_GENERATED_DIR}/solver.cc" CASPAR_SOLVER_TEXT)
string(FIND "${CASPAR_SOLVER_TEXT}" "result.initial_score = score_best;" HAS_INITIAL)
if(HAS_INITIAL EQUAL -1)
  string(FIND "${CASPAR_SOLVER_TEXT}" "score_best = DoResJacFirst();" INITIAL_SITE)
  if(INITIAL_SITE EQUAL -1)
    message(FATAL_ERROR "Caspar initial-score instrumentation needs review")
  endif()
  string(REPLACE "score_best = DoResJacFirst();"
    "score_best = DoResJacFirst();\n  result.initial_score = score_best;"
    CASPAR_SOLVER_TEXT "${CASPAR_SOLVER_TEXT}")
endif()
# Optional wall-budget guard in the build-local copy. Discard an unfinished
# outer candidate rather than allowing overshoot work to improve the endpoint.
string(PREPEND CASPAR_SOLVER_TEXT "#include <cstdlib>\n#include <cmath>\n")
string(REPLACE "score_best = DoResJacFirst();"
  "const char* budget_env = std::getenv(\"CASPAR_MAX_SECONDS\");\n  const double budget_seconds = budget_env ? std::atof(budget_env) : 0.0;\n  if (budget_env && !(std::isfinite(budget_seconds) && budget_seconds > 0)) throw std::runtime_error(\"invalid CASPAR_MAX_SECONDS\");\n  auto budget_expired = [&]() { return budget_seconds > 0 && std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count() > budget_seconds; };\n  score_best = DoResJacFirst();"
  CASPAR_SOLVER_TEXT "${CASPAR_SOLVER_TEXT}")
string(REPLACE "if (solver_iter_ != 0 && solver_iter_ < params_.solver_iter_max - 1) {"
  "if (budget_expired()) { printf(\"BUDGET stop=before_iteration seconds=%.9g\\n\", budget_seconds); break; }\n    if (solver_iter_ != 0 && solver_iter_ < params_.solver_iter_max - 1) {"
  CASPAR_SOLVER_TEXT "${CASPAR_SOLVER_TEXT}")
string(FIND "${CASPAR_SOLVER_TEXT}" "const float diag_current = diag;" BUDGET_COMMIT_FLOAT)
string(FIND "${CASPAR_SOLVER_TEXT}" "const double diag_current = diag;" BUDGET_COMMIT_DOUBLE)
if(BUDGET_COMMIT_FLOAT EQUAL -1 AND BUDGET_COMMIT_DOUBLE EQUAL -1)
  message(FATAL_ERROR "Caspar budget commit instrumentation needs review")
endif()
foreach(BUDGET_TYPE float double)
  string(REPLACE "const ${BUDGET_TYPE} diag_current = diag;"
    "if (budget_expired()) { printf(\"BUDGET stop=before_commit seconds=%.9g\\n\", budget_seconds); break; }\n    const ${BUDGET_TYPE} diag_current = diag;"
    CASPAR_SOLVER_TEXT "${CASPAR_SOLVER_TEXT}")
endforeach()
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/solver_instrumented.cc" "${CASPAR_SOLVER_TEXT}")
get_target_property(CASPAR_SOURCES caspar_lib_core SOURCES)
list(FILTER CASPAR_SOURCES EXCLUDE REGEX "(^|/)solver\\.cc$")
# Relative source paths belong to the generated directory, not this directory.
list(TRANSFORM CASPAR_SOURCES PREPEND "${CASPAR_GENERATED_DIR}/")
list(APPEND CASPAR_SOURCES "${CMAKE_CURRENT_BINARY_DIR}/solver_instrumented.cc")
set_property(TARGET caspar_lib_core PROPERTY SOURCES "${CASPAR_SOURCES}")
option(CASPAR_DRIVER_FLOAT "Build float driver with fp64 endpoint verification" OFF)
option(CASPAR_DRIVER_CHECKED_DOUBLE "Build double driver with target stopping and state export" OFF)
if(CASPAR_DRIVER_FLOAT AND CASPAR_DRIVER_CHECKED_DOUBLE)
  message(FATAL_ERROR "Select only one checked driver precision")
endif()
if(CASPAR_DRIVER_FLOAT)
  add_executable(caspar_bal caspar_bal32_checked.cc)
elseif(CASPAR_DRIVER_CHECKED_DOUBLE)
  add_executable(caspar_bal caspar_bal64_checked.cc)
else()
  add_executable(caspar_bal caspar_bal.cc)
endif()
target_link_libraries(caspar_bal PRIVATE caspar_lib_core)
