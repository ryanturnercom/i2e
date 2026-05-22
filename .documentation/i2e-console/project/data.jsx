// data.jsx — fictional i2e project state for the console demo.
// Mirrors the shape from I2E_simplified.md: capabilities, evidence (cases/targets/constraints),
// pendings, worktrees (in-flight workers), tick logs.

const NOW = new Date('2026-05-21T11:42:00Z');

// ─── Capabilities ────────────────────────────────────────────────────────────
// status: draft | active | shipped | retired
// Evidence items each carry: id, type, provider, query, expect, effort, watcher
const CAPABILITIES = [
  {
    slug: 'shorten-url',
    title: 'Shorten a URL',
    summary: 'A user turns a long URL into a short one and is redirected.',
    status: 'active',
    version: 4,
    created: '2026-04-12',
    updated: '2026-05-19',
    watcher: '@platform-team',
    depends_on: [],
    touches: ['src/shorten_url/**', 'tests/test_shorten_url.py'],
    spec: 'core-link-shortener',
    spec_section: 2,
    evidence: [
      { id: 'code-generated', type: 'case', provider: 'pytest', query: 'tests/test_shorten.py::test_returns_7_char_code', expect: 'passes', effort: 'medium', verdict: 'pass' },
      { id: 'redirect-works', type: 'case', provider: 'pytest', query: 'tests/test_redirect.py::test_redirects_to_original', expect: 'passes', effort: 'medium', verdict: 'pass' },
      { id: 'collision-handled', type: 'case', provider: 'pytest', query: 'tests/test_collision.py', expect: 'passes', effort: 'high', verdict: 'pass' },
      { id: 'redirect-latency-p95', type: 'target', provider: 'datadog', query: 'redirect_latency{quantile=0.95}', window: '5m', expect: '<50ms', effort: 'medium', verdict: 'met', value: '32ms' },
      { id: 'brand-feel', type: 'target', provider: 'human', query: 'Open the shortener and shorten 3 URLs. Trustworthy and snappy?', expect: 'yes', effort: 'lazy', verdict: 'pass', resolved_by: '@ryan', resolved_at: '2026-05-18T18:00:00Z' },
    ],
    constraints: [
      { id: 'no-open-redirect', provider: 'pytest', query: 'tests/adversarial/test_open_redirect_blocked.py', expect: 'passes', effort: 'high', verdict: 'pass' },
      { id: 'pii-not-logged', provider: 'sentry', query: 'events:contains("http") in:logs', expect: '0', effort: 'high', verdict: 'pass' },
    ],
    last_run: '2026-05-19-a3f8c2',
    shippable: true,
  },
  {
    slug: 'change-password',
    title: 'Change Password',
    summary: 'A logged-in user changes their password. Edge cases enforced.',
    status: 'active',
    version: 7,
    created: '2026-03-18',
    updated: '2026-05-21',
    watcher: '@auth-team',
    depends_on: [],
    touches: ['src/auth/password.py', 'tests/auth/**'],
    evidence: [
      { id: 'short-password-rejected', type: 'case', provider: 'pytest', query: 'tests/edge/test_short_password_rejected.py', expect: 'passes', effort: 'medium', verdict: 'pass' },
      { id: 'whitespace-only-rejected', type: 'case', provider: 'pytest', query: 'tests/adversarial/test_whitespace_password_rejected.py', expect: 'passes', effort: 'medium', verdict: 'fail', attempts_used: 2 },
      { id: 'change-flow', type: 'case', provider: 'pytest', query: 'tests/auth/test_change_flow.py', expect: 'passes', effort: 'medium', verdict: 'pass' },
      { id: 'breach-check-latency', type: 'target', provider: 'datadog', query: 'haveibeenpwned_latency{p95}', window: '15m', expect: '<800ms', effort: 'low', verdict: 'met', value: '412ms' },
    ],
    constraints: [
      { id: 'password-min-length-8', provider: 'pytest', query: 'tests/constraints/test_password_min_length.py', expect: 'passes', effort: 'high', verdict: 'pass' },
      { id: 'password-not-logged', provider: 'sentry', query: 'events:contains("password=")', expect: '0', effort: 'high', verdict: 'pass' },
    ],
    last_run: '2026-05-21-9f1c0e',
    shippable: false,
    inflight: { worker: 'w-7c1f2e', step: 'i2e-develop', progress: 'Editing src/auth/password.py — adding whitespace strip' },
  },
  {
    slug: 'rate-limit',
    title: 'Per-key Rate Limiting',
    summary: 'API keys are rate-limited per minute; offenders get back-pressure.',
    status: 'active',
    version: 3,
    created: '2026-04-02',
    updated: '2026-05-20',
    watcher: '@platform-team',
    depends_on: [],
    touches: ['src/middleware/rate_limit.py'],
    evidence: [
      { id: 'limit-enforced', type: 'case', provider: 'pytest', query: 'tests/test_rate_limit.py::test_429_after_threshold', expect: 'passes', effort: 'medium', verdict: 'pass' },
      { id: 'backoff-header-set', type: 'case', provider: 'pytest', query: 'tests/test_rate_limit.py::test_retry_after_present', expect: 'passes', effort: 'low', verdict: 'pass' },
      { id: 'abuse-down-30pct', type: 'target', provider: 'datadog', query: 'abuse_attempts{rate}', window: '7d', expect: '-30%', effort: 'medium', verdict: 'trending', value: '-18%', attempts_used: 2 },
      { id: 'abuse-protection-feel', type: 'target', provider: 'human', query: 'Hit the API with a script that exceeds the limit. Does it back off cleanly?', expect: 'yes', effort: 'medium', verdict: 'awaiting_human', pending: '2026-05-20-rate-limit-abuse-protection-feel' },
    ],
    constraints: [
      { id: 'no-false-429-on-burst', provider: 'pytest', query: 'tests/test_burst.py', expect: 'passes', effort: 'high', verdict: 'pass' },
    ],
    last_run: '2026-05-20-7e2d11',
    shippable: false,
  },
  {
    slug: 'signup-flow',
    title: 'Signup Flow',
    summary: 'A new user signs up with email + password; lands in onboarding.',
    status: 'active',
    version: 5,
    created: '2026-03-22',
    updated: '2026-05-19',
    watcher: '@growth',
    depends_on: [],
    touches: ['src/signup/**', 'tests/signup/**'],
    evidence: [
      { id: 'happy-path', type: 'case', provider: 'pytest', query: 'tests/signup/test_happy.py', expect: 'passes', effort: 'medium', verdict: 'pass' },
      { id: 'duplicate-email-blocked', type: 'case', provider: 'pytest', query: 'tests/signup/test_dupe.py', expect: 'passes', effort: 'medium', verdict: 'pass' },
      { id: 'magic-link-delivery', type: 'target', provider: 'datadog', query: 'magic_link_delivery_p95', window: '1h', expect: '<30s', effort: 'low', verdict: 'met', value: '11s' },
      { id: 'brand-feel', type: 'target', provider: 'human', query: 'Walk through signup from a fresh email. Does it feel quick and reassuring?', expect: 'yes', effort: 'medium', verdict: 'awaiting_human', pending: '2026-05-19-signup-flow-brand-feel' },
      { id: 'd7-activation', type: 'target', provider: 'ga', query: 'd7_activation_rate', window: '14d', expect: '>40%', effort: 'medium', verdict: 'trending', value: '34%', attempts_used: 1 },
    ],
    constraints: [
      { id: 'no-bot-signups', provider: 'sentry', query: 'flag:bot AND signup', expect: '0', effort: 'high', verdict: 'pass' },
    ],
    last_run: '2026-05-19-d44a01',
    shippable: false,
  },
  {
    slug: 'oauth-google',
    title: 'Sign in with Google',
    summary: 'Google OAuth login; account-linking on email match.',
    status: 'active',
    version: 2,
    created: '2026-04-28',
    updated: '2026-05-20',
    watcher: '@auth-team',
    depends_on: [],
    touches: ['src/auth/oauth/**'],
    evidence: [
      { id: 'oauth-callback', type: 'case', provider: 'pytest', query: 'tests/auth/test_oauth_callback.py', expect: 'passes', effort: 'medium', verdict: 'pass' },
      { id: 'account-link-on-email', type: 'case', provider: 'pytest', query: 'tests/auth/test_account_link.py', expect: 'passes', effort: 'high', verdict: 'fail', attempts_used: 6 },
      { id: 'google-consent-flow', type: 'target', provider: 'human', query: 'Sign in with a fresh Google account. Consent screen feels official?', expect: 'yes', effort: 'medium', verdict: 'awaiting_human', pending: '2026-05-20-oauth-google-consent-flow' },
    ],
    constraints: [
      { id: 'no-token-in-url', provider: 'pytest', query: 'tests/constraints/test_no_token_in_url.py', expect: 'passes', effort: 'high', verdict: 'pass' },
    ],
    last_run: '2026-05-20-b7e220',
    shippable: false,
  },
  {
    slug: 'usage-analytics',
    title: 'Usage Analytics Pipeline',
    summary: 'Capture page + funnel events; surface in GA + internal dashboard.',
    status: 'active',
    version: 6,
    created: '2026-02-11',
    updated: '2026-05-18',
    watcher: '@data-team',
    depends_on: [],
    touches: ['src/analytics/**'],
    evidence: [
      { id: 'event-shape-valid', type: 'case', provider: 'pytest', query: 'tests/analytics/test_schema.py', expect: 'passes', effort: 'medium', verdict: 'pass' },
      { id: 'no-duplicate-events', type: 'case', provider: 'pytest', query: 'tests/analytics/test_dedupe.py', expect: 'passes', effort: 'medium', verdict: 'pass' },
      { id: 'dau-growth', type: 'target', provider: 'ga', query: 'daily_active_users', window: '28d', expect: '+10% QoQ', effort: 'medium', verdict: 'unmet', value: '+2.1%', attempts_used: 3, pending: '2026-05-18-usage-analytics-dau-growth' },
      { id: 'funnel-completion', type: 'target', provider: 'ga', query: 'funnel:signup->activate', window: '14d', expect: '>55%', effort: 'low', verdict: 'trending', value: '49%', attempts_used: 1 },
    ],
    constraints: [
      { id: 'no-pii-in-events', provider: 'sentry', query: 'event_props:contains_email', expect: '0', effort: 'high', verdict: 'pass' },
    ],
    last_run: '2026-05-18-c11000',
    shippable: false,
  },
  {
    slug: 'dashboard-charts',
    title: 'Customer Dashboard Charts',
    summary: 'Render time-series + bar charts on the customer dashboard.',
    status: 'active',
    version: 1,
    created: '2026-05-15',
    updated: '2026-05-21',
    watcher: '@frontend',
    depends_on: [],
    touches: ['src/charts/**', 'tests/charts/**'],
    evidence: [
      { id: 'renders-empty-state', type: 'case', provider: 'pytest', query: 'tests/charts/test_empty.py', expect: 'passes', effort: 'low', verdict: 'pass' },
      { id: 'tooltip-positions', type: 'case', provider: 'pytest', query: 'tests/charts/test_tooltip.py', expect: 'passes', effort: 'medium', verdict: 'trending', attempts_used: 1 },
      { id: 'render-perf-1k-points', type: 'target', provider: 'datadog', query: 'chart_render_p95', window: '1h', expect: '<120ms', effort: 'low', verdict: 'awaiting_first_run' },
    ],
    constraints: [
      { id: 'no-canvas-leaks', provider: 'pytest', query: 'tests/constraints/test_canvas_dispose.py', expect: 'passes', effort: 'medium', verdict: 'pass' },
    ],
    last_run: '2026-05-21-fresh',
    shippable: false,
    inflight: [
      { worker: 'w-a8d44b', step: 'i2e-develop', progress: 'Writing src/charts/renderer.tsx — d3 scale fns' },
      { worker: 'w-3b91f7', step: 'i2e-develop', progress: 'Writing tests/charts/test_tooltip.py — hover position cases' },
    ],
  },
  {
    slug: 'email-notifications',
    title: 'Transactional Email',
    summary: 'Send welcome, reset, and digest emails through Postmark.',
    status: 'active',
    version: 4,
    created: '2026-03-30',
    updated: '2026-05-17',
    watcher: '@growth',
    depends_on: ['signup-flow'],
    touches: ['src/email/**'],
    evidence: [
      { id: 'welcome-sent', type: 'case', provider: 'pytest', query: 'tests/email/test_welcome.py', expect: 'passes', effort: 'low', verdict: 'pass' },
      { id: 'reset-sent', type: 'case', provider: 'pytest', query: 'tests/email/test_reset.py', expect: 'passes', effort: 'low', verdict: 'pass' },
      { id: 'unsubscribe-clarity', type: 'target', provider: 'human', query: 'Open the digest in 3 mail clients. Is unsubscribe obvious and one-click?', expect: 'yes', effort: 'medium', verdict: 'awaiting_human', pending: '2026-05-17-email-notifications-unsubscribe-clarity' },
      { id: 'delivery-rate', type: 'target', provider: 'datadog', query: 'postmark_delivery_rate', window: '24h', expect: '>99%', effort: 'low', verdict: 'met', value: '99.6%' },
    ],
    constraints: [
      { id: 'no-pii-in-subject', provider: 'sentry', query: 'email_subject:contains_email', expect: '0', effort: 'high', verdict: 'pass' },
    ],
    last_run: '2026-05-17-aa5500',
    shippable: false,
  },
  {
    slug: 'accessibility-aa',
    title: 'WCAG 2.1 AA Compliance',
    summary: 'Audit + fix to AA across every customer-facing route.',
    status: 'draft',
    version: 1,
    created: '2026-05-12',
    updated: '2026-05-12',
    watcher: '@design',
    depends_on: [],
    touches: [],
    evidence: [
      { id: 'axe-zero-violations', type: 'case', provider: 'pytest', query: 'tests/a11y/test_axe.py', expect: 'passes', effort: 'high' },
      { id: 'keyboard-nav-complete', type: 'target', provider: 'human', query: 'Tab through every route without a mouse. Any traps?', expect: 'yes', effort: 'medium' },
    ],
    constraints: [],
    shippable: false,
  },
  {
    slug: 'password-reset',
    title: 'Password Reset Flow',
    summary: 'Forgot-password → email link → set new password.',
    status: 'draft',
    version: 1,
    created: '2026-05-14',
    updated: '2026-05-14',
    watcher: '@auth-team',
    depends_on: ['change-password'],
    touches: ['src/auth/reset/**'],
    evidence: [
      { id: 'link-expires-15m', type: 'case', provider: 'pytest', query: 'tests/auth/test_reset_expiry.py', expect: 'passes', effort: 'medium' },
      { id: 'reset-completion-rate', type: 'target', provider: 'ga', query: 'reset_completion_rate', window: '7d', expect: '>70%', effort: 'low' },
    ],
    constraints: [],
    shippable: false,
  },
  {
    slug: 'onboarding-tour',
    title: 'In-product Onboarding Tour',
    summary: '4-step product tour shown to fresh signups.',
    status: 'draft',
    version: 1,
    created: '2026-05-16',
    updated: '2026-05-16',
    watcher: '@growth',
    depends_on: ['signup-flow'],
    touches: [],
    evidence: [
      { id: 'tour-completion', type: 'target', provider: 'ga', query: 'tour_completion_rate', window: '14d', expect: '>60%', effort: 'medium' },
    ],
    constraints: [],
    shippable: false,
  },
  {
    slug: 'markdown-editor',
    title: 'Markdown Editor with Mentions',
    summary: 'Rich markdown editor; @-mentions for team members.',
    status: 'shipped',
    version: 8,
    created: '2026-01-09',
    updated: '2026-05-02',
    shipped_at: '2026-05-02',
    watcher: '@frontend',
    depends_on: [],
    touches: ['src/editor/**'],
    evidence: [
      { id: 'mentions-fuzzy-match', type: 'case', provider: 'pytest', query: 'tests/editor/test_mentions.py', expect: 'passes', effort: 'medium', verdict: 'pass' },
      { id: 'code-blocks-highlighted', type: 'case', provider: 'pytest', query: 'tests/editor/test_highlight.py', expect: 'passes', effort: 'medium', verdict: 'pass' },
      { id: 'editor-load-p95', type: 'target', provider: 'datadog', query: 'editor_load_p95', window: '24h', expect: '<400ms', effort: 'low', verdict: 'met', value: '210ms' },
    ],
    constraints: [
      { id: 'no-xss', provider: 'pytest', query: 'tests/security/test_editor_xss.py', expect: 'passes', effort: 'high', verdict: 'pass' },
    ],
    last_run: '2026-05-02-shipped',
    shippable: true,
  },
  {
    slug: 'dark-mode',
    title: 'Dark Mode',
    summary: 'Theme toggle across the app with system-preference detection.',
    status: 'shipped',
    version: 3,
    created: '2026-02-20',
    updated: '2026-04-14',
    shipped_at: '2026-04-14',
    watcher: '@frontend',
    depends_on: [],
    touches: ['src/theme/**'],
    evidence: [
      { id: 'theme-persists', type: 'case', provider: 'pytest', query: 'tests/theme/test_persist.py', expect: 'passes', effort: 'low', verdict: 'pass' },
      { id: 'contrast-aa', type: 'case', provider: 'pytest', query: 'tests/theme/test_contrast.py', expect: 'passes', effort: 'high', verdict: 'pass' },
    ],
    constraints: [],
    last_run: '2026-04-14-shipped',
    shippable: true,
  },
  {
    slug: 'legacy-redirects',
    title: 'Legacy URL Redirects',
    summary: '301 from /v1/* paths to current routes. Retired after v2 cutover.',
    status: 'retired',
    version: 5,
    created: '2025-11-20',
    updated: '2026-03-30',
    watcher: '@platform-team',
    depends_on: [],
    touches: [],
    evidence: [],
    constraints: [],
    shippable: false,
  },
];

