// dashboard.jsx — three layout variants for the home view.
// cockpit (grid), arc (IDEA-shaped), inbox (pending-first).

const { useState: useStateDash, useMemo: useMemoDash } = React;

// ─── Top notification strip — "what needs me?" ──────────────────────────────
function NeedsYou({ profile, onGoToPending, onSelectIntent }) {
  const open = PENDINGS.filter(p => p.status === 'open');
  const mine = open.filter(p => isMine(p.watcher, profile));
  const others = open.filter(p => !isMine(p.watcher, profile));
  if (open.length === 0) return null;
  const me = getProfile(profile);

  return (
    <div style={{
      background: '#e8e0ff',
      borderRadius: 6,
      padding: '14px 18px',
      display: 'flex',
      alignItems: 'center',
      gap: 18,
      flexWrap: 'wrap',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <svg width="14" height="14" viewBox="0 0 16 16">
          <path d="M8 2 L8 9 M8 12 L8 13" stroke="#3d2a72" strokeWidth="1.8" strokeLinecap="round"/>
        </svg>
        <span style={{
          fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase',
          color: '#3d2a72',
        }}>
          {mine.length > 0
            ? <>{mine.length} {mine.length === 1 ? 'item needs' : 'items need'} you</>
            : <>{open.length} {open.length === 1 ? 'item needs' : 'items need'} attention</>}
        </span>
        {me && mine.length > 0 && (
          <Mono faded style={{ fontSize: 11, color: '#3d2a72', opacity: 0.7 }}>as {me.handle}</Mono>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8, flex: 1, flexWrap: 'wrap' }}>
        {mine.length > 0 && (
          <button onClick={onGoToPending} style={{
            background: '#3d2a72', border: 'none',
            borderRadius: 9999, padding: '4px 14px',
            fontFamily: 'inherit', fontSize: 11, fontWeight: 600,
            color: '#fff', cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 6,
          }}>
            <span>For you</span>
            <span style={{ fontWeight: 700 }}>{mine.length}</span>
          </button>
        )}
        {others.length > 0 && (
          <button onClick={onGoToPending} style={{
            background: 'rgba(255,255,255,0.6)', border: 'none',
            borderRadius: 9999, padding: '4px 14px',
            fontFamily: 'inherit', fontSize: 11, fontWeight: 600,
            color: '#3d2a72', cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 6,
          }}>
            <span>Others</span>
            <span style={{ fontWeight: 700 }}>{others.length}</span>
          </button>
        )}
      </div>
      <Button variant="primary" size="sm" onClick={onGoToPending}>Open inbox</Button>
    </div>
  );
}

// ─── Shippability strip — quick overview of all active capabilities ─────────
function ShippabilityStrip({ onSelectIntent }) {
  const active = CAPABILITIES.filter(c => c.status === 'active');
  return (
    <Card padding={24}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 16 }}>
        <H2>Shippability — active capabilities</H2>
        <Mono faded style={{ fontSize: 11 }}>{active.filter(c => c.shippable).length} / {active.length} green</Mono>
      </div>
      <div style={{ display: 'flex', gap: 4, height: 32, marginBottom: 16, borderRadius: 4, overflow: 'hidden' }}>
        {active.map(c => {
          const allItems = [...c.evidence, ...c.constraints];
          const hasFail = allItems.some(i => i.verdict === 'fail' || i.verdict === 'unmet');
          const hasAwaiting = allItems.some(i => i.verdict === 'awaiting_human');
          const hasTrending = allItems.some(i => i.verdict === 'trending');
          let color = 'oklch(0.62 0.07 152)';  // green
          if (hasFail) color = '#ef4444';
          else if (hasAwaiting) color = '#7a5cb8';
          else if (hasTrending) color = 'oklch(0.72 0.10 75)';
          return (
            <div
              key={c.slug}
              onClick={() => onSelectIntent(c.slug)}
              title={c.slug}
              style={{ flex: 1, background: color, cursor: 'pointer', position: 'relative', minWidth: 4 }}
            />
          );
        })}
      </div>
      <div style={{
        display: 'flex', gap: 18, fontSize: 11, color: '#5f5f5f',
      }}>
        <Legend color="oklch(0.62 0.07 152)" label="all green" />
        <Legend color="#7a5cb8" label="awaiting human" />
        <Legend color="oklch(0.72 0.10 75)" label="trending" />
        <Legend color="#ef4444" label="failing" />
      </div>
    </Card>
  );
}
function Legend({ color, label }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
      <span>{label}</span>
    </span>
  );
}

