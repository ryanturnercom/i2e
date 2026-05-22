// pending.jsx — dedicated "what needs me?" view.
// Pendings grouped by watcher, with full prompts and inline resolve UI.

const { useState: useStatePend } = React;

function ResolveDialog({ pending, onClose, onSubmit }) {
  const [choice, setChoice] = useStatePend(null);
  const [note, setNote] = useStatePend('');
  if (!pending) return null;
  const opts = pending.kind === 'escalation'
    ? [
        { v: 'loosen', l: 'Loosen target' },
        { v: 'new-approach', l: 'Try a new approach' },
        { v: 'retire', l: 'Retire target' },
        { v: 'accept', l: 'Accept as met' },
      ]
    : (pending.verdict_options || ['yes', 'no', 'partial']).map(v => ({ v, l: v }));
  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 10000,
    }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{
        background: '#fff', borderRadius: 6, width: 540, maxWidth: '90vw',
        padding: 30, boxShadow: '0 8px 60px rgba(0,0,0,0.18)',
      }}>
        <Eyebrow style={{ marginBottom: 8 }}>Resolve · {pending.watcher}</Eyebrow>
        <div style={{ marginBottom: 6 }}>
          <Mono style={{ fontSize: 13, fontWeight: 600 }}>{pending.capability}</Mono>
          <Mono faded style={{ fontSize: 12, marginLeft: 6 }}>/ {pending.item_id}</Mono>
        </div>
        <div style={{ fontSize: 13, color: '#5f5f5f', lineHeight: 1.6, marginBottom: 18, whiteSpace: 'pre-line' }}>
          {pending.ask}
        </div>
        <Eyebrow style={{ marginBottom: 8 }}>Your verdict</Eyebrow>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
          {opts.map(o => (
            <button
              key={o.v}
              onClick={() => setChoice(o.v)}
              style={{
                background: choice === o.v ? '#272727' : 'transparent',
                color: choice === o.v ? '#fff' : '#272727',
                border: '1px solid #272727',
                padding: '8px 14px 6px', borderRadius: 6,
                fontFamily: 'inherit', fontSize: 11, fontWeight: 600,
                letterSpacing: 1, textTransform: 'uppercase',
                cursor: 'pointer',
              }}
            >{o.l}</button>
          ))}
        </div>
        <Eyebrow style={{ marginBottom: 8 }}>Notes (optional)</Eyebrow>
        <textarea
          value={note}
          onChange={e => setNote(e.target.value)}
          rows={3}
          placeholder="What did you observe?"
          style={{
            width: '100%', boxSizing: 'border-box',
            background: '#fafafa', border: '1px solid #e0e0e0', borderRadius: 6,
            padding: 10, fontFamily: 'inherit', fontSize: 13,
            color: '#333', resize: 'vertical', outline: 'none',
          }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={() => onSubmit(pending.file, choice, note)} disabled={!choice}>Write resolution</Button>
        </div>
      </div>
    </div>
  );
}

function PendingCard({ p, onResolve, mine }) {
  return (
    <Card padding={24} style={mine ? { boxShadow: '0 2px 40px rgba(0,0,0,0.07), inset 3px 0 0 #7a5cb8' } : {}}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14, gap: 10, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.kind === 'escalation' ? '#ef4444' : '#7a5cb8' }} />
          <Mono style={{ fontSize: 13, fontWeight: 600 }}>{p.capability}</Mono>
          <Mono faded style={{ fontSize: 12 }}>/ {p.item_id}</Mono>
          {mine && <Badge style={{ background: '#3d2a72', color: '#fff', fontSize: 9, letterSpacing: 1, textTransform: 'uppercase' }}>for you</Badge>}
        </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Badge kind={p.kind === 'escalation' ? 'fail' : 'awaiting_human'} style={{ textTransform: 'uppercase', letterSpacing: 1, fontSize: 9 }}>
            {p.kind === 'escalation' ? 'escalation' : 'human evaluation'}
          </Badge>
          <Mono faded style={{ fontSize: 11 }}>{formatRelativeTime(p.asked_at || p.escalated_at)}</Mono>
        </div>
      </div>
      <div style={{ fontSize: 14, color: '#333', lineHeight: 1.7, whiteSpace: 'pre-line', marginBottom: p.attempts ? 16 : 18 }}>
        {p.ask}
      </div>
      {p.attempts && (
        <div style={{ marginBottom: 18 }}>
          <Eyebrow style={{ marginBottom: 8 }}>Attempts ({p.attempts.length})</Eyebrow>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {p.attempts.map((a, i) => (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '120px 1fr auto', gap: 12,
                background: '#fafafa', borderRadius: 4, padding: '8px 12px',
                fontSize: 12, alignItems: 'center',
              }}>
                <Mono faded style={{ fontSize: 11 }}>{a.run_id.slice(-6)}</Mono>
                <span style={{ color: '#5f5f5f' }}>{a.changed}</span>
                <Mono style={{ fontSize: 11, color: '#333' }}>{a.observed}</Mono>
              </div>
            ))}
          </div>
        </div>
      )}
      {(p.expect || p.observed) && (
        <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '6px 14px', marginBottom: 18, fontSize: 12 }}>
          {p.expect && <>
            <Mono faded style={{ fontSize: 11 }}>expect</Mono>
            <Mono style={{ fontSize: 12 }}>{p.expect}</Mono>
          </>}
          {p.observed && <>
            <Mono faded style={{ fontSize: 11 }}>observed</Mono>
            <Mono style={{ fontSize: 12 }}>{p.observed}</Mono>
          </>}
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingTop: 14, borderTop: '1px solid #f0f0f0' }}>
        <Mono faded style={{ fontSize: 11 }}>{p.watcher}</Mono>
        <Mono faded style={{ fontSize: 11 }}>·</Mono>
        <Mono faded style={{ fontSize: 11 }}>.i2e/pending/{p.file}</Mono>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <Button size="sm" variant="ghost">Open file</Button>
          <Button size="sm" variant="primary" onClick={() => onResolve(p)}>Resolve</Button>
        </div>
      </div>
    </Card>
  );
}

