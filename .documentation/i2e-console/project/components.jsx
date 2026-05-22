// components.jsx — shared UI primitives for the i2e console.
// All colors and spacing rules come from DESIGN.md.

const { useState, useRef, useEffect, useMemo } = React;

// ─── Colors used outside the monochrome ladder ───────────────────────────────
// Reused: design system mention-lilac doubles as "awaiting human attention".
const VERDICT = {
  pass:           { dot: 'oklch(0.62 0.07 152)', bg: 'oklch(0.96 0.025 152)', fg: 'oklch(0.32 0.05 152)', label: 'pass' },
  met:            { dot: 'oklch(0.62 0.07 152)', bg: 'oklch(0.96 0.025 152)', fg: 'oklch(0.32 0.05 152)', label: 'met' },
  fail:           { dot: '#ef4444',              bg: '#fee9e9',              fg: '#8a1f1f',              label: 'fail' },
  unmet:          { dot: '#ef4444',              bg: '#fee9e9',              fg: '#8a1f1f',              label: 'unmet' },
  trending:       { dot: 'oklch(0.72 0.10 75)',  bg: 'oklch(0.95 0.04 75)',  fg: 'oklch(0.38 0.07 75)',  label: 'trending' },
  awaiting_human: { dot: '#7a5cb8',              bg: '#e8e0ff',              fg: '#3d2a72',              label: 'awaiting human' },
  awaiting_first_run: { dot: '#999',             bg: '#f0f0f0',              fg: '#5f5f5f',              label: 'no data yet' },
  running:        { dot: '#7a5cb8',              bg: '#e8e0ff',              fg: '#3d2a72',              label: 'running' },
};

const STATUS = {
  draft:    { dot: '#999',                       bg: '#f0f0f0',              fg: '#5f5f5f',              label: 'draft' },
  active:   { dot: '#272727',                    bg: '#272727',              fg: '#fff',                 label: 'active' },
  shipped:  { dot: 'oklch(0.55 0.09 240)',       bg: 'oklch(0.96 0.025 240)',fg: 'oklch(0.32 0.07 240)', label: 'shipped' },
  retired:  { dot: '#cccccc',                    bg: '#f5f5f5',              fg: '#999',                 label: 'retired' },
};

// ─── StatusDot — small colored dot, used in lists ───────────────────────────
function StatusDot({ kind, size = 8 }) {
  const c = VERDICT[kind] || STATUS[kind] || { dot: '#999' };
  return (
    <span style={{
      display: 'inline-block', width: size, height: size, borderRadius: '50%',
      background: c.dot, flexShrink: 0,
    }} />
  );
}

// ─── Badge — pill, follows DESIGN.md ─────────────────────────────────────────
function Badge({ children, kind = 'default', style = {} }) {
  const palettes = { ...VERDICT, ...STATUS, default: { bg: '#272727', fg: '#fff' } };
  const c = palettes[kind] || palettes.default;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '2px 8px', borderRadius: 9999,
      background: c.bg, color: c.fg,
      fontSize: 10, fontWeight: 600, letterSpacing: 0,
      whiteSpace: 'nowrap',
      ...style,
    }}>
      {children}
    </span>
  );
}

// ─── VerdictBadge — pre-fills label from verdict key ─────────────────────────
function VerdictBadge({ verdict }) {
  if (!verdict) return <Badge kind="default" style={{ background: '#f0f0f0', color: '#999' }}>no data</Badge>;
  const c = VERDICT[verdict];
  if (!c) return <Badge>{verdict}</Badge>;
  return (
    <Badge kind={verdict}>
      <StatusDot kind={verdict} size={6} />
      {c.label}
    </Badge>
  );
}

// ─── StatusBadge — for capability status ─────────────────────────────────────
function StatusBadge({ status }) {
  return <Badge kind={status} style={{ textTransform: 'uppercase', letterSpacing: 1, fontSize: 9 }}>{STATUS[status]?.label || status}</Badge>;
}

