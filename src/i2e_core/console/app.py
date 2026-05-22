"""Console HTTP route table.

``serve.py`` owns the socket, the SSE channel, and ``/shutdown``; every
other request is delegated here via :func:`handle`. GET routes render
full pages; POST routes run the narrow write actions (promote / resolve)
and return an htmx fragment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, unquote

from . import ui
from .actions.demote import demote
from .actions.promote import promote
from .actions.reconcile import reconcile_spec
from .actions.regression import run_regression
from .actions.resolve import resolve
from .jobs.registry import JobRegistry
from .prefs import DEFAULT_PREFS, build_set_cookie_header
from .sse import ChangeBroker
from .views.dashboard import render_dashboard
from .views.intent import render_intent_detail
from .views.logs import render_logs
from .views.pending import render_pending
from .views.specs import render_spec_detail, render_specs_list
from .views.workers import render_workers

_STATIC = Path(__file__).parent / "static"
_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".html": "text/html; charset=utf-8",
}


@dataclass
class Response:
    status: int = 200
    content_type: str = "text/html; charset=utf-8"
    body: bytes = b""
    headers: dict = field(default_factory=dict)


def _html(text: str, status: int = 200) -> Response:
    return Response(status, "text/html; charset=utf-8", text.encode("utf-8"))


def _first(query: dict, key: str) -> str | None:
    vals = query.get(key)
    return vals[0] if vals else None


def _static(path: str) -> Response:
    name = path[len("/static/"):]
    if not name or "/" in name or "\\" in name or ".." in name:
        return Response(404, "text/plain", b"not found")
    fp = _STATIC / name
    if not fp.is_file():
        return Response(404, "text/plain", b"not found")
    ctype = _CONTENT_TYPES.get(fp.suffix.lower(), "application/octet-stream")
    return Response(200, ctype, fp.read_bytes(), {"Cache-Control": "max-age=3600"})


def _error_modal(title: str, intro: str, errors: list) -> str:
    """A modal-dialog fragment listing structured field/msg errors.

    Rendered into the body-level ``#modal-mount`` (see :func:`_modal_response`)
    so the fixed-position overlay always centers on the viewport instead of
    rendering inline inside whatever element triggered the request.
    """
    items = "".join(
        f'<li><span class="field">{ui.esc(e.get("field"))}</span>'
        f'{ui.esc(e.get("msg"))}</li>'
        for e in errors
    )
    close = "onclick=\"document.getElementById('action-modal').remove()\""
    # Backdrop click dismisses the modal, but only when the click lands on
    # the overlay itself — clicks inside the dialog must not close it.
    backdrop = (
        "onclick=\"if(event.target===this)"
        "document.getElementById('action-modal').remove()\""
    )
    return (
        f'<div class="modal-overlay" id="action-modal" {backdrop}>'
        '<div class="modal" role="dialog" aria-modal="true">'
        '<div class="modal-head">'
        f'<h2 class="h2">{ui.esc(title)}</h2>'
        f'<button class="modal-close" type="button" {close}>&times;</button>'
        "</div>"
        f"<p>{ui.esc(intro)}</p>"
        f'<ul class="modal-errors">{items}</ul>'
        '<div class="modal-foot">'
        f'<button class="btn" type="button" {close}>Close</button>'
        "</div></div></div>"
    )


def _modal_response(title: str, intro: str, errors: list) -> Response:
    """Return an error modal retargeted to the body-level ``#modal-mount``.

    The promote/demote buttons target ``#status-result`` — an inline slot in
    the meta card — for their success badge. An error must instead surface as
    a full-screen overlay, so the swap target is overridden via htmx's
    ``HX-Retarget`` / ``HX-Reswap`` response headers. That lands the modal as
    a direct child of ``<body>``, where ``position: fixed`` reliably centers
    it on the viewport regardless of the triggering element's ancestors.
    """
    resp = _html(_error_modal(title, intro, errors))
    resp.headers["HX-Retarget"] = "#modal-mount"
    resp.headers["HX-Reswap"] = "innerHTML"
    return resp


def _promote_fragment(root: Path, slug: str) -> Response:
    result = promote(root, slug)
    if result.get("valid"):
        return _html(
            '<div class="badge pass">promoted → active</div>'
            '<div class="mono faded" style="margin-top:6px;font-size:11px">'
            "reload to see the new state</div>"
        )
    return _modal_response(
        "Cannot promote",
        "This draft fails forced-evidence validation. Fix it via "
        "i2e-intent, then promote.",
        result.get("errors", []),
    )


def _demote_fragment(root: Path, slug: str) -> Response:
    result = demote(root, slug)
    if result.get("valid"):
        return _html(
            '<div class="badge draft">demoted → draft</div>'
            '<div class="mono faded" style="margin-top:6px;font-size:11px">'
            "reload to see the new state</div>"
        )
    return _modal_response(
        "Cannot demote",
        "This intent cannot be demoted to draft.",
        result.get("errors", []),
    )


def _resolve_fragment(root: Path, filename: str, body: str) -> Response:
    form = parse_qs(body or "")
    verdict = _first(form, "verdict") or "yes"
    notes = _first(form, "notes") or ""
    try:
        resolve(root, filename, verdict=verdict, notes=notes)
    except FileNotFoundError:
        return _html(
            '<article class="pending-card">'
            '<div class="badge fail">pending file not found</div></article>'
        )
    return _html(
        f'<article class="pending-card"><div class="row">'
        f'{ui.badge("resolved: " + verdict, "pass")}'
        f'<span class="mono faded" style="font-size:11px">'
        f"queued — applied on the next i2e-adapt tick</span></div></article>"
    )


def _toast(title: str, body: str, kind: str = "pass") -> Response:
    """An htmx toast fragment, appended into ``#toasts``."""
    close = "onclick=\"this.closest('.toast').remove()\""
    return _html(
        '<div class="toast">'
        f'<div class="toast-head">{ui.badge(title, kind, upper=True)}'
        f'<button class="toast-close" type="button" {close}>&times;</button></div>'
        f'<div class="toast-body">{body}</div></div>'
    )


