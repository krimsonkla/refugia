# Security

## Reporting

Use GitHub's **private vulnerability reporting** on this repository — the Security
tab, "Report a vulnerability". That opens a channel only the maintainer can see.

Please do not open a public issue for something exploitable. For everything else,
a normal issue is the right place, and quicker.

This is a personal project. There is no security team and no response-time promise;
expect a person reading it when they next sit down.

## What is in scope

refugia has no server, no accounts, no credentials and no database. It stores
nothing about you: `data/` is a cache of public files, and a profile is a JSON file
you wrote and can read. That removes most of what would usually be worth reporting,
and leaves four boundaries that are real.

**A spec is a network request in data clothing.** The declarative tier lets a
metric be added as JSON with no code, which is the point of it. What that JSON
names is a URL your machine will fetch, and a column it will parse. It is validated
on load — the URL must be `https`, and the fields that reach the published page may
not contain markup — but validation is not review. A spec arriving by pull request
gets read like code, because that is what it is.

**Fetched data is untrusted.** Ten public endpoints, none of them under this
project's control, and any of them can start returning something unexpected — a
200 with an error body, a renamed column, a value where a number should be. The
page escapes everything it interpolates and the cache refuses an empty response,
but a report showing untrusted upstream content reaching a viewer is a real one.

**A published page is a shared artifact.** It embeds values for every place it
ranks and the profile it was built with, including a home county if one was set.
That is by design and `publish` says so, but a way for a page to disclose more than
its author intended is worth reporting.

**`ask` talks to a model, and so does the page.** On the command line it is a local
Ollama by default, which is where the question and the rows stay; `--host` will
point it somewhere else, and then they go there. The published page has its own Ask
panel, which requests a capability from whatever host it is opened in and sends that
host's model the viewer's weights, requirements and the rows on screen. Both are
opt-in — nothing is sent until somebody asks a question — and a path that reached a
model without the operator choosing it would be a finding.

## What is not a vulnerability

An upstream going down, moving a file, or publishing a wrong number. Those are
data-quality problems, and the tool is built to survive them: a failing source
costs its own metrics, coverage below 75% is flagged, and a page records how old
the data behind it is. Open an issue.
