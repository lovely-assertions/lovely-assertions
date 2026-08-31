"""Generate ``docs/reference/assertions.md`` from ``src/lovely_assertions/``.

    uv run python scripts/generate_reference.py [destination]

Three things are derived rather than written, because a reference that has
drifted from the code is worse than none:

* **The catalogue.** Every subject class is parsed out of the source. The groups
  are the ``# -- ... --`` banners the modules already sort their methods into,
  the signatures come from the AST and the descriptions are the first line of
  each docstring. A method that is added, renamed or regrouped moves in the
  document on the next run, and a signature cannot go stale because it is never
  transcribed. Parameter names are cross-checked against ``inspect.signature``
  on the live classes, so a mis-parse fails the run instead of the reader.
* **The dispatch table.** The order is the ``@overload`` chain on ``expect()``;
  the subject in each row is obtained by *calling* ``expect()`` with a value of
  that shape and asking what came back.
* **Every failure message.** Each example is written to a temporary directory as
  a standalone module, executed, and the ``AssertionFailure`` it raises is
  quoted verbatim. Subject-name recovery reads the source file of the calling
  frame, so the example has to be a real file for the message to be the real
  one. An example that stops failing -- or starts failing differently -- changes
  the document instead of rotting inside it.

Only the connective prose is written by hand, and it is kept to claims the
generated material beside it demonstrates.
"""

import ast
import contextlib
import copy
import inspect
import re
import runpy
import sys
import tempfile
import textwrap
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from pathlib import Path, PurePosixPath
from unittest.mock import Mock


def _find_repo() -> Path:
    """The repository root: the nearest ancestor holding ``src/lovely_assertions``."""
    for start in (Path(__file__).resolve(), Path.cwd().resolve() / "_"):
        for candidate in start.parents:
            if (candidate / "src" / "lovely_assertions" / "__init__.py").exists():
                return candidate
    message = "cannot locate the repository root from " + str(Path(__file__).resolve())
    raise SystemExit(message)


REPO = _find_repo()
SRC = REPO / "src" / "lovely_assertions"
OUT = REPO / "docs" / "reference" / "assertions.md"

sys.path.insert(0, str(REPO / "src"))

import lovely_assertions as la  # noqa: E402  (the import needs the sys.path entry set above)

# ---------------------------------------------------------------------------
# Reading the source.
# ---------------------------------------------------------------------------
SECTION = re.compile(r"^\s*#\s*--\s*(.+?)\s*-{2,}\s*$")


@dataclass(slots=True)
class Method:
    """One public method, as the source declares it."""

    name: str
    signatures: list[str]
    summary: str
    is_property: bool
    group: str


@dataclass(slots=True)
class Subject:
    """One subject class, with its methods in source order."""

    name: str
    display: str
    declaration: str
    methods: list[Method] = field(default_factory=list["Method"])

    def groups(self) -> list[tuple[str, list[Method]]]:
        ordered: list[tuple[str, list[Method]]] = []
        for method in self.methods:
            if not ordered or ordered[-1][0] != method.group:
                ordered.append((method.group, []))
            ordered[-1][1].append(method)
        return ordered


def _unquote(node: ast.expr) -> ast.expr:
    """A string annotation, turned back into the expression it spells."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return node
    return node


def _annotation(node: ast.expr | None) -> str:
    if node is None:
        return ""
    return ast.unparse(_unquote(copy.deepcopy(node)))


def _aliases(tree: ast.Module, /) -> dict[str, str]:
    """The PEP 695 aliases a module can see, ``{"DateTime": "datetime"}``.

    Only the one-name-to-one-name kind, which is all the subject modules declare
    and all this needs to undo.

    Aliases imported from a sibling are followed. A subject split into one file
    per seam declares its base in the assembly and the alias in the module that
    holds the shared root, and an alias exists precisely so a base can name a
    type the package refuses to import -- publishing the alias name instead of
    the type would tell a reader to import something that is not there.
    """
    found: dict[str, str] = {}
    for item in tree.body:
        if isinstance(item, ast.TypeAlias) and isinstance(item.value, ast.Name):
            found[item.name.id] = item.value.id
        elif isinstance(item, ast.ImportFrom):
            within = (item.module or "").removeprefix("lovely_assertions.")
            source = SRC / (within.replace(".", "/") + ".py")
            if within == (item.module or "") or not source.exists():
                continue
            declared = _aliases(ast.parse(source.read_text(encoding="utf-8")))
            found.update(
                {alias.name: declared[alias.name] for alias in item.names if alias.name in declared}
            )
    return found


def _base(node: ast.expr, aliases: dict[str, str] | None = None) -> str:
    """One base class, as the reader wants it rather than as the source spells it.

    ``_datetime.py`` never imports ``datetime`` at runtime, so it cannot name the
    type in a base -- a base is evaluated when the class is created. It writes
    ``DateExpect[_DateTime]`` against a PEP 695 alias rather than the quoted
    ``DateExpect["datetime"]``, because on CPython 3.14 the quoted spelling builds
    a ``ForwardRef`` and building one imports ``annotationlib``, ``ast`` and
    ``enum`` -- three modules importing the library must not pull in.

    Both spellings are the library's import discipline showing through, and the
    reader wants neither. The quotes come off and the alias is resolved, so the
    line reads ``class DateTimeExpect(DateExpect[datetime], ...)`` either way.
    """
    node = copy.deepcopy(node)
    for child in ast.walk(node):
        if isinstance(child, ast.Subscript):
            child.slice = _unquote(child.slice)
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and aliases and child.id in aliases:
            child.id = aliases[child.id]
    return ast.unparse(node)


def _default(node: ast.expr) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return '"' + node.value + '"'
    return ast.unparse(node)


def _parameter(arg: ast.arg, default: ast.expr | None) -> str:
    piece = arg.arg
    annotation = _annotation(arg.annotation)
    if annotation:
        piece += ": " + annotation
    if default is not None:
        piece += (" = " if annotation else "=") + _default(default)
    return piece


def _type_params(node: ast.FunctionDef | ast.ClassDef) -> str:
    """The ``[S: Bound]`` clause, when the declaration carries one."""
    if not node.type_params:
        return ""
    rendered: list[str] = []
    for parameter in node.type_params:
        # `ast.type_param` is the union base and declares no `name`; each of the
        # three concrete forms does.
        if not isinstance(parameter, ast.TypeVar | ast.ParamSpec | ast.TypeVarTuple):
            continue
        piece = parameter.name
        bound = getattr(parameter, "bound", None)
        if bound is not None:
            piece += ": " + _annotation(bound)
        default = getattr(parameter, "default_value", None)
        if default is not None:
            piece += " = " + _annotation(default)
        rendered.append(piece)
    return "[" + ", ".join(rendered) + "]"


def _signature(fn: ast.FunctionDef) -> str:
    """The signature as the source declares it.

    ``self`` is dropped where it is a bare parameter and kept where it carries an
    annotation, because there the annotation is the assertion's precondition --
    what ``is_not_none`` may be called on, what ``contains_match`` may be called
    on.
    """
    args = fn.args
    parts: list[str] = []
    positional = list(args.posonlyargs) + list(args.args)
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults))
    defaults += list(args.defaults)
    for index, (arg, default) in enumerate(zip(positional, defaults, strict=True)):
        if index == 0 and arg.arg == "self" and arg.annotation is None:
            continue
        parts.append(_parameter(arg, default))
        if args.posonlyargs and arg is args.posonlyargs[-1]:
            parts.append("/")
    if args.vararg is not None:
        annotation = _annotation(args.vararg.annotation)
        parts.append("*" + args.vararg.arg + (": " + annotation if annotation else ""))
    elif args.kwonlyargs:
        parts.append("*")
    parts += [
        _parameter(arg, default)
        for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True)
    ]
    if args.kwarg is not None:
        annotation = _annotation(args.kwarg.annotation)
        parts.append("**" + args.kwarg.arg + (": " + annotation if annotation else ""))
    returns = _annotation(fn.returns)
    head = fn.name + _type_params(fn) + "(" + ", ".join(parts) + ")"
    return head + " -> " + returns if returns else head


def _first_line(node: ast.FunctionDef | ast.ClassDef) -> str:
    doc = ast.get_docstring(node, clean=True) or ""
    return doc.split("\n", 1)[0].strip()


def _decorators(fn: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for decorator in fn.decorator_list:
        if isinstance(decorator, ast.Name):
            names.add(decorator.id)
        elif isinstance(decorator, ast.Attribute):
            names.add(decorator.attr)
    return names


def _group_title(title: str) -> str:
    """A ``# -- ... --`` banner as a section heading: trimmed and capitalised."""
    title = title.strip()
    return title[:1].upper() + title[1:]


def _banner_between(lines: list[str], start: int, end: int) -> str:
    """The last ``# -- ... --`` banner between two 1-based source lines."""
    found = ""
    for index in range(start, end):
        match = SECTION.match(lines[index - 1])
        if match is not None:
            found = _group_title(match.group(1))
    return found


