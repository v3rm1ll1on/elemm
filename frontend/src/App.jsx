import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import GlassCard from './components/GlassCard';
import Tooltip from './components/Tooltip';
import ObservabilityConsole from './components/ObservabilityConsole';
import TokenAnalyzer from './components/TokenAnalyzer';
import { Activity, Shield, Cpu, Zap } from 'lucide-react';
import Settings from './components/Settings';
import Security from './components/Security';
import Vault from './components/Vault';
import ManifestDebugger from './components/ManifestDebugger';
import MCPSettings from './components/MCPSettings';
import './App.css';
import './Layout.css';
import { API_BASE, WS_BASE } from './config';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [systemStatus, setSystemStatus] = useState(null);
  const [sessions, setSessions] = useState({});
  const [selectedSessionId, setSelectedSessionId] = useState('global');
  const [vaultSummary, setVaultSummary] = useState([]);
  const [traceEvents, setTraceEvents] = useState([]);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isOnline, setIsOnline] = useState(false);

  // WebSocket for Real-Time Streaming
  useEffect(() => {
    let ws;
    let reconnectTimeout;
    let startTimeout;
    let isMounted = true;

    const connectWS = () => {
      if (!isMounted) return;
      ws = new WebSocket(`${WS_BASE}/ws/trace`);

      ws.onopen = () => { 
        if (isMounted) {
          console.log("WS connected"); 
          setIsOnline(true);
        }
      };
      
      ws.onerror = () => {
        if (isMounted) {
          setIsOnline(false);
        }
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        const data = JSON.parse(event.data);
        
        if (data.type === 'status_update') {
          setSystemStatus(prev => ({ ...prev, ...data }));
          if (data.sessions) {
            setSessions(data.sessions);
          }
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
        if (isMounted) {
          setIsOnline(false);
          reconnectTimeout = setTimeout(connectWS, 3000);
        }
      };
    };

    // Delay connection slightly to avoid React 18 StrictMode double-instantiation errors
    startTimeout = setTimeout(connectWS, 100);

    const initFetch = async () => {
      try {
        const [sRes, vRes, sessRes, cRes] = await Promise.all([
          fetch(`${API_BASE}/api/v1/status`),
          fetch(`${API_BASE}/api/v1/vault/summary`),
          fetch(`${API_BASE}/api/v1/sessions`),
          fetch(`${API_BASE}/api/v1/config`)
        ]);
        if (!isMounted) return;
        setSystemStatus(await sRes.json());
        setVaultSummary(await vRes.json());
        setSessions(await sessRes.json());
        setConfig(await cRes.json());
      } catch (e) { if (isMounted) console.error("Init failed", e); }
      finally { if (isMounted) setLoading(false); }
    };
    initFetch();

    return () => {
      isMounted = false;
      clearTimeout(startTimeout);
      clearTimeout(reconnectTimeout);
      if (ws) {
        ws.onerror = null;
        ws.onclose = null;
        ws.close();
      }
    };
  }, []);

  const handleReset = async () => {
    try {
      await fetch(`${API_BASE}/api/v1/reset`, { method: 'POST' });
      setTraceEvents([]); 
      
      // Sofortiges Re-Fetch der Daten, damit die UI leer ist
      const [sRes, sessRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/status`),
        fetch(`${API_BASE}/api/v1/sessions`)
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
      case 'tokens':
        return <TokenAnalyzer />;
      case 'vault':
        return (
          <div className="premium-page-container animate-slide-up custom-scrollbar" style={{ padding: '32px', overflowY: 'auto' }}>
            <Vault />
          </div>
        );
      case 'manifest':
        return (
          <ManifestDebugger 
            sessions={sessions} 
            selectedSession={selectedSessionId === 'global' ? (Object.keys(sessions).length > 0 ? Object.keys(sessions)[0] : null) : selectedSessionId} 
            setSelectedSession={setSelectedSessionId} 
          />
        );
      case 'settings':
        return (
          <div className="premium-page-container animate-slide-up custom-scrollbar" style={{ padding: '32px', overflowY: 'auto' }}>
            <Settings />
          </div>
        );
      case 'security':
        return (
          <div className="premium-page-container animate-slide-up custom-scrollbar" style={{ padding: '32px', overflowY: 'auto' }}>
            <Security />
          </div>
        );
      case 'mcp':
        return (
          <div className="premium-page-container animate-slide-up" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
            <MCPSettings />
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
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} isOnline={isOnline} />
      <main className="main-content">
        <header className="content-header">
          <div className="title-group">
            <span className="breadcrumb">Elemm / Gateway /</span>
            <h1>{activeTab === 'mcp' ? 'MCP Servers' : activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}</h1>
          </div>
          {(activeTab === 'dashboard' || activeTab === 'manifest') && (
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
              {activeTab === 'dashboard' && (
                <button className="btn-secondary" onClick={handleReset}>Reset Stats</button>
              )}
            </div>
          )}
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