// ─── Card — the signature white card with soft shadow ────────────────────────
function Card({ children, style = {}, padding = 30, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: '#ffffff',
        borderRadius: 6,
        padding,
        boxShadow: '0 2px 40px rgba(0,0,0,0.07)',
        cursor: onClick ? 'pointer' : 'default',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ─── Code / Mono chip — slugs, paths, queries, run-ids ───────────────────────
function Mono({ children, style = {}, faded = false }) {
  return (
    <span style={{
      fontFamily: '"JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace',
      fontSize: 12,
      color: faded ? '#999' : '#333',
      ...style,
    }}>{children}</span>
  );
}

function CodeChip({ children, style = {} }) {
  return (
    <span style={{
      fontFamily: '"JetBrains Mono", ui-monospace, Menlo, monospace',
      fontSize: 11,
      padding: '2px 6px',
      borderRadius: 4,
      background: '#f5f5f5',
      color: '#333',
      whiteSpace: 'nowrap',
      ...style,
    }}>{children}</span>
  );
}

// ─── Eyebrow — uppercase 11px tracked label ──────────────────────────────────
function Eyebrow({ children, style = {} }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, letterSpacing: 1,
      textTransform: 'uppercase', color: '#999',
      ...style,
    }}>{children}</div>
  );
}

// ─── Section heading ─────────────────────────────────────────────────────────
function H1({ children, style = {} }) {
  return <h1 style={{ fontSize: 24, fontWeight: 700, color: '#333', margin: 0, lineHeight: 1.3, ...style }}>{children}</h1>;
}
function H2({ children, style = {} }) {
  return <h2 style={{ fontSize: 16, fontWeight: 600, color: '#333', margin: 0, lineHeight: 1.4, ...style }}>{children}</h2>;
}

// ─── Button — primary uppercase ──────────────────────────────────────────────
function Button({ children, variant = 'primary', size = 'md', onClick, disabled, style = {} }) {
  const [hover, setHover] = useState(false);
  const sizes = {
    sm: { padding: '8px 14px 6px', fontSize: 10 },
    md: { padding: '11px 18px 9px', fontSize: 11 },
    lg: { padding: '15px 24px 12px', fontSize: 11 },
  };
  const palettes = {
    primary: {
      bg: hover ? '#3a3a3a' : '#272727', fg: '#fff', border: 'none',
    },
    outline: {
      bg: hover ? '#272727' : 'transparent', fg: hover ? '#fff' : '#272727',
      border: '1px solid #272727',
    },
    secondary: {
      bg: hover ? '#e0e0e0' : '#efefef', fg: '#333', border: 'none',
    },
    ghost: {
      bg: hover ? '#f5f5f5' : 'transparent', fg: '#333', border: 'none',
    },
  };
  const p = palettes[variant];
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      disabled={disabled}
      style={{
        ...sizes[size],
        background: p.bg, color: p.fg, border: p.border,
        borderRadius: 6,
        fontFamily: 'inherit',
        fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        transition: 'background 120ms, color 120ms',
        ...style,
      }}
    >
      {children}
    </button>
  );
}

// ─── ProviderIcon — tiny inline svg per provider ────────────────────────────
function ProviderIcon({ name, size = 12 }) {
  const c = '#5f5f5f';
  const icons = {
    pytest:  <svg width={size} height={size} viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="none" stroke={c} strokeWidth="1.5"/><path d="M5 8l2 2 4-4" stroke={c} strokeWidth="1.5" fill="none" strokeLinecap="round"/></svg>,
    datadog: <svg width={size} height={size} viewBox="0 0 16 16"><path d="M2 12 L5 7 L8 10 L11 5 L14 12" stroke={c} strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>,
    sentry:  <svg width={size} height={size} viewBox="0 0 16 16"><path d="M8 3 L13 12 L10 12 M3 12 L6 12" stroke={c} strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/><circle cx="8" cy="9" r="1" fill={c}/></svg>,
    ga:      <svg width={size} height={size} viewBox="0 0 16 16"><rect x="3" y="9" width="2" height="5" fill={c}/><rect x="7" y="5" width="2" height="9" fill={c}/><rect x="11" y="2" width="2" height="12" fill={c}/></svg>,
    human:   <svg width={size} height={size} viewBox="0 0 16 16"><circle cx="8" cy="5" r="2" stroke={c} strokeWidth="1.5" fill="none"/><path d="M3 13 C3 10 5 9 8 9 C11 9 13 10 13 13" stroke={c} strokeWidth="1.5" fill="none" strokeLinecap="round"/></svg>,
    survey:  <svg width={size} height={size} viewBox="0 0 16 16"><rect x="3" y="3" width="10" height="10" stroke={c} strokeWidth="1.5" fill="none" rx="1"/><path d="M5 7 L8 9 L11 5" stroke={c} strokeWidth="1.5" fill="none" strokeLinecap="round"/></svg>,
  };
  return icons[name] || <svg width={size} height={size} viewBox="0 0 16 16"><circle cx="8" cy="8" r="2" fill={c}/></svg>;
}

