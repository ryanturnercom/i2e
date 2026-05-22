// workers.jsx — dedicated view for in-flight workers (worktrees).
// Shows parallel fanout grouping, claim.json contents, live log tail (simulated).

const { useState: useStateWk, useEffect: useEffectWk } = React;

// Group workers by capability so parallel fanout reads as a unit.
function groupedWorkers() {
  const groups = {};
  WORKERS.forEach(w => {
    if (!groups[w.capability]) groups[w.capability] = [];
    groups[w.capability].push(w);
  });
  return Object.entries(groups);
}

// Fake log tail — cycles through phrases.
const SIM_LOG_LINES = {
  'w-7c1f2e': [
    '[develop] reading src/auth/password.py …',
    '[develop] applying patch: strip(), len() guard',
    '[develop] running mypy on src/auth/**',
    '[develop] mypy: ok',
    '[develop] writing src/auth/password.py',
    '[develop] writing tests/auth/test_change_flow.py',
    '[evidence] queued: 4 cases',
  ],
  'w-a8d44b': [
    '[develop] reading src/charts/renderer.tsx …',
    '[develop] generating d3.scaleLinear axes',
    '[develop] tsc --noEmit on src/charts/**',
    '[develop] tsc: ok',
    '[develop] writing src/charts/renderer.tsx',
  ],
  'w-3b91f7': [
    '[develop] reading tests/charts/test_tooltip.py …',
    '[develop] adding hover-position fixture',
    '[develop] writing tests/charts/test_tooltip.py',
    '[develop] running pytest tests/charts/ -k tooltip',
    '[develop] pytest: 7 passed, 1 trending',
  ],
};

function LiveLogTail({ workerId, height = 140 }) {
  const lines = SIM_LOG_LINES[workerId] || ['[develop] booting agent …'];
  const [shown, setShown] = useStateWk(Math.min(3, lines.length));
  useEffectWk(() => {
    const t = setInterval(() => {
      setShown(n => Math.min(n + 1, lines.length));
    }, 1800);
    return () => clearInterval(t);
  }, [lines.length]);
  return (
    <div style={{
      background: '#1a1a1a', color: '#d4d4d4',
      borderRadius: 4, padding: '12px 14px',
      fontFamily: '"JetBrains Mono", monospace',
      fontSize: 11, lineHeight: 1.7,
      height, overflow: 'auto', textAlign: 'left',
    }}>
      {lines.slice(0, shown).map((l, i) => {
        const isLatest = i === shown - 1;
        return (
          <div key={i} style={{ opacity: i < shown - 3 ? 0.55 : 1, display: 'flex', gap: 6 }}>
            <span style={{ color: '#666' }}>{String(i + 1).padStart(2, '0')}</span>
            <span style={{ color: l.startsWith('[develop]') ? '#fff' : '#a78bf5' }}>{l}</span>
            {isLatest && <span style={{ color: '#7a5cb8', marginLeft: 'auto' }}>▍</span>}
          </div>
        );
      })}
    </div>
  );
}

