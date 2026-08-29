# Paths

Two subjects, and the split between them is the useful part:

| Value | Subject | Touches the filesystem |
|---|---|---|
| `PurePath`, `PurePosixPath`, `PureWindowsPath` | `PurePathExpect[T]` | **no** — pure name algebra |
| `Path`, `PosixPath`, `WindowsPath` | `PathExpect` | **yes** — and inherits all of the above |

So a `PurePath` subject genuinely has no `exists()` to call by mistake, and a
test about *path shape* cannot accidentally hit the disk.

> `pathlib` is never imported by this library — the dispatch matches these types
> by name. See [Performance](../concepts/performance.md#importing-costs-almost-nothing).

## Path shape (no I/O)

```python
from pathlib import PurePosixPath

from lovely_assertions import expect, AssertionFailure

artefact = PurePosixPath("build/report.tar.gz")
expect(artefact).has_name("report.tar.gz").and_.has_suffix(".gz")

try:
    expect(artefact).has_suffix(".txt")
except AssertionFailure as failure:
    print(failure)

try:
    expect(artefact).has_parent(PurePosixPath("dist"))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected artefact to have the suffix '.txt', but 'build/report.tar.gz' has the suffix '.gz'.
Expected artefact to have the parent 'dist', but 'build/report.tar.gz' has the parent 'build'.
```

The family: `has_name`, `has_stem`, `has_suffix`, `has_suffixes`,
`has_no_suffix`, `has_parent`, `is_absolute`, `is_relative`, `is_relative_to`,
`is_not_relative_to`, `matches_pattern`.

`has_suffixes` takes the whole list, and a filename can have more than you expect:

```python
from pathlib import PurePosixPath

from lovely_assertions import expect, AssertionFailure

artefact = PurePosixPath("build/report.tar.gz")
try:
    expect(artefact).has_suffixes([".tar", ".zip"])
except AssertionFailure as failure:
    print(failure)
```

```text
Expected artefact to have the suffixes ['.tar', '.zip'], but 'build/report.tar.gz' has ['.tar', '.gz'].
```

Watch out for version numbers: `app-1.2.3.whl` has suffixes
`['.2', '.3', '.whl']`, because `pathlib` splits on every dot.

## Filesystem assertions

```python
from pathlib import Path

from lovely_assertions import expect, AssertionFailure

Path("notes.txt").write_text("hello world", encoding="utf-8")
notes = Path("notes.txt")

expect(notes).exists().and_.is_file()

try:
    expect(Path("missing.txt")).exists()
except AssertionFailure as failure:
    print(failure)

try:
    expect(notes).is_directory()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected Path("missing.txt") to exist, but nothing is there at 'missing.txt'.
Expected notes to be a directory, but 'notes.txt' is a regular file.
```

"is a regular file" rather than "is not a directory" — the message says what the
thing *is*, which is usually the fact that resolves the confusion.

### Contents

```python
from pathlib import Path

from lovely_assertions import expect, AssertionFailure

Path("notes.txt").write_text("hello world", encoding="utf-8")
notes = Path("notes.txt")

expect(notes).has_text("hello world").and_.contains_text("world")

try:
    expect(notes).has_text("goodbye")
except AssertionFailure as failure:
    print(failure)

try:
    expect(notes).has_size(999)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected notes to have the text 'goodbye', but 'notes.txt' holds 'hello world'.
Expected notes to hold 999 bytes, but 'notes.txt' holds 11 bytes.
```

`has_text` and `contains_text` take **text, never bytes**, and accept an
`encoding=`. Content that will not decode is a failure with a message; an unknown
encoding name is a `LookupError` at the call.

Also: `does_not_contain_text`, `has_size_greater_than`, `has_size_less_than`,
`is_empty`, `is_not_empty`.

### Directories

```python
from pathlib import Path

from lovely_assertions import expect, AssertionFailure

Path("notes.txt").write_text("hello world", encoding="utf-8")

expect(Path(".")).is_directory().and_.has_child("notes.txt")

try:
    expect(Path(".")).has_child("missing.txt")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected Path(".") to have a child named 'missing.txt', but '.' holds ['notes.txt'].
```

It **lists what is actually there**, which is the answer to "why isn't my file
found" most of the time. The listing is clipped for a large directory.

`does_not_have_child` is the complement, and `is_not_directory` / `is_not_file`
assert the negative *about a path that exists* — see the gotcha below, because
they are not what you want for a path that is absent.

`has_child` takes one entry name, never a route — assert on the child path itself
for anything deeper.

### Symbolic links

`is_symlink`, `is_not_symlink` and `is_same_file_as` round out the set.
`is_same_file_as` names the guilty side rather than reporting a flat mismatch.

## Gotchas

### A suffix carries its leading dot

```python
from pathlib import PurePosixPath

from lovely_assertions import expect

artefact = PurePosixPath("build/report.tar.gz")
try:
    expect(artefact).has_suffix("gz")
except ValueError as error:
    print(error)
```

```text
a suffix carries its leading dot, the way PurePath.suffix reports it: got 'gz', did you mean '.gz'?
```

Raised at the call rather than failing, because `"gz"` could never be any path's
suffix — it is a bug in the test, and the message says what you meant.

### `is_relative_to` is string algebra, not containment

It compares path *components*, and does not resolve symlinks, `..`, or the actual
filesystem. **Never use it as a path-traversal guard.** For that you want
`Path.resolve()` first, and then a check you have thought about properly.

### The negated disk assertions are not complements

A path that does not exist fails `is_file()` *and* `is_not_file()` — the second
asserts "this is on disk and is not a regular file", which a missing path is not.
Assert `does_not_exist()` when that is what you mean.

A dangling symlink is the sharp version: it fails `exists()` **and**
`does_not_exist()`, while `is_symlink()` passes.

### The size family raises for a bad question and fails for a bad answer

A **negative** size raises `ValueError` on all three — no file has one, so it is
a bug in the test rather than a finding about the value:

```python
from pathlib import Path

from lovely_assertions import expect

try:
    expect(Path("notes.txt")).has_size(-1)
except ValueError as error:
    print(error)

try:
    expect(Path("notes.txt")).has_size_less_than(0)
except ValueError as error:
    print(error)
```

```text
a size in bytes is never negative, got -1
no file holds fewer than zero bytes; is_empty is the zero-byte claim
```

Asking the size of a **directory** is a different thing: that is a fact about the
value, so it fails, and the message says what the path actually is.

---

**See also:** [strings](strings.md) for assertions on file contents you have
already read · [any value](any-value.md)
