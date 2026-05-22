// sidebar.jsx — left sidebar with project nav + intent list.
// Supports three treatments via tweaks: grouped-by-status (default), flat, tree-by-watcher.

const { useState: useStateSb, useMemo: useMemoSb } = React;

function SearchInput({ value, onChange, placeholder }) {
  return (
    <div style={{ position: 'relative' }}>
      <svg width="12" height="12" viewBox="0 0 16 16" style={{
        position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
        opacity: 0.6,
      }}>
        <circle cx="7" cy="7" r="4" stroke="#fff" strokeWidth="1.5" fill="none"/>
        <path d="M10 10 L13 13" stroke="#fff" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          width: '100%',
          background: 'rgba(255,255,255,0.08)',
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 6,
          padding: '8px 10px 8px 28px',
          fontFamily: 'inherit',
          fontSize: 12,
          color: '#fff',
          outline: 'none',
        }}
      />
    </div>
  );
}

function FilterChip({ label, count, active, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1,
        background: active ? '#3a3a3a' : 'transparent',
        border: '1px solid ' + (active ? '#3a3a3a' : 'rgba(255,255,255,0.10)'),
        color: '#fff',
        borderRadius: 6,
        padding: '6px 8px',
        fontFamily: 'inherit',
        fontSize: 10, fontWeight: 600,
        letterSpacing: 1, textTransform: 'uppercase',
        cursor: 'pointer',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
      }}
    >
      <span>{label}</span>
      <span style={{
        background: active ? '#272727' : 'rgba(255,255,255,0.12)',
        color: '#fff',
        borderRadius: 9999, padding: '0 5px',
        fontSize: 9, letterSpacing: 0,
        minWidth: 14, textAlign: 'center',
      }}>{count}</span>
    </button>
  );
}

function NavItem({ icon, label, badge, active, onClick }) {
  const [hover, setHover] = useStateSb(false);
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 12px',
        borderRadius: 6,
        background: (active || hover) ? '#3a3a3a' : 'transparent',
        color: '#fff',
        cursor: 'pointer',
      }}
    >
      <span style={{ width: 16, display: 'inline-flex', justifyContent: 'center', opacity: 0.85 }}>{icon}</span>
      <span style={{ flex: 1, fontSize: 12, fontWeight: 600, letterSpacing: 2, textTransform: 'uppercase' }}>{label}</span>
      {badge != null && badge > 0 && (
        <span style={{
          background: '#e8e0ff', color: '#3d2a72',
          borderRadius: 9999, padding: '1px 6px',
          fontSize: 9, fontWeight: 700, letterSpacing: 0,
        }}>{badge}</span>
      )}
    </div>
  );
}

// ─── Intent row in the sidebar list ─────────────────────────────────────────
function IntentRow({ cap, active, onClick }) {
  const [hover, setHover] = useStateSb(false);
  const pendings = countOpenPendings(cap.slug);
  const workers = getWorkersForCapability(cap.slug);
  const inflight = workers.length > 0;
  const allItems = [...(cap.evidence || []), ...(cap.constraints || [])];
  const hasFail = allItems.some(i => i.verdict === 'fail' || i.verdict === 'unmet');
  const hasTrending = allItems.some(i => i.verdict === 'trending');

  // Status indicator dot
  let dotColor = '#999';
  if (cap.status === 'shipped') dotColor = 'oklch(0.55 0.09 240)';
  else if (hasFail) dotColor = '#ef4444';
  else if (pendings > 0) dotColor = '#7a5cb8';
  else if (hasTrending) dotColor = 'oklch(0.72 0.10 75)';
  else if (cap.shippable) dotColor = 'oklch(0.62 0.07 152)';
  else if (cap.status === 'draft') dotColor = '#999';
  else if (cap.status === 'retired') dotColor = '#cccccc';

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 9,
        padding: '7px 10px',
        borderRadius: 6,
        background: active ? '#3a3a3a' : hover ? 'rgba(255,255,255,0.04)' : 'transparent',
        color: '#fff',
        cursor: 'pointer',
        position: 'relative',
      }}
    >
      <span style={{ position: 'relative', width: 8, height: 8, flexShrink: 0 }}>
        {inflight ? <PulseDot color={dotColor} size={8}/> :
          <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: dotColor }}/>
        }
      </span>
      <span style={{
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: 12,
        flex: 1,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        opacity: cap.status === 'retired' ? 0.55 : 1,
        textDecoration: cap.status === 'retired' ? 'line-through' : 'none',
      }}>{cap.slug}</span>
      {pendings > 0 && (
        <span style={{
          background: '#e8e0ff', color: '#3d2a72',
          borderRadius: 9999, padding: '1px 5px',
          fontSize: 9, fontWeight: 700, letterSpacing: 0,
          flexShrink: 0,
        }}>{pendings}</span>
      )}
    </div>
  );
}

