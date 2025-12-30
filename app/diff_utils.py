import html
from difflib import HtmlDiff


def make_side_by_side_diff_html(base_text: str, new_text: str) -> str:
    """
    Returns an HTML table showing a side-by-side diff.
    Safe to inject into the page as HTML.
    """
    base_lines = (base_text or "").splitlines()
    new_lines = (new_text or "").splitlines()

    # HtmlDiff generates a full HTML table; we return just the table markup.
    diff = HtmlDiff(wrapcolumn=80).make_table(
        base_lines,
        new_lines,
        fromdesc="Base Resume",
        todesc="Generated Resume",
        context=True,
        numlines=3,
    )

    # HtmlDiff output is already HTML. If you want additional hardening, you can
    # keep it as-is and only inject into a controlled div.
    return diff
