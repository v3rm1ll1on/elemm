import React, { useState, useMemo, useEffect, useRef } from 'react';
import { ChevronRight, Database, Copy, Check } from 'lucide-react';

// --- Sub-Component: Safe JSON Display with Highlighting ---
const SafeJsonDisplay = ({ data, fullSize }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  if (!data) return <span className="text-muted">N/A</span>;
  
  let displayData = data;
  let isJson = false;
  
  if (typeof data === 'string') {
    try {
      const cleaned = data.trim();
      if ((cleaned.startsWith('{') || cleaned.startsWith('['))) {
        displayData = JSON.parse(cleaned);
        isJson = true;
      }
    } catch (e) {}
  } else if (typeof data === 'object') {
    isJson = true;
  }

  const handleCopy = (e) => {
    e.stopPropagation();
    const textToCopy = isJson ? JSON.stringify(displayData, null, 2) : String(data);
    navigator.clipboard.writeText(textToCopy).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const highlightJson = (obj) => {
    const json = JSON.stringify(obj, null, 2);
    return json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, (match) => {
        let cls = 'json-number';
        if (/^"/.test(match)) {
          if (/:$/.test(match)) cls = 'json-key';
          else cls = 'json-string';
        } else if (/true|false/.test(match)) cls = 'json-boolean';
        else if (/null/.test(match)) cls = 'json-null';
        return `<span class="${cls}">${match}</span>`;
      });
  };

  const renderFormattedText = (text) => {
    if (!text) return '';
    // Basic Markdown/Code highlighting for strings
    let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    // Highlight Code Blocks (``` ... ```)
    html = html.replace(/```(?:typescript|json|javascript)?([\s\S]*?)```/g, (match, code) => {
      return `<div class="embedded-code-block">${code.trim()}</div>`;
    });

    // Highlight Inline Headers (### ...)
    html = html.replace(/^(#{1,6})\s+(.*)$/gm, (match, hashes, content) => {
      const level = hashes.length;
      return `<div class="md-header h${level}">${content}</div>`;
    });

    // Highlight Bold (** ... **)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    return html;
  };

  return (
    <div className="json-container-modern-wrapper">
      <button className={`copy-json-btn ${copied ? 'copied' : ''}`} onClick={handleCopy} title="Copy to clipboard">
        {copied ? <Check size={12} /> : <Copy size={12} />}
        <span>{copied ? 'COPIED' : 'COPY'}</span>
      </button>

      <div className={`json-container-modern ${isExpanded ? 'expanded' : ''}`}>
        {isJson ? (
          <pre className="json-display" dangerouslySetInnerHTML={{ __html: highlightJson(displayData) }} />
        ) : (
          <div className="json-display markdown-body" dangerouslySetInnerHTML={{ __html: renderFormattedText(String(data)) }} />
        )}
      </div>
      {(fullSize || JSON.stringify(displayData).length > 500) && (
        <button className="show-full-btn" onClick={() => setIsExpanded(!isExpanded)}>
          {isExpanded ? 'SHOW LESS' : fullSize ? `SHOW FULL (${(fullSize/1024).toFixed(1)} KB)` : 'SHOW FULL'}
        </button>
      )}
    </div>
  );
};