// ─── Workers compact strip ──────────────────────────────────────────────────
function WorkersStrip({ onGoToWorkers }) {
  return (
    <Card padding={24}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <PulseDot size={8}/>
          <H2>In flight · {WORKERS.length} parallel</H2>
        </div>
        <button onClick={onGoToWorkers} style={{
          background: 'transparent', border: 'none',
          color: '#272727', fontSize: 11, fontWeight: 600, letterSpacing: 1,
          textTransform: 'uppercase', cursor: 'pointer',
        }}>Details →</button>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {WORKERS.map(w => (
          <WorkerRow key={w.id} w={w}/>
        ))}
      </div>
    </Card>
  );
}

function WorkerRow({ w, compact = false }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '14px 110px 1fr auto',
      gap: 12,
      alignItems: 'center',
      padding: '8px 12px',
      borderRadius: 6,
      background: '#fafafa',
    }}>
      <PulseDot size={8}/>
      <Mono style={{ fontSize: 11 }}>{w.capability}</Mono>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <Badge kind="default" style={{ background: '#272727', color: '#fff', fontSize: 9, letterSpacing: 1, textTransform: 'uppercase' }}>{w.step}</Badge>
        <Mono faded style={{ fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{w.progress}</Mono>
      </div>
      <Mono faded style={{ fontSize: 10 }}>{w.agent_id} · {formatRelativeTime(w.started_at)}</Mono>
    </div>
  );
}

// ─── Recent ticks ───────────────────────────────────────────────────────────
function RecentTicks({ limit = 6 }) {
  return (
    <Card padding={24}>
      <H2 style={{ marginBottom: 14 }}>Recent ticks</H2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {TICKS.slice(0, limit).map(t => <TickRow key={t.tick_id} tick={t} />)}
      </div>
    </Card>
  );
}

function TickRow({ tick }) {
  const phaseMap = {
    batch: 'develop', develop: 'develop', evidence: 'evidence',
    adapt: 'adapt', pending_applied: 'intent', auto_ship: 'adapt',
  };
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '24px 120px 1fr auto',
      gap: 12,
      alignItems: 'center',
      padding: '10px 8px',
      borderBottom: '1px solid #f0f0f0',
    }}>
      <PhasePill phase={phaseMap[tick.kind] || 'intent'} />
      <Mono style={{ fontSize: 11 }}>{tick.tick_id.slice(-6)}</Mono>
      <div style={{ fontSize: 12, color: '#5f5f5f', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {tick.actions[0]}
        {tick.actions.length > 1 && (
          <span style={{ color: '#999' }}> +{tick.actions.length - 1} more</span>
        )}
      </div>
      <Mono faded style={{ fontSize: 11 }}>{formatRelativeTime(tick.ran_at)}</Mono>
    </div>
  );
}

// ─── Capability cards section ───────────────────────────────────────────────
function CapabilityGrid({ onSelectIntent, status = 'active' }) {
  const items = CAPABILITIES.filter(c => c.status === status);
  if (items.length === 0) return null;
  const titles = { active: 'Active capabilities', draft: 'Drafts', shipped: 'Shipped', retired: 'Retired' };
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 16 }}>
        <Eyebrow>{titles[status]}</Eyebrow>
        <span style={{ fontSize: 11, color: '#999' }}>· {items.length}</span>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: 16,
      }}>
        {items.map(c => <CapabilityCard key={c.slug} cap={c} onClick={() => onSelectIntent(c.slug)}/>)}
      </div>
    </div>
  );
}

