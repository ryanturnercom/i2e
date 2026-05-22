"""Rock Salt brand font applied to the i2e logo in the report header.

The Google Font Rock Salt is what ryanturner.com uses for its wordmark;
the report header must load it and apply it to the i2e logo so the brand
mark matches.
"""

from __future__ import annotations

from pathlib import Path

from i2e_core.report import render_to_string


def test_implemented(tmp_path: Path) -> None:
    for sub in ("intents", "evidence", "pending", "logs", "context"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    html = render_to_string(tmp_path)

    # Stylesheet imported from Google Fonts.
    assert "fonts.googleapis.com" in html
    assert "Rock+Salt" in html
    # Preconnect hints present so the font loads early.
    assert 'rel="preconnect"' in html
    assert "fonts.gstatic.com" in html

    # The logo span uses Rock Salt in CSS.
    assert "'Rock Salt'" in html or '"Rock Salt"' in html

    # The header banner now contains a logo element.
    header_start = html.index("<header class=\"banner\">")
    header_end = html.index("</header>", header_start)
    header_block = html[header_start:header_end]
    assert 'class="logo"' in header_block
    # The logo wordmark itself reads "i2e" (the brand mark) in the header.
    assert ">i2e<" in header_block
