import React, { useState, useMemo } from 'react';
import './CallHistory.css';

const formatTraffic = (tokens, chars, config) => {
  const displayMode = config?.ui?.display_mode || 'tokens';
  const formatNum = (n) => n > 999 ? (n/1000).toFixed(1) + 'k' : n;
  
  if (displayMode === 'chars') return `${formatNum(chars)} ch`;
  if (displayMode === 'both') return `${formatNum(tokens)}t (${formatNum(chars)}c)`;
  return formatNum(tokens);
};

const CallHistoryItem = ({ group, config }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Find events
  const mainCall = group.find(ev => ev.action?.startsWith('CALL:'));
  const mainReturn = group.find(ev => ev.action?.startsWith('RETURN:'));
  const steps = group.filter(ev => ev.action?.startsWith('Sequence Step')).sort((a, b) => {
    const aNum = parseInt(a.action.match(/\d+/) || 0);
    const bNum = parseInt(b.action.match(/\d+/) || 0);
    return aNum - bNum;
  });

  // Fallback for title if mainCall is missing
  const displayEvent = mainCall || mainReturn || group[0];
  const baseAction = displayEvent.action?.replace(/^(CALL:|RETURN:)\s*/, '') || 'Unknown Action';
  const status = mainReturn?.status || (mainCall?.status === 'pending' ? 'pending' : 'success');
  
  const tokensIn = group.reduce((sum, ev) => sum + (ev.tokens_in || 0), 0);
  const tokensOut = group.reduce((sum, ev) => sum + (ev.tokens_out || 0), 0);
  const charsIn = group.reduce((sum, ev) => sum + (ev.chars_in || 0), 0);
  const charsOut = group.reduce((sum, ev) => sum + (ev.chars_out || 0), 0);

  if (!displayEvent.request_id && group.length === 1 && !displayEvent.action?.includes(':')) {
     // Skip system initialization or noise events that aren't tool calls
     return null;
  }

  return (
    <div className={`call-group-item glass ${status}`}>
      <div className="call-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="call-main-info">
          <span className="call-time">{new Date(displayEvent.timestamp * 1000).toLocaleTimeString()}</span>
          <div className="action-wrapper">
            <span className="call-action-name">{baseAction}</span>
            <span className="request-id-badge">{displayEvent.request_id ? `ID: ${displayEvent.request_id}` : 'LEGACY'}</span>
          </div>
        </div>
        
        <div className="call-status-info">
          <div className="call-traffic">
            <span className="in">↓ {formatTraffic(tokensIn, charsIn, config)}</span>
            <span className="out">↑ {formatTraffic(tokensOut, charsOut, config)}</span>
          </div>
          <div className={`status-pill ${status}`}>
            {status}
          </div>
          <span className={`expand-icon ${isExpanded ? 'open' : ''}`}>▼</span>
        </div>
      </div>

      {isExpanded && (
        <div className="call-details-expanded">
          <div className="payload-grid">
            <div className="payload-box">
              <label>Input Arguments</label>
              <pre><code>{mainCall ? (typeof mainCall.input === 'object' ? JSON.stringify(mainCall.input, null, 2) : mainCall.input) : 'No input captured'}</code></pre>
            </div>
            <div className="payload-box">
              <label>Output Result</label>
              <pre><code>{mainReturn ? (typeof mainReturn.output === 'object' ? JSON.stringify(mainReturn.output, null, 2) : mainReturn.output) : (status === 'pending' ? 'Executing...' : 'No output captured')}</code></pre>
            </div>
          </div>

          {steps.length > 0 && (
            <div className="internal-steps-section">
              <label className="section-label">Execution Trace ({steps.length} steps)</label>
              <div className="steps-timeline">
                {steps.map((step, idx) => (
                  <div key={idx} className="step-row">
                    <span className="step-indicator"></span>
                    <div className="step-content">
                      <div className="step-header">
                        <span className="step-name">{step.action}</span>
                        <span className={`step-status-pill ${step.status}`}>{step.status}</span>
                      </div>
                      <div className="step-io-preview">
                        {step.input && <span className="preview-item">IN: {JSON.stringify(step.input).slice(0, 100)}...</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="call-footer-meta">
            <span>Session: {displayEvent.session_id}</span>
            {mainReturn && mainCall && <span>Duration: {((mainReturn.timestamp - mainCall.timestamp) * 1000).toFixed(0)}ms</span>}
          </div>
        </div>
      )}
    </div>
  );
};

const CallHistory = ({ history, selectedSessionId, config }) => {
  const groups = useMemo(() => {
    if (!history) return [];
    
    const filtered = history
      .filter(ev => ev.action !== "Gateway Initialized")
      .filter(ev => selectedSessionId === 'global' || ev.session_id === selectedSessionId);
      
    const groupedMap = new Map();
    
    filtered.forEach((ev, idx) => {
      // Group by request_id. If no request_id, treat as single-event group but mark as legacy
      const key = ev.request_id || `legacy-${idx}`;
      if (!groupedMap.has(key)) {
        groupedMap.set(key, []);
      }
      groupedMap.get(key).push(ev);
    });
    
    return Array.from(groupedMap.values()).sort((a, b) => b[0].timestamp - a[0].timestamp);
  }, [history, selectedSessionId]);

  if (groups.length === 0) {
    return <div className="placeholder-empty">No secure protocol activity recorded.</div>;
  }

  return (
    <div className="call-history-container">
      {groups.map((group, i) => (
        <CallHistoryItem key={group[0].request_id || i} group={group} config={config} />
      ))}
    </div>
  );
};

export default CallHistory;
