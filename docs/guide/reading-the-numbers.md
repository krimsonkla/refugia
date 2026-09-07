# Reading the numbers

**The score is a position, not a measurement.** `score` in the CLI, `FIT` on the
page, is a 0–100 percentile rank _among the places that survived your filters_. So
it is not comparable between two profiles, and not comparable to itself before and
after you change a requirement — tightening a filter re-spreads everything that is
left. A place at 71 is not "71% good"; it is near the top of this particular
field.

**`cover`** — `Data` on the page — is the share of your weighted metrics that this
place actually has a value for. Anything below `min_coverage` never appears at
all. A row at 90% is scored on nine tenths of what you asked for, and the missing
tenth is not counted against it.

`rank --explain` breaks a place's score into each metric's contribution alongside
the raw value, which is the fastest way to see whether a result is real or an
artefact of one metric doing all the work.

## What these figures are

They are county-wide, and several are modelled estimates rather than direct
measurements — CDC PLACES builds small-area estimates from survey responses rather
than counting anybody. A county is not uniform, and the figure for one is identical
for every town in it.

They are also ranked against one particular set of weights, which is yours if you
wrote the profile and somebody else's if you were handed the page.

So this narrows a list. It is not advice, and it is not a verdict on these places or
the people who live in them.

## How old the data is

A published page carries its own provenance in the footer: when the dataset was
assembled, and the date of the oldest cached response behind it. Those are different
questions, because `fetch` is cache-first — a page built this morning can be made
entirely of figures cached a year ago.

`DATA_SOURCES.md` in the repository root has the vintage and terms of every
publisher.

---

Next: [writing a profile](writing-a-profile.md), or [using the
page](using-the-page.md).
