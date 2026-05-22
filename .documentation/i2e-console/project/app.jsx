// app.jsx — root of the i2e console: route state, top bar, tweak panel, view switcher.

const { useState: useStateApp, useMemo: useMemoApp, useEffect: useEffectApp } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "density": "relaxed",
  "sidebarMode": "grouped",
  "dashboardLayout": "cockpit",
  "intentLayout": "split"
}/*EDITMODE-END*/;

// ─── Top bar — context for the current view + global "what needs me" pulse ─
function TopBar({ route, selectedSlug, onSelectIntent, profile }) {
  const cap = selectedSlug ? getCapability(selectedSlug) : null;
  const allOpen = PENDINGS.filter(p => p.status === 'open');
  const myOpen  = allOpen.filter(p => isMine(p.watcher, profile));
  const pendings = myOpen.length || allOpen.length;
  const workers = WORKERS.length;

  const labels = {
    dashboard: { eyebrow: 'Dashboard', title: 'Operator view' },
    pending: { eyebrow: 'Pending', title: 'Inbox' },
    workers: { eyebrow: 'Workers', title: 'In flight' },
    logs: { eyebrow: 'Logs', title: 'Tick history' },
    intent: cap ? { eyebrow: cap.slug, title: cap.title } : { eyebrow: 'Intent', title: '' },
  };
  const l = labels[route] || labels.dashboard;

  return (
    <div style={{
      position: 'sticky', top: 0, zIndex: 50,
      background: 'rgba(239,239,239,0.85)',
      backdropFilter: 'blur(10px)',
      WebkitBackdropFilter: 'blur(10px)',
      padding: '14px 30px',
      borderBottom: '1px solid rgba(0,0,0,0.04)',
      display: 'flex', alignItems: 'center', gap: 20,
    }}>
      <div style={{ flex: 1, display: 'flex', alignItems: 'baseline', gap: 12, minWidth: 0 }}>
        <Eyebrow style={{ fontSize: 10 }}>{l.eyebrow}</Eyebrow>
        <Mono faded style={{ fontSize: 10 }}>·</Mono>
        <span style={{ fontSize: 13, color: '#333', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.title}</span>
      </div>
      {/* Pulse indicators */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        {workers > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <PulseDot size={7}/>
            <span style={{ fontSize: 11, color: '#5f5f5f' }}>{workers} running</span>
          </div>
        )}
        {pendings > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#7a5cb8' }}/>
            <span style={{ fontSize: 11, color: '#5f5f5f' }}>
              {myOpen.length > 0 ? <><strong style={{ color: '#3d2a72' }}>{myOpen.length} for you</strong>{allOpen.length > myOpen.length ? <span style={{ color: '#999' }}> / {allOpen.length} total</span> : null}</> : <>{allOpen.length} need attention</>}
            </span>
          </div>
        )}
        <Mono faded style={{ fontSize: 11 }}>{new Date(NOW).toISOString().replace('T', ' ').slice(0, 16)}Z</Mono>
      </div>
    </div>
  );
}

// ─── Tweak panel content ────────────────────────────────────────────────────
function Tweaks({ t, setTweak }) {
  return (
    <TweaksPanel>
      <TweakSection label="Layout"/>
      <TweakSelect
        label="Dashboard"
        value={t.dashboardLayout}
        options={[
          { value: 'cockpit', label: 'Cockpit grid' },
          { value: 'arc', label: 'IDEA arc' },
          { value: 'inbox', label: 'Inbox first' },
        ]}
        onChange={(v) => setTweak('dashboardLayout', v)}
      />
      <TweakRadio
        label="Intent detail"
        value={t.intentLayout}
        options={['single', 'split']}
        onChange={(v) => setTweak('intentLayout', v)}
      />
      <TweakSelect
        label="Sidebar"
        value={t.sidebarMode}
        options={[
          { value: 'grouped', label: 'Grouped by status' },
          { value: 'flat', label: 'Flat list' },
          { value: 'tree', label: 'Tree by watcher' },
        ]}
        onChange={(v) => setTweak('sidebarMode', v)}
      />
      <TweakSection label="Density"/>
      <TweakRadio
        label="Spacing"
        value={t.density}
        options={['dense', 'relaxed']}
        onChange={(v) => setTweak('density', v)}
      />
    </TweaksPanel>
  );
}

