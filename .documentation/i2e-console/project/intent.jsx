// intent.jsx — single capability detail view.
// Two layouts via tweaks: 'single' (stacked) and 'split' (evidence right-rail).

const { useState: useStateInt, useMemo: useMemoInt } = React;

// ─── Source-file viewer ─────────────────────────────────────────────────────
function IntentSourceBlock({ cap }) {
  // Reconstruct a faithful intent file from the data.
  const head = [
    `---`,
    `capability: ${cap.slug}`,
    `created: ${cap.created}`,
    `updated: ${cap.updated}`,
    `version: ${cap.version}`,
    `status: ${cap.status}`,
    `watcher: '${cap.watcher}'`,
    cap.depends_on?.length ? `depends_on: [${cap.depends_on.map(d => `'${d}'`).join(', ')}]` : `depends_on: []`,
    cap.touches?.length ? `touches: [${cap.touches.map(t => `'${t}'`).join(', ')}]` : null,
    cap.spec ? `spec: ${cap.spec}` : null,
    cap.spec_section != null ? `spec_section: ${cap.spec_section}` : null,
    `---`,
  ].filter(Boolean);

  return (
    <Card padding={0} style={{ overflow: 'hidden' }}>
      <div style={{
        padding: '12px 18px',
        background: '#fafafa',
        borderBottom: '1px solid #f0f0f0',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <svg width="14" height="14" viewBox="0 0 16 16">
          <path d="M4 2 L11 2 L13 4 L13 14 L4 14 Z" stroke="#5f5f5f" strokeWidth="1.3" fill="none"/>
          <path d="M6 7 L11 7 M6 10 L11 10" stroke="#5f5f5f" strokeWidth="1.3" strokeLinecap="round"/>
        </svg>
        <Mono style={{ fontSize: 12 }}>.i2e/intents/{cap.slug}.md</Mono>
        <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 8 }}>
          <Mono faded style={{ fontSize: 11 }}>v{cap.version}</Mono>
        </span>
      </div>
      <pre style={{
        margin: 0, padding: '16px 20px',
        background: '#fff',
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: 12, lineHeight: 1.7,
        color: '#333', overflow: 'auto', maxHeight: 360,
      }}>
{head.join('\n')}{'\n\n'}
<span style={{ color: '#7a5cb8' }}># {cap.title}</span>{'\n\n'}
{cap.summary}{'\n\n'}
<span style={{ color: '#7a5cb8' }}>## Evidence of success</span>{'\n'}
{cap.evidence.map((e,i) => (
  <span key={i}>{'\n'}
    <span style={{ color: '#999' }}>- </span>id: <span style={{ color: '#5f5f5f' }}>{e.id}</span>{'\n'}
    <span style={{ color: '#999' }}>  </span>type: {e.type}{'\n'}
    <span style={{ color: '#999' }}>  </span>provider: {e.provider}{'\n'}
    <span style={{ color: '#999' }}>  </span>query: {e.query}{'\n'}
    <span style={{ color: '#999' }}>  </span>expect: {e.expect}{'\n'}
    {e.window && <>{'  '}window: {e.window}{'\n'}</>}
    <span style={{ color: '#999' }}>  </span>effort: {e.effort}{'\n'}
  </span>
))}
{cap.constraints && cap.constraints.length > 0 && <>
  {'\n'}<span style={{ color: '#7a5cb8' }}>## Constraints</span>{'\n'}
  {cap.constraints.map((e,i) => (
    <span key={i}>{'\n'}
      <span style={{ color: '#999' }}>- </span>id: <span style={{ color: '#5f5f5f' }}>{e.id}</span>{'\n'}
      <span style={{ color: '#999' }}>  </span>provider: {e.provider}{'\n'}
      <span style={{ color: '#999' }}>  </span>query: {e.query}{'\n'}
      <span style={{ color: '#999' }}>  </span>expect: {e.expect}{'\n'}
      <span style={{ color: '#999' }}>  </span>effort: {e.effort}{'\n'}
    </span>
  ))}
</>}
      </pre>
    </Card>
  );
}