def _is_seam(rendered: str, /) -> bool:
    """Whether a base is one this package's decomposition introduced.

    A subject is assembled from one mixin per seam over a root they share, and
    none of those has a section on this page. Naming one would send a reader
    looking for a heading that does not exist.
    """
    stem = rendered.partition("[")[0]
    return stem.endswith(("Assertions", "Base"))


def _through_the_seams(bases: list[str], class_name: str, /) -> list[str]:
    """What a subject inherits, once its seams are looked past."""
    roots = {name.partition("[")[0] for name in bases if name.partition("[")[0].endswith("Base")}
    for base_module, base_name, _ in SHARED_BASES.get(class_name, ()):
        if base_name not in roots:
            continue
        tree = ast.parse((SRC / base_module).read_text(encoding="utf-8"))
        node = next(
            item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == base_name
        )
        aliases = _aliases(tree)
        return [rendered for base in node.bases if not _is_seam(rendered := _base(base, aliases))]
    return []


def read_subject(module: str, class_name: str, display: str) -> Subject:
    path = SRC / module
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    node = next(
        item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == class_name
    )
    declaration = "class " + class_name + _type_params(node)
    if node.bases:
        aliases = _aliases(tree)
        # The seams a subject is assembled from are left out. Each is one file's
        # worth of assertions, listed under its own heading further down, and
        # naming the class here would tell a reader about an arrangement they
        # cannot see and must not depend on. Every other base stays: what a
        # subject inherits from another subject, or from a base the prose around
        # it refers to, is something they act on.
        bases = [_base(base, aliases) for base in node.bases]
        shown = [name for name in bases if not _is_seam(name)]
        if not shown:
            # Every base is a seam, so the subject would declare nothing at all.
            # Resolve through the root the seams share: what it inherits is what
            # the subject inherits, and that is what a reader acts on.
            shown = _through_the_seams(bases, class_name)
        if shown:
            declaration += "(" + ", ".join(shown) + ")"
    subject = Subject(name=class_name, display=display, declaration=declaration)

    overloads: dict[str, list[str]] = {}
    implementations: dict[str, ast.FunctionDef] = {}
    order: list[str] = []
    for item in node.body:
        if not isinstance(item, ast.FunctionDef) or item.name.startswith("_"):
            continue
        if "overload" in _decorators(item):
            overloads.setdefault(item.name, []).append(_signature(item))
            continue
        implementations[item.name] = item
        order.append(item.name)

    previous_end = node.lineno + 1
    for name in order:
        fn = implementations[name]
        head = min([decorator.lineno for decorator in fn.decorator_list] or [fn.lineno])
        group = _banner_between(lines, previous_end, head)
        previous_end = (fn.end_lineno or fn.lineno) + 1
        subject.methods.append(
            Method(
                name=name,
                signatures=overloads.get(name) or [_signature(fn)],
                summary=_first_line(fn),
                is_property="property" in _decorators(fn),
                group=group,
            )
        )
    carried = ""
    for method in subject.methods:
        carried = method.group or carried
        method.group = carried
    return subject


def build_subjects() -> dict[str, Subject]:
    """Every subject that gets a section, catalogue assembled.

    A subject's own catalogue is what its class declares, plus whatever a private
    shared base contributes to it (:data:`SHARED_BASES`). The shared groups come
    first because they are the more basic ones, and because a reader meeting
    ``DateExpect`` wants ``is_before`` before ``is_weekend``.
    """
    subjects: dict[str, Subject] = {}
    for module, name, display in TARGETS:
        subject = read_subject(module, name, display)
        for method in subject.methods:
            method.group = method.group or GROUP_DEFAULT.get(name, "")
        shared: list[Method] = []
        for base_module, base_name, title in SHARED_BASES.get(name, ()):
            base = read_subject(base_module, base_name, base_name)
            for method in base.methods:
                method.group = method.group or title
                # An explicit `self:` names the class that declares the method.
                # Inside a package split by seam that is a mixin, and naming one
                # in the reference tells a reader about an arrangement they
                # cannot see and must not depend on.
                method.signatures = [
                    signature.replace(base_name, name) for signature in method.signatures
                ]
            shared += base.methods
        subject.methods = shared + subject.methods
        subjects[name] = subject
    return subjects


def read_function(module: str, name: str) -> Method:
    """A module-level function, for the exports that are not methods."""
    tree = ast.parse((SRC / module).read_text(encoding="utf-8"))
    node = next(
        item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return Method(
        name=name,
        signatures=[_signature(node)],
        summary=_first_line(node),
        is_property=False,
        group="",
    )


def read_class_summary(module: str, name: str) -> str:
    tree = ast.parse((SRC / module).read_text(encoding="utf-8"))
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == name)
    return _first_line(node)


def read_value(module: str, name: str) -> str:
    """A module-level constant, described by the ``#:`` comment above it.

    ``once`` and ``twice`` are values rather than functions, so there is no
    docstring to read; the library documents them where Sphinx looks, in the
    comment block immediately above the assignment.
    """
    lines = (SRC / module).read_text(encoding="utf-8").splitlines()
    tree = ast.parse("\n".join(lines))
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.AnnAssign)
        and isinstance(item.target, ast.Name)
        and item.target.id == name
    )
    comment: list[str] = []
    index = node.lineno - 1
    while index > 0 and lines[index - 1].lstrip().startswith("#:"):
        comment.insert(0, lines[index - 1].lstrip()[2:].strip())
        index -= 1
    return _first_sentence(" ".join(comment))


def _first_sentence(text: str) -> str:
    """Up to the first full stop, so a comment block fits in a table cell."""
    head, stop, _ = text.partition(". ")
    return head + "." if stop else text


def verify(subject: Subject, cls: type) -> list[str]:
    """Cross-check what was parsed against the live objects."""
    problems: list[str] = []
    for method in subject.methods:
        attribute = inspect.getattr_static(cls, method.name)
        if isinstance(attribute, property):
            if not method.is_property:
                problems.append(subject.name + "." + method.name + ": property not recognised")
            continue
        problems += [
            subject.name + "." + method.name + ": parameter " + parameter + " missing"
            for parameter in list(inspect.signature(attribute).parameters)[1:]
            if not any(parameter in rendered for rendered in method.signatures)
        ]
    return problems


# ---------------------------------------------------------------------------
# Docstrings are reStructuredText; the document is Markdown.
# ---------------------------------------------------------------------------
_ROLES = (":meth:`", ":attr:`", ":class:`", ":func:`", ":data:`", ":exc:`")


def _role_at(text: str, index: int) -> tuple[str, int] | None:
    for role in _ROLES:
        if not text.startswith(role, index):
            continue
        end = text.find("`", index + len(role))
        if end == -1:
            return None
        target = text[index + len(role) : end].lstrip("~")
        if "lovely_assertions." in target:
            target = target.rpartition(".")[2]
        return "`" + target + "`", end + 1
    return None


