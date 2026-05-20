"""Prevent pytest from collecting the fixture pytest modules in this directory.

These files are *fixtures* for the pytest provider smoke test — they're
invoked deliberately via a subprocess, not collected as part of the suite.
"""

collect_ignore_glob = ["*_test.py", "test_*.py"]