// --- Sub-Component: Tool Call Item ---
const CallItem = ({ group, children = [], depth = 0 }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [showPayload, setShowPayload] = useState(false);
  
  const mainCall = group.find(ev => (ev.action?.startsWith('CALL:') || ev.last_action?.startsWith('CALL:')));
  const mainReturn = group.find(ev => (ev.action?.startsWith('RETURN:') || ev.last_action?.startsWith('RETURN:')));
  const displayEvent = mainCall || mainReturn || group[0];
  
  const actionName = displayEvent?.action?.replace(/^(CALL:|RETURN:)\s*/, '') || 
                     displayEvent?.last_action?.replace(/^(CALL:|RETURN:)\s*/, '') || 'Unknown';

  const duration = mainReturn?.duration_ms || group.reduce((max, ev) => Math.max(max, ev.duration_ms || 0), 0);

  // Recursive Token Aggregation
  const getAggregatedTokens = (node) => {
    const nodeGroup = node.group || [];
    const nodeChildren = node.children || [];
    
    let ownIn = nodeGroup.reduce((sum, ev) => sum + (ev.tokens_in || 0), 0);
    let ownOut = nodeGroup.reduce((sum, ev) => sum + (ev.tokens_out || 0), 0);
    
    let totalIn = ownIn;
    let totalOut = ownOut;
    
    nodeChildren.forEach(child => {
      const childTokens = getAggregatedTokens(child);
      totalIn += childTokens.totalIn;
      totalOut += childTokens.totalOut;
    });
    
    return { ownIn, ownOut, totalIn, totalOut };
  };

  const getToolTheme = (name) => {
    if (name.includes('execute_sequence')) return 'theme-sequence';
    if (name.includes('call_action')) return 'theme-action';
    if (name.includes('inspect') || name.includes('manifest')) return 'theme-discovery';
    return 'theme-default';
  };

  const toolTheme = getToolTheme(actionName);
  
  const formatActionTitle = (name) => {
    const match = name.match(/\(([^)]+)\)/);
    if (match) {
      const base = name.split('(')[0];
      return <>{base}(<strong>{match[1]}</strong>)</>;
    }
    return name;
  };

  // Consolidate data from all events in the group
  const input = group.find(ev => ev.input !== undefined && ev.input !== null)?.input;
  const output = group.find(ev => ev.output !== undefined && ev.output !== null)?.output;
  const fullSize = mainReturn?.full_size || group.find(ev => ev.full_size)?.full_size;

  const { ownIn, ownOut, totalIn, totalOut } = getAggregatedTokens({ group, children });
  const status = mainReturn?.status || (group.find(ev => ev.status === 'error') ? 'error' : 'success');

  return (
    <div className={`call-tree-node depth-${depth} ${toolTheme}`}>
      <div className={`console-call-card ${status} ${isOpen ? 'expanded' : ''}`}>
        <div className="card-header" onClick={() => {
          const nextOpen = !isOpen;
          setIsOpen(nextOpen);
          // Smart-Logic: Öffnen ohne Kinder -> DATA an. Schließen -> DATA aus.
          if (nextOpen && children.length === 0) {
            setShowPayload(true);
          } else if (!nextOpen) {
            setShowPayload(false);
          }
        }}>
          <div className="header-left">
            <div className="status-indicator-dot"></div>
            <span className="time">{displayEvent?.timestamp ? new Date(displayEvent.timestamp * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) : '--:--:--'}</span>
            <span className="action-title">
              {depth > 0 && <span className="step-index-pill">{actionName.match(/Step (\d+):/)?.[1] || depth}</span>}
              {formatActionTitle(actionName.replace(/Step \d+: /, ''))}
            </span>
          </div>
          
          <div className="header-right">
            <div className="meta-group">
              {duration > 0 && <div className="duration-tag">{duration}ms</div>}
              {displayEvent?.request_id && (
                <div className="request-id-tag" title={`Full ID: ${displayEvent.request_id}`}>
                  ID: {displayEvent.request_id.substring(0, 8)}
                </div>
              )}
            </div>

            <div className="metrics-group">
              {children.length > 0 && (
                <button 
                  className={`payload-toggle ${showPayload ? 'active' : ''}`}
                  onClick={(e) => { e.stopPropagation(); setShowPayload(!showPayload); }}
                  title="Toggle Input/Output Data"
                >
                  <Database size={12} />
                  <span>DATA</span>
                </button>
              )}
              
              <div className="token-pills-modern">
                <div className="t-pill in" title={`Own: ${ownIn} | Total: ${totalIn}`}>
                  <span className="t-label">IN</span>
                  <span className="t-value">{totalIn > 999 ? (totalIn/1000).toFixed(1) + 'k' : totalIn}</span>
                </div>
                <div className="t-pill out" title={`Own: ${ownOut} | Total: ${totalOut}`}>
                  <span className="t-label">OUT</span>
                  <span className="t-value">{totalOut > 999 ? (totalOut/1000).toFixed(1) + 'k' : totalOut}</span>
                </div>
              </div>
              <span className={`status-badge-modern ${status}`}>{status}</span>
              <span className={`chevron-modern ${isOpen ? 'open' : ''}`}>
                <ChevronRight size={14} />
              </span>
            </div>
          </div>
        </div>

        {isOpen && (showPayload || children.length > 0) && (
          <div className="card-body">
            {/* Spezieller Button für Sequenz-Rohdaten, nur innerhalb des Bodies */}
            {children.length > 0 && (
              <div className="sequence-data-header">
                <button 
                  className={`sequence-data-toggle ${showPayload ? 'active' : ''}`}
                  onClick={(e) => { e.stopPropagation(); setShowPayload(!showPayload); }}
                >
                  <Database size={12} />
                  <span>{showPayload ? 'HIDE SEQUENCE JSON' : 'SHOW FULL SEQUENCE JSON'}</span>
                </button>
              </div>
            )}

            {showPayload && (
              <div className="payload-section animate-fade-in">
                <div className="payload-box">
                  <label>Arguments / Input <span className="step-duration">local: {ownIn}</span></label>
                  <div className="json-container-modern">
                    <SafeJsonDisplay data={input} />
                  </div>
                </div>
                <div className="payload-box">
                  <label>Result / Output <span className="step-duration">local: {ownOut}</span></label>
                  <div className="json-container-modern">
                    <SafeJsonDisplay data={output} fullSize={fullSize} />
                  </div>
                </div>
              </div>
            )}
            
            {children.length > 0 && (
              <div className="children-container">
                <div className="tree-line"></div>
                {children.map((child, idx) => (
                  <CallItem 
                    key={child.id || idx} 
                    group={child.group} 
                    children={child.children} 
                    depth={depth + 1}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// --- Main Console Component ---
const ObservabilityConsole = ({ history, trace, selectedSessionId }) => {
  const scrollRef = useRef(null);

  // Grouping Logic for History (Enhanced with Recursive Tree Support)
  const groupedHistory = useMemo(() => {
    if (!history || history.length === 0) return [];
    
    const nodesMap = new Map(); // requestId -> { id, group, children }
    const rootNodes = [];

    // 1. Alle Events gruppieren
    history.forEach(ev => {
      if (!ev.request_id) return;
      if (!nodesMap.has(ev.request_id)) {
        nodesMap.set(ev.request_id, { id: ev.request_id, group: [], children: [] });
      }
      nodesMap.get(ev.request_id).group.push(ev);
    });

    // 2. Hierarchie aufbauen
    nodesMap.forEach(node => {
      // Suche nach einer parent_request_id in IRGENDEINEM Event dieser Gruppe
      const parentId = node.group.find(ev => ev.parent_request_id)?.parent_request_id;
      
      if (parentId && nodesMap.has(parentId) && parentId !== node.id) {
        nodesMap.get(parentId).children.push(node);
      } else if (!parentId) {
        rootNodes.push(node);
      } else {
        // Parent existiert (noch) nicht im lokalen Set, behandle als Root
        rootNodes.push(node);
      }
    });

    return rootNodes.sort((a, b) => {
      const timeA = a.group[0]?.timestamp || 0;
      const timeB = b.group[0]?.timestamp || 0;
      return timeB - timeA;
    });
  }, [history]);

  // Grouping Logic for Live Trace (Stream)
  const groupedTrace = useMemo(() => {
    const filtered = trace.filter(ev => selectedSessionId === 'global' || ev.session_id === selectedSessionId);
    
    const map = new Map();
    const order = [];

    filtered.forEach((ev) => {
      const id = ev.request_id || `trace-${ev.timestamp}-${ev.last_action}`;
      if (!map.has(id)) {
        map.set(id, ev);
        order.push(id);
      } else {
        // Update existing entry with newer data (e.g., RETURN overwriting CALL)
        const existing = map.get(id);
        map.set(id, { ...existing, ...ev });
      }
    });

    return order.map(id => map.get(id)).slice(0, 20);
  }, [trace, selectedSessionId]);

  // Auto-scroll trace
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [groupedTrace]);

  return (
    <div className="obs-console-wrapper">
      {/* LEFT: Live Activity (Grouped) */}
      <div className="console-panel stream-panel">
        <div className="panel-header">
          <h3>Live Status</h3>
          <span className="live-indicator">ACTIVE</span>
        </div>
        <div className="panel-content scrollable" ref={scrollRef}>
          {groupedTrace.length > 0 ? groupedTrace.map((ev, i) => {
            const isReturn = ev.last_action?.startsWith('RETURN:');
            const actionName = ev.last_action?.replace(/^(CALL:|RETURN:)\s*/, '') || 'Processing...';
            
            return (
              <div key={i} className={`stream-item ${isReturn ? 'completed' : 'pending'}`}>
                <span className="time">{new Date(ev.timestamp * 1000).toLocaleTimeString([], {hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit'})}</span>
                <div className="stream-content">
                  <span className="label">{actionName}</span>
                  <span className="status-indicator">{isReturn ? '✓' : '...'}</span>
                </div>
              </div>
            );
          }) : <div className="empty-state">Awaiting protocol events...</div>}
        </div>
      </div>

      {/* RIGHT: History Payloads */}
      <div className="console-panel history-panel">
        <div className="panel-header">
          <h3>Call History</h3>
          <div className="count-badge">{groupedHistory.length} Sessions</div>
        </div>
        <div className="panel-content scrollable">
          {groupedHistory.length > 0 ? groupedHistory.map((item, i) => (
            <CallItem 
              key={item.id || i} 
              group={item.group} 
              children={item.children} 
              depth={0} 
            />
          )) : <div className="empty-state">No calls recorded.</div>}
        </div>
      </div>
    </div>
  );
};

export default ObservabilityConsole;