// ─── TypeBadge — case / target / constraint distinction ─────────────────────
function TypeBadge({ type }) {
  const palettes = {
    case:       { bg: '#f5f5f5', fg: '#333',  label: 'CASE'       },
    target:     { bg: '#fafafa', fg: '#5f5f5f', label: 'TARGET'   },
    constraint: { bg: '#fafafa', fg: '#5f5f5f', label: 'CONSTRAINT' },
  };
  const p = palettes[type] || palettes.case;
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 6px',
      borderRadius: 4,
      background: p.bg, color: p.fg,
      fontSize: 9, fontWeight: 600, letterSpacing: 1,
      border: type === 'case' ? '1px solid #e0e0e0' : '1px solid #e5e5e5',
    }}>{p.label}</span>
  );
}

// ─── EffortPip — visual representation of effort budget ─────────────────────
function EffortPip({ effort, attemptsUsed = 0 }) {
  const max = { lazy: 0, low: 3, medium: 6, high: 10 }[effort] || 0;
  if (max === 0) {
    return (
      <span style={{ fontSize: 10, color: '#999', letterSpacing: 1, fontWeight: 600 }}>LAZY</span>
    );
  }
  return (
    <span style={{ display: 'inline-flex', gap: 2, alignItems: 'center' }}>
      <span style={{ fontSize: 10, color: '#999', marginRight: 4, letterSpacing: 0.5 }}>
        {attemptsUsed}/{max}
      </span>
      {Array.from({ length: max }).map((_, i) => (
        <span key={i} style={{
          width: 4, height: 8, borderRadius: 1,
          background: i < attemptsUsed ? (attemptsUsed >= max ? '#ef4444' : '#272727') : '#e5e5e5',
        }} />
      ))}
    </span>
  );
}

// ─── PulseDot — for live/in-flight workers ──────────────────────────────────
function PulseDot({ color = '#7a5cb8', size = 8 }) {
  return (
    <span style={{ position: 'relative', display: 'inline-block', width: size, height: size }}>
      <span style={{
        position: 'absolute', inset: 0, borderRadius: '50%',
        background: color, opacity: 0.4,
        animation: 'i2ePulse 1.6s ease-out infinite',
      }} />
      <span style={{
        position: 'absolute', inset: 0, borderRadius: '50%',
        background: color,
      }} />
    </span>
  );
}

// ─── IDEA phase pill — for ticks and visual indicators ──────────────────────
function PhasePill({ phase }) {
  const colors = {
    intent:   { letter: 'I', bg: '#f0f0f0', fg: '#333' },
    develop:  { letter: 'D', bg: '#272727', fg: '#fff' },
    evidence: { letter: 'E', bg: '#f0f0f0', fg: '#333' },
    adapt:    { letter: 'A', bg: '#f0f0f0', fg: '#333' },
  };
  const c = colors[phase] || colors.intent;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 20, height: 20, borderRadius: 4,
      background: c.bg, color: c.fg,
      fontFamily: '"JetBrains Mono", monospace',
      fontSize: 11, fontWeight: 700,
    }}>{c.letter}</span>
  );
}

// ─── Empty state ─────────────────────────────────────────────────────────────
function EmptyState({ title, subtitle }) {
  return (
    <div style={{ padding: '60px 30px', textAlign: 'center', color: '#999' }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: '#5f5f5f', marginBottom: 6 }}>{title}</div>
      {subtitle && <div style={{ fontSize: 13 }}>{subtitle}</div>}
    </div>
  );
}

Object.assign(window, {
  VERDICT, STATUS,
  StatusDot, Badge, VerdictBadge, StatusBadge,
  Card, Mono, CodeChip, Eyebrow, H1, H2, Button,
  ProviderIcon, TypeBadge, EffortPip, PulseDot, PhasePill, EmptyState,
});
