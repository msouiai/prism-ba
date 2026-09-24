cmake_minimum_required(VERSION 3.20)
project(oca_cuda LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CUDA_STANDARD 17)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_library(CUSOLVER_LIB cusolver HINTS /usr/local/cuda/lib64 /usr/local/cuda/targets/x86_64-linux/lib)
find_library(CUBLAS_LIB cublas HINTS /usr/local/cuda/lib64 /usr/local/cuda/targets/x86_64-linux/lib)

set(OCA_CUDA_ARCHITECTURES "89" CACHE STRING "CUDA architectures to build for")

# ONE source, two consumers. oca_core is the embeddable library (no main, no
# CLI, no BAL IO); oca_cuda is the research CLI. They share every kernel and
# the LM policy on purpose -- see oca_core.h.
add_library(oca_core STATIC oca_cuda.cu)
target_compile_definitions(oca_core PRIVATE OCA_CORE_LIBRARY)
target_include_directories(oca_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
set_target_properties(oca_core PROPERTIES
    CUDA_ARCHITECTURES "${OCA_CUDA_ARCHITECTURES}"
    CUDA_SEPARABLE_COMPILATION ON
    # Perform the device link inside this static library. Without it a plain
    # C++ consumer (COLMAP links with c++, not nvcc) fails with
    # "undefined reference to __cudaRegisterLinkedBinary_..." because the
    # relocatable device code was never device-linked.
    CUDA_RESOLVE_DEVICE_SYMBOLS ON
    POSITION_INDEPENDENT_CODE ON)
target_compile_options(oca_core PRIVATE $<$<COMPILE_LANGUAGE:CUDA>:-O3>)
target_link_libraries(oca_core PUBLIC ${CUSOLVER_LIB} ${CUBLAS_LIB} cudart)
# NOTE: an embedding project that exports its targets must add oca_core to its
# own export set (COLMAP does this via COLMAP_EXPORT_LIBS). Do not install it
# here as well, or the target lands in the export set twice.

# The CLI and its gate are only for standalone use; an embedding project
# (COLMAP) consumes oca_core alone and must not pay for building them.
if(PROJECT_IS_TOP_LEVEL)
add_executable(oca_cuda oca_cuda.cu)
option(OCA_KRYLOV_AUDIT_BUILD "Enable fixed-operator diagnostic CLI (never the core library)" OFF)
if(OCA_KRYLOV_AUDIT_BUILD)
  target_compile_definitions(oca_cuda PRIVATE PRISM_ENABLE_KRYLOV_AUDIT)
endif()
option(OCA_REUSE_FIXED_STUDY_BUILD "Enable CLI-only fixed-system reuse study" OFF)
if(OCA_REUSE_FIXED_STUDY_BUILD)
  target_compile_definitions(oca_cuda PRIVATE PRISM_ENABLE_REUSE_FIXED_STUDY)
endif()
set_target_properties(oca_cuda PROPERTIES
    CUDA_ARCHITECTURES "${OCA_CUDA_ARCHITECTURES}"
    CUDA_SEPARABLE_COMPILATION ON)
target_compile_options(oca_cuda PRIVATE $<$<COMPILE_LANGUAGE:CUDA>:-O3>)
target_link_libraries(oca_cuda PRIVATE ${CUSOLVER_LIB} ${CUBLAS_LIB} cudart)

# Gate: the core library must reproduce the CLI (see run_core_gate.sh).
add_executable(test_oca_core test_oca_core.cc)
target_link_libraries(test_oca_core PRIVATE oca_core)

# Opt-in kernel gate; includes the implementation to test both kernel paths.
add_executable(test_rhs_diag EXCLUDE_FROM_ALL test_rhs_diag.cu)
add_executable(test_bounded_cost EXCLUDE_FROM_ALL test_bounded_cost.cu)
add_executable(test_point_safeguard EXCLUDE_FROM_ALL test_point_safeguard.cu)
set_target_properties(test_point_safeguard PROPERTIES CUDA_ARCHITECTURES "${OCA_CUDA_ARCHITECTURES}" CUDA_SEPARABLE_COMPILATION ON)
target_compile_options(test_point_safeguard PRIVATE $<$<COMPILE_LANGUAGE:CUDA>:-O3>)
target_link_libraries(test_point_safeguard PRIVATE ${CUSOLVER_LIB} ${CUBLAS_LIB} cudart)

find_package(Eigen3 QUIET NO_MODULE)
if(TARGET Eigen3::Eigen)
  add_executable(test_repair_model EXCLUDE_FROM_ALL test_repair_model.cu)
  set_target_properties(test_repair_model PROPERTIES CUDA_ARCHITECTURES "${OCA_CUDA_ARCHITECTURES}" CUDA_SEPARABLE_COMPILATION ON)
  target_compile_options(test_repair_model PRIVATE $<$<COMPILE_LANGUAGE:CUDA>:-O3>)
  target_link_libraries(test_repair_model PRIVATE Eigen3::Eigen ${CUSOLVER_LIB} ${CUBLAS_LIB} cudart)

  add_executable(test_subspace_model EXCLUDE_FROM_ALL test_subspace_model.cu)
  set_target_properties(test_subspace_model PROPERTIES CUDA_ARCHITECTURES "${OCA_CUDA_ARCHITECTURES}" CUDA_SEPARABLE_COMPILATION ON)
  target_compile_options(test_subspace_model PRIVATE $<$<COMPILE_LANGUAGE:CUDA>:-O3>)
  target_link_libraries(test_subspace_model PRIVATE Eigen3::Eigen ${CUSOLVER_LIB} ${CUBLAS_LIB} cudart)
  add_executable(test_full_step_model EXCLUDE_FROM_ALL test_full_step_model.cu)
  set_target_properties(test_full_step_model PROPERTIES CUDA_ARCHITECTURES "${OCA_CUDA_ARCHITECTURES}" CUDA_SEPARABLE_COMPILATION ON)
  target_compile_options(test_full_step_model PRIVATE $<$<COMPILE_LANGUAGE:CUDA>:-O3>)
  target_link_libraries(test_full_step_model PRIVATE Eigen3::Eigen ${CUSOLVER_LIB} ${CUBLAS_LIB} cudart)
  add_executable(test_point_trust EXCLUDE_FROM_ALL test_point_trust.cu)
  set_target_properties(test_point_trust PROPERTIES CUDA_ARCHITECTURES "${OCA_CUDA_ARCHITECTURES}" CUDA_SEPARABLE_COMPILATION ON)
  target_compile_options(test_point_trust PRIVATE $<$<COMPILE_LANGUAGE:CUDA>:-O3>)
  target_link_libraries(test_point_trust PRIVATE Eigen3::Eigen ${CUSOLVER_LIB} ${CUBLAS_LIB} cudart)
endif()
set_target_properties(test_bounded_cost PROPERTIES
    CUDA_ARCHITECTURES "${OCA_CUDA_ARCHITECTURES}"
    CUDA_SEPARABLE_COMPILATION ON)
target_compile_options(test_bounded_cost PRIVATE $<$<COMPILE_LANGUAGE:CUDA>:-O3>)
target_link_libraries(test_bounded_cost PRIVATE ${CUSOLVER_LIB} ${CUBLAS_LIB} cudart)
set_target_properties(test_rhs_diag PROPERTIES
    CUDA_ARCHITECTURES "${OCA_CUDA_ARCHITECTURES}"
    CUDA_SEPARABLE_COMPILATION ON)
target_compile_options(test_rhs_diag PRIVATE $<$<COMPILE_LANGUAGE:CUDA>:-O3>)
target_link_libraries(test_rhs_diag PRIVATE ${CUSOLVER_LIB} ${CUBLAS_LIB} cudart)
# Fixed-input numerical gate for the optional single-copy fragment store.
add_executable(test_compact_fragments EXCLUDE_FROM_ALL test_compact_fragments.cu)
set_target_properties(test_compact_fragments PROPERTIES
    CUDA_ARCHITECTURES "${OCA_CUDA_ARCHITECTURES}"
    CUDA_SEPARABLE_COMPILATION ON)
target_compile_options(test_compact_fragments PRIVATE $<$<COMPILE_LANGUAGE:CUDA>:-O3>)
target_link_libraries(test_compact_fragments PRIVATE ${CUSOLVER_LIB} ${CUBLAS_LIB} cudart)
# Analytic residual and post-hoc shift-reuse checks; no BA data required.
add_executable(test_retained_krylov EXCLUDE_FROM_ALL test_retained_krylov.cu)
set_target_properties(test_retained_krylov PROPERTIES
    CUDA_ARCHITECTURES "${OCA_CUDA_ARCHITECTURES}")
target_link_libraries(test_retained_krylov PRIVATE ${CUBLAS_LIB} cudart)
add_executable(test_cg_capture EXCLUDE_FROM_ALL test_cg_capture.cu)
set_target_properties(test_cg_capture PROPERTIES
    CUDA_ARCHITECTURES "${OCA_CUDA_ARCHITECTURES}")
target_link_libraries(test_cg_capture PRIVATE ${CUBLAS_LIB} cudart)
add_executable(test_reuse_fixed_study EXCLUDE_FROM_ALL test_reuse_fixed_study.cu)
set_target_properties(test_reuse_fixed_study PROPERTIES
    CUDA_ARCHITECTURES "${OCA_CUDA_ARCHITECTURES}")
target_link_libraries(test_reuse_fixed_study PRIVATE ${CUBLAS_LIB} cudart)
endif()  # PROJECT_IS_TOP_LEVEL

# Rig / fisheye / pinhole path gate (constant blocks, gauge, soft-L1, pinhole masks).
if(PROJECT_IS_TOP_LEVEL)
add_executable(test_rigfisheye test_rigfisheye.cc)
target_link_libraries(test_rigfisheye PRIVATE oca_core)
endif()
