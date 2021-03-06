"""
Implements a replacement for `doctest.OutputChecker` that handles certain
normalizations of Python expression output.  See the docstring on
`AstropyOutputChecker` for more details.
"""

import doctest
import re
import numpy as np


# Much of this code, particularly the parts of floating point handling, is
# borrowed from the SymPy project with permission.  See licenses/SYMPY.rst
# for the full SymPy license.

FIX = doctest.register_optionflag('FIX')
FLOAT_CMP = doctest.register_optionflag('FLOAT_CMP')
IGNORE_OUTPUT = doctest.register_optionflag('IGNORE_OUTPUT')
IGNORE_OUTPUT_2 = doctest.register_optionflag('IGNORE_OUTPUT_2')
IGNORE_OUTPUT_3 = doctest.register_optionflag('IGNORE_OUTPUT_3')


class AstropyOutputChecker(doctest.OutputChecker):
    """
    - Removes u'' prefixes on string literals
    - Ignores the 'L' suffix on long integers
    - In Numpy dtype strings, removes the leading pipe, i.e. '|S9' ->
      'S9'.  Numpy 1.7 no longer includes it in display.
    - Supports the FLOAT_CMP flag, which parses floating point values
      out of the output and compares their numerical values rather than their
      string representation.  This naturally supports complex numbers as well
      (simply by comparing their real and imaginary parts separately).
    """

    _str_literal_re = re.compile(
        r"(\W|^)[uU]([rR]?[\'\"])", re.UNICODE)
    _byteorder_re = re.compile(
        r"([\'\"])[|<>]([biufcSaUV][0-9]+)([\'\"])", re.UNICODE)
    _fix_32bit_re = re.compile(
        r"([\'\"])([iu])[48]([\'\"])", re.UNICODE)
    _long_int_re = re.compile(
        r"([0-9]+)L", re.UNICODE)

    def __init__(self):
        super().__init__()

        exp = r'(?:e[+-]?\d+)'

        got_floats = r'([+-]?\d+\.\d*{}?|[+-]?\.\d+{}?|[+-]?\d+{})'.format(exp, exp, exp)

        # floats in the 'want' string may contain ellipses
        want_floats = got_floats + r'(\.{3})?'

        front_sep = r'\s|[*+-,<=(\[]'
        back_sep = front_sep + r'|[>j)\]]'

        fbeg = r'^{}(?={}|$)'.format(got_floats, back_sep)
        fmidend = r'(?<={}){}(?={}|$)'.format(front_sep, got_floats, back_sep)
        self.num_got_rgx = re.compile(r'({}|{})'.format(fbeg, fmidend))

        fbeg = r'^{}(?={}|$)'.format(want_floats, back_sep)
        fmidend = r'(?<={}){}(?={}|$)'.format(front_sep, want_floats, back_sep)
        self.num_want_rgx = re.compile(r'({}|{})'.format(fbeg, fmidend))

    def do_fixes(self, want, got):
        want = re.sub(self._str_literal_re, r'\1\2', want)
        want = re.sub(self._byteorder_re, r'\1\2\3', want)
        want = re.sub(self._fix_32bit_re, r'\1\2\3', want)
        want = re.sub(self._long_int_re, r'\1', want)

        got = re.sub(self._str_literal_re, r'\1\2', got)
        got = re.sub(self._byteorder_re, r'\1\2\3', got)
        got = re.sub(self._fix_32bit_re, r'\1\2\3', got)
        got = re.sub(self._long_int_re, r'\1', got)

        return want, got

    def normalize_floats(self, want, got, flags):
        """
        Alternative to the built-in check_output that also handles parsing
        float values and comparing their numeric values rather than their
        string representations.

        This requires rewriting enough of the basic check_output that, when
        FLOAT_CMP is enabled, it totally takes over for check_output.
        """

        # Handle the common case first, for efficiency:
        # if they're string-identical, always return true.
        if got == want:
            return True

        # TODO parse integers as well ?
        # Parse floats and compare them. If some of the parsed floats contain
        # ellipses, skip the comparison.
        matches = self.num_got_rgx.finditer(got)
        numbers_got = [match.group(1) for match in matches]  # list of strs
        matches = self.num_want_rgx.finditer(want)
        numbers_want = [match.group(1) for match in matches]  # list of strs
        if len(numbers_got) != len(numbers_want):
            return False
        if len(numbers_got) > 0:
            nw_ = []
            for ng, nw in zip(numbers_got, numbers_want):
                if '...' in nw:
                    nw_.append(ng)
                    continue
                else:
                    nw_.append(nw)

                if not np.allclose(float(ng), float(nw)):
                    return False

            got = self.num_got_rgx.sub(r'{}', got)
            got = got.format(*tuple(nw_))

        # <BLANKLINE> can be used as a special sequence to signify a
        # blank line, unless the DONT_ACCEPT_BLANKLINE flag is used.
        if not (flags & doctest.DONT_ACCEPT_BLANKLINE):
            # Replace <BLANKLINE> in want with a blank line.
            want = re.sub(r'(?m)^{}\s*?$'.format(re.escape(doctest.BLANKLINE_MARKER)),
                          '', want)
            # If a line in got contains only spaces, then remove the
            # spaces.
            got = re.sub(r'(?m)^\s*?$', '', got)
            if got == want:
                return True

        # This flag causes doctest to ignore any differences in the
        # contents of whitespace strings. Note that this can be used
        # in conjunction with the ELLIPSIS flag.
        if flags & doctest.NORMALIZE_WHITESPACE:
            got = ' '.join(got.split())
            want = ' '.join(want.split())
            if got == want:
                return True

        # The ELLIPSIS flag says to let the sequence "..." in `want`
        # match any substring in `got`.
        if flags & doctest.ELLIPSIS:
            if doctest._ellipsis_match(want, got):
                return True

        # We didn't find any match; return false.
        return False

    def check_output(self, want, got, flags):
        if (flags & IGNORE_OUTPUT or flags & IGNORE_OUTPUT_3):
            return True

        if flags & FIX:
            want, got = self.do_fixes(want, got)

        if flags & FLOAT_CMP:
            return self.normalize_floats(want, got, flags)

        return super().check_output(want, got, flags)

    def output_difference(self, want, got, flags):
        if flags & FIX:
            want, got = self.do_fixes(want, got)

        return super().output_difference(want, got, flags)
