# Sample PRD — Link Shortener with Analytics

A small URL shortener with click tracking and an aggregate dashboard.
The three sections below are deliberately ordered: each builds on the
previous.

## Section 1: Shorten Links

Users paste a long URL and get a 7-character short code in return.
The shortener guarantees the code is unique and stable.

## Section 2: Track Clicks

Each time a short URL is resolved, the system increments a per-link
counter. The counter is durable across restarts.

## Section 3: Expose Analytics

Owners can view aggregate click counts per link, sorted by recency.
The view is read-only and caches for 60 seconds.
