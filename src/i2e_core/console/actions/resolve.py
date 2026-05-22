"""Console-driven pending resolution.

Narrow boundary carve-out for i2e-serve. Writes a ``resolution:`` block
to an existing pending YAML in the shape that
``i2e-adapt.apply_resolutions`` reads. The pending file stays in
``.i2e/pending/`` until the next ``i2e-adapt`` tick applies it; the UI
surfaces this with a "queued, applied on next tick" hint.

ONLY the ``resolution`` and ``status`` fields of the pending document
change. Every other field stays byte-identical.
"""

from __future__ import annotations

from pathlib import Path

from ...io_utils import atomic_write, dump_yaml
from ...paths import pending_dir
from ...pending import read_pending


def resolve(root: Path, pending_filename: str, verdict: str, notes: str = "") -> Path:
    """Write a resolution block onto ``.i2e/pending/<pending_filename>``.

    ``verdict`` is the operator's choice (e.g. ``"yes"`` for a human
    evaluation or one of the numeric choices ``1``-``4`` for an
    escalation). ``notes`` is appended on a new line so the body still
    parses as a ``new expect: ...`` line when needed by
    ``apply_resolutions``.

    Raises ``FileNotFoundError`` if the pending file does not exist.
    """
    root = Path(root)
    pdir = pending_dir(root)
    path = pdir / pending_filename
    if not path.exists():
        raise FileNotFoundError(f"Pending file not found: {path}")

    pf = read_pending(path)

    body_lines = [verdict.strip()]
    note = (notes or "").strip()
    if note:
        body_lines.append("")
        body_lines.append(note)
    resolution_body = "\n".join(body_lines)

    pf.resolution = resolution_body
    pf.status = "resolved"

    payload = pf.model_dump(mode="json", exclude_none=False)
    atomic_write(path, dump_yaml(payload))
    return path