def rst_to_md(text: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(text):
        role = _role_at(text, index)
        if text.startswith("``", index):
            end = text.find("``", index + 2)
            if end == -1:
                out.append(text[index:])
                break
            out.append("`" + text[index + 2 : end] + "`")
            index = end + 2
        elif role is not None:
            out.append(role[0])
            index = role[1]
        elif text.startswith(" -- ", index):
            out.append(" — ")
            index += 4
        else:
            out.append(text[index])
            index += 1
    return "".join(out)


def summary_of(text: str) -> str:
    """A docstring's first line, as the one-line description of its method."""
    return rst_to_md(text).strip()


# ---------------------------------------------------------------------------
# Examples. Each one is a real file, run for real.
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class Example:
    """One example: what the document shows, and what running it produced."""

    source: str
    message: str


def run_example(directory: Path, name: str, source: str, *, must_fail: bool) -> Example:
    path = directory / (name + ".py")
    path.write_text(source, encoding="utf-8")
    message = ""
    try:
        runpy.run_path(str(path))
    except la.AssertionFailure as failure:
        message = str(failure)
    if must_fail and not message:
        complaint = "example " + name + " was supposed to fail and did not"
        raise SystemExit(complaint)
    if not must_fail and message:
        complaint = "example " + name + " was supposed to pass, but: " + message
        raise SystemExit(complaint)
    return Example(source=source.rstrip("\n"), message=message)


def load_examples() -> dict[str, Example]:
    with tempfile.TemporaryDirectory() as name:
        directory = Path(name)
        # Run them *in* that directory. A path assertion reports the path it was
        # given, so an example about a file that is not there has to be run
        # somewhere it is reliably not there -- and an empty temporary directory
        # is that, whatever the repository happens to hold.
        with contextlib.chdir(directory):
            examples = {
                key: run_example(directory, key, source, must_fail=False)
                for key, source in PASSING.items()
            }
            examples |= {
                key: run_example(directory, key, source, must_fail=True)
                for key, source in FAILING.items()
            }
    return examples


PASSING: dict[str, str] = {
    "intro": """\
from datetime import date
from pathlib import Path

from lovely_assertions import expect

expect("hello").starts_with("he").and_.has_length(5)
expect([3, 1, 2]).has_length(3).and_.contains(2)
expect({"host": "db-01"}).contains_key("host").whose_value.is_equal_to("db-01")
expect(7).is_between(1, 10)
expect(date(2024, 3, 16)).is_weekend()
expect(Path("build/report.txt")).has_suffix(".txt")
""",
    "continuations": """\
from lovely_assertions import expect

response = {"status": "ok"}

expect(response).contains_key("status").whose_value.is_equal_to("ok")
expect(["only"]).contains_single().which.is_equal_to("only")
expect([1, 2, 3]).has_element_at(0, 1).and_.has_length(3)
expect(3).is_instance_of(int).and_.is_positive()
""",
    "rebind": """\
from lovely_assertions import expect

response = {"content-type": "application/json"}

content_type = expect(response).contains_key("content-type").subject
expect(content_type).contains("json").and_.starts_with("application/")
""",
    "matchers": """\
from lovely_assertions import any_instance_of, close_to, containing, expect, string_matching

response = {
    "id": 4171,
    "token": "eyJhbGciOiJIUzI1NiJ9",
    "ttl": 59.7,
    "tags": ["beta", "eu-west"],
}

expect(response).is_equal_to(
    {
        "id": any_instance_of(int),
        "token": string_matching(r"^ey"),
        "ttl": close_to(60, tol=1),
        "tags": containing(["eu-west"]),
    }
)
""",
    "expectation": """\
from lovely_assertions import any_instance_of, expect, one_of

counts = {"hits": 12, "misses": 3, "retries": 1}
expected: dict[str, int] = {"hits": any_instance_of(int), "misses": 3, "retries": one_of(0, 1)}

expect(counts).is_equal_to(expected)
""",
    "refused": """\
from lovely_assertions import any_instance_of, expect, expect_raises

with expect_raises(TypeError) as refused:
    expect(any_instance_of(int))

refused.with_message_containing("<any int> is a matcher, so it belongs in an expectation")
""",
    "caught": """\
from lovely_assertions import expect_raises


def parse(text: str) -> int:
    return int(text)


with expect_raises(ValueError) as caught:
    parse("nope")

caught.with_message_containing("invalid literal")
""",
}


FAILING: dict[str, str] = {
    "because": """\
from lovely_assertions import expect

retries = 5
expect(retries).is_less_than(3, because="the backoff caps at three attempts")
""",
    "difference": """\
from lovely_assertions import expect

config = {"host": "db-01", "port": 8080, "tls": True}
expect(config).is_equal_to({"host": "db-01", "port": 9090})
""",
    "Expect": """\
from dataclasses import dataclass

from lovely_assertions import expect


@dataclass(frozen=True, slots=True)
class Money:
    cents: int
    currency: str


price = Money(1999, "EUR")
expect(price).is_equal_to(Money(2499, "EUR"))
""",
    "BoolExpect": """\
from lovely_assertions import expect

feature_enabled = False
expect(feature_enabled).is_true()
""",
    "StringExpect": """\
from lovely_assertions import expect

hostname = "db-01.internal"
expect(hostname).ends_with(".example.com")
""",
    "OrderedExpect": """\
from decimal import Decimal

from lovely_assertions import expect

balance = Decimal("-12.50")
expect(balance).is_positive()
""",
    "NumericExpect": """\
from lovely_assertions import expect

measured = 9.9
expect(measured).is_close_to(10.0, tol=0.05)
""",
    "CollectionExpect": """\
from lovely_assertions import expect

response_headers = {"content-type": "application/json", "content-length": "27"}
expect(response_headers.keys()).contains("authorization")
""",
    "SequenceExpect": """\
from lovely_assertions import expect

order_totals = [3, 1, 2]
expect(order_totals).is_sorted()
""",
    "MappingExpect": """\
from lovely_assertions import expect

server_config = {"host": "db-01", "port": 5432}
expect(server_config).contains_key("hostname")
""",
    "DateExpect": """\
from datetime import date

from lovely_assertions import expect

invoice_date = date(2024, 3, 16)
expect(invoice_date).is_weekday()
""",
    "DateTimeExpect": """\
from datetime import datetime

from lovely_assertions import expect

recorded_at = datetime(2024, 3, 16, 14, 30)
expect(recorded_at).is_utc()
""",
    "TimeExpect": """\
from datetime import time

from lovely_assertions import expect

cutoff = time(17, 30)
expect(cutoff).is_midnight()
""",
    "TimeDeltaExpect": """\
from datetime import timedelta

from lovely_assertions import expect

elapsed = timedelta(seconds=95)
expect(elapsed).is_shorter_than(timedelta(seconds=60))
""",
    "PurePathExpect": """\
from pathlib import PurePosixPath

from lovely_assertions import expect

artefact = PurePosixPath("build/report.txt")
expect(artefact).has_suffix(".pdf")
""",
    "PathExpect": """\
from pathlib import Path

from lovely_assertions import expect

config_file = Path("settings.toml")
expect(config_file).exists()
""",
    "EnumExpect": """\
from enum import Enum

from lovely_assertions import expect


class Status(Enum):
    PENDING = "pending"
    SHIPPED = "shipped"


order_status = Status.PENDING
expect(order_status).has_name("SHIPPED")
""",
    "CallableExpect": """\
from lovely_assertions import expect


def parse(text: str) -> int:
    return int(text)


expect(lambda: parse("nope")).raises(KeyError)
""",
    "RaisedExpect": """\
from lovely_assertions import expect_raises


def parse(text: str) -> int:
    return int(text)


with expect_raises(ValueError) as caught:
    parse("nope")

caught.with_message_containing("not a number")
""",
    "WarnedExpect": """\
import warnings

from lovely_assertions import expect_warns


def parse_date(text: str) -> str:
    warnings.warn("parse_date() is deprecated since 2.0", DeprecationWarning, stacklevel=2)
    return text


with expect_warns(DeprecationWarning) as warned:
    parse_date("2024-03-16")

warned.with_message_containing("use parse_iso instead")
""",
    "TypeExpect": """\
from lovely_assertions import expect


class Repository:
    pass


expect(Repository).is_subclass_of(dict)
""",
    "MockExpect": """\
from unittest.mock import Mock

from lovely_assertions import expect

send = Mock()
send("welcome", to="ada@example.com")

expect(send).was_called_with("welcome", to="grace@example.com")
""",
    "soft": """\
from lovely_assertions import expect, soft_assertions

total = -3
items: list[str] = []

with soft_assertions("checkout"):
    expect(total).is_positive()
    expect(items).is_not_empty()
""",
}


# ---------------------------------------------------------------------------
# What the document is about.
# ---------------------------------------------------------------------------
class Colour(Enum):
    """A real enum, so the tables below can show a real class and a real member."""

    RED = 1
    GREEN = 2


#: ``(module, class, display)`` for every subject that gets a section, in the
#: order the sections appear. A base comes before what inherits it --
#: ``OrderedExpect`` before ``NumericExpect``, ``CollectionExpect`` before
#: ``SequenceExpect``, ``PurePathExpect`` before ``PathExpect`` -- so that an
#: "inherited from" line always points backwards, and the four date subjects and
#: the two path subjects sit together. The two subjects a call *hands back* --
#: ``RaisedExpect`` and ``WarnedExpect`` -- follow the callable that produces
#: them, for the same reason.
TARGETS: list[tuple[str, str, str]] = [
    ("_core/__init__.py", "Expect", "Expect[T]"),
    ("_bool.py", "BoolExpect", "BoolExpect"),
    ("_string/__init__.py", "StringExpect", "StringExpect"),
    ("_ordered.py", "OrderedExpect", "OrderedExpect[T]"),
    ("_numeric.py", "NumericExpect", "NumericExpect"),
    ("_collection/__init__.py", "CollectionExpect", "CollectionExpect[E, C]"),
    ("_sequence/__init__.py", "SequenceExpect", "SequenceExpect[E]"),
    ("_mapping/__init__.py", "MappingExpect", "MappingExpect[K, V]"),
    ("_datetime/_calendar.py", "DateExpect", "DateExpect[T]"),
    ("_datetime/_instant.py", "DateTimeExpect", "DateTimeExpect"),
    ("_datetime/_time.py", "TimeExpect", "TimeExpect"),
    ("_datetime/_duration.py", "TimeDeltaExpect", "TimeDeltaExpect"),
    ("_path/_purepath.py", "PurePathExpect", "PurePathExpect[T]"),
    ("_path/__init__.py", "PathExpect", "PathExpect"),
    ("_enum.py", "EnumExpect", "EnumExpect[T]"),
    ("_callable/_calling.py", "CallableExpect", "CallableExpect"),
    ("_callable/_raised.py", "RaisedExpect", "RaisedExpect[E]"),
    ("_warnings/_subject.py", "WarnedExpect", "WarnedExpect[W]"),
    ("_type/_subject.py", "TypeExpect", "TypeExpect"),
    ("_mock/_subject.py", "MockExpect", "MockExpect"),
]

#: Private base classes whose assertions belong in a public subject's own
#: catalogue: ``_datetime.py`` shares them between two public subjects and
#: exports neither, so an "inherited from" line would point at a section that
#: does not exist. Listed base-first, and the title is supplied here because
#: ``_datetime.py`` groups its methods by class rather than by ``# -- ... --``
#: banner. ``DateTimeExpect`` takes only the clock half: it inherits
#: ``DateExpect``, which already carries the ordering half.
SHARED_BASES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "MockExpect": (
        ("_mock/_base.py", "MockBase", "How often"),
        ("_mock/_counting.py", "CountingAssertions", "How often"),
        ("_mock/_arguments.py", "ArgumentAssertions", "With what"),
        ("_mock/_continuations.py", "ContinuationAssertions", "Continuations"),
    ),
    "CallableExpect": (
        ("_callable/_raising.py", "RaisingAssertions", "Raising"),
        ("_callable/_warning_form.py", "WarningFormAssertions", "Warning"),
    ),
    "RaisedExpect": (
        ("_callable/_continuation.py", "ContinuationAssertions", "Continuations"),
        ("_callable/_message.py", "MessageAssertions", "Message"),
        ("_callable/_notes.py", "NoteAssertions", "Notes (PEP 678)"),
    ),
    "TypeExpect": (
        ("_type/_subclassing.py", "SubclassAssertions", "Inheritance"),
        ("_type/_attributes.py", "AttributeAssertions", "Attributes and methods"),
        ("_type/_abstractness.py", "AbstractnessAssertions", "Abstractness"),
        ("_type/_conformance.py", "ConformanceAssertions", "Protocols"),
    ),
    "PurePathExpect": (
        ("_path/_names.py", "NameAssertions", "The pieces of a name"),
        ("_path/_placement.py", "PlacementAssertions", "Absoluteness"),
    ),
    "PathExpect": (
        ("_path/_presence.py", "PresenceAssertions", "Presence"),
        ("_path/_emptiness.py", "EmptinessAssertions", "Emptiness"),
        ("_path/_size.py", "SizeAssertions", "Size"),
        ("_path/_contents.py", "ContentAssertions", "Contents"),
        ("_path/_entries.py", "EntryAssertions", "Directory entries"),
        ("_path/_identity.py", "IdentityAssertions", "Identity on disk"),
    ),
    "SequenceExpect": (
        ("_sequence/_base.py", "SequenceBase", "Message positions"),
        ("_sequence/_equality.py", "EqualityAssertions", "Ordered equality"),
        ("_sequence/_access.py", "AccessAssertions", "Element access"),
        ("_sequence/_containment.py", "ContainmentAssertions", "Containment"),
        ("_sequence/_ordering.py", "OrderingAssertions", "Ordering"),
        ("_sequence/_projection.py", "ProjectionAssertions", "Projection"),
        ("_sequence/_nested.py", "NestedAssertions", "Nested assertions"),
    ),
    "MappingExpect": (
        ("_mapping/_size.py", "SizeAssertions", "Size"),
        ("_mapping/_views.py", "ViewAssertions", "Views"),
        ("_mapping/_keys.py", "KeyAssertions", "Keys"),
        ("_mapping/_values.py", "ValueAssertions", "Values"),
        ("_mapping/_entries.py", "EntryAssertions", "Entries"),
    ),
    "CollectionExpect": (
        ("_collection/_base.py", "CollectionBase", "Message positions"),
        ("_collection/_emptiness.py", "EmptinessAssertions", "Emptiness"),
        ("_collection/_length.py", "LengthAssertions", "Length"),
        ("_collection/_containment.py", "ContainmentAssertions", "Containment"),
        ("_collection/_predicates.py", "PredicateAssertions", "Containment"),
        ("_collection/_screening.py", "ScreeningAssertions", "Containment"),
        ("_collection/_relations.py", "RelationAssertions", "Set-like relations"),
        ("_collection/_overlap.py", "OverlapAssertions", "Set-like relations"),
        ("_collection/_multi_item.py", "MultiItemAssertions", "Multi-item membership"),
        ("_collection/_element_types.py", "ElementTypeAssertions", "Element types"),
        ("_collection/_nested.py", "NestedAssertions", "Nested assertions"),
        (
            "_collection/_wildcards.py",
            "WildcardAssertions",
            "Wildcard matching (string collections)",
        ),
        ("_collection/_projection.py", "ProjectionAssertions", "Projection"),
    ),
    "StringExpect": (
        ("_string/_size.py", "SizeAssertions", "Emptiness"),
        ("_string/_caseless.py", "CaselessEqualityAssertions", "Caseless equality"),
        ("_string/_containment.py", "ContainmentAssertions", "Containment"),
        ("_string/_containment_many.py", "MultipleContainmentAssertions", "Containment"),
        ("_string/_containment_caseless.py", "CaselessContainmentAssertions", "Containment"),
        ("_string/_edges.py", "EdgeAssertions", "Edges"),
        ("_string/_regex.py", "RegexAssertions", "Regular expressions"),
        ("_string/_wildcards.py", "WildcardAssertions", "Wildcards"),
        ("_string/_case.py", "CaseAssertions", "Case"),
        ("_string/_classes_letters.py", "LetterClassAssertions", "Character classes"),
        ("_string/_classes_encoding.py", "EncodingClassAssertions", "Character classes"),
        ("_string/_identifier.py", "IdentifierAssertions", "Identifiers"),
        ("_string/_uuid.py", "UuidAssertions", "UUIDs"),
    ),
    "Expect": (
        ("_core/_base.py", "ExpectBase", "Continuations"),
        ("_core/_truthiness.py", "TruthinessAssertions", "Truthiness"),
        (
            "_core/_composition.py",
            "CompositionAssertions",
            "Composition (chaining is an AND; these are the other two)",
        ),
        ("_core/_equality.py", "EqualityAssertions", "Equality"),
        ("_core/_shape.py", "EquivalenceAssertions", "Structural equivalence"),
        ("_core/_identity.py", "IdentityAssertions", "Identity"),
        ("_core/_nullability.py", "NullabilityAssertions", "None (and the narrowing primitive)"),
        ("_core/_membership.py", "MembershipAssertions", "Membership"),
        ("_core/_predicates.py", "PredicateAssertions", "Predicates"),
        ("_core/_instance.py", "InstanceAssertions", "Type"),
        ("_core/_coercion.py", "CoercionAssertions", "Type"),
    ),
    "DateExpect": (("_datetime/_temporal.py", "TemporalExpect", "Ordering and ranges"),),
    "DateTimeExpect": (("_datetime/_clock.py", "ClockExpect", "The clock"),),
    "TimeExpect": (
        ("_datetime/_temporal.py", "TemporalExpect", "Ordering and ranges"),
        ("_datetime/_clock.py", "ClockExpect", "The clock"),
    ),
}