// ─── Pending items ───────────────────────────────────────────────────────────
const PENDINGS = [
  {
    file: '2026-05-19-signup-flow-brand-feel.yaml',
    status: 'open',
    kind: 'human_evaluation',
    capability: 'signup-flow',
    item_id: 'brand-feel',
    watcher: '@growth',
    asked_at: '2026-05-19T16:21:00Z',
    ask: 'Walk through signup from a fresh email. Does it feel quick and reassuring? Any place where you felt unsure what would happen next?',
    verdict_options: ['yes', 'no', 'partial'],
  },
  {
    file: '2026-05-20-oauth-google-consent-flow.yaml',
    status: 'open',
    kind: 'human_evaluation',
    capability: 'oauth-google',
    item_id: 'google-consent-flow',
    watcher: '@auth-team',
    asked_at: '2026-05-20T09:11:00Z',
    ask: 'Sign in with a fresh Google account. Does the consent screen feel official? Are the requested scopes obvious?',
    verdict_options: ['yes', 'no', 'partial'],
  },
  {
    file: '2026-05-20-rate-limit-abuse-protection-feel.yaml',
    status: 'open',
    kind: 'human_evaluation',
    capability: 'rate-limit',
    item_id: 'abuse-protection-feel',
    watcher: '@platform-team',
    asked_at: '2026-05-20T14:02:00Z',
    ask: 'Hit the API with a script that exceeds the limit. Does it back off cleanly? Is the Retry-After header respected by curl?',
    verdict_options: ['yes', 'no', 'partial'],
  },
  {
    file: '2026-05-17-email-notifications-unsubscribe-clarity.yaml',
    status: 'open',
    kind: 'human_evaluation',
    capability: 'email-notifications',
    item_id: 'unsubscribe-clarity',
    watcher: '@growth',
    asked_at: '2026-05-17T20:40:00Z',
    ask: 'Open the digest in Gmail, Apple Mail, and Outlook. Is the unsubscribe link obvious in each? One-click?',
    verdict_options: ['yes', 'no', 'partial'],
  },
  {
    file: '2026-05-18-usage-analytics-dau-growth.yaml',
    status: 'open',
    kind: 'escalation',
    capability: 'usage-analytics',
    item_id: 'dau-growth',
    watcher: '@data-team',
    escalated_at: '2026-05-18T12:00:00Z',
    reason: 'max_attempts exhausted (3/3) without meeting threshold',
    expect: '+10% QoQ',
    observed: '+2.1% QoQ over 3 weeks',
    attempts: [
      { run_id: '2026-04-29-aaa111', changed: 'added share-to-twitter button', observed: '+0.8% in 1 week' },
      { run_id: '2026-05-06-bbb222', changed: 'prominent CTA on homepage', observed: '+1.5% in 1 week' },
      { run_id: '2026-05-13-ccc333', changed: 'reduced redirect latency', observed: '+2.1% in 1 week' },
    ],
    ask: 'Three improvement loops tried — growth is positive but below +10% QoQ. Choose:\n1. Loosen target (e.g. +5% QoQ)\n2. Try a new approach (describe)\n3. Retire this target\n4. Accept current state as met',
  },
];

