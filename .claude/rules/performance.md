---
paths:
  - "src/**/*.py"
---

# Performance — the happy path is sacred, the failure path is free

Loads alongside `code-style.md`. A passing assertion runs in test suites
millions of times; a failing one runs once and then a human reads it for a
minute. Spend accordingly.

**The happy path costs a comparison and a `return self`.** On the success branch
there is no allocation, no frame inspection, no `ContextVar` read, no message.
Ways this gets broken without anyone noticing:

- An f-string built *before* the branch that decides, including one written into
  a helper call that sits above it — Python evaluates arguments eagerly. Moving
  the formatting into a private method beside the assertion changes nothing;
  only moving the call below the `return self` does.
- A comprehension or `tuple(...)` used only to feed the comparison. Iterate and
  return early instead.
- A `finally` with a body. The `try` itself is free until it fires — zero-cost
  exception tables mean the success path is compiled as though the handler were
  not there — but the compiler copies the `finally` body into every exit path,
  including that one. It is the cleanup that costs, not the setup.
- Subscripting a generic at call time (`dict[str, int]()`) allocates. Bind the
  concrete type once at module level. Subscripting a *typing* generic with a
  string is worse: it builds a `ForwardRef`, and on 3.14 building one imports
  `annotationlib`, `ast` and `enum`. PEP 695 aliases are lazy, and are what to
  reach for wherever such a base is wanted.

**Probing for a missing attribute is a happy-path tool, not a smell**, and the
clause above deliberately does not forbid it. `hasattr(subject_type,
FIRST_MOCK_MARKER)` is asked of every value that misses the exact table and
misses in nearly all of them; `is_enum_member` reads `_member_map_` rather than
importing `enum`. Each such miss raises and swallows an `AttributeError`
internally and is still the cheapest form available, because the alternative is
an import or a walk of the MRO. Spend one where it replaces one of those, say so
in a comment, and expect no guard either way.

**Imports are a cost every user pays, and the rule is about import time, not the
failure path.** `re`, `difflib`, `ast`, `linecache` and `dataclasses` are
imported inside the function that needs them, each with a `# noqa: PLC0415`
and a reason — in parentheses after the code, or in a comment on the line above
when the line is already full; `tests/test_source_conventions.py` accepts either
form. Only `ast`, `linecache` and `difflib` are genuinely reached on the failure
path alone. The other two sit on paths an assertion takes in order to *pass*:
`matches()` compiles its pattern to succeed, and comparing two dataclasses reads
their fields. So the claim to defend is that importing the package imports none
of them, which `tests/test_packaging.py` checks twice — statically over every
module body, then again by importing under `-S`, so that CPython having `re`
and `linecache` loaded before user code runs cannot mask a regression. That
list is what the test enforces rather than the whole of what is deferred:
`uuid`, `warnings` and `importlib` sit inside their callers for the same reason,
with nothing standing over them.

The subjects for `datetime`, `enum` and `pathlib` values are typed under
`TYPE_CHECKING` and matched by name through `sys.modules`, so importing this
package imports none of the three. `datetime` and `pathlib` are then never
imported at all. `enum` is — lazily, by the flag assertions and by enum-by-name
equivalence, which cannot do their work without it, and transitively by anything
that pulls in `re`, which is every pattern assertion. Its absence is not a proxy
for anything; do not measure against it.

A deferral *inside* the package is a different animal and its comment has to say
which kind it is: a seam that names the very subject its own package exports
imports it in the method, and what it dodges is a cycle through the package's
front door rather than any weight. Related, and the rule a new family is
likeliest to miss: **a family package that dispatch must touch before it knows
what it is looking at may not pull its subject in with it.** Recognising a mock
is asked of every value handed to `expect()`, so `_mock/__init__.py` binds
`MockExpect` through a module `__getattr__` and loads the counting, the matching
and the rendering only for someone who has a mock.
`test_dispatch_loads_a_family_recognition_and_not_its_subject` pins that
boundary as a set of module names rather than a timing, so it reads the same on
a loaded runner as on an idle laptop.