#: The group title for a subject whose module carries no ``# -- ... --`` banners,
#: used where ``catalogue()`` would otherwise fall back to "General". Only
#: ``_datetime.py`` needs it: it sorts its assertions by class, and the classes
#: are the groups.
GROUP_DEFAULT: dict[str, str] = {
    "DateExpect": "The calendar",
    "DateTimeExpect": "Instants and timezones",
    "TimeExpect": "Midnight",
    "TimeDeltaExpect": "Durations",
}

#: One row per ``expect()`` overload, in declaration order. The subject column is
#: not written here: it is filled by calling ``expect()`` with the sample.
DISPATCH_ROWS: list[tuple[str, str, object, bool]] = [
    ("any value, with `as_=SomeExpect`", "`expect(order, as_=OrderExpect)`", None, False),
    ("`type[Any]`", "`int`, a class of your own, an `Enum` class", int, True),
    ("an `Enum` member", "`Colour.RED`, and `IntEnum`/`StrEnum` members", Colour.RED, True),
    ("`datetime`", "`datetime(2024, 3, 16, 14, 30)`", datetime(2024, 3, 16, 14, 30), True),
    ("`date`", "`date(2024, 3, 16)`", date(2024, 3, 16), True),
    ("`time`", "`time(14, 30)`", time(14, 30), True),
    ("`timedelta`", "`timedelta(minutes=90)`", timedelta(minutes=90), True),
    ("`Path`", "`PosixPath`, `WindowsPath`", Path("build/report.txt"), True),
    ("`PurePath`", "`PurePosixPath`, `PureWindowsPath`", PurePosixPath("build/report.txt"), True),
    ("`Decimal`", '`Decimal("1.5")`', Decimal("1.5"), True),
    ("`Fraction`", "`Fraction(1, 3)`", Fraction(1, 3), True),
    ("`bool`", "`True`, `False`", True, True),
    ("`str`", '`"hello"`, and any `str` subclass', "hello", True),
    ("`int | float`", "`3`, `3.5`, and their subclasses", 3, True),
    ("`Mapping[K, V]`", "`dict`, `OrderedDict`, `ChainMap`, `MappingProxyType`", {"a": 1}, True),
    ("`Sequence[E]`", "`list`, `tuple`, `range`, `bytes`, `bytearray`", [1, 2], True),
    ("`Collection[E]`", "`set`, `frozenset`, and the three `dict` views", {1, 2}, True),
    ("`Callable[..., object]`", "a function, a lambda, a bound method", print, True),
    ("anything else", "`None`, a generator, a plain object", object(), True),
]