// ─── Workers (active claims under .i2e/worktrees/) ───────────────────────────
const WORKERS = [
  {
    id: 'w-7c1f2e',
    agent_id: '7c1f2e',
    session_id: 'sess-9b21',
    pid: 48211,
    tick_id: '2026-05-21-9f1c0e',
    capability: 'change-password',
    step: 'i2e-develop',
    started_at: '2026-05-21T11:38:14Z',
    progress: 'Editing src/auth/password.py — adding whitespace strip + length guard',
    worktree: '.i2e/worktrees/change-password/',
  },
  {
    id: 'w-a8d44b',
    agent_id: 'a8d44b',
    session_id: 'sess-9b21',
    pid: 48244,
    tick_id: '2026-05-21-9f1c0e',
    capability: 'dashboard-charts',
    step: 'i2e-develop',
    started_at: '2026-05-21T11:39:02Z',
    progress: 'Writing src/charts/renderer.tsx — d3 scale fns + axis labels',
    worktree: '.i2e/worktrees/dashboard-charts/',
    fanout_sibling: 'w-3b91f7',
  },
  {
    id: 'w-3b91f7',
    agent_id: '3b91f7',
    session_id: 'sess-9b21',
    pid: 48256,
    tick_id: '2026-05-21-9f1c0e',
    capability: 'dashboard-charts',
    step: 'i2e-develop',
    started_at: '2026-05-21T11:39:02Z',
    progress: 'Writing tests/charts/test_tooltip.py — hover position cases',
    worktree: '.i2e/worktrees/dashboard-charts/',
    fanout_sibling: 'w-a8d44b',
  },
];

