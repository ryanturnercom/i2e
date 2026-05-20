"""Deep-link helpers for the i2e report (spec §8).

Agents share clickable links. If a live server is up (``.i2e/.serve.url`` is
present), prefer ``http://localhost:<port>/<fragment>``. Otherwise fall back
to ``file:///<absolute path to report.html><fragment>``.

The fragment scheme is identical in both modes:

- ``#cap/<slug>``
- ``#item/<slug>/<id>``
- ``#pending/<filename>``
- ``#tick/<tick-id>``

Convenience wrappers exist for each of those. They all delegate to
:func:`deep_link`.
"""

from __future__ import annotations

from pathlib import Path

from ..paths import report_path, serve_url_path


def _read_serve_url(root: Path) -> str | None:
    p = serve_url_path(Path(root))
    if not p.exists():
        return None
    try:
        text = p.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    return text or None


def deep_link(root: Path, fragment: str) -> str:
    """Return a clickable URL for the rendered report.

    Parameters
    ----------
    root:
        Project root containing ``.i2e/``.
    fragment:
        Anchor fragment including the leading ``#``. Pass ``""`` for the
        top of the page.
    """
    root = Path(root)
    if fragment and not fragment.startswith("#"):
        fragment = "#" + fragment

    url = _read_serve_url(root)
    if url:
        # Don't accidentally double a trailing slash before a fragment.
        if not fragment:
            return url
        # Normalise: the URL ends with "/", fragment starts with "#".
        return f"{url}{fragment}"

    p = report_path(root).resolve()
    return p.as_uri() + fragment


def link_capability(root: Path, slug: str) -> str:
    return deep_link(root, f"#cap/{slug}")


def link_item(root: Path, slug: str, item_id: str) -> str:
    return deep_link(root, f"#item/{slug}/{item_id}")


def link_pending(root: Path, filename: str) -> str:
    return deep_link(root, f"#pending/{filename}")


def link_tick(root: Path, tick_id: str) -> str:
    return deep_link(root, f"#tick/{tick_id}")


__all__ = [
    "deep_link",
    "link_capability",
    "link_item",
    "link_pending",
    "link_tick",
]
