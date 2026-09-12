# Registered passenger model: implementation decisions before witness data

Protocol: `../../PROTOCOL_09_NONLINEAR.md`. This is a full joint camera-and-point
coarse model, not the earlier Schur-eliminated camera model. No fine radius is
imposed, no points are conditionally solved, and every observation is scored.

Mode order is world rotation, world translation, log scale. The centroids and
point memberships remain fixed. A point belongs to its first observing camera
in original observation order; points without observations remain fixed.

For a camera with center C and cluster centroid mu, the native tangent is
dw=-R omega and dt=R(omega cross mu-v-s(C-mu)). A passenger point has
dX=omega cross (X-mu)+v+s(X-mu). Camera intrinsics do not move.

The positive fixed metric is pulled back from E^-2 and the actual captured
point penalty divided by lambda, including its trace floor. Each cluster's
stacked weighted tangent is column-normalized, QR factored, then the 7x7 R is
SVD factored. Relative singular cutoff is 1e-10. This is the SVD of the same
tall matrix without constructing its left singular vectors. Whitening and
rank are fixed for all three left-increment solves. The rank is joint: a
singleton-camera scale need not be null when its passengers move.

The finite similarity action is evaluated by algebraically equivalent
increments to avoid subtracting two large translations:
dt=R[(I-Q^T)mu-Q^T v-(exp(s)-1)(C-mu)] and
dX=(exp(s)-1)(X-mu)+exp(s)(Q-I)(X-mu)+v.
Then R'=R Q^T, t'=t+dt and X'=X+dX. These are the registered action in exact
arithmetic; tests compare against direct transformed centers. Both transformed
and untransformed observations are scored from materialized FP64 R,t,X arrays,
so floating-point drift on same-cluster observations remains visible.

The Jacobian is evaluated in chunks. Its two at-most-seven-column blocks are
the chain rule through the observing camera and the passenger cluster. For
same-cluster observations their sum is mathematically zero (the camera vector
only scales); those derivative rows are set to exact zero, but their residuals
remain in the complete objective. Tests independently compare the chain rule,
finite differences, normal accumulation, and same-cluster invariance.

At each of three attempts solve (H+lambda I)y=-g in the fixed metric-whitened
coordinates. Use undamped pred(alpha)=-alpha*g'y-alpha^2*y'Hy/2 and score alpha
1,1/2,...,1/256 until gain>0,pred>0,rho>.1. Failed attempt multiplies only the
coarse lambda by ten; accepted rho>.75 divides it by ten. Recompute normals
after acceptance. No historical fine control state is touched.