function CapabilityCard({ cap, onClick }) {
  const [hover, setHover] = useStateDash(false);
  const allItems = [...(cap.evidence || []), ...(cap.constraints || [])];
  const counts = { pass: 0, fail: 0, trending: 0, awaiting: 0, none: 0 };
  allItems.forEach(i => {
    if (i.verdict === 'pass' || i.verdict === 'met') counts.pass++;
    else if (i.verdict === 'fail' || i.verdict === 'unmet') counts.fail++;
    else if (i.verdict === 'trending') counts.trending++;
    else if (i.verdict === 'awaiting_human') counts.awaiting++;
    else counts.none++;
  });
  const pendings = countOpenPendings(cap.slug);
  const workers = getWorkersForCapability(cap.slug);

  return (
    <Card
      padding={20}
      onClick={onClick}
      style={{
        transition: 'transform 120ms, box-shadow 120ms',
        transform: hover ? 'translateY(-1px)' : 'none',
        boxShadow: hover ? '0 4px 50px rgba(0,0,0,0.10)' : '0 2px 40px rgba(0,0,0,0.07)',
      }}
    >
      <div
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 6 }}>
          <Mono style={{ fontSize: 13, fontWeight: 600 }}>{cap.slug}</Mono>
          <StatusBadge status={cap.status}/>
        </div>
        <div style={{ fontSize: 13, color: '#5f5f5f', minHeight: 38, marginBottom: 12, lineHeight: 1.4 }}>
          {cap.title}
        </div>

        {/* Evidence bar */}
        <div style={{ display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', marginBottom: 10, background: '#f5f5f5' }}>
          {counts.pass > 0 && <div style={{ flex: counts.pass, background: 'oklch(0.62 0.07 152)' }}/>}
          {counts.trending > 0 && <div style={{ flex: counts.trending, background: 'oklch(0.72 0.10 75)' }}/>}
          {counts.awaiting > 0 && <div style={{ flex: counts.awaiting, background: '#7a5cb8' }}/>}
          {counts.fail > 0 && <div style={{ flex: counts.fail, background: '#ef4444' }}/>}
          {counts.none > 0 && <div style={{ flex: counts.none, background: '#e0e0e0' }}/>}
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
          fontSize: 11, color: '#999',
        }}>
          <span>{allItems.length} items</span>
          {counts.fail > 0 && <span style={{ color: '#8a1f1f' }}>· {counts.fail} fail</span>}
          {counts.trending > 0 && <span style={{ color: 'oklch(0.38 0.07 75)' }}>· {counts.trending} trending</span>}
          {counts.awaiting > 0 && <span style={{ color: '#3d2a72' }}>· {counts.awaiting} awaiting</span>}
          {cap.shippable && <span style={{ color: 'oklch(0.32 0.05 152)', fontWeight: 600 }}>· shippable</span>}
          <span style={{ marginLeft: 'auto' }}>{cap.updated ? formatRelativeTime(cap.updated + 'T00:00:00Z') : '—'}</span>
        </div>

        {/* Footer line: worker / pending hints */}
        {(workers.length > 0 || pendings > 0) && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            marginTop: 12, paddingTop: 12, borderTop: '1px solid #f0f0f0',
          }}>
            {workers.length > 0 && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#5f5f5f' }}>
                <PulseDot size={6}/> {workers.length} worker{workers.length > 1 ? 's' : ''}
              </span>
            )}
            {pendings > 0 && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#3d2a72' }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#7a5cb8' }}/>
                {pendings} pending
              </span>
            )}
            {cap.watcher && (
              <span style={{ marginLeft: 'auto', fontSize: 11, color: '#999' }}>{cap.watcher}</span>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

// ─── Layout: COCKPIT (default) — grid of operator surfaces ──────────────────
function CockpitDashboard({ profile, onSelectIntent, onGoToPending, onGoToWorkers }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <NeedsYou profile={profile} onGoToPending={onGoToPending} onSelectIntent={onSelectIntent}/>

      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 20 }}>
        <ShippabilityStrip onSelectIntent={onSelectIntent}/>
        <WorkersStrip onGoToWorkers={onGoToWorkers}/>
      </div>

      <CapabilityGrid status="active" onSelectIntent={onSelectIntent}/>
      <CapabilityGrid status="draft"   onSelectIntent={onSelectIntent}/>
      <CapabilityGrid status="shipped" onSelectIntent={onSelectIntent}/>

      <RecentTicks limit={6}/>
    </div>
  );
}