// ─── Main App ───────────────────────────────────────────────────────────────
function App() {
  const [route, setRoute] = useStateApp('dashboard');  // dashboard | pending | workers | logs | intent
  const [selectedSlug, setSelectedSlug] = useStateApp(null);
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // Profile: who am I working as? Persisted to localStorage so it survives reloads.
  const [profile, setProfileState] = useStateApp(() => {
    try {
      const stored = localStorage.getItem('i2e.profile');
      if (stored && getProfile(stored)) return stored;
    } catch (e) {}
    return '@ryan';  // default
  });
  const setProfile = (handle) => {
    setProfileState(handle);
    try { localStorage.setItem('i2e.profile', handle); } catch (e) {}
  };

  // Local mutable state copy for status toggles + pending resolves (in-memory only)
  const [statusOverrides, setStatusOverrides] = useStateApp({});
  const [resolvedPendings, setResolvedPendings] = useStateApp(new Set());

  // Apply overrides onto CAPABILITIES + PENDINGS (in-memory) so changes show up.
  useEffectApp(() => {
    Object.entries(statusOverrides).forEach(([slug, status]) => {
      const c = CAPABILITIES.find(c => c.slug === slug);
      if (c) c.status = status;
    });
    resolvedPendings.forEach(f => {
      const p = PENDINGS.find(p => p.file === f);
      if (p) p.status = 'resolved';
    });
  }, [statusOverrides, resolvedPendings]);

  const handleUpdateStatus = (slug, status) => {
    setStatusOverrides(prev => ({ ...prev, [slug]: status }));
  };
  const handleResolvePending = (file) => {
    setResolvedPendings(prev => {
      const next = new Set(prev);
      next.add(file);
      return next;
    });
  };

  const onSelectIntent = (slug) => {
    setSelectedSlug(slug);
    setRoute('intent');
  };

  // Density: tweak via CSS var. Apply at the root.
  const density = tweaks.density === 'dense';

  // Background scaffold for #i2e-root provides density baseline.
  useEffectApp(() => {
    document.documentElement.style.setProperty('--i2e-gutter', density ? '14px' : '30px');
    document.documentElement.style.setProperty('--i2e-card-pad', density ? '16px' : '24px');
  }, [density]);

  let main = null;
  if (route === 'dashboard') {
    main = <DashboardView
      layout={tweaks.dashboardLayout}
      profile={profile}
      onSelectIntent={onSelectIntent}
      onGoToPending={() => setRoute('pending')}
      onGoToWorkers={() => setRoute('workers')}
      onResolvePending={handleResolvePending}
    />;
  } else if (route === 'pending') {
    main = <PendingView profile={profile} onSelectIntent={onSelectIntent}/>;
  } else if (route === 'workers') {
    main = <WorkersView onSelectIntent={onSelectIntent}/>;
  } else if (route === 'logs') {
    main = <LogsView onSelectIntent={onSelectIntent}/>;
  } else if (route === 'intent' && selectedSlug) {
    main = <IntentView
      slug={selectedSlug}
      layout={tweaks.intentLayout}
      onUpdateStatus={handleUpdateStatus}
      onResolvePending={handleResolvePending}
      onGoToWorkers={() => setRoute('workers')}
    />;
  } else {
    main = <EmptyState title="Select an intent" subtitle="Pick from the left sidebar"/>;
  }

  const padding = density ? '20px 24px 60px' : '30px 36px 80px';
  const maxWidth = 1240;

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#efefef' }}>
      <Sidebar
        route={route} setRoute={setRoute}
        selectedSlug={selectedSlug} setSelectedSlug={setSelectedSlug}
        sidebarMode={tweaks.sidebarMode}
        profile={profile} setProfile={setProfile}
      />
      <main style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <TopBar route={route} selectedSlug={selectedSlug} onSelectIntent={onSelectIntent} profile={profile}/>
        <div style={{ padding, maxWidth, width: '100%', boxSizing: 'border-box' }}>
          {main}
        </div>
        <footer style={{
          padding: '20px 30px', marginTop: 'auto',
          fontSize: 11, color: '#999', textAlign: 'center',
          borderTop: '1px solid #e5e5e5',
        }}>
          <Mono faded style={{ fontSize: 11 }}>i2e console · running against ~/projects/lithia/.i2e — </Mono>
          <a href="https://ryanturner.com" style={{ color: '#5f5f5f' }}>ryanturner.com</a>
        </footer>
      </main>
      <Tweaks t={tweaks} setTweak={setTweak}/>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('i2e-root')).render(<App/>);
