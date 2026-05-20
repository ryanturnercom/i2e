# Architecture

The URL shortener is intentionally tiny — three modules under `src/shortener/`:

- **`store.py`** — `FileStore` wraps a JSON file. All writes are atomic (`os.replace`) so a crash mid-write never produces a partial mapping. Thread-locked for the in-process server.
- **`service.py`** — `shorten(store, url)` validates scheme, generates a 7-char code from a 62-char alphabet, retries up to 10 times for uniqueness, and persists. `resolve(store, code)` is a pure lookup. `is_safe_url(url)` is the open-redirect guard.
- **`server.py`** — stdlib `ThreadingHTTPServer`. Two routes: `POST /shorten` (JSON in, JSON out) and `GET /<code>` (302 redirect). Loopback-friendly defaults.

## Storage shape

`data/shortener.json`:

```json
{
  "abc1234": "https://example.com/long/path",
  "Xyz7890": "https://other.example.com"
}
```

Flat dictionary — short code → long URL. No reverse index (we don't deduplicate).

## Why no database

This is an I2E demo. The "Code is normal" principle (spec §11) means the storage layer should be whatever's right for the problem. For a single-machine shortener that handles modest traffic, a JSON file with atomic writes is fine; trading it for SQLite would be a different intent.

## Threat model

The single named threat is **open redirect** — an attacker submits `javascript:alert(1)` or `file:///etc/passwd` hoping the server will hand it back via `GET /<code>`. The `is_safe_url` guard rejects anything not in `{http, https}` with a non-empty netloc. The adversarial pytest in `tests/adversarial/` enforces this as a Constraint, so the loop will refuse to ship without it.