// ─── Profile chip (bottom-left) + switcher popup ────────────────────────────
function ProfileChip({ profile, onOpenSwitcher }) {
  const [hover, setHover] = useStateSb(false);
  if (!profile) return null;
  const ringColor = profile.isTeam ? '#5a8a5e' : '#e8e0ff';
  const fgColor   = profile.isTeam ? '#fff'    : '#3d2a72';
  return (
    <div
      onClick={onOpenSwitcher}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 12px',
        background: hover ? '#3a3a3a' : 'rgba(255,255,255,0.04)',
        borderRadius: 6,
        cursor: 'pointer',
      }}>
      <div style={{
        width: 26, height: 26, borderRadius: 4,
        background: ringColor, color: fgColor,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 700, letterSpacing: 0,
        flexShrink: 0,
      }}>{initials(profile.handle)}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, color: '#fff', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{profile.name}</div>
        <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)' }}>{profile.handle}{profile.isTeam ? ' · team' : ''}</Mono>
      </div>
      <svg width="10" height="10" viewBox="0 0 10 10" style={{ opacity: 0.55, flexShrink: 0 }}>
        <path d="M3 2 L7 5 L3 8" stroke="#fff" strokeWidth="1.3" fill="none" strokeLinecap="round"/>
      </svg>
    </div>
  );
}

function ProfileSwitcher({ open, onClose, onPick, current }) {
  if (!open) return null;
  // Show individuals first, then teams.
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 200,
        background: 'rgba(0,0,0,0.35)',
        display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-start',
      }}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          margin: '0 0 16px 16px',
          width: 288,
          background: '#272727', color: '#fff',
          borderRadius: 8,
          boxShadow: '0 12px 60px rgba(0,0,0,0.35)',
          padding: 14,
          maxHeight: '70vh', overflowY: 'auto',
        }}>
        <div style={{
          fontSize: 10, fontWeight: 600, letterSpacing: 2, textTransform: 'uppercase',
          color: 'rgba(255,255,255,0.55)', marginBottom: 8, paddingLeft: 4,
        }}>You</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 14 }}>
          {PROFILES.map(p => (
            <ProfileRow key={p.handle} p={p} active={current === p.handle} onClick={() => { onPick(p.handle); onClose(); }} />
          ))}
        </div>
        <div style={{
          fontSize: 10, fontWeight: 600, letterSpacing: 2, textTransform: 'uppercase',
          color: 'rgba(255,255,255,0.55)', marginBottom: 8, paddingLeft: 4,
        }}>Teams</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {TEAM_PROFILES.map(p => (
            <ProfileRow key={p.handle} p={p} active={current === p.handle} onClick={() => { onPick(p.handle); onClose(); }} />
          ))}
        </div>
        <div style={{
          marginTop: 14, paddingTop: 12,
          borderTop: '1px solid rgba(255,255,255,0.08)',
          fontSize: 11, color: 'rgba(255,255,255,0.55)',
        }}>
          <Mono faded style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)' }}>persisted to localStorage · i2e.profile</Mono>
        </div>
      </div>
    </div>
  );
}

