/* Runs the shared conformance vectors against the page's own scoring kernel.
 *
 * The kernel is lifted verbatim out of template.html between its BEGIN/END
 * markers rather than copied here, because a copy is exactly the failure this
 * exists to catch. Python runs the same vectors in
 * tests/test_scoring_conformance.py, which is what invokes this.
 *
 * Prints one line per case and exits non-zero on any mismatch.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..", "..");

const page = readFileSync(
    resolve(root, "src/refugia/artifact/template.html"),
    "utf8",
);
const BEGIN = "/* ---- scoring kernel: BEGIN";
const END = "/* ---- scoring kernel: END";
const from = page.indexOf(BEGIN);
const to = page.indexOf(END);
if (from < 0 || to < 0) {
    console.error(
        "could not find the scoring kernel markers in template.html.\n" +
            "If the kernel moved, move the markers with it -- this check is the only " +
            "thing keeping the page's scoring and the Python engine in agreement.",
    );
    process.exit(2);
}

// eslint-disable-next-line no-new-func
const kernel = new Function(
    `${page.slice(from, to)}\nreturn { percentile, normalizeAll, scoreAll };`,
)();

const { cases } = JSON.parse(
    readFileSync(resolve(here, "vectors.json"), "utf8"),
);

const round = (n) => Number(n.toFixed(6));
let failed = 0;

for (const c of cases) {
    const fips =
        c.places ??
        [
            ...new Set(Object.values(c.values).flatMap((v) => Object.keys(v))),
        ].sort();
    const places = fips.map((f) => ({ fips: f }));
    const { ranked } = kernel.scoreAll(
        places,
        c.values,
        c.metrics,
        c.weights,
        c.min_coverage,
    );

    const got = ranked.map((r) => ({
        fips: r.p.fips,
        score: round(r.score),
        cover: round(r.cover),
    }));
    const want = c.expect.map((e) => ({
        fips: e.fips,
        score: round(e.score),
        cover: round(e.cover),
    }));

    // Ties are a real ordering ambiguity between two sort implementations, so
    // equal scores are compared as a set at that score rather than by position.
    const key = (rows) =>
        JSON.stringify(
            rows
                .map((r, i) => ({ ...r, i }))
                .sort(
                    (a, b) => b.score - a.score || a.fips.localeCompare(b.fips),
                )
                .map(({ fips, score, cover }) => [fips, score, cover]),
        );

    if (key(got) === key(want)) {
        console.log(`  ok    ${c.name}`);
    } else {
        failed++;
        console.log(`  FAIL  ${c.name}`);
        console.log(`        want ${key(want)}`);
        console.log(`        got  ${key(got)}`);
    }
}

console.log(
    failed
        ? `\n${failed} of ${cases.length} vectors disagree with the page's kernel`
        : `\nall ${cases.length} vectors match the page's kernel`,
);
process.exit(failed ? 1 : 0);
