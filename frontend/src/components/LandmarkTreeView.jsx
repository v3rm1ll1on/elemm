import React, { useState } from 'react';
import {
  ChevronRight,
  Terminal,
  Folder,
  FolderOpen,
  RefreshCw,
  Home,
  Database,
  Globe,
  Layers,
  BookOpen,
  Link as LinkIcon,
  Plus
} from 'lucide-react';

const LandmarkTreeView = ({
  sessions,
  selectedSession,
  onSessionChange,
  treeData,
  selectedLandmark,
  onSelectLandmark,
  expandedNodes,
  onToggleExpand,
  loading,
  onReload,
  onReset,
  probedLandmarks,
  onManualConnect
}) => {
  const [manualUrl, setManualUrl] = useState('');

  const handleConnect = (e) => {
    e.preventDefault();
    if (manualUrl.trim()) {
      onManualConnect(manualUrl.trim());
      setManualUrl('');
    }
  };

  const renderTreeNodes = (nodes, depth = 0) => {
    return Object.values(nodes).map(node => {
      const hasChildren = Object.keys(node.children).length > 0;
      const isExpanded = expandedNodes[node.id];
      const isSelected = selectedLandmark === node.id;
      
      // Aggressive candidate detection for probing
      const isLazyCandidate = !node.isTool && (
        node.isTruncated || 
        !hasChildren || 
        node.id.split(':').length < 5
      );

      return (
        <div key={node.id}>
          <div
            className={`ide-tree-row ${isSelected ? 'selected' : ''}`}
            style={{ paddingLeft: `${depth * 16 + 8}px` }}
            onClick={() => onSelectLandmark(node.id)}
          >
            <div
              className={`ide-tree-chevron ${isExpanded ? 'expanded' : ''} ${(!hasChildren && !isLazyCandidate) ? 'hidden' : ''}`}
              onClick={(e) => {
                e.stopPropagation();
                onToggleExpand(node.id, hasChildren, node.isTool, node.isTruncated);
              }}
            >
              <ChevronRight size={14} />
            </div>

            <div className={`ide-tree-icon ${node.isTool ? 'tool' : 'area'}`}>
              {node.isTool ? (
                <Terminal size={14} />
              ) : (
                isExpanded && hasChildren ? <FolderOpen size={14} /> : <Folder size={14} />
              )}
            </div>

            {(() => {
              const cacheKey = `${selectedSession}_${node.id}`;
              const isFullyProbed = node.isTool || (hasChildren && !node.isTruncated) || probedLandmarks[cacheKey];
              const textClass = isFullyProbed ? 'bold' : 'dimmed';
              return (
                <span className={`ide-tree-text ${textClass}`}>{node.label}</span>
              );
            })()}

            {loading && isExpanded && !hasChildren && (
              <RefreshCw size={12} className="spin opacity-40 ml-2" />
            )}
          </div>
          {hasChildren && isExpanded && (
            <div className="ide-tree-children">
              <div className="ide-tree-indent-guide" style={{ left: `${depth * 16 + 23}px` }}></div>
              {renderTreeNodes(node.children, depth + 1)}
            </div>
          )}
        </div>
      );
    });
  };

  return (
    <div className="console-panel stream-panel flex flex-col" style={{ height: '100%', maxHeight: '100%', minHeight: 0, overflow: 'hidden' }}>
      <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Globe size={16} className="text-accent" />
          <h3 style={{ margin: 0 }}>City Topology</h3>
          {(() => {
            const type = sessions[selectedSession]?.site_type;
            if (type === 'openapi') {
              return <span className="topology-badge" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#34d399' }}>OpenAPI</span>;
            } else if (type === 'graphql') {
              return <span className="topology-badge" style={{ background: 'rgba(236, 72, 153, 0.2)', color: '#f472b6' }}>GraphQL</span>;
            } else if (type === 'elemm') {
              return <span className="topology-badge" style={{ background: 'rgba(56, 189, 248, 0.2)', color: '#7dd3fc' }}>Native Elemm</span>;
            }
            return null;
          })()}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <button className="toolbar-icon-btn" onClick={() => onSelectLandmark('instructions')} title="Reset Browsing to Root">
            <Home size={14} />
          </button>
          <button className={`toolbar-icon-btn ${loading ? 'spin' : ''}`} onClick={() => onReload()} title="Force Reload Topology">
            <RefreshCw size={14} />
          </button>
          <button
            className="toolbar-icon-btn"
            style={{ color: 'var(--accent-blue)', borderColor: 'var(--accent-blue)' }}
            onClick={() => onReset()}
            title="Clear Memory Bank & Reset State"
          >
            <Database size={14} />
          </button>
        </div>
      </div>

      <div className="px-4 py-3 border-b border-white/5">
        {/* Manual Connect Bar */}
        <form onSubmit={handleConnect} className="manual-connect-form">
          <div className="manual-connect-input-wrapper">
            <LinkIcon size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-white/30" />
            <input 
              type="text" 
              className="manual-connect-input"
              placeholder="Connect to URL..."
              value={manualUrl}
              onChange={(e) => setManualUrl(e.target.value)}
            />
          </div>
          <button 
            type="submit"
            className="manual-connect-btn"
            title="Connect & Inspect"
          >
            <Plus size={14} />
          </button>
        </form>

        <div className="session-picker-container">
          <label className="session-picker-label">Active Connection</label>
          <select
            value={selectedSession || ''}
            onChange={(e) => onSessionChange(e.target.value)}
            className="session-picker-select"
          >
            {Object.entries(sessions).map(([sid, sessionData]) => {
              const urlLabel = sessionData?.active_url ? sessionData.active_url : `Session: ${sid.substring(0, 8)}`;
              return <option key={sid} value={sid}>{urlLabel}</option>;
            })}
            {Object.keys(sessions).length === 0 && <option value="">No active sites found</option>}
          </select>
        </div>
      </div>

      <div className="custom-scrollbar bg-black/20 pb-4" style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        <div className="tree-container">
          {/* Protocol Rules as the first "Node" in the tree */}
          <div
            className={`ide-tree-row ${selectedLandmark === 'instructions' ? 'selected' : ''}`}
            style={{ paddingLeft: '8px' }}
            onClick={() => onSelectLandmark('instructions')}
          >
            <div className="ide-tree-chevron hidden"><ChevronRight size={14} /></div>
            <div className="ide-tree-icon rules"><BookOpen size={14} /></div>
            <span className="ide-tree-text bold">Protocol Rules</span>
          </div>

          {renderTreeNodes(treeData)}
        </div>
      </div>
    </div>
  );
};

export default LandmarkTreeView;
