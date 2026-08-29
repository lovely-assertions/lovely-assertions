"""The dispatch remembers what it worked out, and must not remember wrong.

``expect()`` resolves a handful of subjects -- dates, paths, enums, ``Decimal``,
``Fraction`` -- by asking ``sys.modules`` rather than importing the modules those
types live in. That probe is an order of magnitude dearer than the ``dict`` lookup
standing in front of it, and the case that pays it is
``expect(some_domain_object())``: the one value that reaches the end of the chain,
and a common one.

Caching is only sound because of an argument, and an argument is what a test is
for. Three of them, none argued about here:

* every **plain class** in ``_LAZY_SUBJECTS`` has an MRO fixed when the type was
  created, so ``issubclass`` cannot change its mind about it afterwards. Enumerated
  over the real table rather than asserted, so a plain entry that turns into an ABC
  is reported;
* the entries that are *not* plain classes really can gain subclasses after an
  answer is recorded -- ``Fraction`` inherits ``ABCMeta`` from ``numbers.Rational``
  and accepts ``Fraction.register(Whatever)``. Remembering stays sound for those
  only because every such registration bumps ``abc.get_cache_token()``, and the
  dispatch throws its answers away when the token moves. Demonstrated by
  registering into one, not reasoned about;
* a ``None`` recorded because a module was absent cannot become wrong, because to
  build a subclass of ``pathlib.Path`` you must first import ``pathlib``. A type
  that already exists while the module is unloaded is not a subclass of anything
  in it. Run in a subprocess, the only place ``pathlib`` can still be unloaded.
"""

import subprocess
import sys
from abc import ABCMeta
from pathlib import Path
from types import FunctionType
from typing import Any, Final, cast

import pytest

from lovely_assertions import (
    CallableExpect,
    CollectionExpect,
    DateExpect,
    DateTimeExpect,
    EnumExpect,
    Expect,
    MockExpect,
    OrderedExpect,
    PathExpect,
    SequenceExpect,
    expect,
    register,
)
from lovely_assertions import _subjects as subjects

REPO_ROOT: Final = Path(__file__).resolve().parent.parent


def _internal(name: str) -> Any:
    """Reach a private name in ``_subjects`` through the module namespace.

    Both checkers flag a private attribute read across modules, and this file
    exists to test one. ``tests/test_happy_path.py`` sidesteps the same rule by
    handing the name to ``monkeypatch.setattr`` as a string; this is that trick
    with the value returned instead of replaced.
    """
    return vars(subjects)[name]


#: The remembered answers, the table they are worked out from, and the bound.
REMEMBERED: Final[dict[type[Any], Any]] = _internal("_SHAPE_ANSWERS")
REMEMBERED_TABLE: Final[tuple[tuple[str, tuple[tuple[str, Any], ...]], ...]] = _internal(
    "_LAZY_SUBJECTS"
)
MAX_REMEMBERED: Final[int] = _internal("_MAX_SHAPE_ANSWERS")
REGISTERED: Final[dict[type[Any], Any]] = _internal("_REGISTERED")


def built_by(value: object, /) -> type[Any]:
    """The class ``expect()`` really built, widened.

    Widened on purpose: these tests compare the runtime answer against a class the
    checkers have already inferred, and left narrow every one of those comparisons
    is "non-overlapping" to mypy -- which folds away the very question being asked.
    """
    return type(expect(value))


@pytest.fixture(autouse=True)
def forget_remembered_answers() -> None:
    """Every test here starts cold, or it is measuring the one before it."""
    REMEMBERED.clear()


# ---------------------------------------------------------------------------
# The remembered answer is the answer
# ---------------------------------------------------------------------------
def test_a_second_call_agrees_with_the_first() -> None:
    """A warm call answers what the cold call answered.

    The mutants this catches: storing the answer before it is resolved, or storing
    it under a key the second call does not look up.
    """
    from datetime import datetime

    cold = built_by(datetime(2020, 1, 1))
    warm = built_by(datetime(2021, 6, 6))
    assert cold is warm is DateTimeExpect


