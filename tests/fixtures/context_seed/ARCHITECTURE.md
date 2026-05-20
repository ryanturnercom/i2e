# Architecture

The system is a small Python package. URLs are encoded into 7-char codes and
stored in a flat dict for development; later a real KV store.

## Layers
- `src/shorten_url/` — pure functions
- `tests/` — pytest cases
