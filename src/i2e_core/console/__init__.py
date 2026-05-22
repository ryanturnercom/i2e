"""i2e Console — multi-route HTMX+Jinja2 app served by i2e-serve.

Replaces the single-page static report.html with an interactive
developer console. See .i2e/specs/i2e-console.md for the full design.

This package owns: views (one module per top-nav section), the typed
SSE broker, cookie-based prefs, and (in later epics) the write
endpoints and job runner. Templates and static assets live alongside.
"""