def test_every_lazy_subject_survives_a_second_call() -> None:
    """Every entry in ``_LAZY_SUBJECTS`` answers the same warm as it does cold."""
    from datetime import date, datetime, time, timedelta
    from decimal import Decimal
    from enum import Enum
    from fractions import Fraction
    from pathlib import PurePosixPath

    class Colour(Enum):
        RED = 1

    values: list[object] = [
        datetime(2020, 1, 1),
        date(2020, 1, 1),
        time(9, 30),
        timedelta(days=1),
        Path("/etc/hosts"),
        PurePosixPath("/a"),
        Colour.RED,
        Decimal("1.5"),
        Fraction(1, 3),
    ]
    cold = [built_by(value) for value in values]
    warm = [built_by(value) for value in values]
    assert cold == warm


def test_a_remembered_no_does_not_become_a_yes() -> None:
    """``None`` is a real answer, so a miss has to be told apart from a stored no."""

    class Domain:
        __slots__ = ()

    assert built_by(Domain()) is Expect
    assert REMEMBERED[Domain] is None
    assert built_by(Domain()) is Expect


def test_a_remembered_answer_does_not_leak_to_a_sibling_type() -> None:
    """Keyed by the exact type, not by anything it happens to resemble."""
    from datetime import date, datetime

    assert built_by(datetime(2020, 1, 1)) is DateTimeExpect
    assert built_by(date(2020, 1, 1)) is DateExpect


