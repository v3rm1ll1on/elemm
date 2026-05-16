import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import GlassCard from './components/GlassCard';
import Tooltip from './components/Tooltip';
import ObservabilityConsole from './components/ObservabilityConsole';
import CallHistory from './components/CallHistory';
import { Activity, Shield, Cpu, Zap } from 'lucide-react';
import Settings from './components/Settings';
import Security from './components/Security';
import Vault from './components/Vault';
import ManifestDebugger from './components/ManifestDebugger';
import './App.css';
import './Layout.css';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [systemStatus, setSystemStatus] = useState(null);
  const [sessions, setSessions] = useState({});
  const [selectedSessionId, setSelectedSessionId] = useState('global');
  const [vaultSummary, setVaultSummary] = useState([]);
  const [traceEvents, setTraceEvents] = useState([]);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);

  // WebSocket for Real-Time Streaming
  useEffect(() => {
    let ws;
    let reconnectTimeout;
    let isMounted = true;

    const connectWS = () => {
      if (!isMounted) return;
      ws = new WebSocket('ws://127.0.0.1:8090/ws/trace');

      ws.onopen = () => { if (isMounted) console.log("WS connected"); };
      ws.onmessage = (event) => {
        if (!isMounted) return;
        const data = JSON.parse(event.data);
        
        if (data.type === 'status_update') {
          setSystemStatus(prev => ({ ...prev, ...data }));
          return;
        }

        if (data.type === 'activity') {
          const sid = data.session_id || 'default';
          setSystemStatus(prev => ({
            ...prev,
            ...data,
            tokens_in: data.global_tokens_in !== undefined ? data.global_tokens_in : prev?.tokens_in,
            tokens_out: data.global_tokens_out !== undefined ? data.global_tokens_out : prev?.tokens_out,
            chars_in: data.global_chars_in !== undefined ? data.global_chars_in : prev?.chars_in,
            chars_out: data.global_chars_out !== undefined ? data.global_chars_out : prev?.chars_out
          }));

          setSessions(prev => {
            const session = prev[sid] || { tokens_in: 0, tokens_out: 0, chars_in: 0, chars_out: 0 };
            return {
              ...prev,
              [sid]: {
                ...session,
                ...data,
                tokens_in: data.tokens_in_total !== undefined ? data.tokens_in_total : session.tokens_in,
                tokens_out: data.tokens_out_total !== undefined ? data.tokens_out_total : session.tokens_out,
                chars_in: data.chars_in_total !== undefined ? data.chars_in_total : session.chars_in,
                chars_out: data.chars_out_total !== undefined ? data.chars_out_total : session.chars_out,
              }
            };
          });

          setTraceEvents(prev => [data, ...prev].slice(0, 10));
        }
      };

      ws.onclose = () => {
        if (isMounted) reconnectTimeout = setTimeout(connectWS, 3000);
      };
    };

    connectWS();

    const initFetch = async () => {
      try {
        const [sRes, vRes, sessRes, cRes] = await Promise.all([
          fetch('http://127.0.0.1:8090/api/v1/status'),
          fetch('http://127.0.0.1:8090/api/v1/vault/summary'),
          fetch('http://127.0.0.1:8090/api/v1/sessions'),
          fetch('http://127.0.0.1:8090/api/v1/config')
        ]);
        setSystemStatus(await sRes.json());
        setVaultSummary(await vRes.json());
        setSessions(await sessRes.json());
        setConfig(await cRes.json());
      } catch (e) { console.error("Init failed", e); }
      finally { setLoading(false); }
    };
    initFetch();

    return () => {
      isMounted = false;
      ws?.close();
      clearTimeout(reconnectTimeout);
    };
  }, []);

  const handleReset = async () => {
    try {
      await fetch('http://127.0.0.1:8090/api/v1/reset', { method: 'POST' });
      setTraceEvents([]); 
      
      // Sofortiges Re-Fetch der Daten, damit die UI leer ist
      const [sRes, sessRes] = await Promise.all([
        fetch('http://127.0.0.1:8090/api/v1/status'),
        fetch('http://127.0.0.1:8090/api/v1/sessions')
      ]);
      setSystemStatus(await sRes.json());
      setSessions(await sessRes.json());
    } catch (e) { console.error("Reset failed", e); }
  };

  const renderContent = () => {
    const displayData = selectedSessionId === 'global'
      ? systemStatus
      : { ...systemStatus, ...sessions[selectedSessionId] };

    switch (activeTab) {
      case 'dashboard':
        return (
          <div className="dashboard-grid premium-page-container animate-slide-up" style={{ padding: '32px' }}>
            <div className="stat-bar">
              <StatItem label="Uptime" value={displayData?.uptime || "Online"} />
              <StatItem label="Active Clients" value={displayData?.active_clients || 1} />
              <StatItem label="Active APIs" value={displayData?.active_sites || 0} />
              {config?.ui?.display_mode === 'chars' ? (
                <>
                  <StatItem 
                    label="Traffic In (ch)" 
                    value={(displayData?.chars_in || 0).toLocaleString()} 
                    tooltip="Pure payload metric. Shows exact interface input without API-specific overhead (tool definitions, roles)."
                  />
                  <StatItem 
                    label="Traffic Out (ch)" 
                    value={(displayData?.chars_out || 0).toLocaleString()} 
                    tooltip="Pure payload metric. Shows exact interface output without protocol overhead."
                  />
                </>
              ) : config?.ui?.display_mode === 'both' ? (
                <>
                  <StatItem 
                    label="Traffic In" 
                    value={`${(displayData?.tokens_in || 0).toLocaleString()}t / ${(displayData?.chars_in || 0).toLocaleString()}c`} 
                    tooltip="Pure payload metric. Tokens are a mathematical derivation of characters based on your ratio, without fixed API overhead."
                  />
                  <StatItem 
                    label="Traffic Out" 
                    value={`${(displayData?.tokens_out || 0).toLocaleString()}t / ${(displayData?.chars_out || 0).toLocaleString()}c`} 
                    tooltip="Pure payload metric. Shows exact output without protocol overhead."
                  />
                </>
              ) : (
                <>
                  <StatItem 
                    label="Traffic In (t)" 
                    value={(displayData?.tokens_in || 0).toLocaleString()} 
                    tooltip="Estimated tokens based on your ratio. Excludes fixed API overhead for tool calls."
                  />
                  <StatItem 
                    label="Traffic Out (t)" 
                    value={(displayData?.tokens_out || 0).toLocaleString()} 
                    tooltip="Estimated tokens based on your ratio. Excludes fixed API overhead."
                  />
                </>
              )}
            </div>

            <ObservabilityConsole 
              history={displayData?.history} 
              trace={traceEvents}
              selectedSessionId={selectedSessionId} 
              config={config}
            />
          </div>
        );
      case 'history':
        return (
          <div className="history-view-container premium-page-container animate-slide-up" style={{ padding: '32px' }}>
            <CallHistory 
              history={displayData?.history} 
              selectedSessionId={selectedSessionId} 
              config={config}
            />
          </div>
        );
      case 'vault':
        return (
          <div className="premium-page-container animate-slide-up" style={{ padding: '32px' }}>
            <Vault />
          </div>
        );
      case 'manifest':
        return <ManifestDebugger />;
      case 'settings':
        return (
          <div className="premium-page-container animate-slide-up" style={{ padding: '32px' }}>
            <Settings />
          </div>
        );
      case 'security':
        return (
          <div className="premium-page-container animate-slide-up" style={{ padding: '32px' }}>
            <Security />
          </div>
        );
      default:
        return (
          <GlassCard title={activeTab.toUpperCase()}>
            <div className="placeholder-content">Module under construction.</div>
          </GlassCard>
        );
    }
  };

  if (loading) return <div className="loading-screen">INITIALIZING GATEWAY...</div>;

  return (
    <>
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      <main className="main-content">
        <header className="content-header">
          <div className="title-group">
            <span className="breadcrumb">Elemm / Gateway /</span>
            <h1>{activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}</h1>
          </div>
          <div className="controls-group">
            <select
              className="session-selector"
              value={selectedSessionId}
              onChange={(e) => setSelectedSessionId(e.target.value)}
            >
              <option value="global">Global Instance</option>
              {Object.keys(sessions).map(sid => (
                <option key={sid} value={sid}>Session: {sid}</option>
              ))}
            </select>
            <button className="btn-secondary" onClick={handleReset}>Clear Logs</button>
          </div>
        </header>
        <div className="flex-1 min-h-0 flex flex-col">
          {renderContent()}
        </div>
      </main>
    </>
  );
}


const StatItem = ({ label, value, tooltip }) => (
  <div className="stat-item">
    <div className="stat-label">
      {label}
      <Tooltip text={tooltip} />
    </div>
    <span className="stat-value">{value}</span>
  </div>
);

export default App;