def _prefs_fragment(body: str) -> Response:
    form = parse_qs(body or "")
    prefs = dict(DEFAULT_PREFS)
    for key in DEFAULT_PREFS:
        val = _first(form, key)
        if val:
            prefs[key] = val
    resp = _html("ok")
    resp.headers["Set-Cookie"] = build_set_cookie_header(prefs)
    resp.headers["HX-Refresh"] = "true"
    return resp


def _regression_fragment(root: Path, body: str) -> Response:
    scope = _first(parse_qs(body or ""), "scope") or "all-shipped"
    registry = JobRegistry()
    broker = ChangeBroker()
    try:
        job = run_regression(root, scope=scope, registry=registry, broker=broker)
    finally:
        broker.close()
    if job.state == "completed":
        return _toast(
            "regression complete",
            f'scope <span class="mono">{ui.esc(scope)}</span> — '
            '<a href="/logs">see the tick in Logs</a> for per-capability '
            "results and any shipped→active demotions.",
        )
    return _toast("regression failed", "the regression job did not complete", "fail")


def _reconcile_fragment(root: Path, slug: str) -> Response:
    registry = JobRegistry()
    broker = ChangeBroker()
    try:
        job = reconcile_spec(root, slug, registry=registry, broker=broker)
    finally:
        broker.close()
    if job.state == "completed":
        return _toast(
            "reconcile complete",
            f'spec <span class="mono">{ui.esc(slug)}</span> — '
            '<a href="/logs">see Logs</a> for the proposed draft actions.',
        )
    return _toast("reconcile failed", "the reconcile job did not complete", "fail")


def handle(
    root: Path,
    method: str,
    path: str,
    query_string: str,
    body: str,
    cookie: str | None = None,
) -> Response:
    """Resolve one request. ``query_string`` and ``body`` are raw strings."""
    root = Path(root)
    query = parse_qs(query_string or "")

    try:
        if method == "GET":
            if path in ("/", "/index.html"):
                return _html(
                    render_dashboard(
                        root,
                        flt=_first(query, "flt"),
                        q=_first(query, "q"),
                        cookie=cookie,
                    )
                )
            if path == "/pending":
                return _html(render_pending(root, cookie=cookie))
            if path == "/workers":
                return _html(render_workers(root, cookie=cookie))
            if path == "/logs":
                return _html(
                    render_logs(
                        root,
                        _first(query, "mode"),
                        phase=_first(query, "phase"),
                        q=_first(query, "q"),
                        cookie=cookie,
                    )
                )
            if path == "/specs":
                return _html(render_specs_list(root, cookie=cookie))
            if path.startswith("/specs/"):
                sid = unquote(path[len("/specs/"):]).strip("/")
                return _html(render_spec_detail(root, sid, cookie=cookie))
            if path.startswith("/intent/"):
                slug = unquote(path[len("/intent/"):]).strip("/")
                return _html(render_intent_detail(root, slug, cookie=cookie))
            if path.startswith("/static/"):
                return _static(path)
            return _html('<h1 class="h1">404 — not found</h1>', 404)

        if method == "POST":
            if path.startswith("/api/intents/") and path.endswith("/promote"):
                slug = unquote(path[len("/api/intents/"):-len("/promote")])
                return _promote_fragment(root, slug)
            if path.startswith("/api/intents/") and path.endswith("/demote"):
                slug = unquote(path[len("/api/intents/"):-len("/demote")])
                return _demote_fragment(root, slug)
            if path.startswith("/api/pending/") and path.endswith("/resolve"):
                fname = unquote(path[len("/api/pending/"):-len("/resolve")])
                return _resolve_fragment(root, fname, body)
            if path == "/api/prefs":
                return _prefs_fragment(body)
            if path == "/api/regression/run":
                return _regression_fragment(root, body)
            if path.startswith("/api/specs/") and path.endswith("/reconcile"):
                sid = unquote(path[len("/api/specs/"):-len("/reconcile")])
                return _reconcile_fragment(root, sid)
            return _html("not found", 404)

        return _html("method not allowed", 405)
    except Exception as exc:  # noqa: BLE001 — never crash the server thread
        return _html(
            f'<h1 class="h1">500 — render failed</h1>'
            f"<pre>{ui.esc(exc)}</pre>",
            500,
        )
