import React, { useState, useEffect } from 'react';
import {
  Search,
  BookOpen,
  Code,
  RefreshCw,
  AlertCircle,
  ChevronRight,
  Terminal,
  Activity,
  Home
} from 'lucide-react';

const ManifestInspector = () => {
  const [sessionManifests, setSessionManifests] = useState({});
  const [selectedSession, setSelectedSession] = useState('default');
  const [selectedLandmark, setSelectedLandmark] = useState('instructions');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sessions, setSessions] = useState({});
  const [landmarkSignatures, setLandmarkSignatures] = useState({}); // session_id -> { landmark_id -> signature }
  const [landmarkPath, setLandmarkPath] = useState([]); // List of landmark IDs
  const [expandedNodes, setExpandedNodes] = useState({}); // id -> boolean
  const [allLandmarks, setAllLandmarks] = useState({}); // session_id -> { id -> data }

  useEffect(() => {
    fetchSessions();
    const interval = setInterval(fetchSessions, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedSession && !sessionManifests[selectedSession]) {
      fetchManifest(selectedSession);
    }
  }, [selectedSession, sessionManifests[selectedSession]]);

  useEffect(() => {
    if (selectedLandmark !== 'instructions' && selectedSession) {
      const existing = landmarkSignatures[selectedSession]?.[selectedLandmark];
      if (!existing) {
        fetchLandmarkSignature(selectedSession, selectedLandmark);
      }
    }
  }, [selectedLandmark, selectedSession]);

  const fetchLandmarkSignature = async (sid, lid) => {
    try {
      const resp = await fetch(`http://127.0.0.1:8090/api/v1/inspect/landmark?landmark_id=${lid}&session_id=${sid}`);
      const data = await resp.json();
      if (data.status === 'success' && data.signature) {
        setLandmarkSignatures(prev => ({
          ...prev,
          [sid]: {
            ...(prev[sid] || {}),
            [lid]: data.signature
          }
        }));
      }
    } catch (err) {
      console.error("Failed to fetch landmark signature", err);
    }
  };

  const fetchManifest = async (sid) => {
    try {
      const resp = await fetch(`http://127.0.0.1:8090/api/v1/sessions/${sid}/manifest`);
      const data = await resp.json();
      if (data.manifest) {
        setSessionManifests(prev => ({ ...prev, [sid]: data.manifest }));
      }
    } catch (err) {
      console.error("Failed to fetch manifest", err);
    }
  };

  const fetchSessions = async () => {
    try {
      const resp = await fetch('http://127.0.0.1:8090/api/v1/sessions');
      const data = await resp.json();
      setSessions(data);
      if (!selectedSession && Object.keys(data).length > 0) {
        setSelectedSession(Object.keys(data)[0]);
      }
    } catch (err) {
      console.error("Failed to fetch sessions", err);
    }
  };

  const handleInspect = async (landmarkId = null) => {
    const session = sessions[selectedSession];
    if (!session) return;

    setLoading(true);
    setError(null);

    try {
      let url = session.active_url;
      if (!url && session.history) {
        for (const event of session.history) {
          const match = JSON.stringify(event).match(/https?:\/\/[a-zA-Z0-9][-a-zA-Z0-9+&@#/%?=~_|!:,.;]*/);
          if (match) {
            url = match[0].split('"')[0].split("'")[0];
            break;
          }
        }
      }

      if (!url) {
        const userUrl = prompt("No active connection found. Please enter URL:", "http://localhost:8010");
        if (!userUrl) { setLoading(false); return; }
        url = userUrl;
      }

      const API_BASE = "http://127.0.0.1:8090";
      const landmarkQuery = landmarkId ? `&landmark_id=${landmarkId}` : "";
      const resp = await fetch(`${API_BASE}/api/v1/inspect?url=${encodeURIComponent(url)}&session_id=${selectedSession}${landmarkQuery}`);

      if (!resp.ok) throw new Error(`Server error: ${resp.status}`);
      const data = await resp.json();

      const parsed = parseManifest(data.manifest);

      // Merge new landmarks into global store for this session
      setAllLandmarks(prev => ({
        ...prev,
        [selectedSession]: {
          ...(prev[selectedSession] || {}),
          ...parsed.landmarks
        }
      }));

      // If it was a first-time load, set instructions
      if (!landmarkId) {
        setSessionManifests(prev => ({ ...prev, [selectedSession]: data.manifest }));
      }

      // Don't switch to instructions on lazy load if we are already viewing a landmark
      if (!landmarkId) {
        setSelectedLandmark('instructions');
      }
    } catch (err) {
      console.error("Inspection error:", err);
      setError(`Inspection failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const resetBrowsing = () => {
    setLandmarkPath([]);
    setSelectedLandmark('instructions');
    // Clear sub-landmarks if we want a clean start, or keep them? 
    // Let's just reset the manifest to root.
    setSessionManifests(prev => ({ ...prev, [selectedSession]: null }));
  };

  const parseManifest = (manifestText) => {
    if (!manifestText) return { instructions: "", memoryBank: "", landmarks: {}, signatures: [] };

    const sections = {
      instructions: "",
      memoryBank: "",
      landmarks: {},
      signatures: []
    };

    const parts = manifestText.split(/### (PROTOCOL RULES|MEMORY BANK|LANDMARK TOPOLOGY|TECHNICAL SIGNATURES)[^\n]*/i);

    if (parts[0] && parts[0].trim()) {
      sections.instructions = parts[0].trim();
    }

    for (let i = 1; i < parts.length; i += 2) {
      const header = parts[i].toUpperCase();
      let content = parts[i + 1] ? parts[i + 1].trim() : "";

      if (header.includes('PROTOCOL RULES')) {
        sections.instructions = (sections.instructions ? sections.instructions + "\n\n" : "") + content;
      } else if (header.includes('MEMORY BANK')) {
        sections.memoryBank = content;
      } else if (header.includes('LANDMARK TOPOLOGY')) {
        // Match ALL formats
        const pattern = /- (?:\*\*`|Landmark: `|Tool: `)(.*?)(?:`\*\*: |` - |`|: )(.*?)(?:\n|$)/g;
        let match;
        while ((match = pattern.exec(content)) !== null) {
          const id = match[1];
          const desc = match[2] ? match[2].trim() : "Tool/Area";
          // Use a Map or Object to ensure uniqueness by ID
          sections.landmarks[id] = { description: desc };
        }
      } else if (header.includes('TECHNICAL SIGNATURES')) {
        sections.signatures = content.split('/**').filter(s => s.trim()).map(s => '/**' + s);
      }
    }

    return sections;
  };

  const buildTree = (landmarks) => {
    const root = {};
    Object.entries(landmarks).forEach(([id, data]) => {
      const parts = id.split(':');
      let current = root;
      parts.forEach((part, idx) => {
        if (!current[part]) {
          current[part] = {
            id: parts.slice(0, idx + 1).join(':'),
            label: part,
            children: {},
            description: idx === parts.length - 1 ? data.description : ""
          };
        }
        current = current[part].children;
      });
    });
    return root;
  };

  const currentManifest = sessionManifests[selectedSession];
  const parsedData = parseManifest(currentManifest);
  const sessionLandmarks = allLandmarks[selectedSession] || parsedData.landmarks;
  const treeData = buildTree(sessionLandmarks);

  const formatSignature = (sig) => {
    if (!sig) return "// No technical signature loaded for this landmark.\n// This might be a summary manifest.";

    // Simple pseudo-highlighter
    return sig.split('\n').map((line, i) => {
      let className = "text-white/80";
      if (line.includes('/**') || line.includes(' *')) className = "text-green-400/60 italic";
      if (line.includes('function')) className = "text-accent font-bold";
      if (line.includes('action:')) className = "text-accent-blue";
      if (line.includes('parameters:')) className = "text-purple-400";

      return <div key={i} className={className}>{line}</div>;
    });
  };

  const renderTreeNodes = (nodes, depth = 0) => {
    return Object.values(nodes).map(node => {
      const hasChildren = Object.keys(node.children).length > 0;
      const isExpanded = expandedNodes[node.id];
      const isSelected = selectedLandmark === node.id;

      // If a node is an "Area/Namespace" but has no children yet, 
      // it might be a candidate for lazy loading.
      const isLazyCandidate = node.description?.includes('Area/Namespace') || node.description?.includes('District') || node.id.split(':').length < 3;

      return (
        <div key={node.id} className="tree-node" style={{ marginLeft: `${depth > 0 ? 12 : 0}px` }}>
          <div
            className={`tree-row ${isSelected ? 'selected' : ''}`}
            onClick={() => {
              setSelectedLandmark(node.id);
              if (hasChildren || isLazyCandidate) {
                if (!isExpanded && (!hasChildren && isLazyCandidate)) {
                  handleInspect(node.id); // Lazy Load!
                }
                setExpandedNodes(prev => ({ ...prev, [node.id]: !prev[node.id] }));
              }
            }}
          >
            {(hasChildren || isLazyCandidate) ? (
              <ChevronRight size={14} className={`arrow ${isExpanded ? 'rotated' : ''}`} />
            ) : (
              <div className="w-3.5 h-3.5 flex items-center justify-center">
                <div className="w-1 h-1 bg-white/20 rounded-full"></div>
              </div>
            )}
            <span className="node-label">{node.label}</span>
            {loading && isExpanded && !hasChildren && (
              <RefreshCw size={10} className="spin opacity-40 ml-auto" />
            )}
          </div>
          {hasChildren && isExpanded && (
            <div className="tree-children border-l border-white/5 ml-2 pl-1">
              {renderTreeNodes(node.children, depth + 1)}
            </div>
          )}
        </div>
      );
    });
  };

  return (
    <div className="manifest-inspector glass animate-fade-in">
      {/* Sidebar Spalte */}
      <aside className="inspector-sidebar">
        <header className="sidebar-header-area">
          <div className="title-row">
            <Terminal size={18} className="text-accent" />
            <h3>Manifest Debugger</h3>
          </div>

          <div className="session-picker">
            <select
              value={selectedSession}
              onChange={(e) => setSelectedSession(e.target.value)}
            >
              {Object.keys(sessions).map(sid => (
                <option key={sid} value={sid}>Session: {sid.substring(0, 8)}</option>
              ))}
              {Object.keys(sessions).length === 0 && <option>No active sessions</option>}
            </select>
          </div>
        </header>

        <nav className="landmark-nav custom-scrollbar">
          {landmarkPath.length > 0 && (
            <div className="breadcrumbs px-4 py-2 border-b border-white/5 flex items-center gap-1 text-[10px] uppercase opacity-60">
              <span className="cursor-pointer hover:text-accent" onClick={resetBrowsing}>Root</span>
              {landmarkPath.map((p, idx) => (
                <React.Fragment key={`${p}-${idx}`}>
                  <ChevronRight size={10} />
                  <span className={idx === landmarkPath.length - 1 ? 'text-accent' : ''}>{p}</span>
                </React.Fragment>
              ))}
            </div>
          )}

          <div className="px-4 py-4 space-y-4">
            <button
              className={`nav-btn-modern ${selectedLandmark === 'instructions' ? 'active' : ''}`}
              onClick={() => setSelectedLandmark('instructions')}
            >
              <BookOpen size={16} />
              <span>Protocol Rules</span>
            </button>
          </div>

          <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-white/[0.02]">
            <label className="text-[10px] uppercase opacity-40 font-black tracking-[0.2em]">City Topology</label>
            <div className="flex gap-3">
              <button
                className="toolbar-icon-btn"
                onClick={resetBrowsing}
                title="Reset to Root"
              >
                <Home size={14} />
              </button>
              <button
                className={`toolbar-icon-btn ${loading ? 'spin' : ''}`}
                onClick={() => handleInspect(null)}
                title="Reload Manifest"
              >
                <RefreshCw size={14} />
              </button>
            </div>
          </div>
          <div className="tree-container custom-scrollbar">
            {renderTreeNodes(treeData)}
          </div>
        </nav>

        <div className="inspector-footer">
          {!currentManifest ? (
            <button
              className="btn-inspect"
              onClick={() => handleInspect(null)}
              disabled={loading}
            >
              {loading ? <RefreshCw size={18} className="spin" /> : <Activity size={18} />}
              <span>{loading ? "Inspecting..." : "Inspect Active Site"}</span>
            </button>
          ) : (
            <button
              className="btn-inspect opacity-50"
              onClick={() => setSessionManifests(prev => ({ ...prev, [selectedSession]: null }))}
            >
              <RefreshCw size={18} />
              <span>Reset & Reload</span>
            </button>
          )}
        </div>
      </aside>

      {/* Content Area */}
      <div className="inspector-content bg-black/40">
        {error && (
          <div className="m-6 p-4 bg-error/10 border border-error/20 rounded-lg flex items-start gap-3">
            <AlertCircle className="text-error mt-1" size={20} />
            <div>
              <div className="font-bold text-error">Inspection Error</div>
              <div className="text-sm opacity-80">{error}</div>
            </div>
          </div>
        )}

        {!currentManifest && !error && !loading && (
          <div className="h-full flex flex-col items-center justify-center opacity-40">
            <Terminal size={48} className="mb-4" />
            <p>Select a session and click "Inspect Active Site"</p>
            <p className="text-xs">This will lazy-load the manifest for live debugging.</p>
          </div>
        )}

        {loading && (
          <div className="h-full flex flex-col items-center justify-center">
            <RefreshCw size={48} className="spin text-accent mb-4" />
            <p className="animate-pulse">Probing remote interface...</p>
          </div>
        )}

        {currentManifest && (
          <div className="p-6 h-full overflow-auto custom-scrollbar">
            {selectedLandmark === 'instructions' ? (
              <div className="markdown-viewer space-y-8">
                {parsedData.instructions && (
                  <section className="glass p-6 rounded-2xl border-white/5">
                    <div className="flex items-center gap-2 mb-4 text-accent uppercase text-xs font-bold tracking-widest">
                      <BookOpen size={14} />
                      <span>Protocol Rules</span>
                    </div>
                    <div className="prose prose-invert max-w-none text-sm text-white/70 leading-relaxed">
                      {parsedData.instructions}
                    </div>
                  </section>
                )}

                {parsedData.memoryBank && (
                  <section className="glass p-6 rounded-2xl border-white/5">
                    <div className="flex items-center gap-2 mb-4 text-purple-400 uppercase text-xs font-bold tracking-widest">
                      <Activity size={14} />
                      <span>Memory Bank Access</span>
                    </div>
                    <div className="bg-black/40 p-4 rounded-xl font-mono text-xs text-purple-300/80 border border-purple-500/10">
                      {parsedData.memoryBank}
                    </div>
                  </section>
                )}
              </div>
            ) : (
              <div className="landmark-viewer animate-slide-up">
                <div className="landmark-hero mb-8">
                  <div className="flex items-center gap-3 mb-2 opacity-50 text-[10px] uppercase tracking-[0.2em] font-bold">
                    <Activity size={14} className="text-accent" />
                    <span>Active Landmark Detail</span>
                  </div>
                  <h2 className="text-3xl font-black text-white mb-2 tracking-tight">
                    {selectedLandmark.split(':').pop()}
                  </h2>
                  <div className="flex items-center gap-2 text-sm text-accent/60 font-mono">
                    <Code size={14} />
                    <span>{selectedLandmark}</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  <div className="lg:col-span-2 space-y-6">
                    <div className="glass p-6 rounded-3xl border-white/5 relative overflow-hidden group">
                      <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:scale-110 transition-transform duration-500">
                        <BookOpen size={120} />
                      </div>
                      <h4 className="text-xs font-bold uppercase opacity-40 mb-4 tracking-widest">Description</h4>
                      <p className="text-lg text-white/90 leading-relaxed font-medium">
                        {sessionLandmarks[selectedLandmark]?.description || "No description provided."}
                      </p>
                    </div>

                    <div className="signature-box glass rounded-3xl border-white/5 overflow-hidden">
                      <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-accent animate-pulse"></div>
                          <span className="text-[10px] font-bold uppercase tracking-widest opacity-60">Technical Specification</span>
                        </div>
                        <div className="flex gap-1">
                          <div className="w-2 h-2 rounded-full bg-white/10"></div>
                          <div className="w-2 h-2 rounded-full bg-white/10"></div>
                          <div className="w-2 h-2 rounded-full bg-white/10"></div>
                        </div>
                      </div>
                      <div className="p-6 font-mono text-sm relative bg-black/40">
                        <pre className="signature-content custom-scrollbar max-h-[400px] overflow-auto">
                          {formatSignature(landmarkSignatures[selectedSession]?.[selectedLandmark] || sessionLandmarks[selectedLandmark]?.signature)}
                        </pre>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-6">
                    <div className="glass p-6 rounded-3xl border-white/5">
                      <h4 className="text-[10px] font-bold uppercase opacity-40 mb-4 tracking-widest">Navigation Context</h4>
                      <div className="space-y-3">
                        <div className="flex items-center justify-between p-3 rounded-2xl bg-white/5 border border-white/5">
                          <span className="text-xs opacity-60">Depth</span>
                          <span className="text-xs font-bold text-accent">{selectedLandmark.split(':').length}</span>
                        </div>
                        <div className="flex items-center justify-between p-3 rounded-2xl bg-white/5 border border-white/5">
                          <span className="text-xs opacity-60">Status</span>
                          <span className="text-xs font-bold text-success flex items-center gap-1">
                            <div className="w-1.5 h-1.5 rounded-full bg-success"></div>
                            LIVE
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="glass p-6 rounded-3xl border-white/5 border-accent/20 bg-accent/5">
                      <h4 className="text-[10px] font-bold uppercase text-accent mb-4 tracking-widest">Discovery Action</h4>
                      <p className="text-xs opacity-70 mb-4 leading-relaxed">
                        This landmark is part of a larger cluster. Use discovery patterns to find related tools.
                      </p>
                      <button
                        className="w-full py-3 rounded-2xl bg-accent text-black font-bold text-xs uppercase tracking-widest hover:scale-[1.02] active:scale-[0.98] transition-all shadow-[0_0_20px_rgba(var(--accent-rgb),0.3)]"
                        onClick={() => handleInspect(selectedLandmark)}
                      >
                        Force Refresh
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ManifestInspector;