#: ``(module, kind, name)`` for everything in ``__all__`` that is not a subject,
#: grouped because a flat table of this length is a wall. ``kind`` says where the
#: description is read from: a function's signature and docstring, a class's
#: docstring, or the ``#:`` comment above a module-level value.
EXTRAS: list[tuple[str, tuple[tuple[str, str, str], ...]]] = [
    (
        "Failures and scopes",
        (
            ("_exceptions.py", "class", "AssertionFailure"),
            ("_callable/_expect_raises.py", "function", "expect_raises"),
            ("_warnings/_expect_warns.py", "function", "expect_warns"),
            ("_core/_soft.py", "function", "soft_assertions"),
            ("_core/_scope.py", "class", "SoftScope"),
            ("_core/_found.py", "class", "Found"),
            ("_datetime/_within.py", "class", "WithinDelta"),
        ),
    ),
    (
        "How many times",
        (
            ("_occurrence.py", "class", "Occurrence"),
            ("_occurrence.py", "function", "exactly"),
            ("_occurrence.py", "function", "at_least"),
            ("_occurrence.py", "function", "at_most"),
            ("_occurrence.py", "function", "more_than"),
            ("_occurrence.py", "function", "less_than"),
            ("_occurrence.py", "value", "once"),
            ("_occurrence.py", "value", "twice"),
        ),
    ),
    (
        "Structural comparison",
        (
            ("_equivalence/_options/__init__.py", "class", "Equivalency"),
            ("_equivalence/_options/__init__.py", "function", "equivalency"),
            ("_equivalence/_options/__init__.py", "function", "close_within"),
        ),
    ),
    (
        "Matchers",
        (
            ("_matching/_instances.py", "function", "any_instance_of"),
            ("_matching/_instances.py", "function", "anything"),
            ("_matching/_strings.py", "function", "string_matching"),
            ("_matching/_strings.py", "function", "string_containing"),
            ("_matching/_numbers.py", "function", "close_to"),
            ("_matching/_choice.py", "function", "one_of"),
            ("_matching/_containers.py", "function", "containing"),
            ("_matching/_predicate.py", "function", "matching"),
            ("_matching/_base.py", "function", "is_matcher"),
        ),
    ),
    (
        "How values are rendered",
        (
            ("_formatting/_options.py", "class", "FormattingOptions"),
            ("_formatting/_scope.py", "function", "formatting"),
            ("_formatting/_scope.py", "function", "current_formatting"),
            ("_formatters/_registry.py", "function", "register_formatter"),
            ("_formatters/_protocol.py", "class", "ValueFormatter"),
            ("_formatters/_builtin.py", "class", "ObjectFormatter"),
            ("_formatters/_builtin.py", "class", "IterableFormatter"),
            ("_formatters/_render.py", "function", "format_value"),
        ),
    ),
    (
        "Dispatch and extension",
        (
            ("_subjects.py", "function", "register"),
            ("_names/_frames.py", "function", "custom_assertion"),
            ("_mock/_recognition.py", "function", "is_mock"),
        ),
    ),
]

SUBJECT_INTRO: dict[str, str] = {
    "Expect": (
        "The generic subject, and the base class of every other one. `expect(x)` returns\n"
        "it directly when nothing narrower claims `x` — `None`, a generator, an object of\n"
        "your own — and it is what you subclass to add assertions of your own\n"
        "([the extension guide](../guides/extending.md))."
    ),
    "BoolExpect": "Returned for an exact `bool`: `True` and `False`, and nothing else.",
    "StringExpect": (
        "Returned for a `str` and for any subclass of one. Note which `matches` this is:\n"
        "on a string it takes a **regular expression**, because that is what the name\n"
        "means in Python. The wildcard form is `matches_wildcard`, and the inherited\n"
        "predicate form still works."
    ),
    "OrderedExpect": (
        "Returned for a `Decimal` and for a `Fraction`, and inherited by `NumericExpect`.\n"
        "It holds the assertions that ask nothing of a value except that `<` accepts it —\n"
        "comparisons, sign, ranges — which is what lets a `Decimal` have them without\n"
        "being flattened into `int | float`: `.subject` keeps the type it was handed."
    ),
    "NumericExpect": (
        "Returned for an `int`, a `float` and their subclasses, and an `OrderedExpect` as\n"
        "well, so the comparisons and ranges above all apply. What it adds is what only a\n"
        "machine number needs: tolerance, and the two values that are not quite numbers.\n"
        "The subject is the union `int | float` rather than a type parameter, so a\n"
        "predicate handed to the inherited `matches` has to accept both."
    ),
    "CollectionExpect": (
        "Returned for anything with a length, an iterator and a membership test but no\n"
        "order: a `set`, a `frozenset`, and the three `dict` views. It is also the base of\n"
        "[`SequenceExpect[E]`](#sequenceexpecte), which is why the catalogue here is the\n"
        "longest on the page — none of it depends on order, so a sequence inherits the\n"
        "whole of it and adds the assertions that need one."
    ),
    "SequenceExpect": (
        "Returned for a `Sequence` — `list`, `tuple`, `range`, `bytes` — parameterised by\n"
        "the element type, so `expect(names).contains(3)` is a type error when `names` is\n"
        "a `Sequence[str]`. Everything here is an assertion that needs an order to mean\n"
        "anything; the rest of the catalogue is inherited from the collection subject."
    ),
    "MappingExpect": (
        "Returned for a `Mapping` — `dict`, `OrderedDict`, `ChainMap`, `MappingProxyType`\n"
        "— parameterised by key and value type. It is not a `CollectionExpect`: a mapping\n"
        'is a collection of its *keys*, and `contains` meaning "has this key" on one line\n'
        'and "has this element" on the next is exactly the ambiguity this subject exists\n'
        "to remove."
    ),
    "DateExpect": (
        "Returned for a `date`. The ordering assertions come from a base shared with the\n"
        "time subject, written once because a `date` and a `time` answer the comparison\n"
        "operators identically; what a date adds is the calendar — the components, the\n"
        "day of the week, and where today falls."
    ),
    "DateTimeExpect": (
        "Returned for a `datetime` — which *is* a `date`, so this subject is a\n"
        "[`DateExpect`](#dateexpectt) too and the whole calendar catalogue applies to it.\n"
        "What it adds is the half a bare date has not got: the clock, which is the second\n"
        "base class and is shared with [`TimeExpect`](#timeexpect), and then the timezone\n"
        "and closeness measured as a `timedelta` rather than as a number."
    ),
    "TimeExpect": (
        "Returned for a `time`: a clock reading with no date behind it. It shares the\n"
        "ordering assertions with the date subject and the clock assertions with the\n"
        "datetime one, and adds the single thing only a time can be. Both shared groups\n"
        "come from private base classes, which is why `T` appears in the signatures\n"
        "below: here it is always `time`."
    ),
    "TimeDeltaExpect": (
        "Returned for a `timedelta`. A duration is not a moment, so this one deliberately\n"
        "does not inherit the temporal base: `is_before` would have nothing to mean on it.\n"
        "It carries its own comparisons instead, spelled as lengths — `is_longer_than`,\n"
        "`is_at_most` — and they read as durations rather than as positions."
    ),
    "PurePathExpect": (
        "Returned for a `PurePath`: a path as a *name*, with no filesystem behind it.\n"
        "Every assertion here is string and structure work and none of them touches the\n"
        "disk, which is what makes them safe on a `PureWindowsPath` under Linux and on a\n"
        "path that was never going to exist."
    ),
    "PathExpect": (
        "Returned for a `Path`, and a `PurePathExpect` as well, so every name assertion\n"
        "above applies to it. What it adds is everything that has to look: presence, kind,\n"
        "size, contents, directory entries. Each of those can fail for a reason that is\n"
        "not the claim being made — the path is a directory, the parent is missing, the\n"
        "file is not readable — and the message says which, rather than reporting the\n"
        "assertion false."
    ),
    "EnumExpect": (
        "Returned for an enum *member*, and ahead of `str` and `int` because a `StrEnum`\n"
        "member is a `str` and an `IntEnum` member is an `int`: being an enum is the more\n"
        "useful of the two things to know. The flag assertions are for `enum.Flag` and\n"
        "`enum.IntFlag`; asked of a plain `Enum` they raise a `TypeError` rather than\n"
        "report a failure that would mean nothing. An enum *class* is a class, and gets\n"
        "[`TypeExpect`](#typeexpect)."
    ),
    "CallableExpect": (
        "Returned for anything callable that is not a class. The subject is normally a\n"
        "zero-argument thunk, because the assertion has to do the calling itself:\n"
        '`expect(lambda: parse("x")).raises(ValueError)`. A generator function needs\n'
        "draining as well, and `expect(lambda: list(rows()))` is how — calling a\n"
        "generator function only builds a generator, so nothing it would raise has\n"
        "happened yet.\n"
        "\n"
        "The context-manager form is the other spelling and the primary one, because it\n"
        "leaves the code under test a statement instead of folding it into a lambda:\n"
        "\n"
        "@@CAUGHT@@\n"
        "\n"
        "Both hand back a [`RaisedExpect[E]`](#raisedexpecte). Inside the block there is\n"
        "no exception yet, and `caught.subject` says so with a `RuntimeError` rather than\n"
        "reporting on a value that does not exist.\n"
        "\n"
        "The warning assertions below come in the same two forms — `warns` here and\n"
        "`expect_warns` as the block — and both hand back a\n"
        "[`WarnedExpect[W]`](#warnedexpectw)."
    ),
    "RaisedExpect": (
        "The exception itself, as a subject. `raises`, `raises_exactly`, `with_cause`,\n"
        "`with_cause_exactly` and `expect_raises` all hand one back, so the whole generic\n"
        "catalogue applies to the exception too. `.which` is here a spelling rather than\n"
        "a step — the exception is already the subject — so that\n"
        '`raises(ValueError).which.with_message("x")` reads the way it is meant.'
    ),
    "WarnedExpect": (
        "The warnings a call issued, as a subject. A call raises at most one exception\n"
        "and may issue any number of them, so this subject carries every warning of the\n"
        "category asked for, in the order they were issued, and its own assertions ask\n"
        "whether *some* one of them satisfies the claim — never all of them, because a\n"
        "call that deprecates two arguments issues two warnings and the test is about\n"
        "one.\n"
        "\n"
        "Two forms produce it, as the exception family has two. `expect_warns(...)` is\n"
        "the primary one and sits where `pytest.warns` sits, leaving the code under test\n"
        "a statement; `warns(...)` on [`CallableExpect`](#callableexpect) is the\n"
        "thunk-wrapping twin. Both take an `occurrences=` constraint counted over the\n"
        'warnings of that category alone, and mean "at least one" without it. Inside the\n'
        "block there are no warnings yet, and `warned.subject` raises a `RuntimeError`\n"
        "saying so.\n"
        "\n"
        "The negative is `does_not_warn()`, and it sits on the callable subject rather\n"
        "than here: nothing was captured for it to be a subject of."
    ),
    "TypeExpect": (
        "Returned for a class — any class, an `Enum` class and an ABC included. It is a\n"
        "`CallableExpect`, because a class is callable, so `expect(Widget).raises(...)`\n"
        "still asks about the constructor. What it adds is what a class can say about\n"
        "itself: what it inherits, what it declares, whether it can be instantiated at\n"
        "all, and whether it satisfies a protocol.\n"
        "\n"
        "Where an answer cannot honestly be computed — a protocol that is not\n"
        "`runtime_checkable`, a subject that is not a class — the assertion raises rather\n"
        "than reporting a failure it did not establish."
    ),
    "MockExpect": (
        "Returned for a `unittest.mock` mock, ahead of everything else: a `MagicMock`\n"
        "defines `__len__`, `__iter__` and `__contains__`, so the collection subject would\n"
        "otherwise claim it, and a mock is not a collection in any sense the collection\n"
        "catalogue could act on.\n"
        "\n"
        "It is also the one subject with no overload behind it, for the reason given\n"
        "under [Which subject you get](#which-subject-you-get): a mock is statically\n"
        "assignable to everything, so no position in the overload list could reach it.\n"
        "`expect(m, as_=MockExpect)` is the typed route, and\n"
        "[the divergence ledger](../concepts/typing-divergences.md) records the trade."
    ),
}

