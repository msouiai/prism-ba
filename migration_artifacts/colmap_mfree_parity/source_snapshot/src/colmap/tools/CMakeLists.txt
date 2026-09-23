# Copyright (c), ETH Zurich and UNC Chapel Hill.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
#     * Neither the name of ETH Zurich and UNC Chapel Hill nor the names of
#       its contributors may be used to endorse or promote products derived
#       from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDERS OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


set(FOLDER_NAME "tools")

# COLMAP_ADD_EXECUTABLE(example example.cc)

COLMAP_ADD_EXECUTABLE(
    NAME consensus_ba_benchmark
    SRCS consensus_ba_benchmark.cc
    LINK_LIBS
        Ceres::ceres
        Threads::Threads
)

COLMAP_ADD_EXECUTABLE(
    NAME colmap_ba_compare
    SRCS colmap_ba_compare.cc
    LINK_LIBS
        colmap_estimators
        colmap_scene
        colmap_sensor
        colmap_util
)

COLMAP_ADD_EXECUTABLE(
    NAME filter_reconstruction
    SRCS filter_reconstruction.cc
    LINK_LIBS
        colmap_scene
        colmap_sensor
        colmap_util
)

COLMAP_ADD_EXECUTABLE(
    NAME undistort_reconstruction
    SRCS undistort_reconstruction.cc
    LINK_LIBS
        colmap_image
        colmap_scene
        colmap_sensor
        colmap_util
)

COLMAP_ADD_EXECUTABLE(
    NAME filter_cheirality
    SRCS filter_cheirality.cc
    LINK_LIBS
        colmap_scene
        colmap_sensor
        colmap_util
)

# End-to-end smoke check for the MFREE bundle adjustment backend. Exists
# because the gtest suite (bundle_adjustment_mfree_test.cc) needs GTest, which
# is not always present; this runs the same paths through the public factory.
if(MFREE_ENABLED)
    # CPU/OpenMP port of the multi-shift solver, tested against the GPU one.
    COLMAP_ADD_EXECUTABLE(
        NAME mfree_cpu_test
        SRCS mfree_cpu_test.cc
        LINK_LIBS
            oca_core
    )
    find_package(OpenMP QUIET)
    if(OpenMP_CXX_FOUND)
        # COLMAP_ADD_EXECUTABLE uses the plain target_link_libraries signature,
        # so this must too (mixing plain and keyword forms is a CMake error).
        target_link_libraries(mfree_cpu_test OpenMP::OpenMP_CXX)
    endif()

    COLMAP_ADD_EXECUTABLE(
        NAME mfree_backend_check
        SRCS mfree_backend_check.cc
        LINK_LIBS
            colmap_estimators
            colmap_scene
            colmap_sensor
            colmap_util
    )
endif()

# Generates a small synthetic model WITH observation noise, so BA backends can
# be compared on a problem that has a real optimum rather than an exactly
# recoverable one. No GPU needed, so it is not gated on MFREE_ENABLED.
COLMAP_ADD_EXECUTABLE(
    NAME synthesize_ba_model
    SRCS synthesize_ba_model.cc
    LINK_LIBS
        colmap_scene
        colmap_sensor
        colmap_util
)

# Applies rig-aware noise to an existing model, so BA backends can be compared
# on real data with a genuine descent to perform.
COLMAP_ADD_EXECUTABLE(
    NAME perturb_model
    SRCS perturb_model.cc
    LINK_LIBS
        colmap_scene
        colmap_sensor
        colmap_util
)
