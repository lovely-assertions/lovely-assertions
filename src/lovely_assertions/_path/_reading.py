"""Reading a file's text, and what to say when it cannot be read.

An encoding error is not a failed assertion: the file exists, the assertion could
not look at it, and reporting that as "does not contain" would be a lie the reader
has no way to catch. Both are named separately.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._path._filesystem import trouble
from lovely_assertions._path._render import rendered

if TYPE_CHECKING:
    from pathlib import Path

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


# ---------------------------------------------------------------------------
# Reading text -- shared by `has_text`, `contains_text`, `does_not_contain_text`
# ---------------------------------------------------------------------------
def read_text(path: "Path", encoding: str, /) -> str:
    """The exact contents of ``path``, decoded and otherwise untouched.

    Bytes are read and decoded here rather than through ``Path.read_text``
    because ``read_text`` opens in text mode, and text mode translates ``\\r\\n``
    to ``\\n``. An assertion whose whole promise is "this is exactly what is in
    the file" cannot be built on a reader that silently edits two of its
    characters -- ``has_text`` would pass on a CRLF file given LF text, which is
    the difference a Windows checkout introduces and the one a reader most needs
    to be told about.

    Raises ``OSError`` if the file cannot be read and ``UnicodeDecodeError`` if
    it is not text in ``encoding``; both are turned into messages by the caller.
    An unknown ``encoding`` raises ``LookupError``, which is left to propagate --
    a misspelled codec is a bug in the test and not a finding about the file.
    """
    return path.read_bytes().decode(encoding)


def read_trouble(path: "Path", error: "OSError | UnicodeDecodeError", /) -> str:
    """Why a file's text could not be had, as a message clause. Failure path only."""
    if isinstance(error, UnicodeDecodeError):
        return (
            rendered(path)
            + " is not "
            + error.encoding
            + " text ("
            + error.reason
            + " at byte "
            + str(error.start)
            + ")"
        )
    return trouble(path, error)