function PendingView({ profile, onSelectIntent }) {
  const [resolving, setResolving] = useStatePend(null);
  const [scope, setScope] = useStatePend('mine');  // 'mine' | 'all'
  const me = getProfile(profile);
  const allOpen = PENDINGS.filter(p => p.status === 'open');
  const myOpen  = allOpen.filter(p => isMine(p.watcher, profile));
  // If user has 0 personal items, default to 'all' on first paint.
  const effectiveScope = (scope === 'mine' && myOpen.length === 0) ? 'all' : scope;
  const open = effectiveScope === 'mine' ? myOpen : allOpen;

  const escalations = open.filter(p => p.kind === 'escalation');
  const evals = open.filter(p => p.kind === 'human_evaluation');

  const byWatcher = {};
  open.forEach(p => {
    if (!byWatcher[p.watcher]) byWatcher[p.watcher] = [];
    byWatcher[p.watcher].push(p);
  });

  const handleResolveSubmit = (file, choice, note) => {
    console.log('resolution submitted', { file, choice, note });
    setResolving(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <Eyebrow style={{ marginBottom: 6 }}>Pending</Eyebrow>
        <H1>{effectiveScope === 'mine' ? `What needs ${me?.handle || 'you'}` : 'What needs a human'}</H1>
        <div style={{ marginTop: 10, fontSize: 14, color: '#5f5f5f', lineHeight: 1.7, maxWidth: 640 }}>
          {effectiveScope === 'mine'
            ? <>Items watched by you or your teams. {evals.length} evaluations, {escalations.length} escalations.</>
            : <>All items in <Mono>.i2e/pending/</Mono>. {evals.length} evaluations, {escalations.length} escalations across {Object.keys(byWatcher).length} watchers.</>}
        </div>
      </div>

      {/* Scope toggle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ display: 'flex', gap: 2, background: '#fff', padding: 3, borderRadius: 6, boxShadow: '0 1px 12px rgba(0,0,0,0.05)' }}>
          <button onClick={() => setScope('mine')} style={{
            background: effectiveScope === 'mine' ? '#272727' : 'transparent',
            color: effectiveScope === 'mine' ? '#fff' : '#333',
            border: 'none', padding: '6px 14px 4px', borderRadius: 4,
            fontFamily: 'inherit', fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase',
            cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6,
          }}>For you <span style={{ opacity: 0.7 }}>{myOpen.length}</span></button>
          <button onClick={() => setScope('all')} style={{
            background: effectiveScope === 'all' ? '#272727' : 'transparent',
            color: effectiveScope === 'all' ? '#fff' : '#333',
            border: 'none', padding: '6px 14px 4px', borderRadius: 4,
            fontFamily: 'inherit', fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase',
            cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6,
          }}>All <span style={{ opacity: 0.7 }}>{allOpen.length}</span></button>
        </div>
        {me && <Mono faded style={{ fontSize: 11 }}>as {me.handle}{me.teams ? ` · ${me.teams.join(', ')}` : ''}</Mono>}
      </div>

      {/* Watcher summary chips — highlights chips matching your profile */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {Object.entries(byWatcher).map(([w, items]) => {
          const yours = isMine(w, profile);
          return (
            <div key={w} style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '8px 14px',
              background: yours ? '#e8e0ff' : '#fff',
              borderRadius: 6,
              boxShadow: yours ? '0 2px 14px rgba(122,92,184,0.18)' : '0 1px 12px rgba(0,0,0,0.05)',
            }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: yours ? '#3d2a72' : '#333' }}>{w}</span>
              <span style={{
                background: yours ? '#3d2a72' : '#e8e0ff',
                color: yours ? '#fff' : '#3d2a72',
                borderRadius: 9999, padding: '1px 7px',
                fontSize: 10, fontWeight: 700,
              }}>{items.length}</span>
            </div>
          );
        })}
      </div>

      {evals.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
            <Eyebrow>Human evaluations</Eyebrow>
            <span style={{ fontSize: 11, color: '#999' }}>· {evals.length} · provider: human</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {evals.map(p => <PendingCard key={p.file} p={p} onResolve={setResolving} mine={isMine(p.watcher, profile)}/>)}
          </div>
        </div>
      )}

      {escalations.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
            <Eyebrow>Escalations</Eyebrow>
            <span style={{ fontSize: 11, color: '#999' }}>· {escalations.length} · budgets exhausted</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {escalations.map(p => <PendingCard key={p.file} p={p} onResolve={setResolving} mine={isMine(p.watcher, profile)}/>)}
          </div>
        </div>
      )}

      <ResolveDialog pending={resolving} onClose={() => setResolving(null)} onSubmit={handleResolveSubmit}/>
    </div>
  );
}

Object.assign(window, { PendingView });
