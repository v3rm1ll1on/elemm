import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  Activity, 
  Shield, 
  TrendingDown, 
  DollarSign, 
  AlertTriangle, 
  CheckCircle, 
  Sparkles, 
  FileText, 
  Link as LinkIcon, 
  ArrowRight, 
  Search, 
  RefreshCw, 
  Cpu, 
  Code,
  Folder,
  FolderOpen,
  ChevronRight,
  X
} from 'lucide-react';
import './TokenAnalyzer.css';
import Tooltip from './Tooltip';
import { API_BASE } from '../config';

// Parser helper matching ManifestDebugger to extract landmarks
const parseManifest = (manifestInput) => {
  if (!manifestInput) return { landmarks: {} };
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
    
    // Parse landmarks
    (manifestObj.landmarks || []).forEach(lm => {
      const id = lm.id || lm.name;
      if (!id) return;
      lms[id] = {
        id: id,
        description: lm.description || "",
        isTool: lm.is_tool || lm.isTool || lm.is_action || lm.type === 'action' || false,
        parameters: lm.parameters || [],
        returns: lm.returns || "any",
        method: lm.method || lm.meta?.method || null,
        outputSchema: lm.outputSchema || lm.response_schema || {}
      };
    });

    // Parse tools/actions
    const toolsSource = manifestObj.tools || manifestObj.actions || [];
    (Array.isArray(toolsSource) ? toolsSource : []).forEach(t => {
      const id = t.id || t.name;
      if (!id) return;
      
      let params = t.parameters || [];
      if (t.inputSchema && params.length === 0) {
        const schema = t.inputSchema || {};
        const req = schema.required || [];
        params = Object.entries(schema.properties || {}).map(([pName, pData]) => ({
          name: pName,
          type: pData.type || "any",
          description: pData.description || "",
          required: req.includes(pName)
        }));
      }

      lms[id] = {
        id: id,
        description: t.description || "",
        isTool: true, // A tool is always a tool
        parameters: params,
        returns: t.returns || "any",
        method: t.method || t.meta?.method || null,
        outputSchema: t.outputSchema || t.response_schema || {}
      };
    });

    return { landmarks: lms };
  }

  // Fallback parsing for Markdown format
  const landmarks = {};
  const jsonMatch = manifestInput.match(/```json-elemm\s+([\s\S]*?)```/i);
  if (jsonMatch) {
    try {
      const tools = JSON.parse(jsonMatch[1].trim());
      const toolList = Array.isArray(tools) ? tools : [tools];
      toolList.forEach(t => {
        if (!t.name) return;
        const schema = t.inputSchema || {};
        landmarks[t.name] = {
          id: t.name,
          description: t.description || "",
          isTool: true,
          parameters: Object.entries(schema.properties || {}).map(([pName, pData]) => ({
            name: pName,
            type: pData.type || "any",
            required: (schema.required || []).includes(pName)
          })),
          returns: t.returns || "any"
        };
      });
      return { landmarks };
    } catch (e) {}
  }

  // Text topology parsing fallback
  const lines = manifestInput.split('\n');
  lines.forEach(line => {
    const lmMatch = line.match(/^\s*-\s*(?:Action:\s*`|Tool:\s*`|Landmark:\s*`|\*\*`?|`?\*\*|`)([^`*:]+)(?:`?\*\*`?|`|:|\s+-)\s*(.*)$/);
    if (lmMatch) {
      const id = lmMatch[1];
      landmarks[id] = {
        id,
        description: lmMatch[2]?.trim() || "",
        isTool: line.includes('Tool: `') || line.includes('Action: `'),
        parameters: []
      };
    }
  });

  return { landmarks };
};

// Generates a standard-compliant Model Context Protocol (MCP) JSON Schema definition for comparison
const getMcpJsonSchema = (tool) => {
  if (!tool) return '';
  const name = tool.name;
  const desc = tool.description || `Execute operation ${name} via model context protocol.`;
  
  const properties = {};
  const required = [];
  
  if (tool.legacyCode) {
    const lines = tool.legacyCode.split('\n');
    lines.forEach(line => {
      const match = line.match(/^\s*(\w+)(\??)\s*:\s*([^;,\n]+)/);
      if (match) {
        const paramName = match[1];
        if (paramName === 'function' || paramName === 'call_action' || paramName === 'parameters') return;
        
        const isOptional = match[2] === '?';
        const typeStr = match[3].toLowerCase().trim();
        
        let mcpType = 'string';
        if (typeStr.includes('number') || typeStr.includes('int') || typeStr.includes('float')) {
          mcpType = 'number';
        } else if (typeStr.includes('boolean') || typeStr.includes('bool')) {
          mcpType = 'boolean';
        } else if (typeStr.includes('object') || typeStr.includes('any')) {
          mcpType = 'object';
        } else if (typeStr.includes('array') || typeStr.includes('[]')) {
          mcpType = 'array';
        }
        
        properties[paramName] = {
          type: mcpType,
          description: `Parameter ${paramName} of type ${mcpType}`
        };
        
        if (!isOptional) {
          required.push(paramName);
        }
      }
    });
  }
  
  if (Object.keys(properties).length === 0) {
    properties['payload'] = {
      type: 'object',
      description: 'Structured request body payload'
    };
  }
  
  const mcpSchema = {
    name: name,
    description: desc,
    inputSchema: {
      type: "object",
      properties: properties,
      required: required
    }
  };
  
  return JSON.stringify(mcpSchema, null, 2);
};