**Dispatch is a dict lookup first.** `expect()` resolves the exact type through
a table keyed on type *identity* — written inline rather than called, so a hit
costs no Python frame — before anything reaches the `issubclass` chain behind
it. There is no `isinstance` in that chain at all, and the comments say why:
`m.__class__ = int` makes `isinstance(m, int)` true while `type(m)` still reads
`MagicMock`.

What is ordered for **correctness** is the branch order, not the chain as a
whole. First match wins, so narrower cases must precede the wider ones that
would otherwise claim them — a value that *is* a class ahead of `Collection`,
because `EnumMeta` gives an `Enum` class `__len__`, `__iter__` and
`__contains__`; `str` ahead of `Mapping`, because `class Config(str,
Mapping[str, int])` is a class anyone can write — and reordering for speed
changes which subject a value gets. Around that fixed order sit structures whose
only job is speed, and reworking one is fair game — moving it is not. The
callable types have a table of their own behind the mock check, because
`create_autospec(f)` returns something whose `type()` really is `function`, and
in front of it every autospecced function would become a `CallableExpect`; that
table is seeded into `_REGISTERED` so two lookups become one. The lazy subjects
are grouped by module, so a program that never mentioned dates pays one
`sys.modules` miss for the whole family. The shape chain's answer is memoised
per type.

**Every memo is bounded and cleared wholesale.** An unbounded one pins whatever
it is keyed on — every class a suite generates on the fly, every pattern it
compiles. Cleared rather than evicted one at a time, the way `re` bounds its own
pattern cache: the answers are cheap to rebuild, and an eviction policy that has
to be *right* is worse than a bound that only has to hold. A memo of a subclass
answer needs a second half — a guard on `abc.get_cache_token()`, kept in a
one-element list so the guard mutates rather than rebinding a module-level name.
`Sequence.register(X)` really does change the answer after the fact, and a plain
cache goes stale the moment someone calls it.

**`__slots__` on a seam is on your honour.** `code-style.md` states the rule;
this is where it is paid for. The guard reads the subject classes, and the
derivation behind them excludes every `*Assertions` mixin on purpose — counting
a seam as a subject would report each assertion twice, against a class no reader
has heard of. ruff's `SLOT` rules do not fire on an ordinary class either. So a
seam that omits `__slots__ = ()` hands a `__dict__` to every subject inheriting
it, on an object built once per assertion and dropped. Only the few subjects
that assert against their own `__dict__` would catch that, and only if they
inherit the seam in question.

**Measure, never assert by feel.** `benchmarks/__main__.py` prints timings for a
human and blocks nothing — but `benchmarks/` is also the measurement library the
asserting side imports, so breaking it fails collection for the whole suite
rather than one report. `tests/test_performance_invariants.py` asserts only what
holds on any machine: that a passing assertion allocates nothing, and that
importing the package and running a session stay within a bound expressed in
Python startups rather than in seconds. "Allocates nothing" is measured three
ways, because peak bytes, retained bytes and retained blocks are each blind to
something one of the others catches; and it means nothing beyond the assertion's
own product, with every exception a row carrying its cost in bytes and its
reason, in a table that may only shrink. Those recorded byte figures are checked
on the reference interpreter alone, while the invariant itself is checked on
both.

Two claims that sound like they belong in that file and do not. That the happy
path never calls the naming machinery is the `no_failure_machinery` fixture in
`tests/conftest.py`, which traps every escape hatch wherever a module binds it —
a `from ... import` binds a copy, so patching only `_core` leaves every other
caller going straight past — and `tests/test_happy_path.py` points it at the
whole public surface. That a module is not imported at all is
`tests/test_packaging.py`.

The peak-allocation tests skip themselves when something is watching the
interpreter, because a tracer allocates on the path it traces and the reading
becomes the instrument reading itself. `uv run pytest --cov` therefore does not
check that half of your work; the untraced `uv run pytest` does, and CI runs
both for this reason. A speedup claim that is not reproduced by reverting the
change in one checkout, on one interpreter, is not a claim — cross-tree numbers
are noise.

**Don't trade a message for a microsecond.** The failure path may allocate, walk
frames, parse source and import whatever it needs. If an optimisation makes a
message vaguer, it is not an optimisation.
