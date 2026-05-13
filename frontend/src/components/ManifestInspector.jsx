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
  Home,
  Copy,
  Check,
  Layers,
  Zap,
  Cpu,
  Globe,
  Database,
  ArrowRight,
  Info,
  Folder,
  FolderOpen
} from 'lucide-react';
const ToolTester = ({ landmark, parameters, sessions, selectedSession }) => {
  const [params, setParams] = useState({});
  const [result, setResult] = useState(null);
  const [executing, setExecuting] = useState(false);

  useEffect(() => {
    setParams({});
    setResult(null);
  }, [landmark]);

  const handleExecute = async () => {
    setExecuting(true);
    setResult(null);
    try {
      const session = sessions[selectedSession];
      if (!session || !session.active_url) {
         throw new Error("No active URL for execution. Please inspect site first.");
      }
      
      const parsedParams = {};
      parameters.forEach(p => {
         if (params[p.name] !== undefined && params[p.name] !== "") {
            if (p.type === 'number' || p.type === 'integer') {
               parsedParams[p.name] = Number(params[p.name]);
            } else if (p.type === 'boolean') {
               parsedParams[p.name] = params[p.name] === 'true' || params[p.name] === true;
            } else {
               parsedParams[p.name] = params[p.name];
            }
         }
      });

      const resp = await fetch('http://127.0.0.1:8090/api/v1/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: session.active_url,
          action: landmark,
          parameters: parsedParams
        })
      });
      
      let data;
      try {
        data = await resp.json();
      } catch (e) {
        data = await resp.text();
      }
      setResult(data);
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="console-call-card theme-execute expanded mt-6">
      <div className="card-header">
        <div className="header-left">
           <Terminal size={14} className="text-accent" />
           <span className="action-title font-bold text-accent">LIVE TEST EXECUTION</span>
        </div>
        <div className="header-right">
          <button className="btn-action-pill" onClick={handleExecute} disabled={executing}>
            {executing ? <RefreshCw size={14} className="spin" /> : <Terminal size={14} />}
            <span>{executing ? 'EXECUTING...' : 'TRY IT OUT'}</span>
          </button>
        </div>
      </div>
      <div className="card-body bg-black/20 p-6">
         {(() => {
           const normalParams = parameters.filter(p => !p.name.startsWith('_'));
           const elemmParams = parameters.filter(p => p.name.startsWith('_'));
           
           if (parameters.length === 0) {
             return <div style={{color: 'rgba(255,255,255,0.4)', fontSize: '0.875rem', fontStyle: 'italic'}}>This tool takes no parameters.</div>;
           }
           
           return (
             <>
               {normalParams.length > 0 && (
                 <div className="tt-grid">
                   {normalParams.map(p => (
                     <div key={p.name} className="tt-field">
                       <label className="tt-label">
                         <span>{p.name} {p.required && <span style={{color: '#ef4444', marginLeft: '4px'}}>*</span>}</span>
                         <span className="tt-type-badge">{p.type}</span>
                       </label>
                       {p.type === 'boolean' ? (
                         <select 
                           className="tt-input"
                           value={params[p.name] || ''}
                           onChange={e => setParams({...params, [p.name]: e.target.value})}
                         >
                           <option value="">- Select -</option>
                           <option value="true">true</option>
                           <option value="false">false</option>
                         </select>
                       ) : (
                         <input 
                           type={p.type === 'number' || p.type === 'integer' ? 'number' : 'text'}
                           className="tt-input"
                           placeholder={`Enter ${p.name}...`}
                           value={params[p.name] || ''}
                           onChange={e => setParams({...params, [p.name]: e.target.value})}
                         />
                       )}
                     </div>
                   ))}
                 </div>
               )}
               
               {elemmParams.length > 0 && (
                 <div className="mt-6 pt-4 border-t border-white/5">
                   <h5 className="flex items-center gap-1.5 text-[10px] text-accent/60 uppercase tracking-widest mb-3">
                     <Globe size={12} /> Elemm Hygiene Parameters
                   </h5>
                   <div className="tt-grid">
                     {elemmParams.map(p => (
                       <div key={p.name} className="tt-field">
                         <label className="tt-label">
                           <span className="text-accent/80">{p.name}</span>
                           <span className="tt-type-badge" style={{background: 'rgba(255,255,255,0.05)'}}>{p.type}</span>
                         </label>
                         <input 
                           type={p.type === 'number' || p.type === 'integer' ? 'number' : 'text'}
                           className="tt-input"
                           style={{borderColor: 'rgba(255,255,255,0.05)', backgroundColor: 'rgba(0,0,0,0.2)'}}
                           placeholder={`Enter ${p.name}...`}
                           value={params[p.name] || ''}
                           onChange={e => setParams({...params, [p.name]: e.target.value})}
                         />
                       </div>
                     ))}
                   </div>
                 </div>
               )}
             </>
           );
         })()}

         {result && (
            <div className="tt-result-box animate-fade-in">
               <div className="tt-result-header">
                 <div className={`tt-result-dot ${result.error || result.status === 'error' ? 'error' : 'success'}`}></div>
                 <div className="tt-result-title">Execution Result</div>
               </div>
               <pre className="tt-result-pre custom-scrollbar">
                 {typeof result === 'object' ? JSON.stringify(result, null, 2) : result}
               </pre>
            </div>
         )}
      </div>
    </div>
  );
};