// ─── Layout: ARC — IDEA-shaped flow ─────────────────────────────────────────
function ArcDashboard({ profile, onSelectIntent, onGoToPending, onGoToWorkers }) {
  const intentCount   = CAPABILITIES.filter(c => c.status === 'draft' || c.status === 'active').length;
  const developCount  = WORKERS.length;
  const evidenceCount = CAPABILITIES.reduce((n, c) => n + (c.evidence || []).filter(e => e.verdict === 'pass' || e.verdict === 'met').length, 0);
  const adaptCount    = PENDINGS.filter(p => p.status === 'open').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <NeedsYou profile={profile} onGoToPending={onGoToPending} onSelectIntent={onSelectIntent}/>

      {/* IDEA arc */}
      <Card padding={30}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 24 }}>
          <H2>The loop</H2>
          <Mono faded style={{ fontSize: 11 }}>Intent → Develop → Evidence → Adapt</Mono>
        </div>
        <div style={{ position: 'relative', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
          <ArcStation letter="I" name="Intent" count={intentCount} sub={`${CAPABILITIES.filter(c=>c.status==='draft').length} drafts · ${CAPABILITIES.filter(c=>c.status==='active').length} active`} onClick={() => onSelectIntent(CAPABILITIES[0].slug)}/>
          <ArcStation letter="D" name="Develop" count={developCount} sub={`${WORKERS.length} workers running`} active onClick={onGoToWorkers}/>
          <ArcStation letter="E" name="Evidence" count={evidenceCount} sub={`green verdicts`} />
          <ArcStation letter="A" name="Adapt" count={adaptCount} sub={`${adaptCount} pending humans`} onClick={onGoToPending}/>
        </div>
        {/* Connector arrows under the stations */}
        <div style={{ marginTop: 12, height: 14, position: 'relative' }}>
          <svg width="100%" height="14" preserveAspectRatio="none" viewBox="0 0 400 14">
            <path d="M 50 7 C 100 14, 100 14, 150 7" stroke="#e0e0e0" strokeWidth="1.5" fill="none"/>
            <path d="M 150 7 C 200 14, 200 14, 250 7" stroke="#e0e0e0" strokeWidth="1.5" fill="none"/>
            <path d="M 250 7 C 300 14, 300 14, 350 7" stroke="#e0e0e0" strokeWidth="1.5" fill="none"/>
            <path d="M 350 7 C 380 14, 380 0, 380 0 L 50 0 C 50 0, 20 0, 20 7 L 50 7" stroke="#e0e0e0" strokeWidth="1.5" fill="none" strokeDasharray="3 3"/>
          </svg>
        </div>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 20 }}>
        <ShippabilityStrip onSelectIntent={onSelectIntent}/>
        <WorkersStrip onGoToWorkers={onGoToWorkers}/>
      </div>

      <CapabilityGrid status="active" onSelectIntent={onSelectIntent}/>
      <CapabilityGrid status="draft"   onSelectIntent={onSelectIntent}/>
      <CapabilityGrid status="shipped" onSelectIntent={onSelectIntent}/>

      <RecentTicks limit={6}/>
    </div>
  );
}

function ArcStation({ letter, name, count, sub, active, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        textAlign: 'center', padding: '20px 14px', borderRadius: 6,
        background: active ? '#272727' : '#fafafa',
        color: active ? '#fff' : '#333',
        cursor: onClick ? 'pointer' : 'default',
        position: 'relative',
      }}
    >
      <div style={{
        width: 36, height: 36, borderRadius: 8,
        background: active ? '#3a3a3a' : '#272727',
        color: '#fff',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: 18, fontWeight: 700,
        marginBottom: 10,
      }}>{letter}</div>
      <div style={{ fontSize: 11, letterSpacing: 2, textTransform: 'uppercase', fontWeight: 600, marginBottom: 6 }}>{name}</div>
      <div style={{ fontSize: 28, fontWeight: 700, lineHeight: 1, marginBottom: 4 }}>{count}</div>
      <div style={{ fontSize: 11, opacity: 0.7 }}>{sub}</div>
      {active && (
        <div style={{ position: 'absolute', top: 10, right: 10 }}>
          <PulseDot color="#fff" size={6}/>
        </div>
      )}
    </div>
  );
}

