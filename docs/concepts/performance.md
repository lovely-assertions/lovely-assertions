# Performance

An assertion library runs on every test, in every suite, on every commit. It is
allowed to cost approximately nothing when it passes. This page is what that
means in practice and what is actually guaranteed.

## The rule

> **A passing assertion is a comparison and a `return self`.**

No frame inspection, no source parsing, no context-variable read, no message
built, nothing allocated that is then thrown away, and your `because=` string
never rendered. Everything expensive happens only once a failure is certain.

Two honest edges on that. `because=` is an ordinary argument, so an *expression*
there is evaluated by Python before the call like any other — a literal is free,
`because=explain()` is not. And a subject object is allocated per `expect()`
call; what the suite pins is that a passing assertion **retains** nothing and
**builds** nothing it discards.

That is not an aspiration in a design document — it is a set of tests that fail
the build. The suite measures allocation over one pass of every assertion on
every exported subject, and requires:

- a passing assertion **retains** nothing;
- a passing assertion **builds** nothing it throws away — no message formatted
  and discarded;
- `.and_` allocates nothing to hand back `self`;
- and all of the above hold for **every** exported subject, not a sample of them.

## Why it needs guarding

The obvious way to write an assertion is also the wrong one:

<!-- docs-test: skip - illustrates the shape of an assertion, not a callable example -->

```python
# Wrong: the f-string is evaluated on every call, passing or failing.
def is_equal_to(self, expected):
    return self._check(self._subject == expected, f"to equal {expected!r}")
```

A message passed as an *argument* is built before the call that would decide
whether anyone needs it. Every passing assertion in the suite then pays to format
a string nobody will ever read. So the library confines message construction to
the failure branch:

<!-- docs-test: skip - illustrates the shape of an assertion, not a callable example -->

```python
# Right: nothing is formatted unless the comparison already failed.
def is_equal_to(self, expected):
    if self._subject == expected:
        return self
    return self._fail(f"to equal {expected!r}, but was {self._subject!r}")
```

An f-string outside a failure branch is treated as a defect in this codebase, not
a style preference — and the suite has a structural guard that reads the source
and rejects one.

## What a failure is allowed to cost

A great deal, and it should. A failing assertion has already ended the test; the
only thing that matters from there is the quality of the message. So the failure
path freely parses your source to recover the subject's name, reads a
`ContextVar` for formatting options, walks a registry of formatters, and computes
a unified diff.

The one bound on it is that the cost stays proportional to the *statement*, not
to your file: name recovery indexes a source file once and answers by line number
afterwards, so a failing assertion in a very large test module does not re-walk
that module — and neither does each of the failures a
[soft scope](../guides/soft-assertions.md) collects out of it.

## Importing costs almost nothing

Test suites import this package to run one assertion, so the import is bounded
too. `re`, `difflib`, `ast`, `linecache`, `dataclasses` and `uuid` are imported
**inside the function that needs them**, never at module level. `difflib`, `ast`
and `linecache` are reached only from a failure path; `re` and `uuid` are reached
by the assertions built on them — a *passing* `matches(...)` imports `re` — which
is still a suite that never uses them never paying for them.

`datetime` and `pathlib` are never imported at all: the subjects that assert on
them are typed against them under `TYPE_CHECKING` and dispatched by name, so a
suite that never touches a date or a path never pays for either module.

`enum` is typed the same way and imported lazily by the two things that cannot
do their work without it — the flag assertions, and equivalence configured with
`comparing_enums_by_name()`. Importing the package still does not import it.

Check it yourself:

```bash
python -c "import sys; before=set(sys.modules); import lovely_assertions; print(sorted({'re','ast','difflib','linecache','datetime','enum','pathlib','dataclasses','uuid'} & (set(sys.modules)-before)))"
```

That prints an empty list. A suite that never mentions a `Path` never pays for
`pathlib` because of this library — and a suite that never fails an assertion
never pays for `ast`.

This is also why the package has **zero runtime dependencies, permanently**, and
why several things inside are built by hand that a dependency would have
supplied: `FormattingOptions` is written out longhand rather than being a frozen
dataclass, because importing `dataclasses` for it would be a cost paid by every
program that imports the package.

## The dispatch is memoised

Choosing a subject walks an ordered chain of type checks. The answer is
remembered per type, so the second `expect(YourDomainObject())` does not re-walk
it.

Remembering is only sound because the library watches `abc.get_cache_token()`:
`Sequence.register(YourClass)` genuinely changes what the right answer is, and
every such registration bumps that token — which is exactly what it is for, and
what `functools.singledispatch` guards on. When it moves, the remembered answers
are discarded. See [Typed dispatch](typed-dispatch.md).

## Subjects are cheap objects

Every subject class declares `__slots__`, including the subjects you write
yourself. A subject holds one attribute and is allocated once per assertion, so a
`__dict__` on each one is measurable across a real suite. If you
[write your own subject](../guides/extending.md), give it `__slots__ = ()`.

## Measuring it yourself

The repository carries a benchmark suite, printed for a human and never asserted
on:

```bash
uv run python -m benchmarks
```

Wall-clock numbers belong there because they depend on the machine. The claims
that hold on *any* machine — no allocation on a passing assertion, a bounded
import — are in the test suite instead, where they can fail a build.

## The honest summary

This is not faster than a bare `assert`. Nothing is: `assert a == b` compiles to
a comparison and a jump. What is true is that the overhead is a function call and
a comparison, that it allocates nothing, and that you will not find it in a
profile of your test suite. That is a smaller claim than "fast", and it is one
that can actually be kept.

---

See also: [Design goals](design-goals.md) · [Typed dispatch](typed-dispatch.md)