// ─── Evidence item row ──────────────────────────────────────────────────────
function EvidenceRow({ item, isConstraint, onResolvePending }) {
  const [expanded, setExpanded] = useStateInt(false);
  const verdict = item.verdict;
  return (
    <div style={{
      borderTop: '1px solid #f0f0f0',
      padding: '14px 20px',
      cursor: 'pointer',
      background: '#fff',
      transition: 'background 100ms',
    }}
      onMouseEnter={(e) => e.currentTarget.style.background = '#fafafa'}
      onMouseLeave={(e) => e.currentTarget.style.background = '#fff'}
      onClick={() => setExpanded(v => !v)}
    >
      <div style={{
        display: 'grid',
        gridTemplateColumns: '88px 1fr 100px 130px',
        gap: 14, alignItems: 'center',
      }}>
        <TypeBadge type={isConstraint ? 'constraint' : item.type}/>
        <div style={{ minWidth: 0 }}>
          <Mono style={{ fontSize: 12, fontWeight: 600 }}>{item.id}</Mono>
          <div style={{ fontSize: 11, color: '#999', display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
            <ProviderIcon name={item.provider}/>
            <Mono faded style={{ fontSize: 11 }}>{item.provider}</Mono>
            <span style={{ marginLeft: 6 }}>·</span>
            <Mono faded style={{ fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.query}</Mono>
          </div>
        </div>
        <div>
          <EffortPip effort={item.effort} attemptsUsed={item.attempts_used || 0}/>
        </div>
        <div style={{ textAlign: 'right' }}>
          <VerdictBadge verdict={verdict}/>
          {item.value && <div style={{ fontSize: 11, color: '#5f5f5f', marginTop: 4 }}>{item.value}</div>}
        </div>
      </div>
      {expanded && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px dashed #f0f0f0', display: 'grid', gridTemplateColumns: '120px 1fr', gap: '10px 16px', fontSize: 12 }}>
          <Mono faded style={{ fontSize: 11 }}>expect</Mono>
          <Mono style={{ fontSize: 12 }}>{item.expect}</Mono>
          <Mono faded style={{ fontSize: 11 }}>query</Mono>
          <Mono style={{ fontSize: 12, wordBreak: 'break-all' }}>{item.query}</Mono>
          {item.window && <><Mono faded style={{ fontSize: 11 }}>window</Mono><Mono style={{ fontSize: 12 }}>{item.window}</Mono></>}
          {item.pending && <>
            <Mono faded style={{ fontSize: 11 }}>pending</Mono>
            <Mono style={{ fontSize: 12 }}>{item.pending}</Mono>
          </>}
          {item.resolved_by && <>
            <Mono faded style={{ fontSize: 11 }}>resolved by</Mono>
            <span style={{ fontSize: 12, color: '#333' }}>{item.resolved_by} · {formatRelativeTime(item.resolved_at)}</span>
          </>}
          {verdict === 'awaiting_human' && (
            <>
              <span />
              <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                <Button size="sm" variant="primary" onClick={(e) => { e.stopPropagation(); onResolvePending && onResolvePending(item.pending); }}>Resolve</Button>
                <Button size="sm" variant="ghost">Open in editor</Button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Evidence section ───────────────────────────────────────────────────────
function EvidenceSection({ cap, onResolvePending }) {
  return (
    <Card padding={0} style={{ overflow: 'hidden' }}>
      <div style={{ padding: '16px 20px 14px', borderBottom: '1px solid #f0f0f0' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <H2>Evidence of success</H2>
          <Mono faded style={{ fontSize: 11 }}>{cap.evidence.length} items</Mono>
        </div>
      </div>
      {cap.evidence.map(e => (
        <EvidenceRow key={e.id} item={e} onResolvePending={onResolvePending}/>
      ))}
      {cap.constraints && cap.constraints.length > 0 && (
        <>
          <div style={{ padding: '16px 20px 14px', borderTop: '6px solid #fafafa', background: '#fff' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
              <H2>Constraints</H2>
              <Mono faded style={{ fontSize: 11 }}>{cap.constraints.length} items</Mono>
            </div>
          </div>
          {cap.constraints.map(e => (
            <EvidenceRow key={e.id} item={e} isConstraint onResolvePending={onResolvePending}/>
          ))}
        </>
      )}
    </Card>
  );
}

// ─── Sidebar info card (used in split layout, or below header in single) ────
function IntentMeta({ cap, onUpdateStatus }) {
  const [statusHover, setStatusHover] = useStateInt(null);
  const validNext = {
    draft: ['active', 'retired'],
    active: ['shipped', 'retired'],
    shipped: ['active', 'retired'],
    retired: ['draft', 'active'],
  };
  const next = validNext[cap.status] || [];

  return (
    <Card padding={24}>
      <Eyebrow style={{ marginBottom: 14 }}>Status</Eyebrow>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <StatusBadge status={cap.status}/>
        {cap.shippable && <Badge kind="pass">shippable</Badge>}
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 24 }}>
        {next.map(s => (
          <button
            key={s}
            onClick={() => onUpdateStatus(cap.slug, s)}
            onMouseEnter={() => setStatusHover(s)}
            onMouseLeave={() => setStatusHover(null)}
            style={{
              background: statusHover === s ? '#272727' : 'transparent',
              color: statusHover === s ? '#fff' : '#272727',
              border: '1px solid #272727',
              padding: '6px 10px 4px',
              borderRadius: 6,
              fontFamily: 'inherit', fontSize: 10, fontWeight: 600,
              letterSpacing: 1, textTransform: 'uppercase',
              cursor: 'pointer',
            }}
          >→ {s}</button>
        ))}
      </div>

      <Eyebrow style={{ marginBottom: 8 }}>Owner</Eyebrow>
      <div style={{ fontSize: 13, color: '#333', marginBottom: 18 }}>{cap.watcher}</div>

      <Eyebrow style={{ marginBottom: 8 }}>Version</Eyebrow>
      <div style={{ fontSize: 13, color: '#333', marginBottom: 18, display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <Mono>v{cap.version}</Mono>
        <Mono faded style={{ fontSize: 11 }}>updated {cap.updated}</Mono>
      </div>

      {cap.depends_on && cap.depends_on.length > 0 && (
        <>
          <Eyebrow style={{ marginBottom: 8 }}>Depends on</Eyebrow>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 18 }}>
            {cap.depends_on.map(d => <CodeChip key={d}>{d}</CodeChip>)}
          </div>
        </>
      )}

      {cap.touches && cap.touches.length > 0 && (
        <>
          <Eyebrow style={{ marginBottom: 8 }}>Touches</Eyebrow>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 18 }}>
            {cap.touches.map(t => <CodeChip key={t} style={{ background: '#fafafa', border: '1px solid #f0f0f0' }}>{t}</CodeChip>)}
          </div>
        </>
      )}

      {cap.spec && (
        <>
          <Eyebrow style={{ marginBottom: 8 }}>Source spec</Eyebrow>
          <Mono style={{ fontSize: 12 }}>.i2e/specs/{cap.spec}.md §{cap.spec_section}</Mono>
        </>
      )}
    </Card>
  );
}

// ─── In-flight + pending strips on intent page ──────────────────────────────
function IntentInflightStrip({ cap, onGoToWorkers }) {
  const workers = getWorkersForCapability(cap.slug);
  if (workers.length === 0) return null;
  return (
    <div style={{
      background: '#272727', color: '#fff', borderRadius: 6,
      padding: '14px 18px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: workers.length > 0 ? 10 : 0 }}>
        <PulseDot color="#fff" size={8}/>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase' }}>
          {workers.length} worker{workers.length > 1 ? 's' : ''} running on this intent
        </span>
        {workers.length > 1 && <Badge kind="default" style={{ background: 'rgba(255,255,255,0.12)', color: '#fff' }}>parallel fanout</Badge>}
        <span style={{ marginLeft: 'auto' }}>
          <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)' }}>tick {workers[0]?.tick_id?.slice(-6)}</Mono>
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {workers.map(w => (
          <div key={w.id} style={{
            display: 'grid', gridTemplateColumns: '70px 1fr auto', gap: 12,
            fontSize: 12, alignItems: 'center',
          }}>
            <Mono style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)' }}>{w.agent_id}</Mono>
            <Mono style={{ fontSize: 11, color: '#fff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{w.progress}</Mono>
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)' }}>{formatRelativeTime(w.started_at)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function IntentPendingStrip({ cap, onResolvePending }) {
  const pendings = getPendingsForCapability(cap.slug).filter(p => p.status === 'open');
  if (pendings.length === 0) return null;
  return (
    <div style={{
      background: '#e8e0ff', borderRadius: 6,
      padding: '14px 18px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', color: '#3d2a72' }}>
          {pendings.length} pending — needs human
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {pendings.map(p => (
          <div key={p.file} style={{
            background: 'rgba(255,255,255,0.6)',
            borderRadius: 4,
            padding: '10px 14px',
            display: 'grid', gridTemplateColumns: '1fr auto', gap: 14, alignItems: 'center',
          }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <Mono style={{ fontSize: 11, color: '#3d2a72', fontWeight: 600 }}>{p.item_id}</Mono>
                <Badge style={{ background: '#3d2a72', color: '#fff', fontSize: 9, letterSpacing: 1, textTransform: 'uppercase' }}>{p.kind === 'escalation' ? 'escalation' : 'eval'}</Badge>
              </div>
              <div style={{ fontSize: 12, color: '#3d2a72', lineHeight: 1.5 }}>
                {p.ask.split('\n')[0]}
              </div>
            </div>
            <Button size="sm" onClick={() => onResolvePending(p.file)}>Resolve</Button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Run history mini-timeline ──────────────────────────────────────────────
function RunHistoryStrip({ cap }) {
  // Find ticks that mention this slug
  const myTicks = TICKS.filter(t => t.sub_actions.some(s => s.slug === cap.slug)).slice(0, 5);
  if (myTicks.length === 0) return null;
  return (
    <Card padding={24}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14 }}>
        <H2>Run history</H2>
        <Mono faded style={{ fontSize: 11 }}>last {myTicks.length} ticks</Mono>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {myTicks.map(t => {
          const myAction = t.sub_actions.find(s => s.slug === cap.slug);
          const phaseMap = { batch: 'develop', develop: 'develop', evidence: 'evidence', adapt: 'adapt', pending_applied: 'intent', auto_ship: 'adapt' };
          return (
            <div key={t.tick_id} style={{
              display: 'grid',
              gridTemplateColumns: '24px 130px 1fr auto',
              gap: 12, alignItems: 'center',
              padding: '10px 0',
              borderBottom: '1px solid #f0f0f0',
            }}>
              <PhasePill phase={phaseMap[t.kind]}/>
              <Mono style={{ fontSize: 11 }}>{t.tick_id.slice(-12)}</Mono>
              <Mono faded style={{ fontSize: 11 }}>{myAction?.step} → {myAction?.outcome}</Mono>
              <Mono faded style={{ fontSize: 11 }}>{formatRelativeTime(t.ran_at)}</Mono>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ─── Header ─────────────────────────────────────────────────────────────────
function IntentHeader({ cap }) {
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Mono faded style={{ fontSize: 12 }}>.i2e/intents/</Mono>
        <Mono style={{ fontSize: 14, fontWeight: 600 }}>{cap.slug}.md</Mono>
      </div>
      <H1>{cap.title}</H1>
      <div style={{ marginTop: 10, color: '#5f5f5f', fontSize: 14, lineHeight: 1.7, maxWidth: 640 }}>
        {cap.summary}
      </div>
    </div>
  );
}

// ─── IntentView root ────────────────────────────────────────────────────────
function IntentView({ slug, layout, onUpdateStatus, onResolvePending, onGoToWorkers }) {
  const cap = getCapability(slug);
  if (!cap) return <EmptyState title="Intent not found" subtitle={slug}/>;

  const headerAndStrips = (
    <>
      <IntentHeader cap={cap}/>
      <IntentInflightStrip cap={cap} onGoToWorkers={onGoToWorkers}/>
      <IntentPendingStrip cap={cap} onResolvePending={onResolvePending}/>
    </>
  );

  if (layout === 'split') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {headerAndStrips}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 300px', gap: 20, alignItems: 'flex-start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <EvidenceSection cap={cap} onResolvePending={onResolvePending}/>
            <RunHistoryStrip cap={cap}/>
            <IntentSourceBlock cap={cap}/>
          </div>
          <div style={{ position: 'sticky', top: 20, display: 'flex', flexDirection: 'column', gap: 20 }}>
            <IntentMeta cap={cap} onUpdateStatus={onUpdateStatus}/>
          </div>
        </div>
      </div>
    );
  }

  // single column
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {headerAndStrips}
      <IntentMeta cap={cap} onUpdateStatus={onUpdateStatus}/>
      <EvidenceSection cap={cap} onResolvePending={onResolvePending}/>
      <RunHistoryStrip cap={cap}/>
      <IntentSourceBlock cap={cap}/>
    </div>
  );
}

Object.assign(window, { IntentView });