// ─── Tick logs (most recent first) ───────────────────────────────────────────
const TICKS = [
  {
    tick_id: '2026-05-21-9f1c0e', ran_at: '2026-05-21T11:38:00Z', kind: 'batch',
    actions: ['plan_batch: 2 capabilities (disjoint touches)', 'claim: change-password', 'claim: dashboard-charts', 'dispatch: 3 sub-agents'],
    sub_actions: [
      { slug: 'change-password', step: 'develop', agent_id: '7c1f2e', outcome: 'running' },
      { slug: 'dashboard-charts', step: 'develop', agent_id: 'a8d44b', outcome: 'running' },
      { slug: 'dashboard-charts', step: 'develop', agent_id: '3b91f7', outcome: 'running' },
    ],
  },
  {
    tick_id: '2026-05-21-7e2d99', ran_at: '2026-05-21T10:14:00Z', kind: 'evidence',
    actions: ['ran_evidence: shorten-url (5 items)', 'verdict: all met/pass'],
    sub_actions: [
      { slug: 'shorten-url', step: 'evidence', agent_id: '7e2d99', outcome: 'all_green' },
    ],
  },
  {
    tick_id: '2026-05-20-b7e220', ran_at: '2026-05-20T15:02:00Z', kind: 'adapt',
    actions: ['ran_adapt: oauth-google / account-link-on-email', 'attempts: 5 -> 6', 'verdict: still fail', 'escalation: pending_written'],
    sub_actions: [
      { slug: 'oauth-google', step: 'adapt', agent_id: 'b7e220', outcome: 'escalated' },
    ],
  },
  {
    tick_id: '2026-05-20-7e2d11', ran_at: '2026-05-20T11:30:00Z', kind: 'evidence',
    actions: ['ran_evidence: rate-limit (3 items)', 'verdict: 2 pass / 1 trending'],
    sub_actions: [{ slug: 'rate-limit', step: 'evidence', agent_id: '7e2d11', outcome: 'trending' }],
  },
  {
    tick_id: '2026-05-19-d44a01', ran_at: '2026-05-19T17:48:00Z', kind: 'develop',
    actions: ['ran_develop: signup-flow (intent v4 -> v5)', 'ran_evidence: signup-flow', 'verdict: brand-feel awaiting_human'],
    sub_actions: [{ slug: 'signup-flow', step: 'develop+evidence', agent_id: 'd44a01', outcome: 'awaiting_human' }],
  },
  {
    tick_id: '2026-05-19-a3f8c2', ran_at: '2026-05-19T14:32:00Z', kind: 'evidence',
    actions: ['ran_evidence: shorten-url (5 items)', 'verdict: shippable'],
    sub_actions: [{ slug: 'shorten-url', step: 'evidence', agent_id: 'a3f8c2', outcome: 'shippable' }],
  },
  {
    tick_id: '2026-05-18-c11000', ran_at: '2026-05-18T12:00:00Z', kind: 'adapt',
    actions: ['ran_adapt: usage-analytics / dau-growth', 'attempts: 3/3 exhausted', 'escalation: pending_written'],
    sub_actions: [{ slug: 'usage-analytics', step: 'adapt', agent_id: 'c11000', outcome: 'escalated' }],
  },
  {
    tick_id: '2026-05-17-aa5500', ran_at: '2026-05-17T20:40:00Z', kind: 'evidence',
    actions: ['ran_evidence: email-notifications (4 items)', 'verdict: unsubscribe-clarity awaiting_human'],
    sub_actions: [{ slug: 'email-notifications', step: 'evidence', agent_id: 'aa5500', outcome: 'awaiting_human' }],
  },
  {
    tick_id: '2026-05-16-pending-resolved', ran_at: '2026-05-16T09:14:00Z', kind: 'pending_applied',
    actions: ['applied_resolution: shorten-url / brand-feel', 'archived to logs/'],
    sub_actions: [{ slug: 'shorten-url', step: 'apply_resolution', agent_id: 'orch', outcome: 'resolved' }],
  },
  {
    tick_id: '2026-05-15-fresh', ran_at: '2026-05-15T08:00:00Z', kind: 'develop',
    actions: ['ran_develop: dashboard-charts (new intent v1)', 'ran_evidence: dashboard-charts'],
    sub_actions: [{ slug: 'dashboard-charts', step: 'develop+evidence', agent_id: 'fresh', outcome: 'partial' }],
  },
  {
    tick_id: '2026-05-14-shipped', ran_at: '2026-05-14T11:11:00Z', kind: 'auto_ship',
    actions: ['ran_evidence: markdown-editor', 'verdict: all green', 'promoted: active -> shipped'],
    sub_actions: [{ slug: 'markdown-editor', step: 'auto_promote', agent_id: 'orch', outcome: 'shipped' }],
  },
  {
    tick_id: '2026-04-14-shipped', ran_at: '2026-04-14T16:00:00Z', kind: 'auto_ship',
    actions: ['ran_evidence: dark-mode', 'verdict: all green', 'promoted: active -> shipped'],
    sub_actions: [{ slug: 'dark-mode', step: 'auto_promote', agent_id: 'orch', outcome: 'shipped' }],
  },
];