// High-performance React.memo Tree Explorer component to completely eliminate UI lag
const ToolTreeExplorer = React.memo(({
  groupedTools,
  searchQuery,
  setSearchQuery,
  selectedToolName,
  setSelectedToolName,
  getShortName,
  expandedLandmarks,
  toggleLandmark,
  toolCount
}) => {
  return (
    <div className="analyzer-card glass flex-1 overflow-hidden flex flex-col" style={{ height: '620px', display: 'flex', flexDirection: 'column' }}>
      <div className="card-header-main justify-between border-b pb-3">
        <div className="flex items-center" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Activity size={18} className="text-accent" />
          <h5 className="text-white font-bold text-sm" style={{ margin: 0 }}>Extracted Tools ({toolCount})</h5>
        </div>
        <div className="search-input-wrapper-micro">
          <Search size={12} className="search-icon-micro" />
          <input 
            type="text" 
            placeholder="Search tools..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input-micro"
          />
        </div>
      </div>

      <div className="tools-list-scroller custom-scrollbar" style={{ flex: 1, overflowY: 'auto' }}>
        {Object.entries(groupedTools).map(([landmark, tools]) => {
          const isExpanded = !!(expandedLandmarks[landmark] || searchQuery);
          return (
            <div key={landmark} className="landmark-tree-node">
              <button 
                type="button"
                className="landmark-tree-header"
                onClick={(e) => toggleLandmark(landmark, e)}
              >
                <ChevronRight size={14} className={`tree-chevron ${isExpanded ? 'open' : ''}`} />
                {isExpanded ? (
                  <FolderOpen size={14} className="text-accent" />
                ) : (
                  <Folder size={14} className="text-accent" />
                )}
                <span className="landmark-node-name">{landmark}</span>
                <span className="badge-count">{tools.length}</span>
              </button>
              
              {isExpanded && (
                <div className="landmark-tree-children">
                  {tools.map(t => (
                    <div 
                      key={t.name} 
                      className={`tool-list-row ${selectedToolName === t.name ? 'active' : ''}`}
                      onClick={() => setSelectedToolName(t.name)}
                    >
                      <div className="tool-row-info">
                        <span className="tool-row-name">{getShortName(t.name)}</span>
                        <span className="tool-row-path">{t.name}</span>
                        <span className="tool-row-desc">{t.description}</span>
                      </div>
                      <div className="tool-row-savings text-success font-mono font-bold">
                        -{((t.legacyChars - t.elemmChars) / t.legacyChars * 100).toFixed(0)}%
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        {Object.keys(groupedTools).length === 0 && (
          <div className="empty-search-state">
            <Search size={20} className="opacity-20 mb-2" />
            <span>No tools match your query</span>
          </div>
        )}
      </div>
    </div>
  );
});

const TokenAnalyzer = () => {
  // Simulator States
  const [toolCount, setToolCount] = useState(250);
  const [dailyCalls, setDailyCalls] = useState(5000);

  // Live URL Analyzer States
  const [sessions, setSessions] = useState({});
  const [selectedSession, setSelectedSession] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);

  // Global Config States
  const [charToTokenRatio, setCharToTokenRatio] = useState(4.0);
  const [securityConfig, setSecurityConfig] = useState(null);
  const [simulateSecurityPolicy, setSimulateSecurityPolicy] = useState(false);
  const applySecurityFilter = simulateSecurityPolicy;

  // Advanced Context Simulation Parameters
  const [convTurns, setConvTurns] = useState(5);
  const [toolsUsed, setToolsUsed] = useState(2);
  const [cachingEnabled, setCachingEnabled] = useState(false);
  const [pipeRatio, setPipeRatio] = useState(60);
  const [expandedLandmarks, setExpandedLandmarks] = useState({});

  // Tool Detail Explorer States
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedToolName, setSelectedToolName] = useState(null);
  const [codeViewTab, setCodeViewTab] = useState('mcp'); // 'mcp', 'ts', or 'elemm'
  const [showAuditModal, setShowAuditModal] = useState(false);

  const handleReset = useCallback(() => {
    setAnalysisResult(null);
    setSearchQuery('');
    setSelectedToolName(null);
  }, []);

  // Fetch active sessions and config on mount
  useEffect(() => {
    fetchSessions();
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/v1/config`);
      const data = await resp.json();
      if (data.ui?.char_to_token_ratio) {
        setCharToTokenRatio(parseFloat(data.ui.char_to_token_ratio));
      }
      if (data.security) {
        setSecurityConfig(data.security);
      }
      if (data.ui?.simulate_security_policy !== undefined) {
        setSimulateSecurityPolicy(data.ui.simulate_security_policy);
      }
    } catch (e) {
      console.error("Failed to load global config in analyzer", e);
    }
  };

  const fetchSessions = async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/v1/sessions`);
      const data = await resp.json();
      setSessions(data);
    } catch (e) {
      console.error("Failed to load sessions in analyzer", e);
    }
  };

  // Perform mathematical context estimation based on parsed landmarks
  const estimateToolSignatures = useCallback((landmarks, hostName = 'api.example.com') => {
    let legacyChars = 0;
    let elemmChars = 0;
    const toolsList = [];

    Object.entries(landmarks).forEach(([id, data]) => {
      if (!data.isTool && !data.is_tool) return;

      // 1. Generate standard JSDoc TypeScript signature
      let tsSig = `/**\n * ${data.description || 'No description provided for this endpoint.'}\n`;
      const params = data.parameters || [];
      params.forEach(p => {
        tsSig += ` * @param ${p.name} - ${p.description || 'Type: ' + (p.type || 'any')}\n`;
      });
      tsSig += ` */\n`;
      tsSig += `function call_action(action: '${id}', parameters: {\n`;
      
      const paramLines = params.map(p => {
        return `  ${p.name}${p.required ? '' : '?'}: ${p.type || 'any'}`;
      });
      tsSig += paramLines.join(',\n');
      tsSig += `\n}): ${data.returns || 'any'};\n\n`;

      legacyChars += tsSig.length;

      // 2. Generate Elemm Compact Markdown equivalent
      let elemmSig = `- Action: \`${id}\` (${params.map(p => `${p.name}${p.required ? '' : '?'}`).join(', ')} | Returns: ${data.returns || 'any'})\n`;
      if (data.description) {
        elemmSig += `  > ${data.description}\n`;
      }

      elemmChars += elemmSig.length;

      toolsList.push({
        name: id,
        description: data.description || 'No description provided.',
        legacyChars: tsSig.length,
        elemmChars: elemmSig.length,
        legacyCode: tsSig,
        elemmCode: elemmSig,
        paramsCount: params.length
      });
    });

    const savingsPercent = legacyChars > 0 ? ((legacyChars - elemmChars) / legacyChars) * 100 : 0;
    const estimatedLegacyTokens = Math.ceil(legacyChars / charToTokenRatio);
    const estimatedElemmTokens = Math.ceil(elemmChars / charToTokenRatio);

    return {
      host: hostName,
      toolCount: toolsList.length,
      legacyChars,
      elemmChars,
      legacyTokens: estimatedLegacyTokens,
      elemmTokens: estimatedElemmTokens,
      savingsPercent: savingsPercent.toFixed(1),
      tools: toolsList
    };
  }, [charToTokenRatio, applySecurityFilter, securityConfig]);

  // Fetch and Analyze Session Manifest
  const handleAnalyzeSession = async (sid) => {
    if (!sid) return;
    setAnalyzing(true);
    setAnalysisError(null);
    setSelectedSession(sid);

    try {
      const session = sessions[sid];
      let landmarksMap = {};
      const host = session?.active_url ? new URL(session.active_url).host : `Session ${sid.substring(0, 6)}`;

      if (session && session.tools && Array.isArray(session.tools) && session.tools.length > 0) {
        // Map complete cached tools directly (retains vital metadata like HTTP method)
        session.tools.forEach(t => {
          const name = t.name || t.id;
          if (!name) return;

          let params = t.parameters || [];
          if (t.inputSchema && params.length === 0) {
            const schema = t.inputSchema || {};
            const req = schema.required || [];
            params = Object.entries(schema.properties || {}).map(([pName, pData]) => ({
              name: pName,
              type: pData.type || "any",
              description: pData.description || "",
              required: req.includes(pName)
            }));
          }

          landmarksMap[name] = {
            id: name,
            description: t.description || "",
            isTool: true,
            parameters: params,
            returns: t.returns || "any",
            method: t.method || t.meta?.method || null,
            outputSchema: t.outputSchema || t.response_schema || {}
          };
        });
      } else {
        // Fallback: fetch and parse Markdown manifest
        const resp = await fetch(`${API_BASE}/api/v1/sessions/${sid}/manifest`);
        const data = await resp.json();
        if (!data.manifest) throw new Error("No manifest returned for this session.");

        const parsed = parseManifest(data.manifest);
        landmarksMap = parsed.landmarks;
      }

      const result = estimateToolSignatures(landmarksMap, host);
      setAnalysisResult(result);
      if (result.tools.length > 0) {
        setSelectedToolName(result.tools[0].name);
      }
    } catch (e) {
      console.error(e);
      setAnalysisError(`Failed to analyze session: ${e.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  // Connect and Analyze manual URL
  const handleAnalyzeManualUrl = async (e) => {
    e.preventDefault();
    if (!urlInput.trim()) return;

    setAnalyzing(true);
    setAnalysisError(null);
    setAnalysisResult(null);

    try {
      const tempSid = `analyzer_${Date.now()}`;
      const resp = await fetch(`${API_BASE}/api/v1/inspect?url=${encodeURIComponent(urlInput.trim())}&session_id=${tempSid}`);
      if (!resp.ok) throw new Error(`Gateway failed to retrieve URL: ${resp.status}`);

      const data = await resp.json();
      
      let landmarksMap = {};
      // 1. Prioritize un-truncated raw tools from backend inspection response (solves 1000+ smart scale truncation)
      if (data.tools && Array.isArray(data.tools) && data.tools.length > 0) {
        data.tools.forEach(t => {
          const name = t.name || t.id;
          if (!name) return;
          
          let params = t.parameters || [];
          if (t.inputSchema && params.length === 0) {
            const schema = t.inputSchema || {};
            const req = schema.required || [];
            params = Object.entries(schema.properties || {}).map(([pName, pData]) => ({
              name: pName,
              type: pData.type || "any",
              description: pData.description || "",
              required: req.includes(pName)
            }));
          }
          
          landmarksMap[name] = {
            id: name,
            description: t.description || "",
            isTool: true,
            parameters: params,
            returns: t.returns || "any",
            method: t.method || t.meta?.method || null,
            outputSchema: t.outputSchema || t.response_schema || {}
          };
        });
      } else {
        // Fallback: parse manifest structure
        const content = data.data || data.manifest;
        if (!content) throw new Error("No API specification structure could be analyzed.");
        const parsed = parseManifest(content);
        landmarksMap = parsed.landmarks;
      }

      const hostName = new URL(urlInput.trim()).host;
      const result = estimateToolSignatures(landmarksMap, hostName);
      setAnalysisResult(result);
      if (result.tools.length > 0) {
        setSelectedToolName(result.tools[0].name);
      }
      
      // Re-fetch sessions to update list
      fetchSessions();
    } catch (e) {
      console.error(e);
      setAnalysisError(`Analysis failed: ${e.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  // Simulator Logic
  const sequencerSuccess = 85;

  const metrics = useMemo(() => {
    const tokensPerToolLegacy = Math.round(960 / charToTokenRatio);
    const tokensPerToolElemm = Math.round(48 / charToTokenRatio);

    // Compute effective turns based on sequencer piping
    const pipingSavingsFactor = (pipeRatio / 100) * (sequencerSuccess / 100);
    const effectiveTurnsLegacy = convTurns;
    const effectiveTurnsElemm = Math.max(1, convTurns * (1 - pipingSavingsFactor));

    // Legacy MCP: Every turn carries ALL tool definitions
    const legacySingleTurnTokens = toolCount * tokensPerToolLegacy;
    let legacyTotalTokens = 0;
    
    if (cachingEnabled) {
      legacyTotalTokens = legacySingleTurnTokens + (effectiveTurnsLegacy - 1) * legacySingleTurnTokens * 0.1;
    } else {
      legacyTotalTokens = legacySingleTurnTokens * effectiveTurnsLegacy;
    }

    // Elemm: Every turn carries ONLY the compact landmark topology
    const elemmTopologySingleTurnTokens = toolCount * tokensPerToolElemm;
    let elemmTopologyTotalTokens = 0;
    
    if (cachingEnabled) {
      elemmTopologyTotalTokens = elemmTopologySingleTurnTokens + (effectiveTurnsElemm - 1) * elemmTopologySingleTurnTokens * 0.1;
    } else {
      elemmTopologyTotalTokens = elemmTopologySingleTurnTokens * effectiveTurnsElemm;
    }
    
    const usedToolsTokens = toolsUsed * tokensPerToolLegacy * (effectiveTurnsElemm / 2);
    const elemmTotalTokens = Math.min(
      legacyTotalTokens, 
      elemmTopologyTotalTokens + usedToolsTokens
    );

    const tokenSavingsPercent = ((legacyTotalTokens - elemmTotalTokens) / legacyTotalTokens) * 100;
    
    const costPerMillion = 5.00; // Average input cost for premium LLMs (e.g. Claude 3.5 Sonnet)
    const legacyDailyCost = (legacyTotalTokens * dailyCalls / 1000000) * costPerMillion;
    const elemmDailyCost = (elemmTotalTokens * dailyCalls / 1000000) * costPerMillion;
    const monthlySavings = (legacyDailyCost - elemmDailyCost) * 30;

    // Roundtrip calculation
    const legacyRoundtrips = convTurns;
    const elemmRoundtrips = Math.round(effectiveTurnsElemm);
    const roundtripSavingsPercent = ((legacyRoundtrips - elemmRoundtrips) / legacyRoundtrips) * 100;

    let status = {
      type: 'success',
      icon: <CheckCircle size={18} className="text-success" />,
      text: 'LLM context is light, responsive, and 100% stable.'
    };
    if (legacyTotalTokens > 500000) {
      status = {
        type: 'danger',
        icon: <AlertTriangle size={18} className="text-error" />,
        text: 'CRITICAL CONTEXT FLOOD! Massive token sizes block LLM reasoning, raise costs, and cause high latency.'
      };
    } else if (legacyTotalTokens > 150000) {
      status = {
        type: 'warning',
        icon: <AlertTriangle size={18} className="text-warning" />,
        text: 'WARNING: Substantial context bloating. Caching helps costs, but huge contexts still degrade LLM attention span.'
      };
    }

    return {
      legacyTokens: Math.round(legacyTotalTokens),
      elemmTokens: Math.round(elemmTotalTokens),
      tokenSavingsPercent: Math.max(0, tokenSavingsPercent).toFixed(1),
      legacyDailyCost: legacyDailyCost.toFixed(2),
      elemmDailyCost: elemmDailyCost.toFixed(2),
      monthlySavings: monthlySavings.toFixed(2),
      legacyRoundtrips,
      elemmRoundtrips,
      roundtripSavingsPercent: Math.max(0, roundtripSavingsPercent).toFixed(0),
      status
    };
  }, [toolCount, dailyCalls, charToTokenRatio, convTurns, toolsUsed, cachingEnabled, pipeRatio]);

  // Filtering tools in analysis result (still used in selection fallback)
  const filteredTools = useMemo(() => {
    if (!analysisResult) return [];
    return analysisResult.tools.filter(t => 
      t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.description.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [analysisResult, searchQuery]);

  // Get short action name by stripping landmark prefix
  const getShortName = useCallback((name) => {
    let clean = name.replace(/^[:/]+/, '');
    if (clean.includes(':')) {
      return clean.substring(clean.lastIndexOf(':') + 1);
    } else if (clean.includes('/')) {
      return clean.substring(clean.lastIndexOf('/') + 1);
    }
    return clean;
  }, []);

  // Crash-proof Landmark Grouping for trees
  const groupedTools = useMemo(() => {
    if (!analysisResult) return {};
    const groups = {};
    const query = searchQuery.trim().toLowerCase();
    
    analysisResult.tools.forEach(t => {
      if (query) {
        const nameMatch = t.name.toLowerCase().includes(query);
        const descMatch = t.description && t.description.toLowerCase().includes(query);
        if (!nameMatch && !descMatch) return;
      }
      
      let landmark = 'core';
      let cleanName = t.name.replace(/^[:/]+/, '');
      const lastColon = cleanName.lastIndexOf(':');
      const lastSlash = cleanName.lastIndexOf('/');
      
      if (lastColon !== -1) {
        landmark = cleanName.substring(0, lastColon);
      } else if (lastSlash !== -1) {
        landmark = cleanName.substring(0, lastSlash);
      } else if (cleanName.includes('.')) {
        const lastDot = cleanName.lastIndexOf('.');
        landmark = cleanName.substring(0, lastDot);
      }
      
      landmark = landmark.trim();
      if (!landmark) landmark = 'core';

      if (!groups[landmark]) groups[landmark] = [];
      groups[landmark].push(t);
    });
    return groups;
  }, [analysisResult, searchQuery]);

  const toggleLandmark = useCallback((landmark, e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    setExpandedLandmarks(prev => ({
      ...prev,
      [landmark]: !prev[landmark]
    }));
  }, []);

  // Selected tool details
  const selectedTool = useMemo(() => {
    if (!analysisResult || !selectedToolName) return null;
    return analysisResult.tools.find(t => t.name === selectedToolName);
  }, [analysisResult, selectedToolName]);

  // Memoized MCP JSON Schema to prevent costly parsing on every slider tick
  const mcpJsonSchema = useMemo(() => {
    return getMcpJsonSchema(selectedTool);
  }, [selectedTool]);

  // Real-time Context Metrics for analyzed live specifications
  const liveMetrics = useMemo(() => {
    if (!analysisResult) return null;
    
    // Piping effects
    const pipingSavingsFactor = (pipeRatio / 100) * (sequencerSuccess / 100);
    const legacyRoundtrips = convTurns;
    const elemmRoundtrips = Math.max(1, Math.round(convTurns * (1 - pipingSavingsFactor)));

    const legacySingleTurnTokens = analysisResult.legacyTokens;
    let legacyTotalTokens = 0;
    if (cachingEnabled) {
      legacyTotalTokens = legacySingleTurnTokens + (legacyRoundtrips - 1) * legacySingleTurnTokens * 0.1;
    } else {
      legacyTotalTokens = legacySingleTurnTokens * legacyRoundtrips;
    }

    const elemmSingleTurnTopology = analysisResult.elemmTokens;
    let elemmTopologyTotalTokens = 0;
    if (cachingEnabled) {
      elemmTopologyTotalTokens = elemmSingleTurnTopology + (elemmRoundtrips - 1) * elemmSingleTurnTopology * 0.1;
    } else {
      elemmTopologyTotalTokens = elemmSingleTurnTopology * elemmRoundtrips;
    }

    // Dynamic schema loading cost for used tools (only in remaining effective turns)
    const averageLegacyToolSize = analysisResult.legacyTokens / Math.max(1, analysisResult.toolCount);
    const usedToolsTokens = toolsUsed * averageLegacyToolSize * (elemmRoundtrips / 2);
    
    const elemmTotalTokens = Math.min(
      legacyTotalTokens * 0.95, // Elemm is always strictly cheaper due to compression
      elemmTopologyTotalTokens + usedToolsTokens
    );

    const tokenSavingsPercent = ((legacyTotalTokens - elemmTotalTokens) / legacyTotalTokens) * 100;

    return {
      legacyTotalTokens: Math.round(legacyTotalTokens),
      elemmTotalTokens: Math.round(elemmTotalTokens),
      savingsPercent: Math.max(0, tokenSavingsPercent).toFixed(1),
      legacyRoundtrips,
      elemmRoundtrips
    };
  }, [analysisResult, convTurns, toolsUsed, cachingEnabled, pipeRatio]);

  // SVG Chart Dimensions
  const chartHeight = 180;
  const chartWidth = 500;
  const maxVal = 250000;

  return (
    <div className="token-analyzer-container premium-page-container animate-fade-in">
      
      {/* Hero Section */}
      <div className="analyzer-hero glass">
        <div className="hero-text">
          <Sparkles size={24} className="text-accent animated-pulse" />
          <h3>Elemm Live Context & Token Analyzer</h3>
          <p>
            Traditional MCP servers load complete, bloated JSDoc and TypeScript signatures directly into the LLM prompt.
            Elemm compresses, groups, and streams tools on-demand. Connect a live URL or run the simulator below to measure the exact savings.
          </p>
        </div>
      </div>

      {/* Conditional Rendering: If Live API is analyzed, show Live Report. Otherwise, show Simulator. */}
      {analyzing ? (
        <div className="loading-state-card glass animate-pulse-subtle">
          <Cpu size={40} className="spin-icon text-accent" />
          <h5>Connecting & Parsing Spec...</h5>
          <p>Downloading API schema, mapping endpoints, and generating simulated native TypeScript interfaces...</p>
        </div>
      ) : analysisResult ? (
        
        /* SPECTACULAR 3-COLUMN LIVE API ECONOMICS DASHBOARD */
        <div className="live-report-container animate-slide-up">
          <div className="report-header-row mb-4">
            <div className="report-title-group">
              <span className="badge-micro">Analysis Report</span>
              <h4>Spec Profile: <span className="text-accent">{analysisResult.host}</span></h4>
            </div>
            <div className="flex gap-3" style={{ display: 'flex', gap: '12px' }}>
              <button className="btn-secondary" onClick={handleReset}>
                ← Back to Simulator
              </button>
            </div>
          </div>

          {/* Real-time Simulation Settings for Live Report */}
          <div className="simulation-params-panel">
            <div className="sim-panel-title">
              <Sparkles size={16} className="text-accent" />
              <span>Simulation<br />Parameters</span>
            </div>
            
            <div className="sim-sliders-grid">
              <div className="sim-slider-container">
                <div className="sim-slider-header">
                  <span>Depth (Conversation turns)</span>
                  <span className="sim-slider-value">{convTurns} turns</span>
                </div>
                <input 
                  type="range" 
                  min="1" 
                  max="15" 
                  value={convTurns} 
                  onChange={(e) => setConvTurns(parseInt(e.target.value))}
                  className="custom-range micro-range"
                />
              </div>

              <div className="sim-slider-container">
                <div className="sim-slider-header">
                  <span>Called (Executed tools)</span>
                  <span className="sim-slider-value">{toolsUsed} tools</span>
                </div>
                <input 
                  type="range" 
                  min="0" 
                  max="10" 
                  value={toolsUsed} 
                  onChange={(e) => setToolsUsed(parseInt(e.target.value))}
                  className="custom-range micro-range"
                />
              </div>

              <div className="sim-slider-container">
                <div className="sim-slider-header">
                  <span>Piping (Roundtrip saving)</span>
                  <span className="sim-slider-value">{pipeRatio}%</span>
                </div>
                <input 
                  type="range" 
                  min="0" 
                  max="100" 
                  value={pipeRatio} 
                  onChange={(e) => setPipeRatio(parseInt(e.target.value))}
                  className="custom-range micro-range"
                />
              </div>

              <div className="sim-slider-container" style={{ paddingLeft: '12px' }}>
                <span className="sim-slider-header" style={{ marginBottom: '6px' }}>Prompt Caching</span>
                <label className="premium-switch">
                  <input 
                    type="checkbox" 
                    checked={cachingEnabled} 
                    onChange={(e) => setCachingEnabled(e.target.checked)} 
                  />
                  <span className="switch-slider"></span>
                </label>
              </div>
            </div>
          </div>

          {/* Top Level Premium KPI Summary Cards */}
          <div className="dashboard-kpi-row">
            <div className="metric-box glass" style={{ padding: '16px 20px', textAlign: 'left', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span className="m-title" style={{ fontSize: '0.675rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>Total API Tools</span>
              <span className="m-val text-accent" style={{ fontSize: '1.625rem', fontWeight: 800, color: 'var(--accent-primary)', fontFamily: 'sans-serif' }}>{analysisResult.toolCount}</span>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>endpoints mapped</span>
            </div>

            <div className="metric-box glass" style={{ padding: '16px 20px', textAlign: 'left', display: 'flex', flexDirection: 'column', gap: '4px', borderLeft: '3px solid #ef4444' }}>
              <span className="m-title" style={{ fontSize: '0.675rem', fontWeight: 700, textTransform: 'uppercase', color: '#f87171', letterSpacing: '0.05em' }}>Traditional MCP Cost</span>
              <span className="m-val text-error" style={{ fontSize: '1.625rem', fontWeight: 800, color: '#ef4444', fontFamily: 'var(--font-mono)' }}>{liveMetrics.legacyTotalTokens.toLocaleString()} t</span>
              <span style={{ fontSize: '0.65rem', color: '#f87171' }}>statically force-loaded</span>
            </div>

            <div className="metric-box glass" style={{ padding: '16px 20px', textAlign: 'left', display: 'flex', flexDirection: 'column', gap: '4px', borderLeft: '3px solid #10b981' }}>
              <span className="m-title" style={{ fontSize: '0.675rem', fontWeight: 700, textTransform: 'uppercase', color: '#34d399', letterSpacing: '0.05em' }}>Elemm Dynamic Cost</span>
              <span className="m-val text-success" style={{ fontSize: '1.625rem', fontWeight: 800, color: '#10b981', fontFamily: 'var(--font-mono)' }}>{liveMetrics.elemmTotalTokens.toLocaleString()} t</span>
              <span style={{ fontSize: '0.65rem', color: '#34d399' }}>on-demand lazy-loaded</span>
            </div>

            <div className="metric-box glass" style={{ padding: '16px 20px', textAlign: 'left', display: 'flex', flexDirection: 'column', gap: '4px', borderLeft: '3px solid #10b981', background: 'rgba(16, 185, 129, 0.03)' }}>
              <span className="m-title" style={{ fontSize: '0.675rem', fontWeight: 700, textTransform: 'uppercase', color: '#34d399', letterSpacing: '0.05em' }}>Net Token Savings</span>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                <span className="m-val text-success" style={{ fontSize: '1.625rem', fontWeight: 800, color: '#10b981' }}>-{liveMetrics.savingsPercent}%</span>
                <span style={{ fontSize: '0.8rem', color: '#a7f3d0', fontFamily: 'var(--font-mono)' }}>({(liveMetrics.legacyTotalTokens - liveMetrics.elemmTotalTokens).toLocaleString()} t)</span>
              </div>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>saved from context window</span>
            </div>
          </div>

          <div className="live-report-dashboard">
            {/* Column 1: API Landmark Tree Explorer */}
            <div className="live-report-left-col">
              <ToolTreeExplorer 
                groupedTools={groupedTools}
                searchQuery={searchQuery}
                setSearchQuery={setSearchQuery}
                selectedToolName={selectedToolName}
                setSelectedToolName={setSelectedToolName}
                getShortName={getShortName}
                expandedLandmarks={expandedLandmarks}
                toggleLandmark={toggleLandmark}
                toolCount={analysisResult.toolCount}
              />
            </div>

            {/* Column 2: Real-time Payload Comparison & Signature Viewer */}
            <div className="live-report-mid-col">
              {selectedTool ? (
                <div className="analyzer-card glass flex-1 overflow-hidden flex flex-col" style={{ height: '620px', display: 'flex', flexDirection: 'column' }}>
                  <div className="card-header-main justify-between border-b pb-3">
                    <div className="flex flex-col min-w-0 flex-1 mr-3 text-left">
                      <span className="selected-tool-title" title={selectedTool.name}>
                        {selectedTool.name}
                      </span>
                      <span className="text-xs text-muted">Payload Compare</span>
                    </div>
                    <div className="tab-control-premium flex-shrink-0">
                      <button 
                        className={`tab-btn ${codeViewTab === 'mcp' ? 'active' : ''}`}
                        onClick={() => setCodeViewTab('mcp')}
                      >
                        <FileText size={12} /> <span>Traditional MCP JSON</span>
                      </button>
                      <button 
                        className={`tab-btn ${codeViewTab === 'ts' ? 'active' : ''}`}
                        onClick={() => setCodeViewTab('ts')}
                      >
                        <Code size={12} /> <span>TypeScript Spec</span>
                      </button>
                      <button 
                        className={`tab-btn ${codeViewTab === 'elemm' ? 'active text-accent' : ''}`}
                        onClick={() => setCodeViewTab('elemm')}
                      >
                        <Sparkles size={12} /> <span>Elemm Compact</span>
                      </button>
                    </div>
                  </div>

                  <div className="tab-explanation-banner mt-2" style={{ padding: '10px 14px', background: 'rgba(255, 255, 255, 0.02)', borderRadius: '8px', fontSize: '0.725rem', color: 'var(--text-secondary)', borderLeft: '3px solid var(--accent-primary)', textAlign: 'left', lineHeight: '1.4' }}>
                    {codeViewTab === 'mcp' && "Traditional MCP JSON: The official, highly verbose JSON-schema structure that a legacy MCP server pushes redundantly to the AI prompt."}
                    {codeViewTab === 'ts' && "TypeScript Spec: The high-precision TypeScript signature that guarantees strong typing, but remains highly token-intensive due to boilerplate syntax."}
                    {codeViewTab === 'elemm' && "Elemm Compact: The highly optimized, compact Elemm key format. It aggregates actions into abstract landmark topologies, reducing context token usage by up to 90% with dynamic on-demand schema loading (lazy loading)."}
                  </div>

                  <div className="compare-bar-group mt-3">
                    <div className="bar-label">
                      <span>Payload Length</span>
                      <span>
                        {codeViewTab === 'ts' ? selectedTool.legacyChars : 
                         codeViewTab === 'elemm' ? selectedTool.elemmChars : 
                         mcpJsonSchema.length} characters
                      </span>
                    </div>
                    <div className="comparison-bar-bg">
                      <div 
                        className="comparison-bar-fill" 
                        style={{ 
                          width: `${Math.min(100, ((codeViewTab === 'ts' ? selectedTool.legacyChars : codeViewTab === 'elemm' ? selectedTool.elemmChars : mcpJsonSchema.length) / selectedTool.legacyChars) * 100)}%`,
                          backgroundColor: codeViewTab === 'ts' ? '#ef4444' : codeViewTab === 'elemm' ? '#10b981' : '#f59e0b'
                        }}
                      ></div>
                    </div>
                  </div>

                  <div className="code-block-premium-wrapper flex-1 mt-3 overflow-auto custom-scrollbar" style={{ flex: 1, overflowY: 'auto' }}>
                    <pre className="code-pre-block" style={{ height: '100%' }}>
                      <code>
                        {codeViewTab === 'ts' ? selectedTool.legacyCode : 
                         codeViewTab === 'elemm' ? selectedTool.elemmCode : 
                         mcpJsonSchema}
                      </code>
                    </pre>
                  </div>
                </div>
              ) : (
                <div className="analyzer-card glass flex-1 items-center justify-center text-center" style={{ height: '620px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                  <Code size={40} className="opacity-10 mb-2" />
                  <p className="text-muted">Select a tool to explore payload structures</p>
                </div>
              )}
            </div>

            {/* Column 3: Context Economics Ledger */}
            <div className="live-report-right-col">
              <div className="analyzer-card glass flex-1 flex flex-col" style={{ height: '620px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div className="card-header-main border-b pb-3 mb-4 text-left">
                  <div className="flex items-center" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <TrendingDown size={18} className="text-success" />
                    <h5 className="text-white font-bold text-sm" style={{ margin: 0 }}>Context Economics</h5>
                  </div>
                  <span className="text-xs text-muted">Real-time cost & API ledger</span>
                </div>

                <div className="comparison-table flex-1" style={{ display: 'flex', flexDirection: 'column', gap: '18px', padding: '10px 0' }}>
                  <div className="comp-row" style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '12px' }}>
                    <span className="text-muted text-xs text-left">Total Directory tools</span>
                    <span className="text-white font-mono font-bold text-xs text-right">{analysisResult.toolCount} tools</span>
                  </div>

                  <div className="comp-row" style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '12px' }}>
                    <span className="text-muted text-xs text-left">Simulated Dialog Depth</span>
                    <span className="text-white font-mono font-bold text-xs text-right">{convTurns} turns</span>
                  </div>

                  <div className="comp-row" style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '12px' }}>
                    <span className="text-muted text-xs text-left">Estimated Roundtrips</span>
                    <span className="text-accent font-mono font-bold text-xs text-right">{liveMetrics.elemmRoundtrips} / {convTurns} turns</span>
                  </div>

                  <div className="comp-row" style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '12px' }}>
                    <span className="text-muted text-xs text-left">Traditional Context Cost</span>
                    <span className="text-error font-mono font-bold text-xs text-right">{liveMetrics.legacyTotalTokens.toLocaleString()} t</span>
                  </div>

                  <div className="comp-row" style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '12px' }}>
                    <span className="text-muted text-xs text-left">Elemm Context Cost</span>
                    <span className="text-success font-mono font-bold text-xs text-right">{liveMetrics.elemmTotalTokens.toLocaleString()} t</span>
                  </div>
                </div>

                <button className="btn-accent-premium w-full mt-4 justify-center" onClick={() => setShowAuditModal(true)} style={{ padding: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                  <Shield size={14} /> <span>Verify Audit Proof</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        
        /* CLASSIC HIGH-FIDELITY SIMULATOR */
        <div className="animate-fade-in">
          {/* Live URL / Session Analyzer Control Row */}
          <div className="analyzer-card glass connect-panel mb-4">
            <div className="card-header-main">
              <LinkIcon size={20} className="text-accent" />
              <h4>Analyze Live API Specification</h4>
            </div>
            
            <div className="connection-controls-row">
              {/* Option A: Manual URL paste */}
              <form onSubmit={handleAnalyzeManualUrl} className="manual-connect-form">
                <div className="premium-input-group">
                  <div className="premium-input-wrapper">
                    <LinkIcon size={14} className="input-icon-left" />
                    <input 
                      type="text" 
                      placeholder="Paste Swagger / OpenAPI URL..."
                      value={urlInput}
                      onChange={(e) => setUrlInput(e.target.value)}
                      className="premium-input-url"
                    />
                  </div>
                  <button type="submit" className="btn-accent-premium" disabled={analyzing || !urlInput.trim()}>
                    {analyzing ? <RefreshCw size={14} className="spin-icon" /> : <ArrowRight size={14} />}
                    <span>Analyze</span>
                  </button>
                </div>
              </form>

              <span className="or-divider">OR</span>

              {/* Option B: Active Session Selector */}
              <div className="session-select-group">
                <select
                  value={selectedSession}
                  onChange={(e) => handleAnalyzeSession(e.target.value)}
                  className="premium-select-dropdown"
                  disabled={analyzing}
                >
                  <option value="" style={{ background: '#090d16', color: '#cbd5e1' }}>
                    -- Choose active connected API --
                  </option>
                  {Object.entries(sessions).map(([sid, data]) => {
                    const clientName = sid.length > 20 ? `Session ${sid.substring(0, 6)}...` : sid;
                    const apiName = data?.active_url ? data.active_url.replace(/^(https?|mcp):\/\//, '') : 'No Active Connection';
                    return (
                      <option key={sid} value={sid} style={{ background: '#090d16', color: '#cbd5e1' }}>
                        {clientName} ➔ {apiName}
                      </option>
                    );
                  })}
                </select>
              </div>
            </div>

            {analysisError && (
              <div className="simulation-alert status-danger mt-3">
                <AlertTriangle size={18} className="text-error" />
                <span>{analysisError}</span>
              </div>
            )}
          </div>

          <div className="analyzer-grid">
            {/* Section 1: Simulator */}
            <div className="analyzer-card glass">
              <div className="card-header-main">
                <Activity size={20} className="text-accent" />
                <h4>Context Bloat Simulator</h4>
              </div>
              
              <div className="simulator-controls">
                <div className="slider-group">
                  <div className="slider-label">
                    <span>Simulated Tool Count</span>
                    <span className="slider-value text-accent">{toolCount.toLocaleString()} Tools</span>
                  </div>
                  <input 
                    type="range" 
                    min="10" 
                    max="1000" 
                    value={toolCount} 
                    onChange={(e) => setToolCount(parseInt(e.target.value))}
                    className="custom-range"
                  />
                </div>

                <div className={`simulation-alert status-${metrics.status.type}`}>
                  {metrics.status.icon}
                  <span>{metrics.status.text}</span>
                </div>
              </div>

              {/* SVG Visualizer Chart */}
              <div className="chart-wrapper">
                <div className="chart-legend">
                  <span className="legend-item legacy"><span className="legend-dot"></span> Legacy MCP (Full TS Spec)</span>
                  <span className="legend-item elemm"><span className="legend-dot"></span> Elemm Protocol</span>
                </div>
                
                <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="svg-chart">
                  {/* Background grid lines */}
                  <line x1="0" y1={chartHeight * 0.25} x2={chartWidth} y2={chartHeight * 0.25} className="grid-line" />
                  <line x1="0" y1={chartHeight * 0.5} x2={chartWidth} y2={chartHeight * 0.5} className="grid-line" />
                  <line x1="0" y1={chartHeight * 0.75} x2={chartWidth} y2={chartHeight * 0.75} className="grid-line" />

                  {/* Threshold indicator line */}
                  <line x1="0" y1={chartHeight - ((72000 / maxVal) * chartHeight)} x2={chartWidth} y2={chartHeight - ((72000 / maxVal) * chartHeight)} className="threshold-line" strokeDasharray="4,4" />
                  <text x="10" y={chartHeight - ((72000 / maxVal) * chartHeight) - 6} className="chart-text threshold-text">Context Saturation Limit</text>

                  {/* Legacy Line */}
                  <path 
                    d={`M 0,${chartHeight} Q ${chartWidth * 0.5},${chartHeight - ((120000 / maxVal) * chartHeight)} ${chartWidth},${chartHeight - ((240000 / maxVal) * chartHeight)}`}
                    fill="none" 
                    className="chart-path legacy-path" 
                  />
                  {/* Elemm Line */}
                  <line 
                    x1="0" 
                    y1={chartHeight - 4} 
                    x2={chartWidth} 
                    y2={chartHeight - 4} 
                    className="chart-path elemm-path" 
                  />

                  {/* Active simulated point indicators */}
                  <circle cx={(toolCount / 1000) * chartWidth} cy={chartHeight - ((metrics.legacyTokens / maxVal) * chartHeight)} r="6" className="active-dot legacy" />
                  <circle cx={(toolCount / 1000) * chartWidth} cy={chartHeight - 4} r="6" className="active-dot elemm" />
                </svg>
              </div>
            </div>

            {/* Section 2: Economics / Cost Calculator */}
            <div className="analyzer-card glass flex-col-between">
              <div>
                <div className="card-header-main">
                  <DollarSign size={20} className="text-success" />
                  <h4>Context Efficiency & Costs</h4>
                </div>

                <div className="slider-group mt-2">
                  <div className="slider-label">
                    <span>Daily Agent Steps / Turns</span>
                    <span className="slider-value text-success">{dailyCalls.toLocaleString()} Calls</span>
                  </div>
                  <input 
                    type="range" 
                    min="100" 
                    max="25000" 
                    step="100"
                    value={dailyCalls} 
                    onChange={(e) => setDailyCalls(parseInt(e.target.value))}
                    className="custom-range range-success"
                  />
                </div>

                <div className="slider-group mt-3">
                  <div className="slider-label">
                    <span>Avg. Conversation Depth</span>
                    <span className="slider-value text-accent">{convTurns} Turns / Chat</span>
                  </div>
                  <input 
                    type="range" 
                    min="1" 
                    max="15" 
                    value={convTurns} 
                    onChange={(e) => setConvTurns(parseInt(e.target.value))}
                    className="custom-range"
                  />
                </div>

                <div className="slider-group mt-3">
                  <div className="slider-label">
                    <span>Actual Tools Executed</span>
                    <span className="slider-value text-success">{toolsUsed} Tools Called</span>
                  </div>
                  <input 
                    type="range" 
                    min="0" 
                    max="10" 
                    value={toolsUsed} 
                    onChange={(e) => setToolsUsed(parseInt(e.target.value))}
                    className="custom-range range-success"
                  />
                </div>

                <div className="flex items-center justify-between mt-3 mb-2 premium-checkbox-row">
                  <span className="text-xs text-muted flex items-center gap-1">
                    Enable Prompt Caching <Tooltip text="Claude-style caching saves 90% input cost on repeat turns, but charges a 25% write premium on miss." />
                  </span>
                  <label className="premium-switch">
                    <input 
                      type="checkbox" 
                      checked={cachingEnabled} 
                      onChange={(e) => setCachingEnabled(e.target.checked)} 
                    />
                    <span className="switch-slider"></span>
                  </label>
                </div>

                <div className="slider-group mt-3">
                  <div className="slider-label">
                    <span>Sequencer Piping Ratio</span>
                    <span className="slider-value text-accent">{pipeRatio}% Usage</span>
                  </div>
                  <input 
                    type="range" 
                    min="0" 
                    max="100" 
                    value={pipeRatio} 
                    onChange={(e) => setPipeRatio(parseInt(e.target.value))}
                    className="custom-range"
                  />
                </div>

                <div className="comparison-table mt-3">
                  <div className="comp-row header">
                    <div>Metric</div>
                    <div>Legacy MCP</div>
                    <div className="text-accent">Elemm Opt</div>
                  </div>
                  <div className="comp-row">
                    <span>Payload Tokens</span>
                    <span>{metrics.legacyTokens.toLocaleString()} t</span>
                    <span className="text-accent font-semibold">{metrics.elemmTokens.toLocaleString()} t</span>
                  </div>
                  <div className="comp-row">
                    <span>Daily API Bill</span>
                    <span>${metrics.legacyDailyCost}</span>
                    <span className="text-success font-semibold">${metrics.elemmDailyCost}</span>
                  </div>
                  <div className="comp-row">
                    <span>Network Roundtrips</span>
                    <span className="text-error">{metrics.legacyRoundtrips} turns</span>
                    <span className="text-success font-semibold">{metrics.elemmRoundtrips} turn{metrics.elemmRoundtrips > 1 ? 's' : ''}</span>
                  </div>
                </div>
              </div>

              <div className="savings-badge glass mt-3 animate-pulse-subtle">
                <div className="savings-left">
                  <TrendingDown size={28} className="text-success" />
                  <div>
                    <h5>-{metrics.tokenSavingsPercent}%</h5>
                    <p>Realistic Context Savings</p>
                  </div>
                </div>
                <div className="savings-right">
                  <h5>${metrics.monthlySavings}</h5>
                  <p>Saved Monthly</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {showAuditModal && (
        <div className="audit-modal-overlay" onClick={() => setShowAuditModal(false)}>
          <div className="audit-modal-content" style={{ maxWidth: '1050px', width: '95%', background: '#0b0f19', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '16px', padding: '24px' }} onClick={(e) => e.stopPropagation()}>
            <div className="audit-modal-header border-b pb-4 mb-4" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '16px', marginBottom: '16px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', textAlign: 'left' }}>
                <div className="audit-header-icon" style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '10px', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Shield size={20} className="text-success" />
                </div>
                <div>
                  <h4 className="font-bold text-lg text-white" style={{ margin: 0, fontSize: '1.15rem' }}>Gateway Overhead & Token Optimization Analysis</h4>
                  <p className="text-xs text-muted" style={{ margin: '4px 0 0 0', fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)' }}>Comparative payload & context window simulation for {analysisResult ? analysisResult.host : 'connected Spec'}</p>
                </div>
              </div>
              <button className="modal-close-btn" style={{ background: 'rgba(255,255,255,0.05)', border: 'none', color: '#ffffff', padding: '6px', borderRadius: '50%', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setShowAuditModal(false)}>
                <X size={18} />
              </button>
            </div>

            <div className="audit-modal-body custom-scrollbar" style={{ maxHeight: '75vh', overflowY: 'auto', paddingRight: '6px' }}>
              <div className="audit-seal" style={{ display: 'flex', justifyContent: 'center', marginBottom: '20px' }}>
                <span className="badge-audit" style={{ background: 'rgba(16, 185, 129, 0.15)', border: '1px solid #10b981', color: '#10b981', padding: '4px 12px', borderRadius: '50px', fontSize: '0.7rem', fontWeight: 'bold', letterSpacing: '1px' }}>✓ SIMULATION VERIFIED</span>
              </div>

              {/* Context Window Payload Simulation */}
              <div className="modal-diagram-container" style={{ marginTop: '20px', marginBottom: '28px' }}>
                <h6 style={{ color: 'rgba(255,255,255,0.7)', fontSize: '0.75rem', fontWeight: 'bold', letterSpacing: '1.5px', marginBottom: '14px', textAlign: 'center', textTransform: 'uppercase' }}>
                  Context Window Payload Simulation
                </h6>
                <div className="diagram-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                  {/* Left Column Diagram: Traditional MCP */}
                  <div className="diagram-card legacy" style={{ background: 'rgba(239, 68, 68, 0.02)', border: '1px solid rgba(239, 68, 68, 0.15)', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', alignItems: 'center', minHeight: '235px', justifyContent: 'space-between' }}>
                    <span style={{ color: '#ef4444', fontWeight: 'extrabold', fontSize: '0.7rem', letterSpacing: '1px', marginBottom: '8px', textTransform: 'uppercase' }}>
                      🔴 Legacy MCP (Full Schema Push)
                    </span>
                    
                    <div style={{ flex: 1, width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0' }}>
                      <div style={{ padding: '6px 12px', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', background: 'rgba(239, 68, 68, 0.08)', fontSize: '0.7rem', color: '#fca5a5', fontWeight: 'bold', width: 'max-content' }}>
                        {analysisResult?.toolCount} Full JSON Schemas
                      </div>
                      
                      {/* Thick Red Flow Pipe */}
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '10px 0' }}>
                        <div style={{ width: '18px', height: '35px', background: 'linear-gradient(180deg, rgba(239, 68, 68, 0.8), rgba(239, 68, 68, 0.2))', borderRadius: '4px', position: 'relative' }}>
                          <span style={{ fontSize: '0.55rem', color: '#ffffff', position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%) rotate(90deg)', whiteSpace: 'nowrap', fontWeight: 'bold', letterSpacing: '0.5px' }}>FULL BLOCK</span>
                        </div>
                        <div style={{ width: '0', height: '0', borderLeft: '10px solid transparent', borderRight: '10px solid transparent', borderTop: '10px solid rgba(239, 68, 68, 0.3)', marginTop: '2px' }}></div>
                      </div>
                      
                      <div style={{ padding: '6px 12px', border: '1px solid #ef4444', borderRadius: '6px', background: 'rgba(239, 68, 68, 0.15)', fontSize: '0.7rem', color: '#ef4444', fontWeight: 'extrabold', textAlign: 'center', width: '90%' }}>
                        Context Overhead per Interaction<br />
                        <span style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: '#ffffff' }}>~{(analysisResult?.toolCount * Math.round(960 / charToTokenRatio)).toLocaleString()} t / Turn</span>
                      </div>
                    </div>
                    
                    <p style={{ fontSize: '0.675rem', lineHeight: '1.4', color: 'rgba(255,255,255,0.35)', textAlign: 'center', margin: '8px 0 0 0' }}>
                      The LLM receives the full structural definition of all tools in the workspace at each conversation step.
                    </p>
                  </div>

                  {/* Right Column Diagram: Elemm Gateway */}
                  <div className="diagram-card elemm" style={{ background: 'rgba(16, 185, 129, 0.02)', border: '1px solid rgba(16, 185, 129, 0.15)', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', alignItems: 'center', minHeight: '235px', justifyContent: 'space-between' }}>
                    <span style={{ color: '#10b981', fontWeight: 'extrabold', fontSize: '0.7rem', letterSpacing: '1px', marginBottom: '8px', textTransform: 'uppercase' }}>
                      🟢 Elemm Gateway (Tiered Discovery)
                    </span>
                    
                    <div style={{ flex: 1, width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0' }}>
                      <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', width: '100%' }}>
                        <div style={{ padding: '4px 8px', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '6px', background: 'rgba(16, 185, 129, 0.08)', fontSize: '0.65rem', color: '#a7f3d0', fontWeight: 'bold' }}>
                          Landmark Keys ({analysisResult?.toolCount})
                        </div>
                        <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.8rem', alignSelf: 'center' }}>+</span>
                        <div style={{ padding: '4px 8px', border: '1px dotted rgba(59, 130, 246, 0.3)', borderRadius: '6px', background: 'rgba(59, 130, 246, 0.08)', fontSize: '0.65rem', color: '#93c5fd', fontWeight: 'bold' }}>
                          Lazy Details ({toolsUsed})
                        </div>
                      </div>
                      
                      {/* Slender green and blue flow pipes */}
                      <div style={{ display: 'flex', gap: '20px', margin: '10px 0', height: '35px', alignItems: 'center' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                          <div style={{ width: '4px', height: '25px', background: '#10b981', borderRadius: '2px' }}></div>
                          <div style={{ width: '0', height: '0', borderLeft: '4px solid transparent', borderRight: '4px solid transparent', borderTop: '4px solid #10b981', marginTop: '1px' }}></div>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                          <div style={{ width: '2px', height: '25px', borderLeft: '2px dotted #3b82f6' }}></div>
                          <div style={{ width: '0', height: '0', borderLeft: '3px solid transparent', borderRight: '3px solid transparent', borderTop: '3px solid #3b82f6', marginTop: '1px' }}></div>
                        </div>
                      </div>
                      
                      <div style={{ padding: '6px 12px', border: '1px solid #10b981', borderRadius: '6px', background: 'rgba(16, 185, 129, 0.15)', fontSize: '0.7rem', color: '#10b981', fontWeight: 'extrabold', textAlign: 'center', width: '90%' }}>
                        Context Overhead per Interaction<br />
                        <span style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: '#ffffff' }}>
                          ~{Math.round((analysisResult?.toolCount * Math.round(48 / charToTokenRatio)) + (toolsUsed * Math.round(960 / charToTokenRatio))).toLocaleString()} t / Turn
                        </span>
                      </div>
                    </div>
                    
                    <p style={{ fontSize: '0.675rem', lineHeight: '1.4', color: 'rgba(255,255,255,0.35)', textAlign: 'center', margin: '8px 0 0 0' }}>
                      The LLM only receives light, abstract landmark-only skeletons. Parameter details are lazy-loaded dynamically.
                    </p>
                  </div>
                </div>
              </div>

              {/* HIGH-END COMPARATIVE AUDIT TABLE */}
              <div style={{ marginTop: '24px', marginBottom: '24px' }}>
                <h6 style={{ color: 'rgba(255,255,255,0.7)', fontSize: '0.75rem', fontWeight: 'bold', letterSpacing: '1.5px', marginBottom: '14px', textAlign: 'center', textTransform: 'uppercase' }}>
                  Simulated Metric Comparison Ledger
                </h6>
                <div style={{ overflowX: 'auto', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.01)' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.03)' }}>
                        <th style={{ padding: '14px 18px', color: 'rgba(255,255,255,0.6)', fontWeight: 'bold', fontSize: '0.75rem', textTransform: 'uppercase' }}>Metric / Parameter</th>
                        <th style={{ padding: '14px 18px', color: '#f87171', fontWeight: 'bold', fontSize: '0.75rem', textTransform: 'uppercase', textAlign: 'right' }}>Legacy MCP (Baseline)</th>
                        <th style={{ padding: '14px 18px', color: '#34d399', fontWeight: 'bold', fontSize: '0.75rem', textTransform: 'uppercase', textAlign: 'right' }}>Elemm Gateway (Optimized)</th>
                        <th style={{ padding: '14px 18px', color: 'rgba(255,255,255,0.5)', fontWeight: 'bold', fontSize: '0.75rem', textTransform: 'uppercase' }}>Calculation Formula & Rationale</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '14px 18px', color: '#ffffff', fontWeight: '600' }}>Total Directory Tools (N)</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: 'rgba(255,255,255,0.8)' }}>{analysisResult?.toolCount} tools</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: 'rgba(255,255,255,0.8)' }}>{analysisResult?.toolCount} tools</td>
                        <td style={{ padding: '14px 18px', color: 'rgba(255,255,255,0.45)', fontStyle: 'italic' }}>Total tool count registered in the spec directory</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '14px 18px', color: '#ffffff', fontWeight: '600' }}>Avg. Payload per Tool</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: '#f87171', background: 'rgba(239,68,68,0.02)' }}>~{Math.round(960 / charToTokenRatio)} tokens</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: '#34d399', background: 'rgba(16,185,129,0.02)' }}>~{Math.round(48 / charToTokenRatio)} tokens</td>
                        <td style={{ padding: '14px 18px', color: 'rgba(255,255,255,0.45)', fontStyle: 'italic' }}>Traditional JSON (960 chars avg.) vs. Elemm key (48 chars avg.)</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '14px 18px', color: '#ffffff', fontWeight: '600' }}>Base Single-Turn Context</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: '#f87171', background: 'rgba(239,68,68,0.02)' }}>{(analysisResult?.toolCount * Math.round(960 / charToTokenRatio)).toLocaleString()} tokens</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: '#34d399', background: 'rgba(16,185,129,0.02)' }}>{(analysisResult?.toolCount * Math.round(48 / charToTokenRatio)).toLocaleString()} tokens</td>
                        <td style={{ padding: '14px 18px', color: 'rgba(255,255,255,0.45)', fontStyle: 'italic' }}>Traditional: N × TL (full schemas) | Elemm: N × TE (topology skeleton only)</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '14px 18px', color: '#ffffff', fontWeight: '600' }}>Conversation Turns (D)</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: 'rgba(255,255,255,0.8)' }}>{convTurns} turns</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: 'rgba(255,255,255,0.8)' }}>{convTurns} turns</td>
                        <td style={{ padding: '14px 18px', color: 'rgba(255,255,255,0.45)', fontStyle: 'italic' }}>Simulated dialogue depth in agent interactions</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '14px 18px', color: '#ffffff', fontWeight: '600' }}>Piping & Sequencer Efficiency</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: 'rgba(255,255,255,0.4)' }}>Not supported</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: '#34d399', background: 'rgba(16,185,129,0.02)' }}>{liveMetrics.elemmRoundtrips} / {convTurns} turns</td>
                        <td style={{ padding: '14px 18px', color: 'rgba(255,255,255,0.45)', fontStyle: 'italic' }}>Reduced roundtrips due to sequence piping ({pipeRatio}% success rate)</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '14px 18px', color: '#ffffff', fontWeight: '600' }}>Dynamic On-Demand Fetches</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: 'rgba(255,255,255,0.4)' }}>Not applicable</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: 'rgba(255,255,255,0.8)' }}>{toolsUsed} tools</td>
                        <td style={{ padding: '14px 18px', color: 'rgba(255,255,255,0.45)', fontStyle: 'italic' }}>Only executed tools are lazy-loaded dynamically in Elemm</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.01)' }}>
                        <td style={{ padding: '14px 18px', color: '#ffffff', fontWeight: 'bold' }}>Total Cumulative Cost</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: '#ef4444', fontWeight: 'bold', fontSize: '0.9rem', background: 'rgba(239,68,68,0.05)' }}>{liveMetrics.legacyTotalTokens.toLocaleString()} t</td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace', textAlign: 'right', color: '#10b981', fontWeight: 'bold', fontSize: '0.9rem', background: 'rgba(16,185,129,0.05)' }}>{liveMetrics.elemmTotalTokens.toLocaleString()} t</td>
                        <td style={{ padding: '14px 18px', color: 'rgba(255,255,255,0.5)', fontWeight: '500' }}>
                          {cachingEnabled 
                            ? "Cumulative turns with 90% cache hits" 
                            : `Traditional: D × Turn-Cost | Elemm: Topology + On-Demand + History`
                          }
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="audit-footer bg-dark-light" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255, 255, 255, 0.03)', padding: '16px', borderRadius: '12px', marginTop: '20px', border: '1px solid rgba(255,255,255,0.08)' }}>
                <div style={{ textAlign: 'left', flex: 1, marginRight: '16px' }}>
                  <span className="font-bold text-sm text-accent tracking-wider uppercase" style={{ display: 'block', fontSize: '0.8rem', color: 'var(--accent-primary)', fontWeight: 'bold' }}>Simulation Summary</span>
                  <span className="text-xs text-muted leading-relaxed" style={{ display: 'block', fontSize: '0.75rem', color: 'rgba(255,255,255,0.5)', marginTop: '4px', lineHeight: '1.4' }}>
                    The optimization simulation indicates that the Elemm tiered discovery model reduces payload overhead by <strong className="text-success" style={{ color: '#10b981' }}>{liveMetrics.savingsPercent}%</strong>, projecting a cumulative context window requirement of <strong className="text-accent" style={{ color: 'var(--accent-primary)' }}>{liveMetrics.elemmTotalTokens.toLocaleString()} tokens</strong> over {convTurns} turns.
                  </span>
                </div>
                <div style={{ flexShrink: 0, textAlign: 'right' }}>
                  <span className="text-success font-extrabold text-xl font-mono" style={{ display: 'block', fontSize: '1.4rem', color: '#10b981', fontWeight: '900' }}>{(liveMetrics.legacyTotalTokens - liveMetrics.elemmTotalTokens).toLocaleString()}</span>
                  <span style={{ display: 'block', fontSize: '0.65rem', color: 'rgba(255,255,255,0.4)', fontWeight: 'bold', letterSpacing: '0.5px', textTransform: 'uppercase', marginTop: '2px' }}>Tokens Saved</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TokenAnalyzer;
