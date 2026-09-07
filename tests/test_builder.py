"""The page is written to disk, where no host supplies a document around it."""

from refugia.artifact.builder import ArtifactBuilder

FRAGMENT = "<title>T</title>\n<style>\nbody { color: red }\n</style>\n<div>body — ° content</div>"


def test_the_written_page_is_a_complete_document():
    """A fragment on disk renders in quirks mode; the template is a fragment."""
    html = ArtifactBuilder.as_document(FRAGMENT)
    assert html.startswith("<!doctype html>")
    assert html.rstrip().endswith("</html>")


def test_the_document_declares_utf8():
    """The credits line carries non-ASCII, which arrives as mojibake without it."""
    assert '<meta charset="utf-8"' in ArtifactBuilder.as_document(FRAGMENT)


def test_the_document_declares_a_viewport():
    """Without one every phone lays the page out at desktop width."""
    html = ArtifactBuilder.as_document(FRAGMENT)
    assert '<meta name="viewport" content="width=device-width, initial-scale=1"' in html


def test_the_style_stays_in_the_head_and_the_markup_in_the_body():
    """Splitting anywhere else would put the stylesheet in the body."""
    html = ArtifactBuilder.as_document(FRAGMENT)
    head = html[html.index("<head>") : html.index("</head>")]
    body = html[html.index("<body>") :]
    assert "<style>" in head and "<title>T</title>" in head
    assert "<div>body" in body and "<style>" not in body


def test_a_fragment_with_no_style_block_still_becomes_a_document():
    """Nothing should depend on the template keeping exactly one style block."""
    html = ArtifactBuilder.as_document("<div>only body</div>")
    assert html.startswith("<!doctype html>")
    assert "<div>only body</div>" in html