// ─── Derived helpers ─────────────────────────────────────────────────────────
function getPendingsForCapability(slug) {
  return PENDINGS.filter(p => p.capability === slug);
}
function getWorkersForCapability(slug) {
  return WORKERS.filter(w => w.capability === slug);
}
function countOpenPendings(slug) {
  return PENDINGS.filter(p => p.capability === slug && p.status === 'open').length;
}
function getCapability(slug) {
  return CAPABILITIES.find(c => c.slug === slug);
}
function formatRelativeTime(iso) {
  const then = new Date(iso);
  const diff = (NOW - then) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  const days = Math.floor(diff / 86400);
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return then.toISOString().slice(0, 10);
}

// ─── Profiles (watchers a developer can be) ──────────────────────────────────
// Individuals + the teams they belong to. A pending item assigned to @auth-team
// is "for you" if your profile is on the team. The console persists your active
// profile in localStorage under 'i2e.profile'.
const PROFILES = [
  { handle: '@ryan',  name: 'Ryan Turner',    teams: ['@platform-team', '@auth-team', '@growth'] },
  { handle: '@sam',   name: 'Sam Okafor',     teams: ['@auth-team', '@platform-team'] },
  { handle: '@priya', name: 'Priya Iyer',     teams: ['@frontend', '@design'] },
  { handle: '@diego', name: 'Diego Salas',    teams: ['@data-team', '@growth'] },
  { handle: '@alex',  name: 'Alex Wendel',    teams: ['@platform-team'] },
  { handle: '@maya',  name: 'Maya Chen',      teams: ['@design', '@frontend'] },
];