SUBJECT_OUTRO: dict[str, str] = {
    "OrderedExpect": (
        '`Ordered` in the signatures is the module\'s protocol for "anything `<` accepts".\n'
        "It is not part of the public API and there is nothing to import: any type that\n"
        "answers the four comparison operators satisfies it."
    ),
    "NumericExpect": (
        "Two families of argument are rejected outright with a `ValueError`, before the\n"
        "subject is looked at: an unusable range — inverted, `NaN`-bounded, or an empty\n"
        "exclusive one — and an unusable tolerance, negative or `NaN`. Neither describes\n"
        "a claim about the value, so neither is reported as a failure of it."
    ),
    "CollectionExpect": (
        "`occurrences=` takes an occurrence constraint — `exactly(3)`, `at_least(1)`,\n"
        "`once`; they are listed under\n"
        "[Elsewhere in the public API](#elsewhere-in-the-public-api). On a negative\n"
        "assertion it is the constraint that is negated and not the containment, so\n"
        "`does_not_contain(x, occurrences=exactly(3))` passes when `x` appears twice,\n"
        "four times, or not at all, and fails only on exactly three.\n"
        "\n"
        "Every rendering of a collection in a message is bounded, whatever the size of\n"
        "the collection; `formatting(max_items=...)` raises the bound for a block where\n"
        "the whole list is what the reader needs."
    ),
    "SequenceExpect": (
        "`_Ordered` in the `key=` signatures is the module's internal protocol for\n"
        '"anything `<` accepts". It is not exported and there is nothing to import: any\n'
        "key function returning an orderable value satisfies it.\n"
        "\n"
        "`contains_match` and `does_not_contain_match` carry an annotated `self`, which is\n"
        "how they are offered on a sequence of strings and nowhere else.\n"
        "\n"
        "`does_not_contain` and `extracting` are redeclared rather than inherited, and\n"
        "order is the reason for both: a sequence can say *where* it found the item, and\n"
        "an `extracting` over a sequence has to stay a `SequenceExpect` so that the\n"
        "ordering assertions still follow it."
    ),
    "PathExpect": (
        "Nothing here caches. Each assertion asks the filesystem at the moment it is\n"
        "made, which is the only answer worth reporting about a thing another process can\n"
        "change between two lines of a test."
    ),
    "RaisedExpect": (
        "The message names `the value` rather than a variable, and that is worth knowing:\n"
        "subject naming reads the statement that failed, and\n"
        "`caught.with_message_containing(...)` holds no `expect(...)` call to read a name\n"
        "out of. The fluent form keeps it —\n"
        '`expect(lambda: parse("nope")).raises(ValueError).with_message_containing(...)`\n'
        'reports `Expected lambda: parse("nope") to have a message containing ...`.'
    ),
    "WarnedExpect": (
        "The message names the *category*, where the exception subject above names `the\n"
        "value`, and the difference is deliberate: the block form holds no `expect(...)`\n"
        "call to read a name out of, and `DeprecationWarning` is worth more in that\n"
        "sentence than `the value` would be. It reads the same when the category arrived\n"
        "in a variable, because it is taken from the class rather than from the source.\n"
        "\n"
        "**Where `pytest.warns` is the better answer.** It is one line, it is already in\n"
        'the file, and for "did this warn at all" there is nothing here it does not\n'
        "already do. Three things it cannot do are why this exists beside it. A failure\n"
        "here says what *was* there rather than only what was not — the messages above,\n"
        "and, where the capture itself came up empty, every warning that was issued with\n"
        "the file and line `stacklevel` pointed at. It reports through the same path as\n"
        "every other assertion, so a `soft_assertions()` block collects it and runs to\n"
        "the end instead of stopping at the first finding. And `occurrences=` counts,\n"
        "which `pytest.warns` has no spelling for. `does_not_warn` is a fourth:\n"
        "`pytest.warns` can only say that something *did* warn.\n"
        "\n"
        "Capture is process-wide and not thread-safe, because `warnings.catch_warnings`\n"
        "swaps a global filter list — the same caveat `pytest.warns` carries, for the\n"
        "same reason. Warnings *outside* the category under test are re-issued to the\n"
        "project's own filters on the way out rather than swallowed, so a block watching\n"
        "for one category does not quietly disarm the project's handling of the rest."
    ),
}

SURPRISES: list[tuple[str, object, str]] = [
    ('expect(b"abc")', b"abc", "`bytes` is a `Sequence[int]`, so the elements are integers."),
    ("expect(range(3))", range(3), "a `range` is a sequence, and is not materialised."),
    (
        "expect({1, 2})",
        {1, 2},
        "a `set` is a `Collection` but not a `Sequence` — no indexing, no order.",
    ),
    ("expect(int)", int, "a class is a class before it is anything else, callable though it is."),
    (
        "expect(Colour)",
        Colour,
        "an `Enum` class is iterable through its metaclass, and is a class all the same.",
    ),
    ("expect(Colour.RED)", Colour.RED, "a member is not a class, and is not a collection."),
    (
        'expect(Decimal("1.5"))',
        Decimal("1.5"),
        "ordered, but neither an `int` nor a `float`, so it gets the ordering half.",
    ),
    ("expect(Mock())", Mock(), "a mock is a mock first; see the note above the table."),
    ("expect(None)", None, "nothing narrower claims it."),
]

NUMBER_WORDS = {
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
}

DISPLAY: dict[str, str] = {name: display for _, name, display in TARGETS}


def words(count: int) -> str:
    return NUMBER_WORDS.get(count, str(count))


def display_of(cls: type) -> str:
    return DISPLAY.get(cls.__name__, cls.__name__)


