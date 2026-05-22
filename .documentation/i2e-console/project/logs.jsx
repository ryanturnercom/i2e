// logs.jsx — append-only tick log view. Timeline + table modes (toggle).

const { useState: useStateLog, useMemo: useMemoLog } = React;

function TickItem({ tick, expanded, onToggle }) {
  const phaseMap = { batch: 'develop', develop: 'develop', evidence: 'evidence', adapt: 'adapt', pending_applied: 'intent', auto_ship: 'adapt' };
  const isBatch = tick.sub_actions.length > 1;
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '60px 24px 1fr', columnGap: 14,
      position: 'relative',
    }}>
      {/* Time */}
      <div style={{ padding: '14px 0', textAlign: 'right' }}>
        <Mono style={{ fontSize: 11 }}>{formatRelativeTime(tick.ran_at)}</Mono>
        <Mono faded style={{ fontSize: 10, display: 'block', marginTop: 2 }}>{new Date(tick.ran_at).toISOString().slice(11, 16)}</Mono>
      </div>
      {/* Phase column with timeline rail */}
      <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '14px 0 14px' }}>
        <PhasePill phase={phaseMap[tick.kind]} />
        <div style={{ position: 'absolute', top: 0, bottom: 0, left: '50%', width: 1, background: '#e5e5e5', zIndex: -1 }}/>
      </div>
      {/* Card */}
      <div style={{ padding: '4px 0' }}>
        <Card padding={0} style={{ overflow: 'hidden' }}>
          <div style={{ padding: '14px 18px', cursor: 'pointer' }} onClick={onToggle}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
              <Mono style={{ fontSize: 12, fontWeight: 600 }}>{tick.tick_id}</Mono>
              {isBatch && <Badge style={{ background: '#e8e0ff', color: '#3d2a72', fontSize: 9, letterSpacing: 1, textTransform: 'uppercase' }}>batch · {tick.sub_actions.length}</Badge>}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {(expanded ? tick.actions : tick.actions.slice(0, 1)).map((a, i) => (
                <Mono key={i} faded={i > 0} style={{ fontSize: 12, color: i === 0 ? '#333' : '#5f5f5f' }}>{a}</Mono>
              ))}
              {!expanded && tick.actions.length > 1 && (
                <Mono faded style={{ fontSize: 11 }}>+ {tick.actions.length - 1} more</Mono>
              )}
            </div>
          </div>
          {expanded && tick.sub_actions.length > 0 && (
            <div style={{ borderTop: '1px solid #f0f0f0', padding: '12px 18px', background: '#fafafa' }}>
              <Eyebrow style={{ marginBottom: 8 }}>Sub actions</Eyebrow>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {tick.sub_actions.map((s, i) => (
                  <div key={i} style={{ display: 'grid', gridTemplateColumns: '160px 80px 90px 1fr', gap: 12, fontSize: 12 }}>
                    <Mono style={{ fontSize: 12, fontWeight: 600 }}>{s.slug}</Mono>
                    <Mono faded style={{ fontSize: 11 }}>{s.step}</Mono>
                    <Mono style={{ fontSize: 11 }}>{s.agent_id}</Mono>
                    <Mono style={{
                      fontSize: 11,
                      color: s.outcome === 'running' ? '#3d2a72'
                        : s.outcome === 'escalated' ? '#8a1f1f'
                        : (s.outcome === 'shipped' || s.outcome === 'shippable' || s.outcome === 'all_green') ? 'oklch(0.32 0.05 152)'
                        : s.outcome === 'awaiting_human' ? '#3d2a72'
                        : s.outcome === 'trending' ? 'oklch(0.38 0.07 75)'
                        : '#333',
                    }}>{s.outcome}</Mono>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function TableMode({ ticks, expandedSet, toggleExpand, onSelectIntent }) {
  return (
    <Card padding={0} style={{ overflow: 'hidden' }}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: '22px 130px 90px 1fr 80px 90px',
        gap: 14, padding: '10px 18px', background: '#fafafa',
        borderBottom: '1px solid #f0f0f0',
        fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase', color: '#999',
      }}>
        <span/>
        <span>Tick</span>
        <span>Phase</span>
        <span>Actions</span>
        <span>Items</span>
        <span style={{ textAlign: 'right' }}>When</span>
      </div>
      {ticks.map(t => {
        const phaseMap = { batch: 'develop', develop: 'develop', evidence: 'evidence', adapt: 'adapt', pending_applied: 'intent', auto_ship: 'adapt' };
        const exp = expandedSet.has(t.tick_id);
        return (
          <React.Fragment key={t.tick_id}>
            <div
              onClick={() => toggleExpand(t.tick_id)}
              style={{
                display: 'grid',
                gridTemplateColumns: '22px 130px 90px 1fr 80px 90px',
                gap: 14, padding: '12px 18px', alignItems: 'center',
                borderBottom: '1px solid #f0f0f0',
                cursor: 'pointer', fontSize: 12,
              }}>
              <PhasePill phase={phaseMap[t.kind]}/>
              <Mono style={{ fontSize: 11 }}>{t.tick_id.slice(-12)}</Mono>
              <Mono faded style={{ fontSize: 11 }}>{t.kind}</Mono>
              <Mono style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.actions[0]}</Mono>
              <Mono faded style={{ fontSize: 11 }}>{t.sub_actions.length}</Mono>
              <Mono faded style={{ fontSize: 11, textAlign: 'right' }}>{formatRelativeTime(t.ran_at)}</Mono>
            </div>
            {exp && (
              <div style={{ padding: '14px 18px', background: '#fafafa', borderBottom: '1px solid #f0f0f0' }}>
                <Eyebrow style={{ marginBottom: 8 }}>All actions</Eyebrow>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 14 }}>
                  {t.actions.map((a, i) => <Mono key={i} style={{ fontSize: 12 }}>{a}</Mono>)}
                </div>
                <Eyebrow style={{ marginBottom: 8 }}>Sub actions</Eyebrow>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {t.sub_actions.map((s, i) => (
                    <div key={i} style={{ display: 'grid', gridTemplateColumns: '160px 90px 90px 1fr', gap: 12, fontSize: 12 }}>
                      <Mono onClick={(e) => { e.stopPropagation(); onSelectIntent(s.slug); }} style={{ fontSize: 12, fontWeight: 600, cursor: 'pointer', textDecoration: 'underline', textUnderlineOffset: 3, color: '#272727' }}>{s.slug}</Mono>
                      <Mono faded style={{ fontSize: 11 }}>{s.step}</Mono>
                      <Mono style={{ fontSize: 11 }}>{s.agent_id}</Mono>
                      <Mono style={{ fontSize: 11 }}>{s.outcome}</Mono>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </React.Fragment>
        );
      })}
    </Card>
  );
}

function LogsView({ onSelectIntent }) {
  const [mode, setMode] = useStateLog('timeline');
  const [filterPhase, setFilterPhase] = useStateLog('all');
  const [filterSlug, setFilterSlug] = useStateLog('');
  const [expandedSet, setExpandedSet] = useStateLog(() => new Set());

  const ticks = useMemoLog(() => {
    let xs = TICKS.slice();
    if (filterPhase !== 'all') xs = xs.filter(t => {
      const phaseMap = { batch: 'develop', develop: 'develop', evidence: 'evidence', adapt: 'adapt', pending_applied: 'intent', auto_ship: 'adapt' };
      return phaseMap[t.kind] === filterPhase;
    });
    if (filterSlug.trim()) {
      const s = filterSlug.trim().toLowerCase();
      xs = xs.filter(t => t.sub_actions.some(sa => sa.slug.includes(s)) || t.tick_id.includes(s));
    }
    return xs;
  }, [filterPhase, filterSlug]);

  const toggleExpand = (id) => {
    setExpandedSet(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <Eyebrow style={{ marginBottom: 6 }}>Logs</Eyebrow>
        <H1>Tick history</H1>
        <div style={{ marginTop: 10, fontSize: 14, color: '#5f5f5f', lineHeight: 1.7, maxWidth: 640 }}>
          Append-only. <Mono>.i2e/logs/</Mono> stores one yaml per resolved pending and per non-empty tick. Empty ticks don't log.
        </div>
      </div>

      {/* Toolbar */}
      <Card padding={16}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          {/* Phase filter */}
          <div style={{ display: 'flex', gap: 4 }}>
            {['all', 'intent', 'develop', 'evidence', 'adapt'].map(p => (
              <button
                key={p}
                onClick={() => setFilterPhase(p)}
                style={{
                  background: filterPhase === p ? '#272727' : '#fafafa',
                  color: filterPhase === p ? '#fff' : '#333',
                  border: 'none',
                  padding: '6px 12px 4px',
                  borderRadius: 4,
                  fontFamily: 'inherit', fontSize: 10, fontWeight: 600,
                  letterSpacing: 1, textTransform: 'uppercase',
                  cursor: 'pointer',
                }}>{p}</button>
            ))}
          </div>
          <div style={{ flex: 1, minWidth: 200 }}>
            <input
              type="text"
              value={filterSlug}
              onChange={e => setFilterSlug(e.target.value)}
              placeholder="filter by slug or tick-id"
              style={{
                width: '100%', boxSizing: 'border-box',
                background: '#fff', border: '1px solid #e0e0e0',
                borderRadius: 6, padding: '6px 10px',
                fontFamily: 'inherit', fontSize: 12, color: '#333', outline: 'none',
              }}
            />
          </div>
          <div style={{ display: 'flex', gap: 4, background: '#fafafa', padding: 2, borderRadius: 6 }}>
            {['timeline', 'table'].map(m => (
              <button
                key={m}
                onClick={() => setMode(m)}
                style={{
                  background: mode === m ? '#fff' : 'transparent',
                  color: mode === m ? '#272727' : '#5f5f5f',
                  boxShadow: mode === m ? '0 1px 3px rgba(0,0,0,0.06)' : 'none',
                  border: 'none', padding: '6px 12px 4px', borderRadius: 4,
                  fontFamily: 'inherit', fontSize: 10, fontWeight: 600,
                  letterSpacing: 1, textTransform: 'uppercase',
                  cursor: 'pointer',
                }}>{m}</button>
            ))}
          </div>
        </div>
      </Card>

      {ticks.length === 0 && <Card><EmptyState title="No ticks match" subtitle="Try clearing the filter"/></Card>}

      {mode === 'timeline' && ticks.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {ticks.map(t => (
            <TickItem key={t.tick_id} tick={t}
              expanded={expandedSet.has(t.tick_id)}
              onToggle={() => toggleExpand(t.tick_id)}
            />
          ))}
        </div>
      )}

      {mode === 'table' && ticks.length > 0 && (
        <TableMode ticks={ticks} expandedSet={expandedSet} toggleExpand={toggleExpand} onSelectIntent={onSelectIntent}/>
      )}
    </div>
  );
}

Object.assign(window, { LogsView });
