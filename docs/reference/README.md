# Reference

Every assertion on every subject, with its signature and a one-line description.
It is the exhaustive list; the guides are the organised tour.

**[The assertion reference →](assertions.md)** ·
[the guides](../README.md#guides)

## It is generated, and checked

The reference is not written by hand. Three things in it are rebuilt on every
run:

- **The catalogue.** Every subject class is parsed out of the source. The groups
  are the banners the modules already sort their methods into, the signatures
  come from the syntax tree, and the descriptions are the first line of each
  docstring. Parameter names are cross-checked against the live classes, so a
  mis-parse fails the run rather than the reader.
- **The dispatch table.** Its rows transcribe the `@overload` chain on
  `expect()` and are kept in step with it by hand; the subject in each row is
  derived, by *calling* `expect()` with a value of that shape and asking what
  came back.
- **Every failure message.** Each example is written to a temporary directory as
  a standalone module, executed, and the failure it raises is quoted verbatim.

A test fails if the checked-in file has drifted from its generator, another fails
if a public name is documented nowhere, and a third fails if any assertion
reachable on an exported subject is missing. So a reference that lies is a
failing build rather than a stale page — with one gap: nothing compares those
transcribed dispatch rows against the overloads they mirror.

To regenerate it after changing an assertion signature or the first line of a
docstring:

```bash
uv run python scripts/generate_reference.py
```

Never edit `assertions.md` by hand — the next run overwrites it.

## How it is laid out

| Section | What is in it |
|---|---|
| **How to read this** | one worked example, and the facts that hold for every assertion |
| **Which subject you get** | the ordered dispatch table, and the surprising rows |
| **Continuations** | `.and_`, `.which`, `.whose_value`, `.subject`, and `Found` |
| **One section per subject** | `Expect[T]` first, since everything inherits it, then the rest roughly simplest-first |
| **Elsewhere in the public API** | the free functions, matchers and formatters |

Subjects inherit, so read a section together with its parents: everything on
[`Expect[T]`](assertions.md#expectt) is available on every subject, and a
`SequenceExpect` also has the whole of `CollectionExpect`.

## Finding things

- **You know the value's type** → the [guides index](../README.md#by-what-you-are-asserting-on)
  routes by type.
- **You know roughly what the assertion is called** → search `assertions.md`; it
  is one page on purpose.
- **You want to know why something behaves as it does** → the
  [concepts](../README.md#concepts) pages.

---

**See also:** [documentation index](../README.md) ·
[typed dispatch](../concepts/typed-dispatch.md)