def python_floor() -> str:
    """The ``requires-python`` floor, so the closing note cannot go stale either."""
    for line in (REPO / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("requires-python"):
            return line.partition("=")[2].strip().strip('"').lstrip(">=")
    complaint = "requires-python not found in pyproject.toml"
    raise SystemExit(complaint)


def cell(text: str) -> str:
    """A ``|`` inside a table cell has to be escaped, code span or not."""
    return text.replace("|", "\\|")


def fenced(source: str) -> str:
    return "```python\n" + source + "\n```"


def output(message: str) -> str:
    return "```\n" + message + "\n```"


def wrapped(text: str) -> list[str]:
    """Markdown joins the lines of a paragraph, so a long one may as well wrap."""
    return textwrap.wrap(text, width=80, break_long_words=False, break_on_hyphens=False)


def anchor(display: str) -> str:
    slug = display.lower().replace(" ", "-")
    return "#" + "".join(character for character in slug if character.isalnum() or character == "-")


def signature_line(method: Method) -> str:
    if method.is_property:
        return " or ".join(
            "`." + signature.replace("()", "", 1) + "`" for signature in method.signatures
        )
    return " or ".join("`" + signature + "`" for signature in method.signatures)


def catalogue(subject: Subject) -> list[str]:
    lines: list[str] = []
    for group, methods in subject.groups():
        title = group
        if not title:
            title = "Continuations" if all(m.is_property for m in methods) else "General"
        lines += ["", "**" + title + "**", ""]
        lines += [
            "- " + signature_line(method) + " — " + summary_of(method.summary) for method in methods
        ]
    return lines


def public_extras() -> list[tuple[str, list[tuple[str, str]]]]:
    rows: list[tuple[str, list[tuple[str, str]]]] = []
    for title, entries in EXTRAS:
        group: list[tuple[str, str]] = []
        for module, kind, name in entries:
            if kind == "function":
                method = read_function(module, name)
                group.append((method.signatures[0], summary_of(method.summary)))
            elif kind == "value":
                group.append((name, summary_of(read_value(module, name))))
            else:
                group.append((name, summary_of(read_class_summary(module, name))))
        rows.append((title, group))
    return rows


def collapse(lines: list[str]) -> str:
    """One blank line is a paragraph break; two are a slip in the assembly."""
    out: list[str] = []
    for line in lines:
        if not line and out and not out[-1]:
            continue
        out.append(line)
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# The document.
# ---------------------------------------------------------------------------
def header(add: Callable[[str], None], examples: dict[str, Example]) -> None:
    add("# Assertion reference")
    add("")
    add("Every assertion in `lovely-assertions`, grouped by the subject it belongs to,")
    add("with the signature and the one-line description taken from the code.")
    add("")
    add("> **This file is generated.** `scripts/generate_reference.py` parses")
    add("> `src/lovely_assertions/`, calls `expect()` to fill the dispatch table, and")
    add("> *runs* every example below to quote the message it produces. Regenerate it")
    add("> rather than editing it: a hand-edit is lost on the next run, and a reference")
    add("> that has drifted from the code is worse than no reference at all.")
    add("")
    add("## How to read this")
    add("")
    add("`expect(x)` wraps `x` in the subject that knows how to assert on it, chosen by")
    add("the type of `x`. That is the entire entry point.")
    add("")
    add(fenced(examples["intro"].source))
    add("")
    add("Four things hold everywhere, so they are said once here instead of on every")
    add("line below.")
    add("")
    add('**Every assertion takes a keyword-only `because`.** It defaults to `""`, it')
    add("reaches the message only on failure, and it attaches at the end of the")
    add("sentence. It is an ordinary argument, so whatever you interpolate into it is")
    add("computed whether or not the assertion fails — keep it cheap. Write it with or")
    add('without the leading word — neither reads "because because".')
    add("")
    add(fenced(examples["because"].source))
    add("")
    add(output(examples["because"].message))
    add("")
    add("**A message can run to more than one line.** An equality failure on a composite")
    add("value carries a difference block under the sentence — a unified diff for")
    add("multi-line text, the first offending index for a sequence, the keys that moved")
    add("for a mapping. It stays bounded, whatever the size of the two values.")
    add("")
    add(fenced(examples["difference"].source))
    add("")
    add(output(examples["difference"].message))
    add("")
    add("**Every assertion returns something chainable.** Most return the subject itself,")
    add("so assertions stack directly. The ones that *find* a value return a")
    add("[`Found`](#continuations), and the ones that narrow return a re-typed subject.")
    add("Which it is, is in the signature.")
    add("")
    add("**A failure raises `AssertionFailure`**, a subclass of `AssertionError`, so")
    add("pytest and unittest treat it as an ordinary test failure. Inside a")
    add("`soft_assertions()` block nothing is raised until the block ends.")
    add("")
    signature_note(add)


def signature_note(add: Callable[[str], None]) -> None:
    add("Signatures are quoted as the source declares them: `/` closes the")
    add("positional-only parameters, `*` opens the keyword-only ones, and `self` appears")
    add("only where its annotation is load-bearing — which is how `is_not_none` says it")
    add("wants an optional subject, and how `contains_match` says it wants a sequence of")
    add("strings.")
    add("")


def dispatch(add: Callable[[str], None]) -> None:
    add("## Which subject you get")
    add("")
    add("`expect()` is overloaded, and the overloads are **ordered**: the first one that")
    add("matches wins. The runtime dispatch walks the same order, so what a type checker")
    add("offers and what you actually get are the same thing.")
    add("")
    add("| # | Matches | For example | Subject |")
    add("| --- | --- | --- | --- |")
    for index, (shape, sample_text, sample, call_it) in enumerate(DISPATCH_ROWS, 1):
        found = "`" + display_of(type(la.expect(sample))) + "`"
        name = found if call_it else "whatever `as_=` names"
        columns = [str(index), cell(shape), cell(sample_text), name]
        add("| " + " | ".join(columns) + " |")
    add("")
    add("The order is the mechanism, not an accident, and it reads from the narrow to")
    add("the broad. A class comes first because an `Enum` class is iterable through its")
    add("metaclass, and a class whose metaclass implements the mapping protocol is a")
    add("`Mapping`, so anything further down would claim one or the other. The enum, date")
    add("and path rows come next because an `IntEnum` member is an `int` and a `StrEnum`")
    add("member is a `str`. `bool` is a subclass of `int` and a `str` is a")
    add("`Sequence[str]`, so without the order `expect(True)` would be a `NumericExpect`")
    add('and `expect("x")` a `SequenceExpect[str]`. `Mapping` precedes `Sequence` and')
    add("`Sequence` precedes `Collection` on the same argument: each of them is one, with")
    add("more to say about itself. The bare `T` fallback is last.")
    add("")
    add("One subject is missing from the table because it is missing from the overloads.")
    add("A mock is dispatched to [`MockExpect`](#mockexpect) before anything else is")
    add("looked at, and no overload can say so: typeshed puts an `Any` in")
    add("`NonCallableMock`'s MRO, which makes a mock statically assignable to every")
    add("parameter type, so the first concrete overload would always win whatever order")
    add("they were written in. The runtime is left to be right on its own, and")
    add("`expect(m, as_=MockExpect)` is the typed route.")
    add("")
    add("A few results that surprise people. The subject column is the class `expect()`")
    add("actually returned when this table was generated.")
    add("")
    add("| Call | Subject | Why |")
    add("| --- | --- | --- |")
    for call, sample, why in SURPRISES:
        add("| `" + call + "` | `" + type(la.expect(sample)).__name__ + "` | " + cell(why) + " |")
    add("")
    add("`register(SomeType, SomeExpect)` inserts your own subject just after the exact")
    add("built-in table, so it is consulted before the `Mapping`/`Sequence`/callable")
    add("chain. Registering *over* a built-in is refused, because it would put the")
    add("runtime out of step with the overloads above — and no checker can see a runtime")
    add("registration in any case. `expect(x, as_=SomeExpect)` is the typed route. See")
    add("[the extension guide](../guides/extending.md).")
    add("")


def continuations(add: Callable[[str], None], found: Subject, examples: dict[str, Example]) -> None:
    add("## Continuations")
    add("")
    add("Four properties carry a chain from one assertion to the next. Which of them")
    add("you have depends on what the last assertion returned.")
    add("")
    add("| Continuation | Appears on | Gives you |")
    add("| --- | --- | --- |")
    add(
        "| `.and_` | every subject, and `Found` | the subject the assertion was made on, "
        "so the next one reads as a continuation of the same sentence |"
    )
    add(
        "| `.which` | `Found`, and `RaisedExpect` | a subject over the value the assertion "
        "*found* — the single item, the element at an index, the value under a key, the "
        "exception |"
    )
    add("| `.whose_value` | `Found` | the same as `.which`, spelled for a key lookup |")
    add("| `.subject` | every subject, and `Found` | the raw value, re-typed |")
    add("")
    add("`Found[P, V, A]` is what an assertion returns when it found something: `P` is")
    add("the subject it was made on, `V` the value it found, and `A` the subject")
    add("`.which` hands back. `A` defaults to `Expect[V]`, which is what nearly every")
    add("producer leaves it at; one that knows better says so, and")
    add("`is_instance_of(str)` returns `Found[Self, str, StringExpect]` because that is")
    add("the object `expect()` builds for a string. Its four members are the four")
    add("continuations:")
    add("")
    for method in found.methods:
        add("- " + signature_line(method) + " — " + summary_of(method.summary))
    add("")
    add(fenced(examples["continuations"].source))
    add("")
    add("Left at that default — everywhere but `is_instance_of` and")
    add("`is_exactly_instance_of` — `.which` is declared `Expect[V]`, the generic")
    add("subject. At runtime it routes through `expect()`, so for a string the object")
    add("really is a `StringExpect`, but a checker reads the declared type and the string")
    add("catalogue is not offered. Re-bind through `.subject` and call `expect()` again")
    add("where you want it:")
    add("")
    add(fenced(examples["rebind"].source))
    add("")
    add("The same trade is why `is_not_none()` returns `Expect[S]` rather than a")
    add("re-specialised subject; [the divergence ledger](../concepts/typing-divergences.md)")
    add("records the reasoning.")
    add("")


def and_listed(names: list[str]) -> str:
    rendered = ["`" + name + "`" for name in names]
    if len(rendered) == 1:
        return rendered[0]
    return ", ".join(rendered[:-1]) + " and " + rendered[-1]


def inherited_note(subject: Subject, cls: type, subjects: dict[str, Subject]) -> list[str]:
    """Where the rest of this subject's catalogue comes from, ancestor by ancestor.

    Several subjects stand on another one — ``NumericExpect`` on
    ``OrderedExpect``, ``SequenceExpect`` on ``CollectionExpect``, ``PathExpect``
    on ``PurePathExpect``, ``DateTimeExpect`` on ``DateExpect`` — so the MRO is
    walked rather than assumed, and each documented ancestor is credited with the
    names no nearer one has already accounted for.
    """
    own = {method.name for method in subject.methods}
    accounted = set(own)
    lines: list[str] = []
    for ancestor in cls.__mro__[1:]:
        documented = subjects.get(ancestor.__name__)
        if documented is None:
            continue
        names = [method.name for method in documented.methods]
        contributed = [name for name in names if name not in accounted]
        redeclared = [name for name in names if name in own]
        accounted.update(names)
        if not contributed:
            continue
        note = (
            "**Inherited from [`"
            + documented.display
            + "`]("
            + anchor(documented.display)
            + ")** ("
            + words(len(contributed))
            + " more): "
            + ", ".join("`" + name + "`" for name in contributed)
            + "."
        )
        if redeclared:
            note += (
                " "
                + and_listed(redeclared)
                + (" is" if len(redeclared) == 1 else " are")
                + " redeclared above, and the declaration there is the one this subject offers."
            )
        lines += wrapped(note)
        lines.append("")
    return lines[:-1]


def build(subjects: dict[str, Subject], found: Subject, examples: dict[str, Example]) -> str:
    base = subjects["Expect"]
    assertions = [method.name for method in base.methods if not method.is_property]
    properties = [method.name for method in base.methods if method.is_property]

    lines: list[str] = []
    add = lines.append

    header(add, examples)

    add("## Contents")
    add("")
    add("- [Which subject you get](#which-subject-you-get)")
    add("- [Continuations](#continuations)")
    for subject in subjects.values():
        add("- [`" + subject.display + "`](" + anchor(subject.display) + ")")
    add("- [Elsewhere in the public API](#elsewhere-in-the-public-api)")
    add("")

    dispatch(add)
    continuations(add, found, examples)
    lines += subject_sections(subjects, assertions, properties, examples)
    lines += closing(examples)
    return collapse(lines)


def subject_sections(
    subjects: dict[str, Subject],
    assertions: list[str],
    properties: list[str],
    examples: dict[str, Example],
) -> list[str]:
    lines: list[str] = []
    add = lines.append
    for key, subject in subjects.items():
        add("## `" + subject.display + "`")
        add("")
        add("```python\n" + subject.declaration + ":\n```")
        add("")
        add(SUBJECT_INTRO[key].replace("@@CAUGHT@@", fenced(examples["caught"].source)))
        add("")
        if key == "Expect":
            add(
                "The "
                + words(len(assertions))
                + " assertions and "
                + words(len(properties))
                + " continuations below are inherited by"
            )
            add("every other subject on this page. They are listed here once, and referred to")
            add("as *inherited* from there on.")
            add("")
        lines += catalogue(subject)
        add("")
        if key != "Expect":
            lines += inherited_note(subject, getattr(la, key), subjects)
            add("")
        add("**What a failure looks like**")
        add("")
        add(fenced(examples[key].source))
        add("")
        add(output(examples[key].message))
        add("")
        if key in SUBJECT_OUTRO:
            add(SUBJECT_OUTRO[key])
            add("")
    return lines


def closing(examples: dict[str, Example]) -> list[str]:
    lines: list[str] = []
    add = lines.append
    add("## Elsewhere in the public API")
    add("")
    add("Not assertions, but exported from `lovely_assertions` and worth knowing exist;")
    add("names and descriptions come from the same source as everything above.")
    add("[the extension guide](../guides/extending.md) is where the extension half")
    add("of the list belongs.")
    add("")
    for title, rows in public_extras():
        add("**" + title + "**")
        add("")
        add("| Name | What it is |")
        add("| --- | --- |")
        for name, description in rows:
            add("| `" + cell(name) + "` | " + cell(description) + " |")
        add("")
    add("A soft scope changes the shape of a message rather than its content: failures")
    add("are collected instead of raised, the scope's name is prefixed to every subject")
    add("name, and the block reports all of them on the way out. Scopes nest, and the")
    add("names compose into a `/`-joined path, so a failure two levels down reads")
    add("`checkout/totals/total`.")
    add("")
    add(fenced(examples["soft"].source))
    add("")
    add(output(examples["soft"].message))
    add("")
    matchers(add, examples)
    add("---")
    add("")
    add("This document describes the code it was generated from: Python " + python_floor() + "+,")
    add("zero runtime dependencies. Assertions that are planned but not yet written are")
    add("deliberately absent — see [CHANGELOG.md](../../CHANGELOG.md) for what has shipped.")
    return lines


def matchers(add: Callable[[str], None], examples: dict[str, Example]) -> None:
    """The matcher family, which needs more than a table row.

    It is the one entry in the list above whose *design* is the thing to explain:
    the objects are declared to be what they stand in for, and a reader who meets
    ``any_instance_of(int)`` in a table without that sentence will read it as the
    type-erased trick it deliberately is not.
    """
    add("A matcher is a placeholder that goes in an *expectation* and never in a")
    add('subject. `{"id": any_instance_of(int)}` is an ordinary dict holding an ordinary')
    add("object, and the object answers `==` loosely. Nothing in this library walks them:")
    add("a matcher is reached by Python's own comparison protocol, which is why one works")
    add("at any depth inside `is_equal_to`, `is_equivalent_to`, `contains` and")
    add("`was_called_with` with not a line of support written for any of them.")
    add("")
    add(fenced(examples["matchers"].source))
    add("")
    add("The unusual part is the declaration. Each factory is *declared* to return the")
    add("type it stands in for, so a matcher drops into an invariant slot —")
    add("`dict[str, int]`, `list[int]` — that no honestly typed placeholder could reach,")
    add("and the slot goes on being checked:")
    add("")
    add(fenced(examples["expectation"].source))
    add("")
    add("`dict[str, int]` is what that annotation says and what both checkers enforce:")
    add("`any_instance_of(str)` in the same slot is an error, and so is")
    add("`expect(names).contains(any_instance_of(int))` on a `list[str]`. It is the")
    add("caller's own annotations that switch the protection on, which is the argument")
    add("for declaring the expectation rather than inlining it — `is_equal_to` takes an")
    add("`object`, so that any two values can be compared, and a matcher written straight")
    add("into the call has no slot to be checked against.")
    add("")
    add("The declaration is also a fiction, and the cost is worth stating rather than")
    add("discovering: `any_instance_of(str)` is annotated `str` and has no `.upper()`. So")
    add("a matcher belongs in an expectation and nowhere else — never the subject, never")
    add("stored, never operated on — and `expect()` refuses one outright rather than")
    add("reporting on a placeholder:")
    add("")
    add(fenced(examples["refused"].source))
    add("")
    add("`<any int>` there is the matcher's `repr`, which is the phrase it stands for,")
    add("because that is the text a reader meets in the message it turns up in. One place")
    add("a matcher does not reach: `in` against a `set`, a `frozenset` or a mapping's")
    add("keys is a hash lookup rather than a scan, so nothing is ever compared against it")
    add("and `expect({1, 2}).contains(any_instance_of(int))` finds nothing. Sequences,")
    add("mappings' values and recorded call arguments are all scans, and work.")
    add("")


def main(destination: Path = OUT) -> None:
    """Write the document. An argument sends it somewhere other than ``docs/reference/``.

    ``tests/test_packaging.py`` regenerates into a temporary file and compares, so
    that a contributor who adds an assertion and forgets to run this is told so. A
    check that wrote over the file it is checking would pass by construction, which
    is why the destination is a parameter rather than a constant.
    """
    subjects = build_subjects()
    found = read_subject("_core/_found.py", "Found", "Found[P, V]")

    problems: list[str] = []
    for name, subject in subjects.items():
        problems += verify(subject, getattr(la, name))
    problems += verify(found, la.Found)
    if problems:
        complaint = "signature verification failed:\n" + "\n".join(problems)
        raise SystemExit(complaint)

    document = build(subjects, found, load_examples())
    destination.write_text(document, encoding="utf-8")
    print("wrote", destination, "-", len(document.splitlines()), "lines")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