function WorkerCard({ w, sibling, onKill }) {
  return (
    <Card padding={20} style={{ borderLeft: '3px solid #7a5cb8' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <PulseDot size={9}/>
          <Mono style={{ fontSize: 13, fontWeight: 600 }}>{w.id}</Mono>
          <Badge kind="default" style={{ background: '#272727', color: '#fff', fontSize: 9, letterSpacing: 1, textTransform: 'uppercase' }}>{w.step}</Badge>
          {sibling && <Badge style={{ background: '#e8e0ff', color: '#3d2a72', fontSize: 9, letterSpacing: 1, textTransform: 'uppercase' }}>fanout</Badge>}
        </div>
        <Mono faded style={{ fontSize: 11 }}>started {formatRelativeTime(w.started_at)}</Mono>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '8px 16px', fontSize: 12, marginBottom: 14 }}>
        <Mono faded style={{ fontSize: 11 }}>capability</Mono>
        <Mono style={{ fontSize: 12, fontWeight: 600 }}>{w.capability}</Mono>
        <Mono faded style={{ fontSize: 11 }}>agent</Mono>
        <Mono style={{ fontSize: 12 }}>{w.agent_id}</Mono>
        <Mono faded style={{ fontSize: 11 }}>session</Mono>
        <Mono style={{ fontSize: 12 }}>{w.session_id}</Mono>
        <Mono faded style={{ fontSize: 11 }}>pid</Mono>
        <Mono style={{ fontSize: 12 }}>{w.pid}</Mono>
        <Mono faded style={{ fontSize: 11 }}>tick</Mono>
        <Mono style={{ fontSize: 12 }}>{w.tick_id}</Mono>
        <Mono faded style={{ fontSize: 11 }}>worktree</Mono>
        <Mono style={{ fontSize: 12 }}>{w.worktree}</Mono>
      </div>

      <Eyebrow style={{ marginBottom: 8 }}>Current step</Eyebrow>
      <div style={{
        background: '#fafafa', padding: '10px 14px', borderRadius: 4,
        fontSize: 13, color: '#333', marginBottom: 16,
      }}>{w.progress}</div>

      <Eyebrow style={{ marginBottom: 8 }}>Live log</Eyebrow>
      <LiveLogTail workerId={w.id}/>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
        <Button size="sm" variant="ghost">Open worktree</Button>
        <Button size="sm" variant="outline" onClick={() => onKill && onKill(w.id)}>Kill</Button>
      </div>
    </Card>
  );
}

function WorkersView({ onSelectIntent }) {
  const groups = groupedWorkers();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <Eyebrow style={{ marginBottom: 6 }}>Workers</Eyebrow>
        <H1>{WORKERS.length} parallel workers in flight</H1>
        <div style={{ marginTop: 10, fontSize: 14, color: '#5f5f5f', lineHeight: 1.7, maxWidth: 640 }}>
          Each lock under <Mono>.i2e/worktrees/&lt;slug&gt;/</Mono> claims a capability for this tick.
          Within a capability, workers run as a parallel fanout — distinct files in different sub-agents.
        </div>
      </div>

      {/* Bird's-eye lane chart */}
      <Card padding={24}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14 }}>
          <H2>Tick lanes</H2>
          <Mono faded style={{ fontSize: 11 }}>tick {WORKERS[0]?.tick_id}</Mono>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {groups.map(([cap, ws]) => (
            <div key={cap} style={{
              display: 'grid', gridTemplateColumns: '160px 1fr', gap: 14, alignItems: 'center',
            }}>
              <div
                onClick={() => onSelectIntent(cap)}
                style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}
              >
                <PulseDot size={7}/>
                <Mono style={{ fontSize: 12, fontWeight: 600 }}>{cap}</Mono>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                {ws.map(w => (
                  <div key={w.id} style={{
                    flex: 1, background: '#272727', color: '#fff',
                    borderRadius: 4, padding: '8px 12px',
                    display: 'flex', alignItems: 'center', gap: 8,
                    minHeight: 30,
                  }}>
                    <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)' }}>{w.agent_id}</Mono>
                    <Mono style={{ fontSize: 11, color: '#fff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {w.progress.replace(/^Writing |^Editing /, '')}
                    </Mono>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {groups.map(([cap, ws]) => (
          <div key={cap}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10 }}>
              <Eyebrow>{cap}</Eyebrow>
              {ws.length > 1 && <span style={{ fontSize: 11, color: '#3d2a72' }}>· parallel fanout ({ws.length})</span>}
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: ws.length > 1 ? 'repeat(auto-fit, minmax(360px, 1fr))' : '1fr',
              gap: 16,
            }}>
              {ws.map(w => <WorkerCard key={w.id} w={w} sibling={ws.length > 1}/>)}
            </div>
          </div>
        ))}
      </div>

      {WORKERS.length === 0 && (
        <Card>
          <EmptyState title="No workers in flight" subtitle="The orchestrator is idle. Next tick will start at the top of the decision tree."/>
        </Card>
      )}
    </div>
  );
}

Object.assign(window, { WorkersView });