function ProfileRow({ p, active, onClick }) {
  const [hover, setHover] = useStateSb(false);
  const isMyPending = PENDINGS.filter(x => x.status === 'open' && (x.watcher === p.handle || (getProfile(p.handle)?.teams || []).includes(x.watcher))).length;
  const directOnly = PENDINGS.filter(x => x.status === 'open' && x.watcher === p.handle).length;
  const count = p.isTeam ? directOnly : isMyPending;
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '8px 10px',
        borderRadius: 6,
        background: active ? '#3a3a3a' : hover ? 'rgba(255,255,255,0.05)' : 'transparent',
        cursor: 'pointer',
      }}>
      <div style={{
        width: 22, height: 22, borderRadius: 4,
        background: p.isTeam ? '#5a8a5e' : '#e8e0ff',
        color: p.isTeam ? '#fff' : '#3d2a72',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 9, fontWeight: 700, flexShrink: 0,
      }}>{initials(p.handle)}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, color: '#fff', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</div>
        <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)' }}>{p.handle}</Mono>
      </div>
      {count > 0 && (
        <span style={{
          background: '#e8e0ff', color: '#3d2a72',
          borderRadius: 9999, padding: '1px 6px',
          fontSize: 9, fontWeight: 700, letterSpacing: 0,
        }}>{count}</span>
      )}
      {active && (
        <svg width="10" height="10" viewBox="0 0 10 10">
          <path d="M2 5 L4 7 L8 3" stroke="#fff" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
        </svg>
      )}
    </div>
  );
}

