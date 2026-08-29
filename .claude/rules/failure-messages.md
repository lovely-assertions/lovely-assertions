---
paths:
  - "src/**/*.py"
---

# Failure messages — the sentence is the product

pytest's assertion rewriting already prints a diff. This library exists because a
diff shows you two values and leaves you to work out which bug you have. Every
message here is a sentence that names the bug.

**The grammar is fixed**, and it is assembled in exactly one place:

```
Expected {subject name} {expectation}[ because {reason}].
[optional detail block]
```

So an expectation is written as the middle of that sentence — `"to be sorted, but
1 at index 1 came after 3: [3, 1, 2]"` — never as a whole sentence, never
capitalised, never ending in a full stop.

**Say what was expected *and* what was actually there.** "to contain key
'hostname'" is half a message; "to contain key 'hostname' (did you mean 'host'?),
but the keys were ['host']" is the whole one. The reader should not have to
re-run anything.

**Distinguish the failures that look alike.** A missing key and a key holding the
wrong value are different bugs and get different sentences. When an assertion
cannot tell two causes apart, that is a reason to reconsider the assertion, not
to write a vaguer message.

**Bounded, always.** A detail block — a unified diff, the first offending index,
the keys that moved — is capped so that comparing two very large values produces
a few hundred characters, not the values themselves. An unbounded message is a
message nobody reads.

**Render values through the formatter registry**, never with a raw `repr` at the
call site, or a user's registered formatter is silently skipped for that one
assertion.

**The detail block attaches after the first line.** The `because` reason ends the
first sentence; anything multi-line follows it. Appending the reason to the whole
rendered block leaves it dangling off the last line of a diff.

**A new assertion earns its place by its message.** If the sentence it produces
says no more than the comparison a reader would have written by hand, the
assertion is not worth adding.
