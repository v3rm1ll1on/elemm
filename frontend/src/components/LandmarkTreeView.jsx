import React, { useState, memo } from 'react';
import './LandmarkTreeView.css';
import {
  ChevronRight,
  Terminal,
  Folder,
  FolderOpen,
  RefreshCw,
  Home,
  Database,
  Globe,
  BookOpen,
  Link as LinkIcon,
  Plus,
  Search,
  Activity
} from 'lucide-react';

// --- Sub-Components ---

const TreeNode = memo(({ 
  node, 
  depth, 
  isSelected, 
  isExpanded, 
  isProbed,
  onSelect, 
  onToggle, 
  loading,
  children 
}) => {
  const hasChildren = Object.keys(node.children).length > 0;
  
  // Logic: When should we show a chevron even if there are no children yet? (Lazy Loading)
  const isLazyCandidate = !node.isTool && (node.isTruncated || !hasChildren);

  return (
    <div className="tree-node-wrapper">
      <div
        className={`tree-node-row ${isSelected ? 'selected' : ''}`}
        style={{ paddingLeft: `${depth * 16 + 12}px` }}
        onClick={() => onSelect(node.id)}
      >
        <div
          className={`chevron-icon ${isExpanded ? 'expanded' : ''} ${(!hasChildren && !isLazyCandidate) ? 'invisible' : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggle(node.id, hasChildren, node.isTool, node.isTruncated);
          }}
        >
          <ChevronRight size={14} />
        </div>

        <div className={`node-icon ${node.isTool ? 'tool' : 'area'}`}>
          {node.isTool ? <Terminal size={12} /> : (isExpanded && hasChildren ? <FolderOpen size={13} /> : <Folder size={13} />)}
        </div>

        <span className={`node-text ${!isProbed ? 'dimmed' : ''}`}>
          {node.label}
        </span>

        {loading && isExpanded && !hasChildren && (
          <RefreshCw size={10} className="spin-icon opacity-40" />
        )}
      </div>
      
      {isExpanded && (hasChildren || (loading && !node.isTool)) && (
        <div className="node-children">
          <div className="indent-guide" style={{ left: `${depth * 16 + 20}px` }}></div>
          {children}
        </div>
      )}
    </div>
  );
});

// --- Main Explorer Component ---

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
  onManualConnect,
  searchQuery,
  onSearch,
  searchResults
}) => {
  const [manualUrl, setManualUrl] = useState('');

  const handleConnect = (e) => {
    e.preventDefault();
    if (manualUrl.trim()) {
      onManualConnect(manualUrl.trim());
      setManualUrl('');
    }
  };

  const getSessionBadge = () => {
    const type = sessions[selectedSession]?.site_type;
    const styles = {
      openapi: { label: 'OpenAPI', color: '#34d399' },
      graphql: { label: 'GraphQL', color: '#f472b6' },
      elemm: { label: 'Elemm Native', color: '#7dd3fc' },
      native: { label: 'Elemm Native', color: '#7dd3fc' }
    };
    const config = styles[type] || { label: 'Unknown', color: '#94a3b8' };
    return <span className="badge-micro" style={{ color: config.color }}>{config.label}</span>;
  };

  const renderNodes = (nodes, depth = 0) => {
    return Object.values(nodes).map(node => {
      const cacheKey = `${selectedSession}_${node.id}`;
      const isProbed = node.isTool || (Object.keys(node.children).length > 0 && !node.isTruncated) || probedLandmarks[cacheKey];
      
      return (
        <TreeNode
          key={node.id}
          node={node}
          depth={depth}
          isSelected={selectedLandmark === node.id}
          isExpanded={expandedNodes[node.id]}
          isProbed={isProbed}
          onSelect={onSelectLandmark}
          onToggle={onToggleExpand}
          loading={loading}
        >
          {renderNodes(node.children, depth + 1)}
        </TreeNode>
      );
    });
  };

  return (
    <div className="tree-explorer-container">
      {/* Header Section */}
      <div className="explorer-header">
        <div className="explorer-title-row">
          <div className="explorer-title">
            <Activity size={16} className="text-accent" />
            <span>Landmark Explorer</span>
          </div>
          <div className="explorer-toolbar">
            <button className="tool-btn" onClick={() => onSelectLandmark('instructions')} title="Go Home">
              <Home size={14} />
            </button>
            <button className={`tool-btn ${loading ? 'active' : ''}`} onClick={onReload} title="Refresh">
              <RefreshCw size={14} className={loading ? 'spin-icon' : ''} />
            </button>
            <button className="tool-btn" onClick={onReset} title="Reset Protocol State">
              <Database size={14} />
            </button>
          </div>
        </div>

        {/* URL / Connection Bar */}
        <form onSubmit={handleConnect} className="connect-bar">
          <div className="connect-input-wrapper">
            <LinkIcon size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-white/20" />
            <input 
              type="text" 
              className="connect-input"
              placeholder="https://api.example.com..."
              value={manualUrl}
              onChange={(e) => setManualUrl(e.target.value)}
            />
          </div>
          <button type="submit" className="connect-btn">
            <Plus size={16} />
          </button>
        </form>

        {/* Search Bar */}
        <div className="search-bar">
          <div className="search-input-wrapper">
            <Search size={12} className={`search-icon ${searchQuery ? 'active' : ''}`} />
            <input 
              type="text" 
              className="search-input"
              placeholder="Search landmarks (Regex)..."
              value={searchQuery || ''}
              onChange={(e) => onSearch(e.target.value)}
            />
            {searchQuery && (
              <button className="clear-search" onClick={() => onSearch('')}>
                <Plus size={14} style={{ transform: 'rotate(45deg)' }} />
              </button>
            )}
          </div>
        </div>

        {/* Session Selection */}
        <div className="active-session-card">
          <div className="flex justify-between items-center mb-1">
            <label className="session-label">Active Connection</label>
            {getSessionBadge()}
          </div>
          <select
            value={selectedSession || ''}
            onChange={(e) => onSessionChange(e.target.value)}
            className="session-select"
          >
            {Object.entries(sessions).map(([sid, data]) => (
              <option key={sid} value={sid}>
                {data?.active_url ? data.active_url.replace(/^https?:\/\//, '') : `Session ${sid.substring(0, 6)}`}
              </option>
            ))}
            {Object.keys(sessions).length === 0 && <option value="">Awaiting site link...</option>}
          </select>
        </div>
      </div>

      {/* Tree Content */}
      <div className="tree-scroller custom-scrollbar">
        {!searchQuery && (
          <div 
            className={`tree-node-row ${selectedLandmark === 'instructions' ? 'selected' : ''}`}
            onClick={() => onSelectLandmark('instructions')}
          >
            <div className="chevron-icon invisible"><ChevronRight size={14} /></div>
            <div className="node-icon rules"><BookOpen size={13} /></div>
            <span className="node-text bold">Protocol Rules</span>
          </div>
        )}

        {searchQuery ? (
          <div className="search-results-list">
            <div className="search-results-header">
              Search Results ({searchResults?.length || 0})
            </div>
            {searchResults && searchResults.length > 0 ? (
              searchResults.map(lm => (
                <div 
                  key={lm.id}
                  className={`tree-node-row search-result ${selectedLandmark === lm.id ? 'selected' : ''}`}
                  onClick={() => onSelectLandmark(lm.id)}
                  style={{ paddingLeft: '12px' }}
                >
                  <div className="node-icon tool"><Terminal size={12} /></div>
                  <div className="search-result-info">
                    <div className="node-text">{lm.name || lm.id}</div>
                    <div className="node-description-micro">{lm.description}</div>
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-search">
                <Search size={24} className="opacity-10 mb-2" />
                <span>No landmarks matched your query</span>
              </div>
            )}
          </div>
        ) : (
          renderNodes(treeData)
        )}
      </div>
    </div>
  );
};

export default LandmarkTreeView;
