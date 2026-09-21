"""Shared CUDA code printer for the gen_grad*.py generators.

sympy's default ccode emits pow(x, 2), pow(x, 3), pow(x, -2) ... for integer
powers. On the device that is a libm call per use; the kernels want plain
multiplications. This printer unrolls integer exponents with |n| <= 5 into
products (and 1.0/(product) for negative n) and leaves everything else --
non-integer exponents, sqrt, |n| > 5 -- to the stock printer, so the generated
temporaries and CSE structure are unchanged.
"""
import sympy as sp
from sympy.printing.c import C99CodePrinter


class _PowUnrollPrinter(C99CodePrinter):
    MAX_UNROLL = 5

    def _print_Pow(self, expr):
        e = expr.exp
        if e.is_Integer and 2 <= abs(int(e)) <= self.MAX_UNROLL:
            n = int(e)
            base = self.parenthesize(expr.base, sp.printing.precedence.PRECEDENCE["Mul"])
            prod = "*".join([base] * abs(n))
            if n > 0:
                return f"({prod})"
            return f"(1.0/({prod}))"
        return super()._print_Pow(expr)


def ccode(expr, **settings):
    """Drop-in for sp.ccode with integer powers unrolled."""
    return _PowUnrollPrinter(settings).doprint(expr)
