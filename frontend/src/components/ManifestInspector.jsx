import React, { useState, useEffect, useCallback } from 'react';
import { Cpu } from 'lucide-react';
import LandmarkTreeView from './LandmarkTreeView';
import LandmarkDetails from './LandmarkDetails';

const ManifestInspector = () => {
  const [sessions, setSessions] = useState({});
  const [selectedSession, setSelectedSession] = useState(null);
  const [selectedLandmark, setSelectedLandmark] = useState('instructions');
  const [sessionManifests, setSessionManifests] = useState({});
  const [expandedNodes, setExpandedNodes] = useState({}); // id -> boolean
  const [allLandmarks, setAllLandmarks] = useState({}); // session_id -> { id -> data }
  const [probedLandmarks, setProbedLandmarks] = useState({}); // track auto-probing
  const [landmarkSignatures, setLandmarkSignatures] = useState({}); // session_id -> { id -> sig }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [executing, setExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState(null);

  // --- Utilities ---

  const renderFormattedText = useCallback((text) => {
    if (!text) return '';
    let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    // GitHub-style alerts
    html = html.replace(/^&gt;\s+\[!([A-Z]+)\]\n((?:&gt;.*\n?)+)/gm, (match, type, content) => {
      const cleanedContent = content.replace(/^&gt;\s*/gm, '');
      return `<div class="github-alert alert-${type.toLowerCase()}"><strong class="alert-title">${type}</strong><div class="alert-content">${cleanedContent}</div></div>`;
    });
    
    html = html.replace(/^&gt;\s+(.*)/gm, '<blockquote>$1</blockquote>');
    html = html.replace(/```(?:typescript|json|javascript)?([\s\S]*?)```/g, (match, code) => `<div class="embedded-code-block">${code.trim()}</div>`);
    html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    html = html.replace(/^(#{1,6})\s+(.*)$/gm, (match, hashes, content) => `<div class="md-header h${hashes.length}">${content}</div>`);
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\n/g, '<br/>');
    html = html.replace(/<br\/><br\/>/g, '<br/>');
    html = html.replace(/(<\/div>)\s*(<div class="md-header)/g, '$1<div style="height: 12px"></div>$2');

    return html;
  }, []);

  const parseManifest = useCallback((manifestText) => {
    if (!manifestText) return { instructions: "", memoryBank: "", landmarks: {}, displayManifest: "" };
    
    const sections = {
      instructions: "",
      memoryBank: "",
      landmarks: {},
      displayManifest: manifestText
    };

    const jsonMatch = manifestText.match(/```json-elemm\s+([\s\S]*?)```/i) || manifestText.match(/###\s+Technical Discovery[\s\S]*?```(?:json-elemm|json)\s+([\s\S]*?)```/i);
    let jsonBlockFound = false;
    
    if (jsonMatch) {
      try {
        const jsonStr = jsonMatch[1].trim();
        console.log("[Parser] Attempting to parse JSON block of length:", jsonStr.length);
        const tools = JSON.parse(jsonStr);
        const toolList = Array.isArray(tools) ? tools : [tools];
        
        toolList.forEach(t => {
          if (!t.name) return;
          const schema = t.inputSchema || {};
          sections.landmarks[t.name] = {
            id: t.name,
            description: t.description || "",
            isTool: true,
            isTruncated: false,
            parameters: Object.entries(schema.properties || {}).map(([pName, pData]) => ({
              name: pName,
              type: pData.type || "any",
              required: (schema.required || []).includes(pName),
              description: pData.description || "",
              location: pData.location
            })),
            requiredParams: schema.required || [],
            returns: t.returns || "any",
            signature: t.signature || ""
          };
        });
        jsonBlockFound = true;
        console.log("[Parser] Successfully extracted", Object.keys(sections.landmarks).length, "landmarks from JSON.");
        
        // Final aggressive cleanup of the display manifest
        sections.displayManifest = manifestText
          .replace(/---\s*###\s+Technical Discovery[\s\S]*?```[\s\S]*?```/gi, "")
          .replace(/###\s+Technical Discovery[\s\S]*?```[\s\S]*?```/gi, "")
          .replace(/```json-elemm[\s\S]*?```/gi, "")
          .trim();
      } catch (e) {
        console.error("[Parser] Failed to parse Technical Discovery JSON:", e);
        console.log("[Parser] Problematic JSON string:", jsonMatch[1]);
      }
    }

    const parts = sections.displayManifest.split(/^### /m);
    parts.forEach(part => {
      const lines = part.split('\n');
      if (lines.length === 0) return;
      const header = lines[0].trim().toUpperCase();
      const content = lines.slice(1).join('\n').trim();

      if (header.includes('PROTOCOL RULES')) sections.instructions = content;
      else if (header.includes('MEMORY BANK')) sections.memoryBank = content;
      else if (header.includes('LANDMARK TOPOLOGY')) {
        content.split('\n').forEach(line => {
          // Allow leading whitespace for indented sub-landmarks
          const lmMatch = line.match(/^\s*- (?:\*\*`|Landmark: `|Tool: `)(.*?)(?:`\*\*: |` - |`|: )(.*?)(?:\n|$)/);
          if (lmMatch) {
            const id = lmMatch[1];
            // Don't overwrite if JSON already provided more detail, but ensure it exists
            if (!sections.landmarks[id]) {
              sections.landmarks[id] = { 
                id, 
                description: lmMatch[2]?.trim() || "", 
                isTool: line.includes('Tool: `'), 
                isTruncated: false, 
                parameters: [] 
              };
            } else {
              // Augment existing entry with description if missing
              sections.landmarks[id].description = sections.landmarks[id].description || lmMatch[2]?.trim() || "";
            }
          }
        });
      }
    });

    return sections;
  }, []);

  const buildTree = useCallback((landmarks) => {
    const root = {};
    const landmarkList = Object.entries(landmarks);
    
    // Sort by path depth to ensure parents are processed before children if possible
    landmarkList.sort((a, b) => {
      const depthA = a[0].split(':').length;
      const depthB = b[0].split(':').length;
      return depthA - depthB;
    });

    landmarkList.forEach(([id, data]) => {
      const parts = id.split(':'); 
      let current = root;
      let currentPath = [];

      parts.forEach((part, idx) => {
        currentPath.push(part);
        const isLeaf = idx === parts.length - 1;
        const currentId = currentPath.join(':');

        if (!current[part]) {
          current[part] = {
            id: isLeaf ? id : currentId,
            label: part,
            children: {},
            description: isLeaf ? data.description : "",
            isTruncated: isLeaf ? data.isTruncated : false,
            isTool: isLeaf ? data.isTool : false
          };
        } else if (isLeaf) {
          current[part].description = data.description || current[part].description;
          current[part].isTruncated = data.isTruncated || current[part].isTruncated;
          if (data.isTool !== undefined) current[part].isTool = data.isTool;
          current[part].id = id;
        }
        current = current[part].children;
      });
    });
    return root;
  }, []);

  // --- Logic ---

  const sniffUrl = (session) => {
    if (session?.active_url) return session.active_url;
    if (session?.history) {
      for (const event of session.history) {
        const match = JSON.stringify(event).match(/https?:\/\/[a-zA-Z0-9][-a-zA-Z0-9+&@#/%?=~_|!:,.;]*/);
        if (match) return match[0].split('"')[0].split("'")[0];
      }
    }
    return null;
  };

  const fetchSessions = async (forceSelectId = null) => {
    try {
      const resp = await fetch('http://127.0.0.1:8090/api/v1/sessions');
      const data = await resp.json();
      setSessions(data);
      
      if (forceSelectId && data[forceSelectId]) {
        setSelectedSession(forceSelectId);
      } else if (!selectedSession && Object.keys(data).length > 0) {
        setSelectedSession(Object.keys(data)[0]);
      }
    } catch (err) {
      console.error("Failed to fetch sessions", err);
    }
  };

  const fetchManifest = async (sid) => {
    try {
      const resp = await fetch(`http://127.0.0.1:8090/api/v1/sessions/${sid}/manifest`);
      const data = await resp.json();
      if (data.manifest) {
        setSessionManifests(prev => ({ ...prev, [sid]: data.manifest }));
        const parsed = parseManifest(data.manifest);
        setAllLandmarks(prev => {
          const sessionLandmarks = prev[sid] || {};
          return { ...prev, [sid]: { ...sessionLandmarks, ...parsed.landmarks } };
        });
      }
    } catch (err) {
      console.error("Failed to fetch manifest", err);
    }
  };

  const handleInspect = async (landmarkId = null) => {
    const session = sessions[selectedSession];
    if (!session) return;

    setLoading(true);
    setError(null);

    try {
      let url = sniffUrl(session);
      if (!url) {
        const userUrl = prompt("No active connection found. Please enter URL:", "http://localhost:8010");
        if (!userUrl) { setLoading(false); return; }
        url = userUrl;
      }

      const landmarkQuery = landmarkId ? `&landmark_id=${landmarkId}` : "";
      const resp = await fetch(`http://127.0.0.1:8090/api/v1/inspect?url=${encodeURIComponent(url)}&session_id=${selectedSession}${landmarkQuery}`);
      if (!resp.ok) throw new Error(`Server error: ${resp.status}`);
      
      const data = await resp.json();
      console.log(`[Inspector] Data for ${landmarkId || 'root'}:`, data);
      const parsed = parseManifest(data.manifest);

      if (data.tools) {
        data.tools.forEach(t => {
          const schema = t.inputSchema || {};
          parsed.landmarks[t.name] = {
            id: t.name,
            description: t.description || "",
            isTool: true,
            isTruncated: false,
            parameters: Object.entries(schema.properties || {}).map(([pName, pData]) => ({
              name: pName,
              type: pData.type || "any",
              required: (schema.required || []).includes(pName),
              description: pData.description || "",
              location: pData.location
            })),
            requiredParams: schema.required || [],
            returns: t.returns || "any"
          };
        });
      }

      console.log(`[Inspector] Parsed landmarks:`, Object.keys(parsed.landmarks));

      setAllLandmarks(prev => {
        const sessionLandmarks = prev[selectedSession] || {};
        const newLandmarks = { ...sessionLandmarks, ...parsed.landmarks };
        return { ...prev, [selectedSession]: newLandmarks };
      });

      if (landmarkId === null) {
        setProbedLandmarks(prev => {
          const newState = { ...prev };
          Object.keys(newState).forEach(key => { if (key.startsWith(`${selectedSession}_`)) delete newState[key]; });
          return newState;
        });
        setSessionManifests(prev => ({ ...prev, [selectedSession]: data.manifest }));
        setSelectedLandmark('instructions');
      }
    } catch (err) {
      console.error("Inspection error:", err);
      setError(`Inspection failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleManualConnect = async (url) => {
    setLoading(true);
    setError(null);
    try {
      const sid = selectedSession || 'default';
      const resp = await fetch(`http://127.0.0.1:8090/api/v1/inspect?url=${encodeURIComponent(url)}&session_id=${sid}`);
      if (!resp.ok) throw new Error(`Failed to connect to ${url}`);
      
      const data = await resp.json();
      console.log(`[Inspector] Manual connect data:`, data);
      const parsed = parseManifest(data.manifest);
      
      // Update ALL relevant states immediately
      setSessionManifests(prev => ({ ...prev, [sid]: data.manifest }));
      setAllLandmarks(prev => {
        const sessionLandmarks = prev[sid] || {};
        return { ...prev, [sid]: { ...sessionLandmarks, ...parsed.landmarks } };
      });
      
      // Update sessions state locally even before re-fetching
      setSessions(prev => ({
        ...prev,
        [sid]: { active_url: url, site_type: 'elemm', ...(prev[sid] || {}) }
      }));

      setSelectedSession(sid);
      
      // Then sync with server
      await fetchSessions(sid);
      setSelectedLandmark('instructions');
    } catch (err) {
      console.error("Manual connect error:", err);
      setError(`Connection failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchLandmarkSignature = async (sid, lid) => {
    try {
      const session = sessions[sid];
      const url = sniffUrl(session);
      const urlParam = url ? `&url=${encodeURIComponent(url)}` : "";
      
      const resp = await fetch(`http://127.0.0.1:8090/api/v1/inspect/landmark?landmark_id=${lid}&session_id=${sid}${urlParam}`);
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(errData.detail || `Server error: ${resp.status}`);
      }
      
      const data = await resp.json();
      console.log(`[Inspector] Received signature for ${lid}. Length: ${data.signature?.length}`);
      
      if (data.status === 'success' && data.signature) {
        const parsed = parseManifest(data.signature);
        console.log(`[Inspector] Parsed signature. Found ${Object.keys(parsed.landmarks).length} tools.`);
        
        setLandmarkSignatures(prev => ({
          ...prev,
          [sid]: { ...(prev[sid] || {}), [lid]: parsed.displayManifest }
        }));

        if (parsed?.landmarks && Object.keys(parsed.landmarks).length > 0) {
          setAllLandmarks(prev => {
            const currentSessionLms = prev[sid] || {};
            const newLms = { ...currentSessionLms, ...parsed.landmarks };
            console.log(`[Inspector] Merged landmarks for session ${sid}. Total now: ${Object.keys(newLms).length}`);
            return { ...prev, [sid]: newLms };
          });
        }
      }
    } catch (err) {
      console.error("Failed to fetch landmark signature", err);
      setError(`Signature fetch failed: ${err.message}`);
    }
  };

  const handleExecute = async (landmark, parsedParams) => {
    setExecuting(true);
    setExecutionResult(null);
    try {
      const session = sessions[selectedSession];
      const url = sniffUrl(session);
      if (!url) throw new Error("No active URL for execution.");

      const resp = await fetch('http://127.0.0.1:8090/api/v1/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          url, 
          action: landmark, 
          parameters: parsedParams,
          session_id: selectedSession
        })
      });
      
      const data = await resp.json().catch(() => resp.text());
      setExecutionResult(data);
    } catch (err) {
      setExecutionResult({ error: err.message });
    } finally {
      setExecuting(false);
    }
  };

  // --- Effects ---

  useEffect(() => {
    fetchSessions();
    const interval = setInterval(fetchSessions, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedSession && !sessionManifests[selectedSession]) fetchManifest(selectedSession);
  }, [selectedSession]);

  useEffect(() => {
    if (selectedLandmark !== 'instructions' && selectedSession && !landmarkSignatures[selectedSession]?.[selectedLandmark]) {
      fetchLandmarkSignature(selectedSession, selectedLandmark);
    }
  }, [selectedLandmark, selectedSession]);

  // --- Render Prep ---

  const currentManifest = sessionManifests[selectedSession];
  const parsedData = parseManifest(currentManifest);
  
  // Merge landmarks from manifest and probed cache for the selected session
  const sessionLandmarks = {
    ...(parsedData.landmarks || {}),
    ...(allLandmarks[selectedSession] || {})
  };
  
  const treeData = buildTree(sessionLandmarks);
  const selectedLandmarkData = sessionLandmarks[selectedLandmark];

  return (
    <div className="obs-console-wrapper m-5" style={{ height: 'calc(100vh - 140px)', gridTemplateRows: 'minmax(0, 1fr)' }}>
      <LandmarkTreeView 
        sessions={sessions}
        selectedSession={selectedSession}
        onSessionChange={(sid) => { setSelectedSession(sid); setSelectedLandmark('instructions'); }}
        treeData={treeData}
        selectedLandmark={selectedLandmark}
        onSelectLandmark={setSelectedLandmark}
        expandedNodes={expandedNodes}
        onToggleExpand={(id, hasChildren, isTool, isTruncated) => {
          const cacheKey = `${selectedSession}_${id}`;
          if (!expandedNodes[id] && !isTool && (!hasChildren || isTruncated) && !probedLandmarks[cacheKey]) {
            handleInspect(id);
            setProbedLandmarks(prev => ({ ...prev, [cacheKey]: true }));
          }
          setExpandedNodes(prev => ({ ...prev, [id]: !prev[id] }));
        }}
        loading={loading}
        onReload={() => handleInspect(null)}
        onReset={() => {
          setAllLandmarks(prev => ({ ...prev, [selectedSession]: {} }));
          setSessionManifests(prev => ({ ...prev, [selectedSession]: null }));
          handleInspect(null);
        }}
        onManualConnect={handleManualConnect}
        probedLandmarks={probedLandmarks}
      />

      <div className="console-panel history-panel flex flex-col bg-black/40" style={{ height: '100%', maxHeight: '100%', minHeight: 0, overflow: 'hidden' }}>
        <div className="panel-header">
          <div className="flex items-center gap-2">
            <Cpu size={16} className="text-accent" />
            <h3>Landmark Details</h3>
          </div>
          <div className="count-badge">{selectedLandmark === 'instructions' ? 'Manifest' : 'Technical Spec'}</div>
        </div>

        <LandmarkDetails 
          selectedLandmark={selectedLandmark}
          landmarkData={selectedLandmarkData}
          signature={landmarkSignatures[selectedSession]?.[selectedLandmark]}
          instructions={parsedData.instructions}
          memoryBank={parsedData.memoryBank}
          onExecute={handleExecute}
          executing={executing}
          executionResult={executionResult}
          renderFormattedText={renderFormattedText}
          error={error}
          loading={loading}
        />
      </div>
    </div>
  );
};

export default ManifestInspector;