// Team-only profiles (so the watcher selector can also switch into a "team mailbox" view)
const TEAM_PROFILES = [
  { handle: '@platform-team', name: 'Platform team',  isTeam: true },
  { handle: '@auth-team',     name: 'Auth team',      isTeam: true },
  { handle: '@growth',        name: 'Growth team',    isTeam: true },
  { handle: '@data-team',     name: 'Data team',      isTeam: true },
  { handle: '@design',        name: 'Design team',    isTeam: true },
  { handle: '@frontend',      name: 'Frontend team',  isTeam: true },
];

function getProfile(handle) {
  return PROFILES.find(p => p.handle === handle) || TEAM_PROFILES.find(p => p.handle === handle);
}

// Does this watcher value (e.g. "@auth-team" on a pending) belong to my profile?
function isMine(watcher, myHandle) {
  if (!myHandle || !watcher) return false;
  if (watcher === myHandle) return true;
  const me = getProfile(myHandle);
  if (!me) return false;
  if (me.teams && me.teams.includes(watcher)) return true;
  return false;
}

function initials(handle) {
  const p = getProfile(handle);
  if (!p) return handle.slice(1, 3).toUpperCase();
  const parts = p.name.split(' ');
  return (parts[0][0] + (parts[1]?.[0] || '')).toUpperCase();
}

Object.assign(window, {
  NOW, CAPABILITIES, PENDINGS, WORKERS, TICKS,
  PROFILES, TEAM_PROFILES, getProfile, isMine, initials,
  getPendingsForCapability, getWorkersForCapability, countOpenPendings,
  getCapability, formatRelativeTime,
});