const renderFormattedText = (text) => {
  if (!text) return '';
  let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  
  // GitHub-style alerts
  html = html.replace(/^&gt;\s+\[!([A-Z]+)\]\n((?:&gt;.*\n?)+)/gm, (match, type, content) => {
    const cleanedContent = content.replace(/^&gt;\s*/gm, '');
    return `<div class="github-alert alert-${type.toLowerCase()}"><strong class="alert-title">${type}</strong><div class="alert-content">${cleanedContent}</div></div>`;
  });
  
  // Standard blockquotes
  html = html.replace(/^&gt;\s+(.*)/gm, '<blockquote>$1</blockquote>');

  // Code blocks
  html = html.replace(/```(?:typescript|json|javascript)?([\s\S]*?)```/g, (match, code) => {
    return `<div class="embedded-code-block">${code.trim()}</div>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

  // Headers
  html = html.replace(/^(#{1,6})\s+(.*)$/gm, (match, hashes, content) => {
    const level = hashes.length;
    return `<div class="md-header h${level}">${content}</div>`;
  });

  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  
  // Line breaks for normal text
  html = html.replace(/\n/g, '<br/>');
  
  // Fix double br inside blocks
  html = html.replace(/<br\/><br\/>/g, '<br/>');

  return html;
};

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
  const [probedLandmarks, setProbedLandmarks] = useState({}); // track auto-probing: id -> boolean
  const [copied, setCopied] = useState(false);

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  useEffect(() => {
    fetchSessions();
    const interval = setInterval(fetchSessions, 5000);
    return () => clearInterval(interval);
  }, []);

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

        // CRITICAL: Also parse the signature (it's a manifest fragment) and update allLandmarks
        // This ensures the ToolTester gets the parameters
        const parsed = parseManifest(data.signature);
        if (parsed && parsed.landmarks && Object.keys(parsed.landmarks).length > 0) {
          setAllLandmarks(prev => ({
            ...prev,
            [sid]: {
              ...(prev[sid] || {}),
              ...parsed.landmarks
            }
          }));
        }
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
    setError(null);
    setSelectedLandmark('instructions');
    setExpandedNodes({}); // Alle Zweige einklappen
    
    // Gründlicher Reset des Session-Speichers
    setAllLandmarks(prev => ({ ...prev, [selectedSession]: {} }));
    setLandmarkSignatures(prev => ({ ...prev, [selectedSession]: {} }));
    setSessionManifests(prev => ({ ...prev, [selectedSession]: null }));
    
    // Frische Inspektion vom Root-Level aus
    setTimeout(() => {
      handleInspect(null);
    }, 50);
  };

  const parseManifest = (manifestText) => {
    if (!manifestText) return { instructions: "", memoryBank: "", landmarks: {}, signatures: [] };

    const sections = {
      instructions: "",
      memoryBank: "",
      landmarks: {},
      signatures: []
    };

    const lines = manifestText.split('\n');
    let currentSection = 'instructions';
    let lastLandmarkId = null;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;

      // Section detection
      if (line.match(/^### PROTOCOL RULES/i)) { currentSection = 'instructions'; continue; }
      if (line.match(/^### MEMORY BANK/i)) { currentSection = 'memoryBank'; continue; }
      if (line.match(/^### LANDMARK TOPOLOGY/i)) { currentSection = 'landmarks'; continue; }
      if (line.match(/^### TECHNICAL SIGNATURES/i)) { currentSection = 'signatures'; continue; }

      if (currentSection === 'instructions') {
        sections.instructions += line + '\n';
      } else if (currentSection === 'memoryBank') {
        sections.memoryBank += line + '\n';
      } else if (currentSection === 'landmarks') {
        // Match standard landmark/tool line
        const lmMatch = line.match(/^- (?:\*\*`|Landmark: `|Tool: `)(.*?)(?:`\*\*: |` - |`|: )(.*?)(?:\n|$)/);
        if (lmMatch) {
          const isToolLine = line.includes('- Tool: `');
          let id = lmMatch[1];
          let desc = lmMatch[2] ? lmMatch[2].trim() : "";

          // If it's the 'Specific Tool Inspector' line, extract the actual tool ID from the description
          if (id === "Specific Tool Inspector") {
            const idMatch = desc.match(/signature for (.*)/);
            if (idMatch) id = idMatch[1].trim();
          }
          
          // Check for parameter hints in the title line
          // Example: - Tool: `id` (Required: `p1`) -> Returns: type
          const paramHint = line.match(/\(Required: (.*?)\)/);
          const returnHint = line.match(/-> Returns: (.*?)$/);
          
          sections.landmarks[id] = { 
            description: desc, 
            isTruncated: false,
            isTool: isToolLine,
            requiredParams: paramHint ? paramHint[1].split(',').map(p => p.trim().replace(/`/g, '')) : [],
            returns: returnHint ? returnHint[1].trim() : null,
            parameters: []
          };
          lastLandmarkId = id;
        } else if (line.startsWith('|') && lastLandmarkId && sections.landmarks[lastLandmarkId]) {
          // Parse Markdown Table row
          // | Name | Type | Required | Default | Description |
          if (!line.includes('---') && !line.includes('Name | Type')) {
            const rawCols = line.split('|');
            // Remove first and last empty elements from the split
            const cols = rawCols.slice(1, rawCols.length - 1).map(c => c.trim());
            
            if (cols.length >= 3) {
              sections.landmarks[lastLandmarkId].parameters.push({
                name: cols[0].replace(/`/g, ''),
                type: cols[1],
                required: cols[2].includes('✅'),
                default: cols[3] ? cols[3].replace(/`/g, '') : "",
                description: cols[4] || ""
              });
            }
          }
        } else if (line.startsWith('**Returns**:') && lastLandmarkId) {
          sections.landmarks[lastLandmarkId].returns = line.split('**Returns**:')[1].trim();
        } else if (line.includes('... and') && line.includes('more items') && lastLandmarkId) {
          // Detect truncation marker and attach to the PREVIOUS landmark
          // Actually, in the manifest, the 'more items' line is a child of the parent.
          // Example:
          // - **`Parent`**: Desc
          //   - Tool: `Parent:Child`
          //   - ... and 95 more items
          // In this case, 'Parent' is truncated.
          
          const parentId = lastLandmarkId.split(':').slice(0, -1).join(':');
          if (parentId && sections.landmarks[parentId]) {
            sections.landmarks[parentId].isTruncated = true;
            sections.landmarks[parentId].description += ` (${line.split('(')[0].replace('...', '').trim()})`;
          } else if (lastLandmarkId) {
            // Fallback: If it's a top-level truncation or we can't find parent
            sections.landmarks[lastLandmarkId].isTruncated = true;
          }
        }
      } else if (currentSection === 'signatures') {
        if (line.startsWith('/**')) {
          sections.signatures.push(line);
        } else if (sections.signatures.length > 0) {
          sections.signatures[sections.signatures.length - 1] += '\n' + line;
          
          // Technical Signature Parsing
          // Example: function call_action(action: 'search:search_users', parameters: { q: string, ... }): any;
          if (line.includes('function call_action')) {
            const actionMatch = line.match(/action: '([^']+)'/);
            const paramsMatch = line.match(/parameters: \{ ([^}]+) \}/);
            
            if (actionMatch && paramsMatch) {
              const actionId = actionMatch[1];
              const paramStr = paramsMatch[1];
              
              if (!sections.landmarks[actionId]) {
                sections.landmarks[actionId] = { description: "", parameters: [] };
              }
              
              // Parse parameters from: name?: type, name: type
              const params = paramStr.split(',').map(p => p.trim());
              params.forEach(p => {
                const parts = p.split(':').map(part => part.trim());
                if (parts.length === 2) {
                  const isOptional = parts[0].endsWith('?');
                  const name = isOptional ? parts[0].slice(0, -1) : parts[0];
                  const type = parts[1];
                  
                  // Avoid duplicates
                  if (!sections.landmarks[actionId].parameters.some(existing => existing.name === name)) {
                    sections.landmarks[actionId].parameters.push({
                      name,
                      type,
                      required: !isOptional,
                      description: ""
                    });
                  }
                }
              });
            }
          }
        }
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
        const isLeaf = idx === parts.length - 1;
        if (!current[part]) {
          current[part] = {
            id: parts.slice(0, idx + 1).join(':'),
            label: part,
            children: {},
            description: isLeaf ? data.description : "",
            isTruncated: isLeaf ? data.isTruncated : false,
            isTool: isLeaf ? data.isTool : false
          };
        } else if (isLeaf) {
          // Falls der Knoten schon existiert (als Parent), aber jetzt auch als 
          // Landmark mit Beschreibung im Manifest auftaucht.
          current[part].description = data.description;
          current[part].isTruncated = data.isTruncated;
          if (data.isTool !== undefined) current[part].isTool = data.isTool;
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

  const getSelectedNode = () => {
    if (!selectedLandmark || selectedLandmark === 'instructions') return null;
    const parts = selectedLandmark.split(':');
    let current = treeData;
    let node = null;
    for (const part of parts) {
      if (current[part]) {
        node = current[part];
        current = node.children;
      } else {
        return null;
      }
    }
    return node;
  };
  const activeNode = getSelectedNode();
  const childrenList = activeNode ? Object.values(activeNode.children) : [];

  // --- Effects (Placed here because they depend on computed values like sessionLandmarks and treeData) ---

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

  useEffect(() => {
    if (selectedLandmark === 'instructions' || !selectedSession) return;
    
    // Auto Probe Logic
    const cacheKey = `${selectedSession}_${selectedLandmark}`;
    if (!probedLandmarks[cacheKey]) {
      const isTool = sessionLandmarks[selectedLandmark]?.isTool;
      
      // We already have activeNode from above, so we don't need to manually traverse treeData!
      const childrenCount = activeNode && activeNode.children ? Object.keys(activeNode.children).length : 0;
      
      // We probe if it's an Area with 0 children OR if it's specifically marked as truncated
      if (!isTool && (childrenCount === 0 || (activeNode && activeNode.isTruncated))) {
        handleInspect(selectedLandmark);
        setProbedLandmarks(prev => ({...prev, [cacheKey]: true}));
      }
    }
  }, [selectedLandmark, selectedSession, sessionLandmarks, activeNode]);

  const formatSignature = (sig) => {
    if (!sig) return "// No technical signature loaded for this landmark.\n// Use 'Inspect Active Site' to fetch technical details.";

    return sig.split('\n').map((line, i) => {
      let className = "text-white/80";
      if (line.includes('/**') || line.includes(' *')) className = "text-green-400/60 italic";
      if (line.includes('function') || line.includes('class')) className = "text-accent font-bold";
      if (line.includes('action:') || line.includes('method:')) className = "text-accent-blue";
      if (line.includes('parameters:') || line.includes('props:')) className = "text-purple-400";
      if (line.includes('return') || line.includes('export')) className = "text-pink-400";

      return <div key={i} className={className}>{line}</div>;
    });
  };

  const SafeJsonDisplay = ({ data, title }) => {
    const [copied, setCopied] = useState(false);
    const [isExpanded, setIsExpanded] = useState(false);
    
    if (!data) return null;

    const handleCopy = (e) => {
      e.stopPropagation();
      navigator.clipboard.writeText(data).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    };

    return (
      <div className={`console-call-card theme-discovery overflow-hidden mb-6 ${isExpanded ? 'expanded' : ''}`}>
        <div 
          className="card-header cursor-pointer select-none" 
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="header-left">
            <Cpu size={14} className="text-accent" />
            <span className="action-title font-bold">{title || 'TECHNICAL SIGNATURE'}</span>
            <span className="text-white/20 text-[10px] ml-2 font-normal">{isExpanded ? '(CLICK TO COLLAPSE)' : '(CLICK TO EXPAND)'}</span>
          </div>
          <div className="flex items-center gap-2">
            <button 
              className={`copy-json-btn ${copied ? 'copied' : ''}`} 
              onClick={handleCopy}
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              <span>{copied ? 'COPIED' : 'COPY'}</span>
            </button>
            <ChevronRight size={14} className={`text-white/40 transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`} />
          </div>
        </div>
        {isExpanded && (
          <div className="card-body bg-black/40 p-0 animate-slide-down">
            <pre className="signature-content custom-scrollbar max-h-[500px] overflow-auto p-6 font-mono text-xs leading-relaxed">
              {formatSignature(data)}
            </pre>
          </div>
        )}
      </div>
    );
  };

  const renderTreeNodes = (nodes, depth = 0) => {
    return Object.values(nodes).map(node => {
      const hasChildren = Object.keys(node.children).length > 0;
      const isExpanded = expandedNodes[node.id];
      const isSelected = selectedLandmark === node.id;
      const isLazyCandidate = node.description?.includes('Area/Namespace') || node.description?.includes('District') || node.id.split(':').length < 2;

      return (
        <div key={node.id}>
          <div
            className={`ide-tree-row ${isSelected ? 'selected' : ''}`}
            style={{ paddingLeft: `${depth * 16 + 8}px` }}
            onClick={() => setSelectedLandmark(node.id)}
          >
            <div 
              className={`ide-tree-chevron ${isExpanded ? 'expanded' : ''} ${!hasChildren && !isLazyCandidate ? 'hidden' : ''}`}
              onClick={(e) => {
                e.stopPropagation();
                const cacheKey = `${selectedSession}_${node.id}`;
                const isFullyProbed = node.isTool || (hasChildren && !node.isTruncated) || probedLandmarks[cacheKey];
                
                if (!isExpanded && !isFullyProbed) {
                  setProbedLandmarks(prev => ({...prev, [cacheKey]: true}));
                  handleInspect(node.id);
                }
                setExpandedNodes(prev => ({ ...prev, [node.id]: !prev[node.id] }));
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
    <div className="obs-console-wrapper m-5" style={{ height: 'calc(100vh - 140px)', gridTemplateRows: 'minmax(0, 1fr)' }}>
      {/* LEFT: Landmark Tree Panel */}
      <div className="console-panel stream-panel flex flex-col" style={{ height: '100%', maxHeight: '100%', minHeight: 0, overflow: 'hidden' }}>
        <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Globe size={16} className="text-accent" />
            <h3 style={{ margin: 0 }}>City Topology</h3>
            {(() => {
              const type = sessions[selectedSession]?.site_type;
              if (type === 'openapi') {
                return <span className="topology-badge" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', marginLeft: '0.5rem' }}>OpenAPI</span>;
              } else if (type === 'graphql') {
                return <span className="topology-badge" style={{ background: 'rgba(236, 72, 153, 0.2)', color: '#f472b6', marginLeft: '0.5rem' }}>GraphQL</span>;
              } else if (type === 'elemm') {
                return <span className="topology-badge" style={{ background: 'rgba(56, 189, 248, 0.2)', color: '#7dd3fc', marginLeft: '0.5rem' }}>Native Elemm</span>;
              }
              return null;
            })()}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <button className="toolbar-icon-btn" onClick={resetBrowsing} title="Reset Browsing to Root">
              <Home size={14} />
            </button>
            <button className={`toolbar-icon-btn ${loading ? 'spin' : ''}`} onClick={() => handleInspect(null)} title="Force Reload Topology">
              <RefreshCw size={14} />
            </button>
            <button 
              className="toolbar-icon-btn" 
              style={{ color: 'var(--accent-blue)', borderColor: 'var(--accent-blue)' }} 
              onClick={() => setSessionManifests(prev => ({ ...prev, [selectedSession]: null }))} 
              title="Clear Memory Bank & Reset State"
            >
              <Database size={14} />
            </button>
          </div>
        </div>

        <div className="session-picker px-4 py-3 bg-white/[0.02] border-b border-white/5">
          <select
            value={selectedSession}
            onChange={(e) => setSelectedSession(e.target.value)}
            className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-xs font-mono"
          >
            {Object.entries(sessions).map(([sid, sessionData]) => {
              const urlLabel = sessionData?.active_url ? sessionData.active_url : `Session: ${sid.substring(0, 8)}`;
              return <option key={sid} value={sid}>{urlLabel}</option>;
            })}
            {Object.keys(sessions).length === 0 && <option>No active sites found</option>}
          </select>
        </div>

        <div className="custom-scrollbar bg-black/20 pb-4" style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          <div className="tree-container">
            {/* Protocol Rules as the first "Node" in the tree */}
            <div
              className={`ide-tree-row ${selectedLandmark === 'instructions' ? 'selected' : ''}`}
              style={{ paddingLeft: '8px' }}
              onClick={() => setSelectedLandmark('instructions')}
            >
              <div className="ide-tree-chevron hidden"><ChevronRight size={14} /></div>
              <div className="ide-tree-icon rules"><BookOpen size={14} /></div>
              <span className="ide-tree-text bold">Protocol Rules</span>
            </div>
            
            {renderTreeNodes(treeData)}
          </div>
        </div>

      </div>

      {/* RIGHT: Detail Panel */}
      <div className="console-panel history-panel flex flex-col bg-black/40" style={{ height: '100%', maxHeight: '100%', minHeight: 0, overflow: 'hidden' }}>
        <div className="panel-header">
          <div className="flex items-center gap-2">
            <Cpu size={16} className="text-accent" />
            <h3>Landmark Details</h3>
          </div>
          <div className="count-badge">{selectedLandmark === 'instructions' ? 'Manifest' : 'Technical Spec'}</div>
        </div>

        <div className="panel-content scrollable">
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
              <Globe size={48} className="mb-4 text-accent" />
              <p className="text-lg font-bold">Satellite Link Ready</p>
              <p className="text-sm">Connect to a session to begin landmark inspection.</p>
            </div>
          )}

          {loading && (
            <div className="h-full flex flex-col items-center justify-center">
              <RefreshCw size={48} className="spin text-accent mb-4" />
              <p className="animate-pulse font-mono text-xs tracking-widest">PROBING REMOTE MANIFEST...</p>
            </div>
          )}

          {currentManifest && (
            <div className="p-8">
              {selectedLandmark === 'instructions' ? (
                <div className="space-y-8 animate-fade-in">
                  <div className="console-call-card success expanded">
                    <div className="card-header">
                      <div className="header-left">
                        <BookOpen size={14} className="text-accent" />
                        <span className="action-title font-bold">PROTOCOL RULES</span>
                      </div>
                    </div>
                    <div className="card-body bg-black/20">
                      <div 
                        className="markdown-body text-sm leading-relaxed p-6 text-white/90" 
                        dangerouslySetInnerHTML={{ __html: renderFormattedText(parsedData.instructions || "No protocol rules defined in this manifest.") }} 
                      />
                    </div>
                  </div>

                  {parsedData.memoryBank && (
                    <div className="console-call-card theme-discovery expanded">
                      <div className="card-header">
                        <div className="header-left">
                          <Database size={14} className="text-purple-400" />
                          <span className="action-title font-bold">MEMORY BANK</span>
                        </div>
                      </div>
                      <div className="card-body bg-black/20">
                        <div 
                          className="p-6 font-mono text-sm text-purple-300/90 markdown-body" 
                          dangerouslySetInnerHTML={{ __html: renderFormattedText(parsedData.memoryBank) }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-8 animate-slide-up">
                  <div className="mi-header-row">
                    <div className="mi-header-left">
                      <div className="mi-header-badge">
                        <div className="mi-header-pulse"></div>
                        <span>{sessionLandmarks[selectedLandmark]?.isTool ? 'EXECUTABLE TOOL' : 'AREA NAMESPACE'}</span>
                      </div>
                      <h2 className="mi-header-title">{selectedLandmark.split(':').pop()}</h2>
                      
                      <div className="mi-header-desc">
                        {sessionLandmarks[selectedLandmark]?.description || "No specific architectural data available for this node."}
                      </div>
                    </div>
                    
                    <div className="mi-header-right">
                      <div className="token-pills-modern">
                        <div className="t-pill in">
                          <span className="t-label">DEPTH</span>
                          <span className="t-value">{selectedLandmark.split(':').length}</span>
                        </div>
                      </div>
                      <span className="mi-path-badge">{selectedLandmark}</span>
                    </div>
                  </div>

                  {(!sessionLandmarks[selectedLandmark]?.isTool) && (
                    <div className="console-call-card theme-info expanded">
                      <div className="card-header border-b border-white/5">
                        <div className="header-left">
                          <Layers size={14} className="text-accent-blue" />
                          <span className="action-title font-bold">AREA TOPOLOGY ({childrenList.length} ITEMS)</span>
                        </div>
                      </div>
                      <div className="card-body bg-black/20 p-0">
                        {childrenList.length === 0 ? (
                          <div className="topology-empty">
                            <Zap size={32} className="text-accent" />
                            <p className="topology-empty-title">Area Not Scanned Yet</p>
                            <p className="topology-empty-desc">
                              The contents of this area have not been loaded into the memory bank. 
                              Click 'PROBE NOW' below to discover the topology.
                            </p>
                          </div>
                        ) : (
                          <div className="topology-list">
                            {childrenList.map(child => (
                              <div 
                                key={child.id} 
                                className="topology-item"
                                onClick={() => {
                                  setSelectedLandmark(child.id);
                                  if (child.isTruncated || !child.isTool) {
                                    handleInspect(child.id);
                                  }
                                }}
                              >
                                <div className={`topology-icon ${child.isTool ? 'tool' : 'area'}`}>
                                  {child.isTool ? <Terminal size={14} /> : <Layers size={14} />}
                                </div>
                                <div className="topology-content">
                                  <div className="topology-header">
                                    <span className="topology-title">{child.label}</span>
                                    {child.isTool && <span className="topology-badge tool">Tool</span>}
                                    {!child.isTool && <span className="topology-badge area">Area</span>}
                                    {child.isTruncated && <span className="topology-badge explore" style={{opacity: 0.7}}><Info size={10} /> Unscanned</span>}
                                  </div>
                                  <div className="topology-desc">
                                    {child.description || "No description available."}
                                  </div>
                                </div>
                                <div className="topology-arrow">
                                  <ChevronRight size={16} />
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {sessionLandmarks[selectedLandmark]?.parameters?.length > 0 && (
                    <div className="console-call-card theme-discovery expanded">
                      <div className="card-header">
                        <div className="header-left">
                          <Layers size={14} className="text-purple-400" />
                          <span className="action-title font-bold">PARAMETERS</span>
                        </div>
                      </div>
                      <div className="card-body p-0 bg-black/20">
                        <div className="mi-table-wrapper">
                          <table className="mi-table">
                            <thead>
                              <tr>
                                <th>Name</th>
                                <th>Type</th>
                                <th style={{textAlign: 'center'}}>Req</th>
                                <th>Description</th>
                              </tr>
                            </thead>
                            <tbody>
                              {sessionLandmarks[selectedLandmark].parameters.map((p, i) => (
                                <tr key={i}>
                                  <td className="mi-table-name">{p.name}</td>
                                  <td className="mi-table-type">{p.type}</td>
                                  <td style={{textAlign: 'center'}}>{p.required ? <Check size={14} style={{color: 'var(--accent)', display: 'inline'}} /> : <span style={{opacity: 0.2}}>-</span>}</td>
                                  <td className="mi-table-desc">{p.description}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  )}

                  {sessionLandmarks[selectedLandmark]?.returns && (
                    <div className="stat-pill-modern mb-6">
                      <div className="flex items-center gap-3">
                        <ArrowRight size={14} className="text-pink-400" />
                        <span className="text-[10px] font-bold uppercase tracking-widest opacity-40">Expected Returns</span>
                      </div>
                      <span className="font-mono text-xs text-pink-300">{sessionLandmarks[selectedLandmark].returns}</span>
                    </div>
                  )}

                  <SafeJsonDisplay 
                    data={landmarkSignatures[selectedSession]?.[selectedLandmark] || sessionLandmarks[selectedLandmark]?.signature} 
                    title="TECHNICAL SIGNATURE"
                  />

                  {sessionLandmarks[selectedLandmark]?.isTool === true && (
                    <ToolTester 
                      landmark={selectedLandmark} 
                      parameters={sessionLandmarks[selectedLandmark].parameters || []} 
                      sessions={sessions}
                      selectedSession={selectedSession}
                    />
                  )}

                  <div className="mi-probe-card">
                    <div className="mi-probe-left">
                      <Zap size={16} className="text-accent" />
                      <div>
                        <p className="mi-probe-title">Satellite Probe</p>
                        <p className="mi-probe-desc">Trigger a deep discovery scan for this specific area.</p>
                      </div>
                    </div>
                    <button 
                      className="btn-action-pill" 
                      onClick={() => {
                        const cacheKey = `${selectedSession}_${selectedLandmark}`;
                        setProbedLandmarks(prev => ({...prev, [cacheKey]: true}));
                        handleInspect(selectedLandmark);
                      }}
                    >
                      {loading ? <RefreshCw size={14} className="spin" /> : <ArrowRight size={14} />}
                      <span>PROBE NOW</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ManifestInspector;