// ─── Sidebar ────────────────────────────────────────────────────────────────
function Sidebar({ route, setRoute, selectedSlug, setSelectedSlug, sidebarMode, profile, setProfile }) {
  const [switcherOpen, setSwitcherOpen] = useStateSb(false);
  const [filter, setFilter] = useStateSb('active');  // active | draft | shipped | retired | all
  const [search, setSearch] = useStateSb('');
  const [sortMode, setSortMode] = useStateSb('updated');  // updated | name

  const filtered = useMemoSb(() => {
    let xs = CAPABILITIES.slice();
    if (filter !== 'all') xs = xs.filter(c => c.status === filter);
    if (search.trim()) {
      const s = search.trim().toLowerCase();
      xs = xs.filter(c => c.slug.includes(s) || c.title.toLowerCase().includes(s) || (c.watcher || '').toLowerCase().includes(s));
    }
    xs.sort((a, b) => {
      if (sortMode === 'name') return a.slug.localeCompare(b.slug);
      return (b.updated || '').localeCompare(a.updated || '');
    });
    return xs;
  }, [filter, search, sortMode]);

  const counts = useMemoSb(() => ({
    active:  CAPABILITIES.filter(c => c.status === 'active').length,
    draft:   CAPABILITIES.filter(c => c.status === 'draft').length,
    shipped: CAPABILITIES.filter(c => c.status === 'shipped').length,
    retired: CAPABILITIES.filter(c => c.status === 'retired').length,
  }), []);

  const totalPendings = PENDINGS.filter(p => p.status === 'open').length;
  const myPendings = PENDINGS.filter(p => p.status === 'open' && isMine(p.watcher, profile)).length;
  const totalWorkers = WORKERS.length;

  // Group filtered list according to sidebarMode
  let grouped = null;
  if (sidebarMode === 'grouped') {
    grouped = [];
    ['active', 'draft', 'shipped', 'retired'].forEach(s => {
      const items = filtered.filter(c => c.status === s);
      if (items.length > 0) grouped.push({ label: s, items });
    });
  } else if (sidebarMode === 'tree') {
    const byWatcher = {};
    filtered.forEach(c => {
      const w = c.watcher || '@unowned';
      if (!byWatcher[w]) byWatcher[w] = [];
      byWatcher[w].push(c);
    });
    grouped = Object.entries(byWatcher).sort((a,b) => a[0].localeCompare(b[0])).map(([label, items]) => ({ label, items }));
  }

  const onIntentClick = (slug) => {
    setSelectedSlug(slug);
    setRoute('intent');
  };

  return (
    <aside style={{
      width: 300, flexShrink: 0,
      background: '#272727', color: '#fff',
      padding: 24,
      display: 'flex', flexDirection: 'column', gap: 20,
      overflowY: 'auto',
      height: '100vh',
      position: 'sticky', top: 0,
    }}>
      {/* Wordmark */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span style={{
          fontFamily: '"Rock Salt", "Caveat", cursive',
          fontSize: 22, fontWeight: 400, letterSpacing: 0,
        }}>i2e</span>
        <span style={{
          fontSize: 10, letterSpacing: 2, textTransform: 'uppercase',
          color: 'rgba(255,255,255,0.55)', fontWeight: 600,
        }}>console</span>
      </div>

      {/* Project switcher (decorative) */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '8px 10px',
        background: 'rgba(255,255,255,0.05)',
        borderRadius: 6,
      }}>
        <div style={{
          width: 18, height: 18, borderRadius: 4,
          background: '#e8e0ff', color: '#3d2a72',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 10, fontWeight: 700,
        }}>L</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11, fontWeight: 600 }}>lithia</div>
          <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)' }}>~/projects/lithia/.i2e</Mono>
        </div>
        <svg width="10" height="10" viewBox="0 0 10 10" style={{ opacity: 0.5 }}>
          <path d="M2 4 L5 7 L8 4" stroke="#fff" strokeWidth="1.3" fill="none" strokeLinecap="round"/>
        </svg>
      </div>

      {/* Top nav */}
      <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <NavItem
          icon={<svg width="12" height="12" viewBox="0 0 16 16"><rect x="2" y="2" width="5" height="5" stroke="#fff" strokeWidth="1.4" fill="none"/><rect x="9" y="2" width="5" height="5" stroke="#fff" strokeWidth="1.4" fill="none"/><rect x="2" y="9" width="5" height="5" stroke="#fff" strokeWidth="1.4" fill="none"/><rect x="9" y="9" width="5" height="5" stroke="#fff" strokeWidth="1.4" fill="none"/></svg>}
          label="Dashboard" active={route === 'dashboard'}
          onClick={() => setRoute('dashboard')}
        />
        <NavItem
          icon={<svg width="12" height="12" viewBox="0 0 16 16"><circle cx="8" cy="8" r="3" stroke="#fff" strokeWidth="1.4" fill="none"/><circle cx="8" cy="8" r="6" stroke="#fff" strokeWidth="1.4" fill="none" opacity="0.5"/></svg>}
          label="Pending" badge={myPendings || totalPendings} active={route === 'pending'}
          onClick={() => setRoute('pending')}
        />
        <NavItem
          icon={<svg width="12" height="12" viewBox="0 0 16 16"><circle cx="4" cy="8" r="2" stroke="#fff" strokeWidth="1.4" fill="none"/><circle cx="12" cy="8" r="2" stroke="#fff" strokeWidth="1.4" fill="none"/><path d="M6 8 L10 8" stroke="#fff" strokeWidth="1.4"/></svg>}
          label="Workers" badge={totalWorkers} active={route === 'workers'}
          onClick={() => setRoute('workers')}
        />
        <NavItem
          icon={<svg width="12" height="12" viewBox="0 0 16 16"><path d="M3 4 L13 4 M3 8 L13 8 M3 12 L13 12" stroke="#fff" strokeWidth="1.4" strokeLinecap="round"/></svg>}
          label="Logs" active={route === 'logs'}
          onClick={() => setRoute('logs')}
        />
      </nav>

      {/* Divider */}
      <div style={{ height: 1, background: 'rgba(255,255,255,0.08)' }} />

      {/* Intents header */}
      <div>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
          <span style={{ fontSize: 12, fontWeight: 600, letterSpacing: 2, textTransform: 'uppercase' }}>Intents</span>
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.45)' }}>{filtered.length} of {CAPABILITIES.length}</span>
        </div>

        {/* Search */}
        <div style={{ marginBottom: 10 }}>
          <SearchInput value={search} onChange={setSearch} placeholder="search slug / watcher" />
        </div>

        {/* Filter row */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
          <FilterChip label="Active"  count={counts.active}  active={filter === 'active'}  onClick={() => setFilter('active')}/>
          <FilterChip label="Drafts"  count={counts.draft}   active={filter === 'draft'}   onClick={() => setFilter('draft')}/>
          <FilterChip label="Shipped" count={counts.shipped} active={filter === 'shipped'} onClick={() => setFilter('shipped')}/>
        </div>
        <div style={{ display: 'flex', gap: 4, marginBottom: 12 }}>
          <FilterChip label="Retired" count={counts.retired} active={filter === 'retired'} onClick={() => setFilter('retired')}/>
          <FilterChip label="All" count={CAPABILITIES.length} active={filter === 'all'} onClick={() => setFilter('all')}/>
        </div>

        {/* Sort */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: 10,
        }}>
          <span style={{ fontSize: 10, letterSpacing: 1, textTransform: 'uppercase', color: 'rgba(255,255,255,0.45)' }}>Sort by</span>
          <div style={{ display: 'flex', gap: 4 }}>
            {['updated', 'name'].map(m => (
              <button
                key={m}
                onClick={() => setSortMode(m)}
                style={{
                  background: sortMode === m ? 'rgba(255,255,255,0.10)' : 'transparent',
                  border: 'none', color: '#fff',
                  padding: '3px 7px', borderRadius: 4,
                  fontFamily: 'inherit', fontSize: 10, fontWeight: 600,
                  letterSpacing: 1, textTransform: 'uppercase',
                  cursor: 'pointer',
                }}
              >{m}</button>
            ))}
          </div>
        </div>

        {/* List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {grouped ? (
            grouped.map(g => (
              <div key={g.label} style={{ marginBottom: 8 }}>
                <div style={{
                  fontSize: 9, letterSpacing: 2, textTransform: 'uppercase',
                  color: 'rgba(255,255,255,0.38)', fontWeight: 600,
                  padding: '8px 10px 4px',
                }}>{g.label}  ·  {g.items.length}</div>
                {g.items.map(c => (
                  <IntentRow key={c.slug} cap={c}
                    active={route === 'intent' && selectedSlug === c.slug}
                    onClick={() => onIntentClick(c.slug)} />
                ))}
              </div>
            ))
          ) : (
            filtered.map(c => (
              <IntentRow key={c.slug} cap={c}
                active={route === 'intent' && selectedSlug === c.slug}
                onClick={() => onIntentClick(c.slug)} />
            ))
          )}
          {filtered.length === 0 && (
            <div style={{
              padding: '14px 10px', fontSize: 12,
              color: 'rgba(255,255,255,0.45)', textAlign: 'center',
            }}>no intents match</div>
          )}
        </div>
      </div>

      {/* Footer — profile chip + serve indicator */}
      <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 10, paddingTop: 16, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
        <ProfileChip profile={getProfile(profile)} onOpenSwitcher={() => setSwitcherOpen(true)}/>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, color: 'rgba(255,255,255,0.45)', paddingLeft: 4 }}>
          <PulseDot color="oklch(0.62 0.07 152)" size={6}/>
          <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.7)' }}>i2e-serve · 127.0.0.1:8814</Mono>
        </div>
      </div>
      <ProfileSwitcher open={switcherOpen} onClose={() => setSwitcherOpen(false)} onPick={setProfile} current={profile}/>
    </aside>
  );
}

Object.assign(window, { Sidebar, ProfileChip, ProfileSwitcher });
