"""Putting a hunk header's line numbers back after the windowing moved them.

A unified diff names, in each ``@@`` header, the line the hunk starts at in each
text. Trimming the identical head before ``difflib`` sees anything is what keeps
the diff affordable, and it is also what makes every one of those numbers wrong
by however many lines came off -- so they are corrected here, once, on the way
out.

Getting this wrong is not cosmetic. A header that points at a line the reader
cannot find in the value they were just shown reads as the library being
confused about its own output.
"""

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def is_hunk_header(line: str, /) -> bool:
    """Whether a diff line is ``difflib``'s ``@@ -a,b +c,d @@`` position marker."""
    return line.startswith("@@ ")


def shift_hunk(line: str, offset: int, /) -> str:
    """Put a hunk header's line numbers back where the untrimmed text had them."""
    if offset == 0 or not is_hunk_header(line):
        return line
    head, _, rest = line.partition(" ")
    removed, _, rest = rest.partition(" ")
    added, _, trailer = rest.partition(" ")
    # Insurance for the windowing rather than a case this caller can reach: a
    # header arrives exactly as `difflib` wrote it, closing `@@` included.
    if not trailer:
        return line
    return " ".join((head, _shift_range(removed, offset), _shift_range(added, offset), trailer))


def _shift_range(field: str, offset: int, /) -> str:
    """``"-1,4"`` moved forward by the number of lines the window dropped."""
    start, comma, length = field[1:].partition(",")
    # Insurance for the windowing rather than a case this caller can reach:
    # `difflib` writes a range as a line number and an optional `,length`, so
    # what precedes the comma is always digits.
    if not start.isdigit():
        return field
    return field[:1] + str(int(start) + offset) + comma + length
