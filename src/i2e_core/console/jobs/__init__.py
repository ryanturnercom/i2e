"""Long-running console-triggered operations (Jobs).

A Job is a regression run or a spec reconcile dispatched from the
console. The registry tracks every Job in-memory; the runner executes
the work and streams stdout into a per-job ring buffer. SSE emits
``{"kind": "job", "job_id": "..."}`` events on every line so the
toast component can re-render.

Jobs are not persisted across i2e-serve restarts. If serve dies
mid-job, the subprocess survives (worktree-style sweep), the final
result still lands in ``.i2e/logs/`` as a tick entry, but the toast
is gone.
"""