# ---------------------------------------------------------------------------
# The soundness argument, checked rather than asserted
# ---------------------------------------------------------------------------
def test_a_type_seen_before_its_module_was_imported_is_still_right_after() -> None:
    """The half of the argument that could actually be wrong.

    A class is dispatched while ``pathlib`` and ``datetime`` are unloaded, so the
    probe records "not one of those" against it. The modules are then imported and
    the same class is dispatched again. It must still be the generic subject --
    and a real ``Path``, whose type did not exist when the ``None`` was recorded,
    must still reach :class:`PathExpect`.
    """
    probe = (
        "import sys;"
        "sys.path.insert(0, 'src');"
        "from lovely_assertions import expect;"
        "assert 'pathlib' not in sys.modules, 'the probe needs pathlib unloaded';"
        "Domain = type('Domain', (), {});"
        "first = type(expect(Domain())).__name__;"
        "import pathlib, datetime;"
        "second = type(expect(Domain())).__name__;"
        "third = type(expect(pathlib.Path('/etc/hosts'))).__name__;"
        "print(first, second, third)"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-S", "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    assert result.stdout.split() == [Expect.__name__, Expect.__name__, PathExpect.__name__]


def test_the_table_still_names_which_entries_can_gain_subclasses() -> None:
    """Which entries rest on the token guard, and which on a fixed MRO.

    An entry whose metaclass is ``ABCMeta`` can gain subclasses after the fact --
    ``SomeAbc.register(MyClass)`` makes ``issubclass(MyClass, SomeAbc)`` true from
    then on. For those, remembering is sound only because
    ``abc.get_cache_token()`` moves when it happens. For the plain classes it is
    sound because an MRO is fixed when the type is created, and no token is needed.

    ``Fraction`` is the one entry in the first camp: it inherits ``ABCMeta`` from
    ``numbers.Rational``. Pinning the membership of that camp is what keeps the
    two arguments matched to the entries they actually cover -- a plain class that
    becomes an ABC would silently move to relying on a guard nobody checked it
    against.
    """
    registrable = [
        module_name + "." + type_name
        for module_name, candidates in REMEMBERED_TABLE
        for type_name, _factory in candidates
        if type(getattr(__import__(module_name), type_name)) is ABCMeta
    ]
    assert registrable == ["fractions.Fraction"], (
        f"the set of entries that rely on the token guard changed: {registrable}. "
        f"Either the token argument now covers something new, or something plain "
        f"became an ABC -- read _SHAPE_ANSWERS before deciding which."
    )


def test_a_registration_after_first_use_is_honoured() -> None:
    """The token guard, demonstrated rather than asserted -- for both camps.

    A remembered ``None`` would silently outlive the registration that makes it
    wrong. ``Fraction`` is the concrete stdlib number nobody registers into on
    purpose; ``Sequence`` is the one a real project might.
    """
    from collections.abc import Sequence
    from fractions import Fraction

    class Ratio:
        __slots__ = ()

    class Rowish:
        __slots__ = ()

        def __len__(self) -> int:
            return 0

        def __getitem__(self, index: int) -> int:
            return 0

    assert built_by(Ratio()) is Expect
    Fraction.register(Ratio)
    assert built_by(Ratio()) is OrderedExpect, "the token did not discard the stale answer"

    assert built_by(Rowish()) is Expect
    # Cast to the metaclass: typeshed declares `register` on `ABCMeta` and not on
    # the ABCs themselves, so `Sequence.register(...)` is a pyright error even
    # though it is the spelling every project uses.
    cast("ABCMeta", Sequence).register(Rowish)
    assert built_by(Rowish()) is SequenceExpect, "the token did not discard the stale answer"


# ---------------------------------------------------------------------------
# It stays bounded
# ---------------------------------------------------------------------------
def test_the_table_does_not_grow_without_limit() -> None:
    """The keys are type objects; holding them forever pins every class a suite makes."""
    for index in range(MAX_REMEMBERED + 50):
        made = type("Generated" + str(index), (), {})
        expect(made())
    assert len(REMEMBERED) <= MAX_REMEMBERED


def test_clearing_the_table_does_not_change_any_answer() -> None:
    """A cleared entry is rebuilt, not lost."""
    from enum import Enum

    class Colour(Enum):
        RED = 1

    before = built_by(Colour.RED)
    REMEMBERED.clear()
    assert built_by(Colour.RED) is before is EnumExpect


# ---------------------------------------------------------------------------
# Registration still wins
# ---------------------------------------------------------------------------
def test_a_registered_subject_beats_a_remembered_one() -> None:
    """``register()`` is consulted first, so it overrides an answer already stored.

    Worth pinning: the natural way to write the cache is in front of the whole
    fallback, which would make a type registered *after* its first use silently
    keep the subject it had.
    """

    class Invoice:
        __slots__ = ()

    subject = Invoice()
    assert built_by(subject) is Expect
    assert REMEMBERED[Invoice] is None, "the remembered answer this has to beat"

    class InvoiceExpect(Expect[Invoice]):
        __slots__ = ()

    register(Invoice, InvoiceExpect)
    try:
        assert built_by(subject) is InvoiceExpect
    finally:
        del REGISTERED[Invoice]


def test_a_type_the_overloads_already_claim_cannot_be_registered() -> None:
    """``register()`` must refuse every type the dispatch already claims.

    Comparing against the exact-type table alone is not enough: a type reached
    through the fallback chain -- a ``date`` subclass, a ``Decimal``, ``bytes``, an
    ``Enum`` subclass, any ``Mapping`` subclass -- would be accepted, and then the
    runtime answers the caller's subject while both checkers go on promising the
    one the overloads declare. ``register()`` asks the same chain ``_dispatch``
    asks, so the two answers cannot part company.
    """
    from datetime import date

    class BillingDate(date):
        __slots__ = ()

    class BillingDateExpect(Expect[BillingDate]):
        __slots__ = ()

    with pytest.raises(ValueError, match="DateExpect"):
        register(BillingDate, BillingDateExpect)
    assert BillingDate not in REGISTERED


# ---------------------------------------------------------------------------
# The probe sits where it has to sit
# ---------------------------------------------------------------------------
def test_an_enum_member_wins_over_the_type_it_is_built_on() -> None:
    """Why the probe precedes ``str`` and ``int | float`` in the chain.

    A ``StrEnum`` member really is a ``str`` and an ``IntEnum`` member really is an
    ``int``. Moving the probe below either branch is a one-line change that leaves
    every other test green.
    """
    from enum import IntEnum, StrEnum

    class Tag(StrEnum):
        A = "a"

    class Level(IntEnum):
        LOW = 1

    assert isinstance(Tag.A, str)
    assert isinstance(Level.LOW, int)
    assert built_by(Tag.A) is EnumExpect
    assert built_by(Level.LOW) is EnumExpect


def test_an_enum_class_wins_over_the_collection_it_looks_like() -> None:
    """Why the ``type[Any]`` overload leads the static table.

    ``EnumMeta`` gives an enum class ``__len__``, ``__iter__`` and ``__contains__``,
    so it satisfies ``Collection``. Both halves have to answer ``TypeExpect``, and
    the static half only does so while the ``type[Any]`` overload comes first --
    the typing corpus cannot catch a regression here on its own unless it holds an
    enum class.
    """
    from enum import Enum

    class Colour(Enum):
        RED = 1
        BLUE = 2

    assert len(Colour) == 2, "the shape that made the two halves disagree"
    assert isinstance(Colour, type)
    assert built_by(Colour) is not CollectionExpect


# ---------------------------------------------------------------------------
# The two spellings of "is it callable" must agree
# ---------------------------------------------------------------------------
def test_the_type_and_value_callable_checks_give_the_same_answer() -> None:
    """A seam created on purpose, so it gets a test.

    ``_dispatch`` asks ``callable(value)`` -- a C-level slot test, and the cheapest
    spelling there is -- while ``claimed_by`` has to reproduce the same answer from
    a type alone, by walking the MRO, because ``register()`` is handed a type and
    no value. One question, two spellings: if they ever disagree, ``register()``
    starts refusing types the dispatch would not claim, or worse, accepting ones it
    would.

    ``hasattr(subject_type, "__call__")`` is the spelling that looks right and is
    wrong -- it finds ``type.__call__`` on the metaclass, so it answers ``True``
    for every class ever written. ``Plain`` below is the case that catches it.
    """
    from collections import OrderedDict
    from datetime import date

    class Plain:
        __slots__ = ()

    class Handler:
        __slots__ = ()

        def __call__(self) -> None: ...

    class InheritsCall(Handler):
        __slots__ = ()

    candidates: list[object] = [
        Plain(),
        Handler(),
        InheritsCall(),
        object(),
        len,
        (lambda: None),
        Plain,
        date(2020, 1, 1),
        OrderedDict(),
        "text",
        3,
        [1],
    ]
    for value in candidates:
        subject_type = type(value)
        from_value = built_by(value) is CallableExpect
        from_type = subjects.claimed_by(subject_type) is CallableExpect
        assert from_value == from_type, (
            f"{subject_type.__name__}: `_dispatch` says callable={from_value} while "
            f"`claimed_by` says {from_type}; `register()` and the dispatch would disagree"
        )


# ---------------------------------------------------------------------------
# The exact table leads, and no mock can reach it
# ---------------------------------------------------------------------------
def test_no_mock_spelling_has_the_type_of_a_built_in() -> None:
    """The claim that lets the exact table run before the mock check.

    Leading the dispatch with ``is_mock`` spends a third of the hottest path in
    the library on every ``expect(3)``, ruling out something an ``int`` cannot be.
    The table is keyed on *identity of type*, so a hit means ``type(value) is
    int``, and putting it first is sound only if no mock can ever say that.

    Every spelling ``unittest.mock`` offers is checked here rather than argued
    about, including ``m.__class__ = int`` -- which makes ``isinstance(m, int)``
    true while ``type(m)`` still reads ``MagicMock``, because ``__class__`` is an
    attribute and ``type()`` reads the object header. That one is the whole reason
    this test enumerates instead of asserting.
    """
    from unittest.mock import (
        AsyncMock,
        MagicMock,
        Mock,
        NonCallableMock,
        create_autospec,
    )

    class Subclassed(MagicMock):
        pass

    # Widened on purpose: assigning `__class__` is what the trick *is*, and both
    # checkers refuse it on a `MagicMock` -- which is itself the point being made.
    patched: Any = MagicMock()
    patched.__class__ = int

    mocks: list[object] = [
        Mock(),
        MagicMock(),
        AsyncMock(),
        NonCallableMock(),
        Mock(spec=int),
        Mock(spec=str),
        Mock(spec_set=list),
        create_autospec(int),
        create_autospec(dict),
        MagicMock(spec=dict),
        Subclassed(),
        patched,
    ]
    exact = _internal("_EXACT_SUBJECTS")
    for mock in mocks:
        assert type(mock) not in exact, (
            f"{type(mock).__name__} is in the exact table, so the dispatch would build a "
            f"built-in subject for a mock. Put `is_mock` back in front of the table."
        )
    assert isinstance(patched, int), "the trick this test exists for stopped working"
    assert type(patched) is not int, "...while `type()` still reads a mock class"


def test_every_mock_still_reaches_the_mock_subject() -> None:
    """The other half: no mock spelling may lose its subject to the table in front."""
    from unittest.mock import AsyncMock, MagicMock, Mock, NonCallableMock, create_autospec

    for mock in (Mock(), MagicMock(), AsyncMock(), NonCallableMock(), create_autospec(dict)):
        assert built_by(mock) is MockExpect, f"{type(mock).__name__} lost its subject"


def test_a_registered_type_still_loses_to_a_mock_of_it() -> None:
    """A mock of a registered type is dispatched as a mock, not as the registration.

    ``_REGISTERED`` is consulted behind the mock check, so ``create_autospec`` of a
    type with a subject of its own still reaches :class:`MockExpect` -- the mock is
    what the test is holding, whatever it is standing in for.
    """

    class Payload:
        __slots__ = ()

    class PayloadExpect(Expect[Payload]):
        __slots__ = ()

    register(Payload, PayloadExpect)
    try:
        from unittest.mock import create_autospec

        assert built_by(Payload()) is PayloadExpect
        assert built_by(create_autospec(Payload)) is MockExpect
    finally:
        del REGISTERED[Payload]


def test_a_callable_type_must_not_join_the_table_that_leads() -> None:
    """The trap that keeps ``_CALLABLE_TYPES`` a separate table.

    Dispatching a callable through the whole ``issubclass`` chain is the slowest
    route in the library, so the three callable types live in a dict of their own.
    Folding them into ``_EXACT_SUBJECTS`` is the obvious next step and it is wrong:
    that table runs *before* the mock check, and
    ``create_autospec(some_function)`` builds a genuine function wrapper carrying
    the target's signature, so its ``type()`` really is ``function``. In front of
    ``is_mock``, every autospecced function would quietly become a
    ``CallableExpect``.

    Nothing in ``_EXACT_SUBJECTS`` has that property, which is the whole reason
    there are two tables rather than one.
    """
    from unittest.mock import create_autospec

    def target(a: int, b: int) -> int:
        return a + b

    autospecced = create_autospec(target)
    assert type(autospecced) is FunctionType, "the trap this test exists for changed shape"

    exact = _internal("_EXACT_SUBJECTS")
    callables = _internal("_CALLABLE_TYPES")
    assert FunctionType in callables, "the fast path for callables went missing"
    for kind in callables:
        assert kind not in exact, (
            f"{kind.__name__} is in the table that leads, so an autospecced callable "
            f"would be dispatched as a plain callable instead of as a mock"
        )
    assert built_by(autospecced) is MockExpect
    assert built_by(target) is CallableExpect


def test_every_callable_spelling_reaches_the_callable_subject() -> None:
    """One row per shape, because they are three different types wearing one word."""

    class Service:
        def fetch(self) -> None: ...

    def plain() -> None: ...

    service = Service()
    spellings: list[object] = [plain, lambda: None, len, service.fetch, {}.keys]
    for value in spellings:
        assert built_by(value) is CallableExpect, f"{type(value).__name__} lost its subject"
