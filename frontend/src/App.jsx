import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import GlassCard from './components/GlassCard';
import ObservabilityConsole from './components/ObservabilityConsole';
import CallHistory from './components/CallHistory';
import { Activity, Shield, Cpu, Zap } from 'lucide-react';
import Settings from './components/Settings';
import Vault from './components/Vault';
import ManifestInspector from './components/ManifestInspector';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [systemStatus, setSystemStatus] = useState(null);
  const [sessions, setSessions] = useState({});
  const [selectedSessionId, setSelectedSessionId] = useState('global');
  const [vaultSummary, setVaultSummary] = useState([]);
  const [traceEvents, setTraceEvents] = useState([]);
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
            tokens_out: data.global_tokens_out !== undefined ? data.global_tokens_out : prev?.tokens_out
          }));

          setSessions(prev => {
            const session = prev[sid] || { tokens_in: 0, tokens_out: 0 };
            return {
              ...prev,
              [sid]: {
                ...session,
                ...data,
                tokens_in: data.tokens_in_total !== undefined ? data.tokens_in_total : session.tokens_in,
                tokens_out: data.tokens_out_total !== undefined ? data.tokens_out_total : session.tokens_out,
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
        const [sRes, vRes, sessRes] = await Promise.all([
          fetch('http://127.0.0.1:8090/api/v1/status'),
          fetch('http://127.0.0.1:8090/api/v1/vault/summary'),
          fetch('http://127.0.0.1:8090/api/v1/sessions')
        ]);
        setSystemStatus(await sRes.json());
        setVaultSummary(await vRes.json());
        setSessions(await sessRes.json());
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
          <div className="dashboard-grid">
            <div className="stat-bar">
              <StatItem label="Uptime" value={displayData?.uptime || "Online"} />
              <StatItem label="Active Clients" value={displayData?.active_clients || 1} />
              <StatItem label="Active APIs" value={displayData?.active_sites || 0} />
              <StatItem label="Traffic In" value={(displayData?.tokens_in || 0).toLocaleString()} />
              <StatItem label="Traffic Out" value={(displayData?.tokens_out || 0).toLocaleString()} />
            </div>

            <ObservabilityConsole 
              history={displayData?.history} 
              trace={traceEvents}
              selectedSessionId={selectedSessionId} 
            />
          </div>
        );
      case 'history':
        return (
          <div className="history-view-container">
            <CallHistory 
              history={displayData?.history} 
              selectedSessionId={selectedSessionId} 
            />
          </div>
        );
      case 'vault':
        return <Vault />;
      case 'manifest':
        return <ManifestInspector />;
      case 'settings':
        return <Settings />;
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
        <div className="animate-fade-in">
          {renderContent()}
        </div>
      </main>
    </>
  );
}


const StatItem = ({ label, value }) => (
  <div className="stat-item">
    <span className="stat-label">{label}</span>
    <span className="stat-value">{value}</span>
  </div>
);

export default App;