// ─── Layout: INBOX — pending-first ──────────────────────────────────────────
function InboxDashboard({ profile, onSelectIntent, onGoToPending, onGoToWorkers, onResolvePending }) {
  const open = PENDINGS.filter(p => p.status === 'open');
  const mine = open.filter(p => isMine(p.watcher, profile));
  const display = mine.length > 0 ? mine : open;
  const showingForYou = mine.length > 0;
  const me = getProfile(profile);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <Card padding={30}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <Eyebrow style={{ marginBottom: 4 }}>{showingForYou ? `Inbox · ${me?.handle || 'you'}` : 'Inbox · all watchers'}</Eyebrow>
            <H1>{display.length} {display.length === 1 ? 'item needs' : 'items need'} {showingForYou ? 'you' : 'a human'}</H1>
          </div>
          <Mono faded style={{ fontSize: 11 }}>{showingForYou ? `${open.length - mine.length} more for others` : `across ${new Set(open.map(p => p.watcher)).size} watchers`}</Mono>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {display.slice(0, 5).map(p => (
            <InboxRow key={p.file} p={p}
              onClick={() => { onSelectIntent(p.capability); }}
              onResolve={onResolvePending}
            />
          ))}
        </div>
        {display.length > 5 && (
          <div style={{ marginTop: 14, textAlign: 'center' }}>
            <Button variant="ghost" onClick={onGoToPending}>See all {display.length} →</Button>
          </div>
        )}
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <WorkersStrip onGoToWorkers={onGoToWorkers}/>
        <RecentTicks limit={5}/>
      </div>

      <ShippabilityStrip onSelectIntent={onSelectIntent}/>

      <CapabilityGrid status="active" onSelectIntent={onSelectIntent}/>
    </div>
  );
}

function InboxRow({ p, onClick, onResolve }) {
  const [hover, setHover] = useStateDash(false);
  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'grid',
        gridTemplateColumns: '12px 160px 1fr auto',
        gap: 14, alignItems: 'center',
        padding: '12px 14px',
        background: hover ? '#fafafa' : '#fff',
        border: '1px solid #f0f0f0',
        borderRadius: 6,
        cursor: 'pointer',
      }}
      onClick={onClick}
    >
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.kind === 'escalation' ? '#ef4444' : '#7a5cb8' }} />
      <div>
        <Mono style={{ fontSize: 12, fontWeight: 600 }}>{p.capability}</Mono>
        <Mono faded style={{ fontSize: 11, display: 'block' }}>{p.item_id}</Mono>
      </div>
      <div style={{
        fontSize: 13, color: '#5f5f5f', lineHeight: 1.5,
        overflow: 'hidden', textOverflow: 'ellipsis',
        display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
      }}>
        {p.ask.split('\n')[0]}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-end' }}>
        <Badge kind={p.kind === 'escalation' ? 'fail' : 'awaiting_human'} style={{ textTransform: 'uppercase', letterSpacing: 1, fontSize: 9 }}>
          {p.kind === 'escalation' ? 'escalation' : 'needs eval'}
        </Badge>
        <Mono faded style={{ fontSize: 10 }}>{p.watcher} · {formatRelativeTime(p.asked_at || p.escalated_at)}</Mono>
      </div>
    </div>
  );
}

// ─── Dashboard root — picks layout by tweak ─────────────────────────────────
function DashboardView({ layout, profile, onSelectIntent, onGoToPending, onGoToWorkers, onResolvePending }) {
  if (layout === 'arc') return <ArcDashboard profile={profile} onSelectIntent={onSelectIntent} onGoToPending={onGoToPending} onGoToWorkers={onGoToWorkers}/>;
  if (layout === 'inbox') return <InboxDashboard profile={profile} onSelectIntent={onSelectIntent} onGoToPending={onGoToPending} onGoToWorkers={onGoToWorkers} onResolvePending={onResolvePending}/>;
  return <CockpitDashboard profile={profile} onSelectIntent={onSelectIntent} onGoToPending={onGoToPending} onGoToWorkers={onGoToWorkers}/>;
}

Object.assign(window, { DashboardView, NeedsYou, CapabilityCard, WorkerRow, TickRow });
