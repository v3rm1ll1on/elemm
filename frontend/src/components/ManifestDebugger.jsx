import React, { useState, useEffect, useCallback } from 'react';
import './ManifestDebugger.css';
import './ObservabilityConsole.css';
import { Cpu } from 'lucide-react';
import { API_BASE } from '../config';
import LandmarkTreeView from './LandmarkTreeView';
import LandmarkDetails from './LandmarkDetails';

const ManifestDebugger = ({ sessions: externalSessions, selectedSession: externalSelectedSession, setSelectedSession: externalSetSelectedSession }) => {
  const [internalSessions, setInternalSessions] = useState({});
  const [internalSelectedSession, setInternalSelectedSession] = useState(null);

  const sessions = externalSessions || internalSessions;
  const setSessions = externalSessions ? () => {} : setInternalSessions;
  const selectedSession = externalSelectedSession !== undefined ? externalSelectedSession : internalSelectedSession;
  const setSelectedSession = externalSetSelectedSession || setInternalSelectedSession;
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
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  // --- Search Logic ---
  const handleSearch = async (query) => {
    setSearchQuery(query);
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }

    try {
      const session = sessions[selectedSession];
      const url = sniffUrl(session);
      if (!url) return;

      const resp = await fetch(`${API_BASE}/api/v1/search?query=${encodeURIComponent(query)}&session_id=${selectedSession}`);
      const data = await resp.json();
      
      if (data.status === 'success' || data.landmarks) {
        const results = data.landmarks || [];
        setSearchResults(results);
        
        // Also merge results into allLandmarks cache to ensure details can be loaded
        if (data.landmarks) {
          const newFound = {};
          results.forEach(lm => {
            newFound[lm.id] = {
              id: lm.id,
              description: lm.description || "",
              isTool: lm.is_tool || lm.isTool || true, // Search results are usually tools
              parameters: lm.parameters || [],
              returns: lm.returns || "any",
              method: lm.method || lm.meta?.method || null,
              outputSchema: lm.outputSchema || {}
            };
          });
          setAllLandmarks(prev => ({
            ...prev,
            [selectedSession]: { ...(prev[selectedSession] || {}), ...newFound }
          }));
        }
      }
    } catch (err) {
      console.error("Search failed:", err);
    }
  };

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

  const parseManifest = useCallback((manifestInput) => {
    if (!manifestInput) return { instructions: "", memoryBank: "", landmarks: {}, displayManifest: "" };

    let manifestObj = null;
    if (typeof manifestInput === 'object') {
      manifestObj = manifestInput;
    } else if (typeof manifestInput === 'string' && manifestInput.trim().startsWith('{')) {
      try {
        manifestObj = JSON.parse(manifestInput);
      } catch (e) {}
    }

    if (manifestObj) {
      const lms = {};
      (manifestObj.landmarks || []).forEach(lm => {
        lms[lm.id] = {
          id: lm.id,
          description: lm.description || "",
          isTool: lm.is_tool || lm.isTool,
          isTruncated: lm.is_truncated,
          parameters: lm.parameters || [],
          returns: lm.returns || "any",
          method: lm.method || lm.meta?.method || null,
          outputSchema: lm.outputSchema || lm.response_schema || {},
          remedy: lm.remedy,
          signature: lm.signature || ""
        };
      });
      return {
        instructions: manifestObj.instructions || "",
        memoryBank: "",
        landmarks: lms,
        displayManifest: typeof manifestInput === 'string' ? manifestInput : JSON.stringify(manifestObj, null, 2)
      };
    }

    const manifestText = manifestInput;

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
            method: t.method || t.meta?.method || null,
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
          const lmMatch = line.match(/^\s*-\s*(?:Action:\s*`|Tool:\s*`|Landmark:\s*`|\*\*`?|`?\*\*|`)([^`*:]+)(?:`?\*\*`?|`|:|\s+-)\s*(.*)$/);
          if (lmMatch) {
            const id = lmMatch[1];
            // Don't overwrite if JSON already provided more detail, but ensure it exists
            if (!sections.landmarks[id]) {
              sections.landmarks[id] = {
                id,
                description: lmMatch[2]?.trim() || "",
                isTool: line.includes('Tool: `') || line.includes('Action: `'),
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
            isTool: isLeaf ? data.isTool : false,
            outputSchema: isLeaf ? data.outputSchema : {}
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
      const resp = await fetch(`${API_BASE}/api/v1/sessions`);
      const data = await resp.json();
      setSessions(data);

      setSelectedSession(prev => {
        if (forceSelectId && data[forceSelectId]) return forceSelectId;
        if (!prev && Object.keys(data).length > 0) return Object.keys(data)[0];
        if (prev && !data[prev] && Object.keys(data).length > 0) return Object.keys(data)[0];
        return prev;
      });
    } catch (err) {
      console.error("Failed to fetch sessions", err);
    }
  };

  const fetchManifest = async (sid) => {
    try {
      const resp = await fetch(`${API_BASE}/api/v1/sessions/${sid}/manifest`);
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
      const resp = await fetch(`${API_BASE}/api/v1/inspect?url=${encodeURIComponent(url)}&session_id=${selectedSession}${landmarkQuery}`);
      if (!resp.ok) throw new Error(`Server error: ${resp.status}`);

      const data = await resp.json();
      console.log(`[Inspector] Data received:`, data);

      let newFoundLandmarks = {};
      let newSignatures = {};

      // 1. Handle New M2M JSON Format
      if (data.data) {
        const payload = data.data;
        const lms = payload.landmarks || (payload.id ? [payload] : []);
        
        lms.forEach(lm => {
          const id = (lms.length === 1 && landmarkId) ? landmarkId : lm.id;
          newFoundLandmarks[id] = {
            id: id,
            description: lm.description || "",
            isTool: lm.is_tool || lm.isTool,
            isTruncated: lm.is_truncated || false,
            parameters: lm.parameters || [],
            returns: lm.returns || "any",
            outputSchema: lm.outputSchema || lm.response_schema || {},
            remedy: lm.remedy,
            method: lm.method || lm.meta?.method || null
          };

          if ((lm.is_tool || lm.isTool)) {
            newSignatures[id] = `// Structured Profile for ${id}`;
          }
        });
      }
      // 2. Handle Legacy / Bridge Format
      else if (data.manifest || data.signature) {
        const content = data.manifest || data.signature;
        const parsed = parseManifest(content);
        newFoundLandmarks = parsed.landmarks;

        if (data.tools) {
          data.tools.forEach(t => {
            const schema = t.inputSchema || {};
            newFoundLandmarks[t.name] = {
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
              returns: t.returns || "any",
              method: t.method || t.meta?.method || null
            };
          });
        }
      }

      setLandmarkSignatures(prev => ({
        ...prev,
        [selectedSession]: { ...(prev[selectedSession] || {}), ...newSignatures }
      }));

      setAllLandmarks(prev => {
        const sessionLandmarks = prev[selectedSession] || {};
        return { ...prev, [selectedSession]: { ...sessionLandmarks, ...newFoundLandmarks } };
      });

      if (landmarkId === null) {
        setProbedLandmarks(prev => {
          const newState = { ...prev };
          Object.keys(newState).forEach(key => { if (key.startsWith(`${selectedSession}_`)) delete newState[key]; });
          return newState;
        });
        if (data.manifest || data.data) {
          setSessionManifests(prev => ({ ...prev, [selectedSession]: data.manifest || data.data }));
        }
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
      const sid = `manual_${Date.now()}`;
      const resp = await fetch(`${API_BASE}/api/v1/inspect?url=${encodeURIComponent(url)}&session_id=${sid}`);
      if (!resp.ok) throw new Error(`Failed to connect to ${url}`);

      const data = await resp.json();
      console.log(`[Inspector] Manual connect data:`, data);
      const parsed = parseManifest(data.data || data.manifest);

      // Update ALL relevant states immediately
      setSessionManifests(prev => ({ ...prev, [sid]: data.manifest || data.data }));
      setAllLandmarks(prev => ({ ...prev, [sid]: parsed.landmarks }));

      // Update sessions state locally even before re-fetching
      setSessions(prev => ({
        ...prev,
        [sid]: { active_url: url, site_type: data.type || 'elemm', ...(prev[sid] || {}) }
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
      setLoading(true);
      setError(null);
      const session = sessions[sid];
      const url = sniffUrl(session);
      const urlParam = url ? `&url=${encodeURIComponent(url)}` : "";

      const resp = await fetch(`${API_BASE}/api/v1/inspect/landmark?landmark_id=${lid}&session_id=${sid}${urlParam}`);
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ detail: "Unknown server error" }));
        throw new Error(errData.detail || `Server error: ${resp.status}`);
      }

      const data = await resp.json();

      if (data.status === 'success') {
        console.log(`[Inspector] Success for ${lid}.`, data);
        let newFoundLandmarks = {};
        let newSignatures = {};

        // Case A: Structured JSON Data
        if (data.data) {
          const payload = data.data;
          const lms = payload.landmarks || (payload.id ? [payload] : []);
          
          lms.forEach(lm => {
            const id = (lms.length === 1) ? lid : lm.id;
            newFoundLandmarks[id] = {
              id: id,
              description: lm.description || "",
              isTool: lm.is_tool || lm.isTool,
              isTruncated: lm.is_truncated || false,
              parameters: lm.parameters || [],
              returns: lm.returns || "any",
              outputSchema: lm.outputSchema || lm.response_schema || {},
              remedy: lm.remedy
            };
            newSignatures[id] = data.signature || `// Structured Profile for ${id}`;
          });

          // Ensure our target lid is at least marked as loaded
          if (!newSignatures[lid]) newSignatures[lid] = data.signature || "// Loaded via JSON (No Signature)";
        } 
        // Case B: Markdown Manifest/Signature
        else if (data.signature || data.manifest) {
          const content = data.signature || data.manifest;
          const parsed = parseManifest(content);
          newFoundLandmarks = parsed.landmarks;
          newSignatures[lid] = parsed.displayManifest || content;
        } else {
          // Fallback if success but no recognized data keys
          newSignatures[lid] = "// No technical data available";
        }

        setLandmarkSignatures(prev => ({
          ...prev,
          [sid]: { ...(prev[sid] || {}), ...newSignatures }
        }));

        setAllLandmarks(prev => {
          const currentSessionLms = prev[sid] || {};
          return { ...prev, [sid]: { ...currentSessionLms, ...newFoundLandmarks } };
        });
      }
    } catch (err) {
      console.error("Failed to load signature:", err);
      setError(`Signature error: ${err.message}`);
      // Also mark as "errored" in signatures to prevent loop
      setLandmarkSignatures(prev => ({
        ...prev,
        [sid]: { ...(prev[sid] || {}), [lid]: `// Error: ${err.message}` }
      }));
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async (landmark, parsedParams) => {
    setExecuting(true);
    setExecutionResult(null);
    try {
      const session = sessions[selectedSession];
      const url = sniffUrl(session);
      if (!url) throw new Error("No active URL for execution.");

      const resp = await fetch(`${API_BASE}/api/v1/execute`, {
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
    if (!externalSessions) {
      fetchSessions();
      const interval = setInterval(fetchSessions, 10000);
      return () => clearInterval(interval);
    }
  }, [externalSessions]);

  useEffect(() => {
    if (externalSessions) {
      setSelectedSession(prev => {
        if (!prev && Object.keys(externalSessions).length > 0) return Object.keys(externalSessions)[0];
        if (prev && !externalSessions[prev] && Object.keys(externalSessions).length > 0) return Object.keys(externalSessions)[0];
        return prev;
      });
    }
  }, [externalSessions, setSelectedSession]);

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

  useEffect(() => {
    if (selectedLandmark && selectedLandmark !== 'instructions' && selectedSession) {
      const cacheKey = `${selectedSession}_${selectedLandmark}`;
      if (!probedLandmarks[cacheKey]) {
        const lm = sessionLandmarks[selectedLandmark];
        if (lm && !lm.isTool && !lm.is_tool) {
          handleInspect(selectedLandmark);
          setProbedLandmarks(prev => ({ ...prev, [cacheKey]: true }));
        }
      }
    }
  }, [selectedLandmark, selectedSession]);

  const treeData = buildTree(sessionLandmarks);
  const selectedLandmarkData = sessionLandmarks[selectedLandmark];

  return (
    <div className="manifest-inspector" style={{ display: 'flex', flexDirection: 'row', width: '100%', height: 'calc(100vh - 120px)', overflow: 'hidden' }}>
      <div className="inspector-sidebar">
        <LandmarkTreeView
          sessions={sessions}
          selectedSession={selectedSession}
          onSessionChange={(sid) => { setSelectedSession(sid); setSelectedLandmark('instructions'); }}
          treeData={treeData}
          selectedLandmark={selectedLandmark}
          onSelectLandmark={(id) => {
            setSelectedLandmark(id);
            setExecutionResult(null);
          }}
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
          searchQuery={searchQuery}
          onSearch={handleSearch}
          searchResults={searchResults}
        />
      </div>

      <div className="inspector-content custom-scrollbar">
        <LandmarkDetails
          key={selectedLandmark}
          selectedLandmark={selectedLandmark}
          landmarkData={selectedLandmarkData}
          allLandmarks={sessionLandmarks}
          onSelectLandmark={setSelectedLandmark}
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

export default ManifestDebugger;
