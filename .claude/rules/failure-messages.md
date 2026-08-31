---
paths:
  - "src/**/*.py"
---

# Failure messages — the sentence is the product

pytest's assertion rewriting already prints a diff. This library exists because a
diff shows you two values and leaves you to work out which bug you have. Every
message here is a sentence that names the bug.

**The grammar is fixed**, and it is assembled in exactly one place: `_render_failure`
in `_core/_routing.py`, reached only through `report_failure`, which nothing calls
but `_fail` and `_fail_narrowing` on the base subject in `_core/_base.py`. The
`_fail` overrides in `_callable/_block.py` and `_warnings/_caught.py` fall silent
once a soft scope has already collected the block's own failure and otherwise
delegate to `super()`; they are absorb guards, not second assemblers. An override
that renders anything itself is a defect.

```
Expected {subject name} {expectation}[ because {reason}].
[optional detail block]
```

The name gains a `{scope path}/` prefix inside a named soft scope, and falls back
to the literal `the value` when nothing readable can be recovered from the call
site. A reason that already opens with `because ` is not doubled. The full stop
closes the *first line*, not the message.

So an expectation is written as the middle of that sentence — `"to be sorted, but
1 at index 1 came after 3: [3, 1, 2]"` — never as a whole sentence, never
capitalised, never ending in a full stop. It holds by discipline and not by a
guard: every expectation is a literal written at its own `_fail` call site and no
helper produces one, but nothing checks the rule — only individual messages,
pinned one exact string at a time.

**Say what was expected *and* what was actually there.** "to contain key
'hostname'" is half a message; "to contain key 'hostname' (did you mean 'host'?),
but the keys were ['host']" is the whole one. The reader should not have to
re-run anything.

**Distinguish the failures that look alike.** A missing key and a key holding the
wrong value are different bugs and get different sentences. When an assertion
cannot tell two causes apart, that is a reason to reconsider the assertion, not
to write a vaguer message.

**Bounded per value and per level — not in total.** `max_items` caps one
collection at one level, `max_chars` caps one rendered value and one line of a
unified diff, `max_depth` caps how far a difference descends, and `max_diff_lines`
caps the unified text diff and nothing else. A structural difference can therefore
reach `max_items ** (max_depth + 1)` lines, and the report a soft scope raises
loops its collected failures uncapped in `_core/_rendering.py` — whose own
docstring claims the opposite. Both are gaps to close, not claims to make. Say
what a bound actually bounds, and never write "bounded" of something that is not.

**Know which kind of bound a new number is.** A legibility bound is a field on
`FormattingOptions`, read through `current_formatting()` at the point of use and
never copied, so a reader who opens a wider `formatting()` block sees more. A cost
bound is a module constant deliberately not offered, because a caller who could
raise one could hang a red test run. `_MAX_RENDERED` in `_ordered` and `_callable`
is a legibility bound written as a constant, and it shows: a widened `max_chars`
grows the string subject's message and leaves those two exactly where they were.

**Render values through the formatter registries** — scoped first, innermost
outwards, then the global ones in registration order, then `repr` — and never with
a raw `repr` at the call site, or a user's registered formatter is skipped for that
one assertion. `format_value` never raises: a formatter that throws is skipped as
though it had declined, and a value whose `repr` throws is named by its type.
Where `repr` is deliberate the site says so — a key inside an `excluding=` path,
which is text the user has to be able to type back; the `repr` of an options
object, which has to read like the call that built it; the string fragments
`_diff/_strings.py` quotes, whose "the first N characters match" counts characters
of the raw string. `did_you_mean` in `_mapping/_previews.py` and `render_names` in
`_equivalence/_labels.py` are not among them: each is a bare `repr` beside values
the same message renders through the registries.

The discipline is necessary and not sufficient. `repr` is the fallback for anything
no formatter claims, and a container's `repr` does not re-enter the registries — so
a formatter registered for the items is honoured in a difference block that renders
them one at a time and skipped in a sentence that renders the container whole.

**A message reads the same on two runs.** Sets and `str` iteration order follow the
hash seed, so anything rendering an unordered collection sorts first — `stable_order`
in `_diff`, `stably_ordered` in `_equivalence` — and keeps iteration order rather
than raising when the members will not compare. No general guard exists:
`tests/test_collection.py` re-runs one failing set assertion under several hash
seeds, in subprocesses, and demands a single message; every other shape is on this
rule.

**Concatenation, never f-strings, in the rendering engines.** A message is built
inside the argument list of a `_fail(...)` call and nowhere else, because Python
evaluates arguments eagerly and an f-string one line early is paid by every
passing assertion in every suite. `_diff` and `_formatters` hold no `_fail` and
therefore no f-string at all, which is a rule with no exception to weigh rather
than a judgement per line. Elsewhere an f-string is confined to a `__repr__`, to
a `TypeError` raised at a misuse, and to the routing and aggregation in `_core`
that only run once a failure is certain.

**The detail block attaches after the first line.** The `because` reason ends the
first sentence; anything multi-line follows it. Appending the reason to the whole
rendered block leaves it dangling off the last line of a diff.

**A new assertion earns its place by its message.** If the sentence it produces
says no more than the comparison a reader would have written by hand, the
assertion is not worth adding.
