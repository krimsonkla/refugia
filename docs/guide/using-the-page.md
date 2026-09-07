# Using the page

`refugia publish` writes one self-contained HTML file. Everything below happens in
your browser, with no server: the page carries the whole dataset and re-scores as
you change your mind.

Hand the file to somebody and they get the same thing, with the weights it was
published with. They can re-weight it to their own priorities without installing
anything.

Two things travel with it. The page embeds the profile it was built from, including
your home county if you set one, so sharing a page says something about you as well
as about the places. And it loads its typefaces from Google, so a viewer's browser
contacts `fonts.googleapis.com` — no server of ours, but a third party. Offline it
falls back to system faces and works unchanged.

**The sliders are the point.** Move one and everything re-ranks immediately: the
table reorders, the map reshades, the scores change. Nothing is precomputed, so
there is no wrong question to ask of it.

**Weights reorder, requirements remove.** The requirements panel drops places out
of the running entirely — a minimum population, a maximum home value, states you
will not consider — and each metric additionally offers "rule out anywhere worse
than home", which is the cut you cannot express by weighting however heavily.

**The map shades on whichever metric you pick**, from the selector above it, not
only on the overall fit. That is how you see a single metric's geography rather
than the answer's.

**Click a county** for the comparison panel: every metric against home, ordered by
how much it actually moved the score. **Click a town marker** for the city panel,
where land cover and the health estimates are measured at the town rather than
averaged over the county.

**By keyboard:** tab to the results table and it is one stop, not three hundred.
Arrows move between rows, Home and End jump to either end, Enter opens a county and
Escape closes it and puts you back on the row you came from. Column headers are
reachable and sortable with Enter, and announce their direction.

**Saved setups live in your browser**, under `refugia.setups.v1` in `localStorage`.
They are per-browser and per-device: they do not travel with a page you share, and
somebody you send it to sees the weights it was published with, not yours.

## The city panel measures two things at a sharper grain

Land cover and the CDC place-release health estimates are measured at the town, not
averaged over the county. Everything else in that panel is the county's figure, and
each row says which — a county figure is identical for every town in it, and saying
so is the difference between a measurement and a repetition.

The reasoning is in the README's [two grains](../../README.md#two-grains).

---

Next: [reading the numbers](reading-the-numbers.md), which is what the columns
actually mean, or [writing a profile](writing-a-profile.md) to change what the page
is ranking on.
