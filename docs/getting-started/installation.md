# Installation

## Requirements

| | |
|---|---|
| **Python** | 3.13 or newer |
| **Runtime dependencies** | none, permanently |
| **Type checkers** | pyright and mypy, both strict, both supported |
| **Test runners** | pytest, `unittest`, or none at all |

Python 3.13 is a floor rather than a preference. It is
[PEP 696](https://peps.python.org/pep-0696/) — **defaults on type parameters** —
that draws the line: the continuation type `Found[P, V, A = Expect[V]]` is a
syntax error before 3.13, and it is what lets `.which` mean "a subject over the
found value" without every producer spelling it out. (PEP 695's
`def expect[T](...)` syntax arrived in 3.12 and is not the constraint.)

The zero-dependency rule is worth one sentence, because it is the reason some
things inside are built the hard way: this package is installed into test suites
that already carry their own dependency trees, and adding to somebody else's tree
is a cost they did not choose. It will never grow a dependency.

## Installing

Not published to PyPI yet. Install from the repository:

```bash
pip install git+https://github.com/lovely-assertions/lovely-assertions
```

With [uv](https://docs.astral.sh/uv/), which is what the project itself uses:

```bash
uv add git+https://github.com/lovely-assertions/lovely-assertions
```

Once published, the usual will work:

```bash
pip install lovely-assertions
```

The distribution is named `lovely-assertions`; the module you import is
`lovely_assertions`, with the underscore Python requires.

## As a test dependency

Assertions belong with your tests, not with your shipped package. In a
`pyproject.toml`:

```toml
[dependency-groups]
dev = ["pytest>=8.4", "lovely-assertions"]
```

Or, for the older extras convention:

```toml
[project.optional-dependencies]
test = ["pytest>=8.4", "lovely-assertions"]
```

## Checking it works

```python
from lovely_assertions import expect

expect("lovely").starts_with("love")
print("ready")
```

```text
ready
```

That snippet passes, so it prints and moves on. To see the half you actually
came for, break it:

```python
from lovely_assertions import expect, AssertionFailure

server_name = "db-01.internal"
try:
    expect(server_name).starts_with("web-")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected server_name to start with 'web-', but was 'db-01.internal'.
```

`server_name` in that message is not a string anyone typed twice. The library
recovered it from your source at failure time, which is why naming your variables
well is the cheapest improvement you can make to your failure messages.

## Type checking

The package ships [`py.typed`](https://peps.python.org/pep-0561/), so both
checkers pick up its annotations with no configuration. Nothing needs to be
installed alongside it and no plugin is required.

Both are supported at their strictest settings, and the library's own CI runs
both on every commit. If you use one, you get discoverability and narrowing for
free; if you use neither, every assertion still works — you lose the editor
completion and the compile-time rejection, not the behaviour.

```bash
pyright tests/
```

```bash
mypy tests/
```

Where the two checkers genuinely disagree about this library, the disagreement is
written down rather than designed around:
[Type-checker divergences](../concepts/typing-divergences.md).

## Editor setup

Nothing to configure. Completion after `expect(value).` comes from the return
type of `expect()`, so any editor with a language server — Pylance, Pyright LSP,
BasedPyright, mypy's LSP, PyCharm — offers the right catalogue for the value's
type as soon as the package is installed in the interpreter your editor uses.

If completion shows *everything* rather than the catalogue for your value's type,
the editor is resolving `expect` to something else or is pointed at the wrong
interpreter. Check that `from lovely_assertions import expect` resolves in the
same environment your editor reports.

---

Next: [Your first assertions](first-assertions.md).
