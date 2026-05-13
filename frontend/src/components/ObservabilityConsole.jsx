import React, { useState, useMemo, useEffect, useRef } from 'react';
import { ChevronRight } from 'lucide-react';

// --- Sub-Component: Safe JSON Display with Highlighting ---
const SafeJsonDisplay = ({ data, fullSize }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  if (!data) return <span className="text-muted">N/A</span>;
  
  let displayData = data;
  let isJson = false;
  const isTruncated = fullSize && data.length < fullSize;
  
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

  const highlightJson = (json) => {
    if (typeof json !== 'string') {
      json = JSON.stringify(json, null, 2);
    }
    
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, (match) => {
      let cls = 'json-number';
      if (/^"/.test(match)) {
        if (/:$/.test(match)) cls = 'json-key';
        else cls = 'json-string';
      } else if (/true|false/.test(match)) cls = 'json-boolean';
      else if (/null/.test(match)) cls = 'json-null';
      return `<span class="${cls}">${match}</span>`;
    });
  };

  const containerStyle = isExpanded ? { maxHeight: 'none' } : { maxHeight: '300px' };

  return (
    <div className="json-container-modern-wrapper">
      <div className={`json-container-modern ${isExpanded ? 'expanded' : ''}`} style={containerStyle}>
        <pre className="json-display">
          <code dangerouslySetInnerHTML={{ __html: isJson ? highlightJson(displayData) : displayData }} />
        </pre>
      </div>
      {(isTruncated || (!isExpanded && data.length > 500)) && (
        <button className="load-more-json" onClick={() => setIsExpanded(!isExpanded)}>
          {isExpanded ? 'Show Less' : isTruncated ? `Show Full (${(fullSize/1024).toFixed(1)} KB)` : 'Show Full'}
        </button>
      )}
    </div>
  );
};

// --- Sub-Component: Tool Call Item ---
const CallItem = ({ group, children = [], depth = 0 }) => {
  const [isOpen, setIsOpen] = useState(depth === 0 ? false : true); // Child calls often auto-open
  
  const mainCall = group.find(ev => (ev.action?.startsWith('CALL:') || ev.last_action?.startsWith('CALL:')));
  const mainReturn = group.find(ev => (ev.action?.startsWith('RETURN:') || ev.last_action?.startsWith('RETURN:')));
  const displayEvent = mainCall || mainReturn || group[0];
  
  const actionName = displayEvent?.action?.replace(/^(CALL:|RETURN:)\s*/, '') || 
                     displayEvent?.last_action?.replace(/^(CALL:|RETURN:)\s*/, '') || 'Unknown';

  const duration = mainReturn?.duration_ms || group.reduce((max, ev) => Math.max(max, ev.duration_ms || 0), 0);

  // Recursive Token Aggregation (Fixed)
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

  const { ownIn, ownOut, totalIn, totalOut } = getAggregatedTokens({ group, children });
  const status = mainReturn?.status || (mainCall?.status === 'pending' ? 'pending' : 'success');

  return (
    <div className={`call-tree-node depth-${depth}`}>
      <div className={`console-call-card ${status} ${isOpen ? 'expanded' : ''}`}>
        <div className="card-header" onClick={() => setIsOpen(!isOpen)}>
          <div className="header-left">
            <div className="status-indicator-dot"></div>
            <span className="time">{displayEvent?.timestamp ? new Date(displayEvent.timestamp * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) : '--:--:--'}</span>
            <span className="action-title">
              {depth > 0 && <span className="step-index-pill">{actionName.match(/Step (\d+):/)?.[1] || depth}</span>}
              {actionName.replace(/Step \d+: /, '')}
            </span>
          </div>
          <div className="header-right">
            {duration > 0 && (
              <div className="duration-tag" title="Execution Time">
                {duration}ms
              </div>
            )}
            <div className="token-pills-modern">
              <div className="t-pill in" title={`Own: ${ownIn} / Total: ${totalIn}`}>
                <span className="t-label">IN</span>
                <span className="t-value">{totalIn.toLocaleString()}</span>
              </div>
              <div className="t-pill out" title={`Own: ${ownOut} / Total: ${totalOut}`}>
                <span className="t-label">OUT</span>
                <span className="t-value">{totalOut.toLocaleString()}</span>
              </div>
            </div>
            <span className={`status-badge-modern ${status}`}>{status}</span>
            <span className={`chevron-modern ${isOpen ? 'open' : ''}`}>
              <ChevronRight size={16} />
            </span>
          </div>
        </div>

        {isOpen && (
          <div className="card-body animate-fade-in">
            {/* Payload Breakdown */}
            <div className={`payload-section ${children.length > 0 ? 'sequence-sub-info' : ''}`}>
              <div className="payload-box">
                <label>Arguments / Input {totalIn > ownIn && <span className="overhead-label">(Local: {ownIn})</span>}</label>
                <SafeJsonDisplay data={mainCall?.input} fullSize={mainCall?.full_size} />
              </div>
              <div className="payload-box">
                <label>Result / Output {totalOut > ownOut && <span className="overhead-label">(Local: {ownOut})</span>}</label>
                <SafeJsonDisplay data={mainReturn?.output} fullSize={mainReturn?.full_size} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Recursive Children Rendering (Timeline Mode) */}
      {isOpen && children.length > 0 && (
        <div className="nested-calls-container">
          <div className="tree-line-vertical"></div>
          {children.map((child, idx) => (
            <CallItem 
              key={child.id} 
              group={child.group} 
              children={child.children} 
              depth={depth + 1} 
            />
          ))}
        </div>
      )}
    </div>
  );
};

// --- Main Console Component ---
const ObservabilityConsole = ({ history, trace, selectedSessionId }) => {
  const scrollRef = useRef(null);

  // Grouping Logic for History (Enhanced with Recursive Tree Support)
  const groupedHistory = useMemo(() => {
    if (!history) return [];
    const filtered = history.filter(ev => 
       ev.action !== "Gateway Initialized" && 
       (selectedSessionId === 'global' || ev.session_id === selectedSessionId)
    );
    
    const groupsMap = new Map(); // requestId -> array of events
    const childrenMap = new Map(); // parentRequestId -> array of groupIds

    // 1. Group events by request_id
    filtered.forEach((ev) => {
      if (ev.request_id) {
        if (!groupsMap.has(ev.request_id)) groupsMap.set(ev.request_id, []);
        groupsMap.get(ev.request_id).push(ev);
        
        if (ev.parent_request_id) {
          if (!childrenMap.has(ev.parent_request_id)) childrenMap.set(ev.parent_request_id, new Set());
          childrenMap.get(ev.parent_request_id).add(ev.request_id);
        }
      }
    });

    // 2. Identify Root Groups (those that don't have a parent in THIS set)
    const allGroupIds = Array.from(groupsMap.keys());
    const childGroupIds = new Set();
    childrenMap.forEach(ids => ids.forEach(id => childGroupIds.add(id)));
    
    const rootIds = allGroupIds.filter(id => !childGroupIds.has(id));

    // 3. Build recursive structure
    const buildTree = (id) => {
      const group = groupsMap.get(id);
      const childIds = Array.from(childrenMap.get(id) || []);
      return {
        id,
        group,
        children: childIds.map(cid => buildTree(cid)).sort((a,b) => a.group[0].timestamp - b.group[0].timestamp)
      };
    };

    const results = rootIds.map(id => buildTree(id));
    return results.sort((a,b) => b.group[0].timestamp - a.group[0].timestamp);
  }, [history, selectedSessionId]);

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
