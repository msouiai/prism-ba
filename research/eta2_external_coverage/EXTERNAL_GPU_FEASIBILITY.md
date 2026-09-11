# Optional external GPU tier — read-only feasibility review, 2026-09-11

MegBA is a plausible next external GPU comparator. Its official repository
supports a single-device configuration; NCCL is optional for distributed use.
Our environment has CUDA, CMake and NCCL libraries, so missing MPI is not a
blocker. [Official MegBA build instructions](https://github.com/MegviiRobot/MegBA#quickstart).

The build declares an Eigen submodule and explicit CUDA architecture list
through sm_87, with hard-coded Thrust/CUB package locations. An isolated build
would need to confirm compatibility with this CUDA installation and target
sm_89 appropriately. No compile has been attempted while timed Ceres runs are
active. [MegBA CMake configuration](https://github.com/MegviiRobot/MegBA/blob/main/CMakeLists.txt).

The comparison requires more than compiling the existing example. Its camera
vertex has nine parameters and its residual uses f, k1 and k2, whereas our
registered objective freezes k2 and optimizes eight camera coordinates. A
fair adapter must fix/remove that parameter, validate the initial and final
original-observation FP64 objective, export states, expose accepted-iterate
timing, and retain all setup and target-check overhead. The current example
calls solve and exits without our endpoint audit/export protocol. The released
analytical and implicit variants also require a declared choice before testing.
[MegBA BAL driver](https://github.com/MegviiRobot/MegBA/blob/main/examples/BAL_Double.cpp),
[example build targets](https://github.com/MegviiRobot/MegBA/blob/main/examples/CMakeLists.txt).

RootBA's released repository includes square-root BA and Power BA. Its documented
dependencies and build use C++/TBB; simply building its existing BAL example
would add an algorithmic comparator, without establishing the requested new GPU
comparison. [RootBA repository and build](https://github.com/NikolausDemmel/rootba).

Decision for this task: defer the optional build/adapter until the two requested
coverage holes are resolved. The cost of compiling may be modest, but certifying
an equivalent objective and audited timing is a separate implementation task.
No inability-to-build or performance result is claimed. Public wording remains
restricted to measured Ceres/Caspar implementations and the recorded panels.
