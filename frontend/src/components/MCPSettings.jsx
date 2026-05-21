import React, { useState, useEffect } from 'react';
import { 
  Cpu, Save, AlertTriangle, CheckCircle, Terminal, Plus, Trash2, 
  Settings2, Key, HelpCircle, ShieldAlert, FileText, ChevronRight, ChevronDown, X, Zap, Wrench, Search, MoreVertical
} from 'lucide-react';
import { API_BASE } from '../config';
import { Input, Select, Button, Switch, FormGroup, Textarea } from './ui';
import Slide2Delete from './Slide2Delete';
import './MCPSettings.css';

const Tooltip = ({ text }) => (
  <span className="mcp-tooltip-container">
    <HelpCircle size={12} className="mcp-tooltip-icon" />
    <span className="mcp-tooltip-text">{text}</span>
  </span>
);

const renderParameterSchema = (inputSchema) => {
  if (!inputSchema || !inputSchema.properties) {
    return <span className="no-params-text">No parameters required.</span>;
  }
  const requiredList = inputSchema.required || [];
  return (
    <div className="mcp-tool-params-list">
      {Object.entries(inputSchema.properties).map(([name, prop]) => {
        const isRequired = requiredList.includes(name);
        return (
          <div key={name} className="mcp-tool-param-row">
            <div className="param-meta">
              <code className="param-name">{name}</code>
              <span className={`param-badge ${isRequired ? 'required' : 'optional'}`}>
                {isRequired ? 'required' : 'optional'}
              </span>
              <span className="param-type">{prop.type || 'any'}</span>
            </div>
            {prop.description && <p className="param-desc">{prop.description}</p>}
            {prop.default !== undefined && (
              <small className="param-default">Default: <code>{JSON.stringify(prop.default)}</code></small>
            )}
          </div>
        );
      })}
    </div>
  );
};

const MCPSettings = () => {
  const [yamlConfig, setYamlConfig] = useState('');
  const [servers, setServers] = useState({});
  const [savedServers, setSavedServers] = useState({});
  const [activeServerId, setActiveServerId] = useState(null);
  const [editMode, setEditMode] = useState('form'); // 'form' or 'yaml'
  const [serverStatuses, setServerStatuses] = useState({}); // { [id]: 'online' | 'offline' | 'checking' | 'unknown' }
  const [searchQuery, setSearchQuery] = useState('');
  const [activeMenuId, setActiveMenuId] = useState(null);
  const [status, setStatus] = useState({ type: null, message: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [toolInputs, setToolInputs] = useState({});
  const [executingTool, setExecutingTool] = useState(null);
  const [execResults, setExecResults] = useState({});
  const [vaultKeys, setVaultKeys] = useState([]);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importText, setImportText] = useState('');
  const [autoMigrateVault, setAutoMigrateVault] = useState(true);
  const [deletingServerId, setDeletingServerId] = useState(null);
  const [deletingEnvKey, setDeletingEnvKey] = useState(null);
  const [deletingRemedyTool, setDeletingRemedyTool] = useState(null);
  const [toolSearch, setToolSearch] = useState('');
  const [expandedTools, setExpandedTools] = useState({});

  // Helper: Convert JS state back to clean YAML
  const serializeToYaml = (serversObj) => {
    let yaml = "version: \"1.0\"\nservers:\n";
    const entries = Object.entries(serversObj);
    if (entries.length === 0) {
      return yaml;
    }
    entries.forEach(([id, srv]) => {
      yaml += `  ${id}:\n`;
      if (srv.name) yaml += `    name: "${srv.name}"\n`;
      if (srv.transport) yaml += `    transport: "${srv.transport}"\n`;
      
      if (srv.transport === 'sse') {
        if (srv.url) yaml += `    url: "${srv.url}"\n`;
      } else {
        if (srv.command) yaml += `    command: "${srv.command}"\n`;
        if (srv.args && srv.args.length > 0) {
          yaml += `    args:\n`;
          srv.args.forEach(arg => {
            yaml += `      - "${arg}"\n`;
          });
        }
      }
      
      if (srv.env && Object.keys(srv.env).length > 0) {
        yaml += `    env:\n`;
        Object.entries(srv.env).forEach(([k, v]) => {
          yaml += `      ${k}: "${v}"\n`;
        });
      }
      
      if (srv.remedies && Object.keys(srv.remedies).length > 0) {
        yaml += `    remedies:\n`;
        Object.entries(srv.remedies).forEach(([k, v]) => {
          if (typeof v === 'object' && v.on_error) {
            yaml += `      ${k}:\n        on_error: "${v.on_error}"\n`;
          } else {
            yaml += `      ${k}: "${v}"\n`;
          }
        });
      }
    });
    return yaml;
  };

  // Fetch current config on load
  const fetchConfig = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/v1/mcp/config`);
      const data = await res.json();
      if (res.ok) {
        setYamlConfig(data.yaml || '');
        const loadedServers = data.servers || {};
        setServers(loadedServers);
        setSavedServers(loadedServers);
        
        // Auto-select first server if available
        const keys = Object.keys(loadedServers);
        if (keys.length > 0) {
          setActiveServerId(keys[0]);
        }
        setStatus({ type: null, message: '' });
      } else {
        setStatus({ type: 'error', message: data.detail || 'Error loading configuration.' });
      }
    } catch (e) {
      setStatus({ type: 'error', message: 'Connection to dashboard server failed.' });
    } finally {
      setLoading(false);
    }
  };

  const fetchVaultKeys = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/vault`);
      if (res.ok) {
        const data = await res.json();
        setVaultKeys(Object.keys(data));
      }
    } catch (e) {
      console.error("Failed to load vault keys", e);
    }
  };

  useEffect(() => {
    fetchConfig();
    fetchVaultKeys();
  }, []);

  const handleImportConfig = async () => {
    try {
      setSaving(true);
      setStatus({ type: 'info', message: 'Importing configuration and migrating secrets...' });
      
      const res = await fetch(`${API_BASE}/api/v1/mcp/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          text: importText,
          migrate_to_vault: autoMigrateVault
        })
      });
      
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to import configuration.');
      }
      
      setStatus({ type: 'success', message: data.message });
      setShowImportModal(false);
      setImportText('');
      
      // Reload everything
      await fetchConfig();
      await fetchVaultKeys();
    } catch (e) {
      setStatus({ type: 'error', message: e.message || 'Import failed.' });
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    setTestResult(null);
  }, [activeServerId]);

  // Save changes to backend and test connection
  const handleSaveAndVerify = async (configToSave) => {
    try {
      setSaving(true);
      setStatus({ type: 'info', message: 'Validating syntax and saving configuration...' });
      
      const res = await fetch(`${API_BASE}/api/v1/mcp/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ yaml: configToSave })
      });
      
      const data = await res.json();
      if (!res.ok) {
        setStatus({ type: 'error', message: data.detail || 'Failed to save configuration.' });
        setSaving(false);
        return;
      }

      setYamlConfig(configToSave);
      
      // Refresh servers state from parsed response
      const configRes = await fetch(`${API_BASE}/api/v1/mcp/config`);
      const configData = await configRes.json();
      if (configRes.ok) {
        setServers(configData.servers || {});
        setSavedServers(configData.servers || {});
      }

      // Now immediately trigger active connection test!
      if (!activeServerId) {
        setStatus({ type: 'success', message: 'MCP configuration saved and validated successfully (no active server selected to test).' });
        setSaving(false);
        return;
      }

      setStatus({ type: 'info', message: 'Configuration saved. Executing live connection test...' });
      setTesting(true);
      setTestResult(null);

      const testRes = await fetch(`${API_BASE}/api/v1/mcp/test/${activeServerId}`);
      const testData = await testRes.json();

      if (testRes.ok) {
        setStatus({ 
          type: 'success', 
          message: `Verified & Saved! Connection to "mcp:${activeServerId}" successful with ${testData.tools?.length || 0} tools.` 
        });
        setTestResult({
          success: true,
          message: testData.message,
          tools: testData.tools || []
        });
      } else {
        setStatus({ 
          type: 'error', 
          message: `Saved & syntax validated, but connection test for "mcp:${activeServerId}" failed! ${testData.detail || ''}` 
        });
        setTestResult({
          success: false,
          message: testData.detail || 'Connection handshake failed.'
        });
      }
    } catch (e) {
      setStatus({ type: 'error', message: 'Failed to save. Network or connection error.' });
    } finally {
      setSaving(false);
      setTesting(false);
    }
  };

  // Triggered when clicking save in UI
  const triggerSave = () => {
    let currentServers = servers;
    if (editMode !== 'yaml' && newEnvKey.trim() && activeServerId) {
      const currentEnv = servers[activeServerId].env || {};
      const updatedServers = {
        ...servers,
        [activeServerId]: {
          ...servers[activeServerId],
          env: {
            ...currentEnv,
            [newEnvKey.trim()]: newEnvVal.trim()
          }
        }
      };
      setServers(updatedServers);
      currentServers = updatedServers;
      setNewEnvKey('');
      setNewEnvVal('');
    }

    if (editMode === 'yaml') {
      handleSaveAndVerify(yamlConfig);
    } else {
      const generatedYaml = serializeToYaml(currentServers);
      handleSaveAndVerify(generatedYaml);
    }
  };

  // Execute a live tool call with arguments
  const handleExecuteTool = async (toolName, inputSchema) => {
    if (!activeServerId) return;
    
    const args = {};
    if (inputSchema && inputSchema.properties) {
      Object.keys(inputSchema.properties).forEach(key => {
        const inputKey = `${activeServerId}:${toolName}:${key}`;
        const val = toolInputs[inputKey];
        if (val !== undefined && val !== '') {
          if (typeof val === 'string' && (val.startsWith('[') || val.startsWith('{'))) {
            try {
              args[key] = JSON.parse(val);
            } catch (err) {
              args[key] = val;
            }
          } else {
            args[key] = val;
          }
        }
      });
    }

    try {
      setExecutingTool(toolName);
      setExecResults(prev => ({
        ...prev,
        [toolName]: { loading: true }
      }));
      
      const res = await fetch(`${API_BASE}/api/v1/mcp/execute/${activeServerId}/${toolName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ arguments: args })
      });
      
      const data = await res.json();
      if (res.ok) {
        setExecResults(prev => ({
          ...prev,
          [toolName]: { success: true, data: data.result }
        }));
      } else {
        setExecResults(prev => ({
          ...prev,
          [toolName]: { success: false, error: data.detail || 'Execution failed.' }
        }));
      }
    } catch (e) {
      setExecResults(prev => ({
        ...prev,
        [toolName]: { success: false, error: 'Network error or execution failed.' }
      }));
    } finally {
      setExecutingTool(null);
    }
  };

  // Switch between Tabs: Parse/Sync config on switch
  const handleModeSwitch = (newMode) => {
    if (newMode === editMode) return;
    
    if (newMode === 'yaml') {
      // Sync from Form state to YAML string
      const generatedYaml = serializeToYaml(servers);
      setYamlConfig(generatedYaml);
    } else if (editMode === 'yaml') {
      // Sync from YAML string to Form/Tools state via backend validation/parse
      try {
        setStatus({ type: 'info', message: 'Synchronizing editor data...' });
        fetch(`${API_BASE}/api/v1/mcp/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ yaml: yamlConfig })
        }).then(res => {
          if (res.ok) {
            fetch(`${API_BASE}/api/v1/mcp/config`).then(r => r.json()).then(data => {
              setServers(data.servers || {});
              setSavedServers(data.servers || {});
              const keys = Object.keys(data.servers || {});
              if (keys.length > 0 && (!activeServerId || !data.servers[activeServerId])) {
                setActiveServerId(keys[0]);
              }
              setStatus({ type: null, message: '' });
              // If new mode is tools and we don't have tools, auto-load
              if (newMode === 'tools' && (!testResult || !testResult.tools || testResult.tools.length === 0)) {
                handleTestConnection();
              }
            });
          } else {
            res.json().then(err => {
              setStatus({ type: 'error', message: `Cannot load data: ${err.detail}` });
            });
          }
        });
      } catch (e) {
        setStatus({ type: 'error', message: 'Synchronization failed.' });
      }
    } else {
      // Switching between Form and Tools (no YAML sync needed)
      if (newMode === 'tools' && (!testResult || !testResult.tools || testResult.tools.length === 0)) {
        handleTestConnection();
      }
    }
    setEditMode(newMode);
  };

  // Form handlers
  const updateActiveServerField = (field, value) => {
    if (!activeServerId) return;
    setServers(prev => ({
      ...prev,
      [activeServerId]: {
        ...prev[activeServerId],
        [field]: value
      }
    }));
  };

  // Arguments
  const [newArgText, setNewArgText] = useState('');
  const addArgument = () => {
    if (!newArgText.trim() || !activeServerId) return;
    const currentArgs = servers[activeServerId].args || [];
    updateActiveServerField('args', [...currentArgs, newArgText.trim()]);
    setNewArgText('');
  };

  const removeArgument = (index) => {
    if (!activeServerId) return;
    const currentArgs = servers[activeServerId].args || [];
    updateActiveServerField('args', currentArgs.filter((_, i) => i !== index));
  };

  // Env variables
  const [newEnvKey, setNewEnvKey] = useState('');
  const [newEnvVal, setNewEnvVal] = useState('');
  const addEnvVar = () => {
    if (!newEnvKey.trim() || !activeServerId) return;
    const currentEnv = servers[activeServerId].env || {};
    setServers(prev => ({
      ...prev,
      [activeServerId]: {
        ...prev[activeServerId],
        env: {
          ...currentEnv,
          [newEnvKey.trim()]: newEnvVal.trim()
        }
      }
    }));
    setNewEnvKey('');
    setNewEnvVal('');
  };

  const removeEnvVar = (key) => {
    if (!activeServerId) return;
    const currentEnv = { ...servers[activeServerId].env };
    delete currentEnv[key];
    setServers(prev => ({
      ...prev,
      [activeServerId]: {
        ...prev[activeServerId],
        env: currentEnv
      }
    }));
  };

  // Remedies
  const [newRemedyTool, setNewRemedyTool] = useState('');
  const [newRemedyMsg, setNewRemedyMsg] = useState('');
  const addRemedy = () => {
    if (!newRemedyTool.trim() || !newRemedyMsg.trim() || !activeServerId) return;
    const currentRemedies = servers[activeServerId].remedies || {};
    setServers(prev => ({
      ...prev,
      [activeServerId]: {
        ...prev[activeServerId],
        remedies: {
          ...currentRemedies,
          [newRemedyTool.trim()]: newRemedyMsg.trim()
        }
      }
    }));
    setNewRemedyTool('');
    setNewRemedyMsg('');
  };

  const removeRemedy = (toolName) => {
    if (!activeServerId) return;
    const currentRemedies = { ...servers[activeServerId].remedies };
    delete currentRemedies[toolName];
    setServers(prev => ({
      ...prev,
      [activeServerId]: {
        ...prev[activeServerId],
        remedies: currentRemedies
      }
    }));
  };

  // Add new Server
  const addNewServer = () => {
    const newId = `new_server_${Object.keys(servers).length + 1}`;
    const newServerObj = {
      name: "New MCP Server",
      transport: "stdio",
      command: "npx",
      args: [],
      env: {},
      remedies: {}
    };
    
    setServers(prev => ({
      ...prev,
      [newId]: newServerObj
    }));
    setActiveServerId(newId);
  };

  // Delete server
  const deleteServer = async (idToDelete) => {
    try {
      setStatus({ type: 'info', message: `Deleting server '${idToDelete}'...` });
      const res = await fetch(`${API_BASE}/api/v1/mcp/server/${idToDelete}`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (res.ok) {
        setStatus({ type: 'success', message: data.message });
        
        // Update local state
        const updatedServers = { ...servers };
        delete updatedServers[idToDelete];
        setServers(updatedServers);
        
        // Auto-select another server
        const keys = Object.keys(updatedServers);
        if (keys.length > 0) {
          setActiveServerId(keys[0]);
        } else {
          setActiveServerId(null);
        }
        
        // Refresh servers state from config
        const configRes = await fetch(`${API_BASE}/api/v1/mcp/config`);
        const configData = await configRes.json();
        if (configRes.ok) {
          setServers(configData.servers || {});
          setSavedServers(configData.servers || {});
        }
      } else {
        setStatus({ type: 'error', message: data.detail || 'Failed to delete server.' });
      }
    } catch (err) {
      setStatus({ type: 'error', message: 'Network error occurred while deleting server.' });
    }
  };

  const testServer = async (serverId) => {
    if (!serverId) return;
    try {
      setServerStatuses(prev => ({ ...prev, [serverId]: 'checking' }));
      const res = await fetch(`${API_BASE}/api/v1/mcp/test/${serverId}`);
      const data = await res.json();
      if (res.ok) {
        if (data.status === 'warning') {
          setServerStatuses(prev => ({ ...prev, [serverId]: 'warning' }));
          if (serverId === activeServerId) {
            setTestResult({
              success: 'warning',
              message: data.message,
              tools: []
            });
          }
        } else if (data.status === 'success') {
          setServerStatuses(prev => ({ ...prev, [serverId]: 'online' }));
          if (serverId === activeServerId) {
            setTestResult({
              success: true,
              message: data.message,
              tools: data.tools || []
            });
          }
        } else {
          setServerStatuses(prev => ({ ...prev, [serverId]: 'offline' }));
          if (serverId === activeServerId) {
            setTestResult({
              success: false,
              message: data.message || 'Connection test returned an error status.'
            });
          }
        }
      } else {
        setServerStatuses(prev => ({ ...prev, [serverId]: 'offline' }));
        if (serverId === activeServerId) {
          setTestResult({
            success: false,
            message: data.detail || 'Connection testing handshake failed.'
          });
        }
      }
    } catch (e) {
      setServerStatuses(prev => ({ ...prev, [serverId]: 'offline' }));
      if (serverId === activeServerId) {
        setTestResult({
          success: false,
          message: 'Network error occurred while executing connection test.'
        });
      }
    }
  };

  // Connection tester
  const handleTestConnection = async () => {
    if (!activeServerId) return;
    setTesting(true);
    setTestResult(null);
    
    let currentServers = servers;
    if (newEnvKey.trim()) {
      const currentEnv = servers[activeServerId].env || {};
      const updatedServers = {
        ...servers,
        [activeServerId]: {
          ...servers[activeServerId],
          env: {
            ...currentEnv,
            [newEnvKey.trim()]: newEnvVal.trim()
          }
        }
      };
      setServers(updatedServers);
      currentServers = updatedServers;
      setNewEnvKey('');
      setNewEnvVal('');
    }
    
    // Auto-save pending changes first so the backend actually knows about this new/updated server!
    if (JSON.stringify(currentServers) !== JSON.stringify(savedServers)) {
      const generatedYaml = serializeToYaml(currentServers);
      try {
        const res = await fetch(`${API_BASE}/api/v1/mcp/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ yaml: generatedYaml })
        });
        if (res.ok) {
          const configData = await res.json();
          setSavedServers(configData.servers || {});
          setYamlConfig(generatedYaml);
        }
      } catch (e) {
        console.error("Auto-save before test failed:", e);
      }
    }
    
    await testServer(activeServerId);
    setTesting(false);
  };

  // Parallel verify all servers
  const verifyAllServers = async () => {
    const ids = Object.keys(servers);
    if (ids.length === 0) return;
    setStatus({ type: 'info', message: `Verifying all ${ids.length} MCP servers...` });
    
    // Run them in parallel!
    await Promise.all(ids.map(id => testServer(id)));
    setStatus({ type: 'success', message: 'Verification handshake complete for all servers.' });
  };

  if (loading) {
    return (
      <div className="mcp-loading">
        <Cpu className="mcp-spin-icon" size={48} />
        <p>Loading MCP configuration...</p>
      </div>
    );
  }

  const hasPendingChanges = editMode === 'yaml' ? false : (JSON.stringify(servers) !== JSON.stringify(savedServers));
  const activeServer = activeServerId ? servers[activeServerId] : null;

  const filteredServers = Object.entries(servers).filter(([id, srv]) => {
    const query = searchQuery.toLowerCase().trim();
    if (!query) return true;
    const name = (srv.name || '').toLowerCase();
    const serverId = id.toLowerCase();
    const command = (srv.command || '').toLowerCase();
    return name.includes(query) || serverId.includes(query) || command.includes(query);
  });

  return (
    <div className="mcp-settings-container animate-slide-up custom-scrollbar">
      {/* Main Master-Detail split workspace */}
      <div className="mcp-workspace">
        {/* Left Sidebar: Servers Menu */}
        <div className="mcp-sidebar-menu">
          <div className="mcp-sidebar-header">
            <div className="mcp-sidebar-header-top">
              <div className="mcp-sidebar-title-pill">
                <h2>Servers</h2>
                <span className="count-badge">{Object.keys(servers).length}</span>
              </div>
              <div className="mcp-sidebar-actions">
                <Button 
                  className="mcp-action-btn secondary"
                  onClick={verifyAllServers}
                  title="Verify all servers in parallel"
                >
                  <Zap size={14} />
                </Button>
                <Button 
                  className="mcp-action-btn secondary" 
                  onClick={() => {
                    setImportText('');
                    setShowImportModal(true);
                  }} 
                  title="Import existing Claude/Elemm configuration"
                >
                  <FileText size={14} />
                </Button>
                <Button 
                  className="mcp-action-btn primary" 
                  onClick={addNewServer} 
                  title="Add new server"
                >
                  <Plus size={14} />
                </Button>
              </div>
            </div>

            <div className="mcp-sidebar-search">
              <Search size={14} className="search-icon" />
              <Input 
                type="text" 
                placeholder="Search servers..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="search-input"
              />
              {searchQuery && (
                <Button className="clear-search-btn" onClick={() => setSearchQuery('')}>
                  ×
                </Button>
              )}
            </div>
          </div>
          
          <div className="mcp-sidebar-list">
            {Object.keys(servers).length === 0 ? (
              <div className="mcp-sidebar-empty">
                No servers configured.
              </div>
            ) : filteredServers.length === 0 ? (
              <div className="mcp-sidebar-empty">
                No matching servers found.
              </div>
            ) : (
              filteredServers.map(([id, srv]) => (
                <div 
                  key={id} 
                  className={`mcp-sidebar-item ${activeServerId === id ? 'active' : ''} ${deletingServerId === id ? 'deleting' : ''}`}
                  onClick={() => {
                    if (deletingServerId !== id) {
                      setActiveServerId(id);
                      setActiveMenuId(null);
                    }
                  }}
                >
                  {deletingServerId === id && (
                    <Slide2Delete 
                      onConfirm={() => {
                        deleteServer(id);
                        setDeletingServerId(null);
                      }}
                      onCancel={() => setDeletingServerId(null)}
                      label="Slide to delete"
                    />
                  )}
                  <div className="mcp-sidebar-item-info">
                    <div className="mcp-server-icon-container">
                      <Cpu size={16} />
                      <span className={`status-dot ${serverStatuses[id] || 'unknown'}`} title={`Status: ${serverStatuses[id] || 'unknown'}`} />
                    </div>
                    <div className="mcp-sidebar-item-names">
                      <span className="name">{srv.name || id}</span>
                      <span className="id">mcp:{id}</span>
                    </div>
                  </div>
                  
                  <div className="mcp-item-menu-container">
                    <Button 
                      className={`mcp-more-btn ${activeMenuId === id ? 'active' : ''}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveMenuId(activeMenuId === id ? null : id);
                      }}
                      title="Server actions"
                    >
                      <MoreVertical size={16} />
                    </Button>
                    
                    {activeMenuId === id && (
                      <>
                        <div className="mcp-dropdown-backdrop" onClick={(e) => {
                          e.stopPropagation();
                          setActiveMenuId(null);
                        }} />
                        <div className="mcp-item-dropdown glass animate-fade-in" onClick={(e) => e.stopPropagation()}>
                          <Button 
                            className="dropdown-item" 
                            onClick={(e) => {
                              e.stopPropagation();
                              testServer(id);
                              setActiveMenuId(null);
                            }}
                          >
                            <Zap size={14} className="text-accent" />
                            <span>Verify Status</span>
                          </Button>
                          <Button 
                            className="dropdown-item delete" 
                            onClick={(e) => {
                              e.stopPropagation();
                              setDeletingServerId(id);
                              setActiveMenuId(null);
                            }}
                          >
                            <Trash2 size={14} />
                            <span>Delete Server</span>
                          </Button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Detail Panel: Form/YAML Editor */}
        <div className="mcp-detail-panel">
          {/* Detail Tabs */}
          <div className="mcp-detail-header">
            <div className="mcp-tabs">
              <Button 
                className={`mcp-tab ${editMode === 'form' ? 'active' : ''}`}
                onClick={() => handleModeSwitch('form')}
                disabled={!activeServerId}
              >
                <Settings2 size={16} /> Form Editor
              </Button>
              <Button 
                className={`mcp-tab ${editMode === 'tools' ? 'active' : ''}`}
                onClick={() => handleModeSwitch('tools')}
                disabled={!activeServerId}
              >
                <Wrench size={16} /> Discovered Tools & Remedies
              </Button>
              <Button 
                className={`mcp-tab ${editMode === 'yaml' ? 'active' : ''}`}
                onClick={() => handleModeSwitch('yaml')}
              >
                <Terminal size={16} /> Code Editor (YAML)
              </Button>
            </div>

          </div>

          {/* Tab content area */}
          <div className="mcp-detail-body custom-scrollbar">
            {!activeServerId && editMode === 'form' ? (
              <div className="mcp-detail-empty-state">
                <HelpCircle size={48} />
                <p>No Server Selected</p>
                <span>Add a new server on the left or select an existing one to configure.</span>
              </div>
            ) : editMode === 'form' && activeServer ? (
              <div className="mcp-form-layout animate-slide-up">
                <div className="mcp-form-intro">
                  <p>Configure this external Model Context Protocol server. Bridges tools into Elemm landmarks via stdio subprocess transport.</p>
                </div>

                {/* Section 1: Core Configuration */}
                <div className="mcp-form-section">
                  <h5>Core Details</h5>
                  <div className="mcp-form-row-2">
                    <FormGroup label={<>Server Identifier (Key)* <Tooltip text="A unique lowercase key. All tools will be namespaced under this identifier, e.g. mcp:github:search_repos." /></>}>
                      <Input 
                        type="text" 
                        value={activeServerId} 
                        onChange={(e) => {
                          const oldId = activeServerId;
                          const newId = e.target.value.replace(/[^a-zA-Z0-9_-]/g, '');
                          if (newId && newId !== oldId) {
                            setServers(prev => {
                              const updated = { ...prev };
                              updated[newId] = updated[oldId];
                              delete updated[oldId];
                              return updated;
                            });
                            setActiveServerId(newId);
                          }
                        }}
                        placeholder="e.g. github"
                      />
                      <small>Unique system key in the landmark namespace.</small>
                    </FormGroup>
                    
                    <FormGroup label={<>Display Name <Tooltip text="A descriptive display name for the server used in logs, telemetry, and gateway dashboards." /></>}>
                      <Input 
                        type="text" 
                        value={activeServer.name || ''} 
                        onChange={(e) => updateActiveServerField('name', e.target.value)}
                        placeholder="e.g. GitHub Server"
                      />
                      <small>Friendly name for logs and dashboard.</small>
                    </FormGroup>
                  </div>

                  <div className="mcp-form-row-2">
                    <FormGroup label={<>Transport Type <Tooltip text="Use 'stdio' to spawn local subprocesses or 'sse' to communicate with remote HTTP-based servers." /></>}>
                      <Select 
                        value={activeServer.transport || 'stdio'} 
                        onChange={(e) => updateActiveServerField('transport', e.target.value)}
                      >
                        <option value="stdio">stdio (Standard Input/Output)</option>
                        <option value="sse">sse (HTTP Server Sent Events)</option>
                      </Select>
                      <small>Communication protocol for data exchange.</small>
                    </FormGroup>
                    
                    {activeServer.transport === 'sse' ? (
                      <FormGroup label={<>Remote Server URL (URL)* <Tooltip text="The full HTTP/HTTPS URL of the remote SSE MCP server, e.g. https://tandem.ac/mcp." /></>}>
                        <Input 
                          type="text" 
                          value={activeServer.url || ''} 
                          onChange={(e) => {
                            const newUrl = e.target.value;
                            updateActiveServerField('url', newUrl);
                            
                            try {
                              if (newUrl && (newUrl.startsWith('http://') || newUrl.startsWith('https://'))) {
                                const parsedUrl = new URL(newUrl);
                                const host = parsedUrl.hostname; // e.g. mcp.notion.com
                                let cleanName = host.replace('www.', '');
                                
                                // Make clean ID like "notion-mcp"
                                const domainParts = cleanName.split('.');
                                const mainDomain = domainParts.length > 1 ? domainParts[domainParts.length - 2] : domainParts[0];
                                const cleanId = `${mainDomain}-mcp`.toLowerCase().replace(/[^a-z0-9_-]/g, '');

                                // Update display name if it's default or empty
                                if (!activeServer.name || activeServer.name === 'New MCP Server' || activeServer.name === 'New Server') {
                                  updateActiveServerField('name', cleanName.split('.').map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(' '));
                                }

                                // Update server id if it's still the default new_server_x
                                if (activeServerId.startsWith('new_server_')) {
                                  let finalId = cleanId;
                                  let counter = 1;
                                  while (servers[finalId] && finalId !== activeServerId) {
                                    finalId = `${cleanId}_${counter}`;
                                    counter++;
                                  }
                                  
                                  const oldId = activeServerId;
                                  setServers(prev => {
                                    const updated = { ...prev };
                                    updated[finalId] = updated[oldId];
                                    delete updated[oldId];
                                    return updated;
                                  });
                                  setActiveServerId(finalId);
                                }
                              }
                            } catch (err) {
                              // Not a valid URL yet, skip auto-fill
                            }
                          }}
                          placeholder="e.g. https://tandem.ac/mcp"
                        />
                        <small>Endpoint URL of the remote SSE landmark.</small>
                      </FormGroup>
                    ) : (
                      <FormGroup label={<>Executable Command (Command)* <Tooltip text="The main CLI command to boot your server process, e.g. npx, python3, node, or a direct binary path." /></>}>
                        <Input 
                          type="text" 
                          value={activeServer.command || ''} 
                          onChange={(e) => updateActiveServerField('command', e.target.value)}
                          placeholder="e.g. npx, python3, node"
                        />
                        <small>CLI command used to boot the subprocess.</small>
                      </FormGroup>
                    )}
                  </div>
                </div>

                {/* Section: Live Connection Tester */}
                <div className="mcp-form-section">
                  <h5>Connection Testing & Debugging</h5>
                  <div className="mcp-test-box">
                    <div className="mcp-test-action-row">
                      <p>
                        Verify that the Elemm Gateway can successfully spawn this MCP server process, 
                        establish the standard JSON-RPC handshake, and retrieve the list of tools.
                      </p>
                      <Button 
                        type="button"
                        className="btn-secondary-sm mcp-test-btn" 
                        onClick={handleTestConnection} 
                        disabled={testing}
                      >
                        <Zap size={14} className={testing ? 'mcp-pulse animate-spin' : ''} />
                        {testing ? 'Testing...' : 'Test Connection'}
                      </Button>
                    </div>
                    
                    {testResult && (
                      <div className={`mcp-test-result-box ${testResult.success === 'warning' ? 'warning' : testResult.success ? 'success' : 'error'}`}>
                        <div className="mcp-test-result-header">
                          {testResult.success === 'warning' ? <AlertTriangle size={16} /> : testResult.success ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
                          <strong>{testResult.success === 'warning' ? 'Connection Warning' : testResult.success ? 'Connection Successful!' : 'Connection Failed!'}</strong>
                        </div>
                        <p className="mcp-test-result-msg" style={{ whiteSpace: 'pre-wrap' }}>{testResult.message}</p>
                        
                        {testResult.success === true && (
                          <div className="mcp-test-tools-discovered">
                            <h6>Tools Discovered ({testResult.tools.length}):</h6>
                            {testResult.tools.length === 0 ? (
                              <span className="no-tools-text">No tools returned by this server.</span>
                            ) : (
                              <div className="mcp-test-tools-list custom-scrollbar">
                                {testResult.tools.map((tool, idx) => (
                                  <div key={idx} className="mcp-discovered-tool-item">
                                    <div className="tool-name-row">
                                      <code>{tool.name}</code>
                                      <span className="tool-desc">{tool.description}</span>
                                    </div>
                                    {tool.inputSchema && (
                                      <pre className="tool-schema-pre">
                                        {JSON.stringify(tool.inputSchema, null, 2)}
                                      </pre>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Section 2: Command Arguments */}
                {activeServer.transport !== 'sse' && (
                  <div className="mcp-form-section">
                    <h5>
                      Startup Arguments (args)
                      <Tooltip text="Pass command line arguments one by one to the process startup command, e.g. -y or paths to local scripts." />
                    </h5>
                    <div className="mcp-args-box">
                      <div className="mcp-args-list">
                        {(activeServer.args || []).length === 0 ? (
                          <span className="no-args-text">No arguments configured.</span>
                        ) : (
                          (activeServer.args || []).map((arg, i) => (
                            <div key={i} className="mcp-arg-badge">
                              <span>{arg}</span>
                              <Button onClick={() => removeArgument(i)}><X size={12} /></Button>
                            </div>
                          ))
                        )}
                      </div>
                      <div className="mcp-args-input-row">
                        <Input 
                          type="text" 
                          value={newArgText} 
                          onChange={(e) => setNewArgText(e.target.value)}
                          placeholder="New argument (e.g. -y)"
                          onKeyDown={(e) => { if (e.key === 'Enter') addArgument(); }}
                        />
                        <Button onClick={addArgument} className="btn-secondary-sm"><Plus size={14} /> Add</Button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Section 3: Environment Variables */}
                <div className="mcp-form-section">
                  <h5>
                    Environment Variables (env)
                    <Tooltip text="Environment variables passed to the subprocess. Prefix values with 'env:' to dynamically and securely load host variables." />
                  </h5>
                  <div className="mcp-table-box">
                    <div className="mcp-table-header">
                      <span>Variable (Key)</span>
                      <span>Value</span>
                      <span>Action</span>
                    </div>
                    <div className="mcp-table-rows">
                      {Object.keys(activeServer.env || {}).length === 0 ? (
                        <div className="mcp-table-empty">No environment variables configured.</div>
                      ) : (
                        Object.entries(activeServer.env || {}).map(([key, val]) => (
                          <div key={key} className={`mcp-table-row ${deletingEnvKey === key ? 'deleting-row-mode' : ''}`} style={{ position: 'relative', overflow: 'hidden' }}>
                            {deletingEnvKey === key && (
                              <Slide2Delete 
                                onConfirm={() => {
                                  removeEnvVar(key);
                                  setDeletingEnvKey(null);
                                }}
                                onCancel={() => setDeletingEnvKey(null)}
                                label="Slide to delete variable"
                              />
                            )}
                            <code className="key-code">{key}</code>
                            <div className="val-box">
                              <span>{val}</span>
                              {val.startsWith('env:') && <span className="val-badge">🔒 Resolved</span>}
                            </div>
                            <Button onClick={() => setDeletingEnvKey(key)} className="row-delete-btn" title="Delete environment variable">
                              <Trash2 size={14} />
                            </Button>
                          </div>
                        ))
                      )}
                    </div>
                    <div className="mcp-table-input-row with-vault">
                      <Input 
                        type="text" 
                        placeholder="KEY (e.g. GITHUB_TOKEN)" 
                        value={newEnvKey}
                        onChange={(e) => setNewEnvKey(e.target.value)}
                      />
                      <Input 
                        type="text" 
                        placeholder="Value or env:VAR" 
                        value={newEnvVal}
                        onChange={(e) => setNewEnvVal(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') addEnvVar(); }}
                      />
                      {vaultKeys.length > 0 && (
                        <Select 
                          className="mcp-vault-quickselect"
                          value=""
                          onChange={(e) => {
                            if (e.target.value) {
                              setNewEnvVal(`vault:${e.target.value}`);
                              if (!newEnvKey) {
                                setNewEnvKey(e.target.value);
                              }
                            }
                          }}
                        >
                          <option value="">-- Link Vault Secret --</option>
                          {vaultKeys.map(k => (
                            <option key={k} value={k}>{k}</option>
                          ))}
                        </Select>
                      )}
                      <Button onClick={addEnvVar} className="btn-secondary-sm"><Plus size={14} /> Add</Button>
                    </div>
                  </div>
                </div>

                {/* Section 4: Smart Remedies */}
                <div className="mcp-form-section">
                  <h5>
                    Smart Remedies
                    <Tooltip text="Associate corrective instructions with specific tools. When a tool fails, the AI will use this prompt to repair the error." />
                  </h5>
                  <div className="mcp-table-box">
                    <div className="mcp-table-header">
                      <span>Tool (Action Name)</span>
                      <span>Remedy Instruction (on_error)</span>
                      <span>Action</span>
                    </div>
                    <div className="mcp-table-rows">
                      {Object.keys(activeServer.remedies || {}).length === 0 ? (
                        <div className="mcp-table-empty">No custom remedies assigned.</div>
                      ) : (
                        Object.entries(activeServer.remedies || {}).map(([tool, rem]) => (
                          <div key={tool} className={`mcp-table-row ${deletingRemedyTool === tool ? 'deleting-row-mode' : ''}`} style={{ position: 'relative', overflow: 'hidden' }}>
                            {deletingRemedyTool === tool && (
                              <Slide2Delete 
                                onConfirm={() => {
                                  removeRemedy(tool);
                                  setDeletingRemedyTool(null);
                                }}
                                onCancel={() => setDeletingRemedyTool(null)}
                                label="Slide to delete remedy"
                              />
                            )}
                            <code className="key-code">{tool}</code>
                            <span className="remedy-text">{typeof rem === 'object' ? rem.on_error : rem}</span>
                            <Button onClick={() => setDeletingRemedyTool(tool)} className="row-delete-btn" title="Delete remedy">
                              <Trash2 size={14} />
                            </Button>
                          </div>
                        ))
                      )}
                    </div>
                    <div className="mcp-table-input-row">
                      <Input 
                        type="text" 
                        placeholder="Tool name (e.g. search_repos)" 
                        value={newRemedyTool}
                        onChange={(e) => setNewRemedyTool(e.target.value)}
                      />
                      <Input 
                        type="text" 
                        placeholder="Remedy hint on error..." 
                        value={newRemedyMsg}
                        onChange={(e) => setNewRemedyMsg(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') addRemedy(); }}
                      />
                      <Button onClick={addRemedy} className="btn-secondary-sm"><Plus size={14} /> Add</Button>
                    </div>
                  </div>
                </div>
              </div>
            ) : editMode === 'tools' && activeServer ? (
              <div className="mcp-tools-layout animate-slide-up">
                <div className="mcp-form-intro">
                  <p>
                    Browse the live tools exposed by this Model Context Protocol server. 
                    Configure custom AI remedies directly next to each tool to guide agent recovery on failures.
                  </p>
                </div>

                <div className="mcp-tools-action-bar">
                  <Button 
                    type="button" 
                    className="btn-secondary-sm mcp-tools-fetch-btn"
                    onClick={handleTestConnection}
                    disabled={testing}
                  >
                    <Zap size={14} className={testing ? 'mcp-pulse animate-spin' : ''} />
                    {testing ? 'Fetching tools...' : 'Reload Live Tools'}
                  </Button>
                  <span className="mcp-badge">Live Handshake</span>
                </div>

                {testing && (!testResult || !testResult.tools || testResult.tools.length === 0) && (
                  <div className="mcp-tools-loading-state">
                    <Cpu size={32} className="mcp-pulse animate-spin" />
                    <p>Executing handshake and querying tools list...</p>
                  </div>
                )}

                {!testing && !testResult && (
                  <div className="mcp-tools-loading-state">
                    <Cpu size={32} />
                    <p>No tools loaded yet. Click 'Reload Live Tools' to connect.</p>
                  </div>
                )}

                {testResult && !testResult.success && (
                  <div className="mcp-tools-error-state">
                    <AlertTriangle size={32} className="error-icon" />
                    <p>Failed to retrieve tools from the server. Check your startup command and environment variables.</p>
                    <pre className="error-pre">{testResult.message}</pre>
                  </div>
                )}

                {testResult && testResult.success && (
                  <>
                    {testResult.tools.length > 0 && (
                      <div className="mcp-tools-search-bar">
                        <Search size={16} className="search-icon" />
                        <Input
                          type="text"
                          placeholder="Search tools by name or description..."
                          value={toolSearch}
                          onChange={(e) => setToolSearch(e.target.value)}
                          className="tools-search-input"
                        />
                        {toolSearch && (
                          <Button className="clear-search-btn" onClick={() => setToolSearch('')}>
                            ×
                          </Button>
                        )}
                      </div>
                    )}

                    <div className="mcp-tools-grid">
                      {testResult.tools.length === 0 ? (
                        <div className="mcp-table-empty">No tools returned by this server.</div>
                      ) : (
                        testResult.tools
                          .filter(tool => {
                            const q = toolSearch.toLowerCase().trim();
                            if (!q) return true;
                            return tool.name.toLowerCase().includes(q) || (tool.description || '').toLowerCase().includes(q);
                          })
                          .map((tool, idx) => {
                            const isExpanded = !!expandedTools[tool.name];
                            const currentRemedy = activeServer.remedies?.[tool.name] || '';
                            const hasRemedy = !!currentRemedy;
                            return (
                              <div key={idx} className={`mcp-tool-card ${isExpanded ? 'expanded' : 'collapsed'}`}>
                                <div 
                                  className="mcp-tool-card-header"
                                  onClick={() => {
                                    setExpandedTools(prev => ({
                                      ...prev,
                                      [tool.name]: !prev[tool.name]
                                    }));
                                  }}
                                >
                                  <div className="mcp-tool-card-header-left">
                                    <div className="tool-name-container">
                                      <Wrench size={16} className="tool-card-icon" />
                                      <span className="tool-card-name">{tool.name}</span>
                                    </div>
                                    <p className="tool-card-desc">
                                      {isExpanded 
                                        ? tool.description 
                                        : (tool.description ? tool.description.split('\n')[0].substring(0, 120) + (tool.description.length > 120 ? '...' : '') : 'No description.')
                                      }
                                    </p>
                                  </div>
                                  <div className="mcp-tool-card-header-right">
                                    {hasRemedy && (
                                      <span className="tool-remedy-badge">
                                        <ShieldAlert size={12} />
                                        Remedy set
                                      </span>
                                    )}
                                    {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                                  </div>
                                </div>

                                {isExpanded && (
                                  <div className="mcp-tool-card-body">
                                    <div className="mcp-tool-body-left">
                                      {tool.inputSchema && (
                                        <div className="mcp-tool-schema-section">
                                          <span className="schema-label">Parameters Schema:</span>
                                          {renderParameterSchema(tool.inputSchema)}
                                        </div>
                                      )}

                                      {/* Testing arguments input form */}
                                      {tool.inputSchema && tool.inputSchema.properties && (
                                        <div className="mcp-tool-test-inputs">
                                          <span className="schema-label">Execution Arguments:</span>
                                          <div className="mcp-tool-params-grid">
                                            {Object.entries(tool.inputSchema.properties).map(([pName, pProp]) => {
                                              const inputKey = `${activeServerId}:${tool.name}:${pName}`;
                                              const isRequired = (tool.inputSchema.required || []).includes(pName);
                                              return (
                                                <div key={pName} className="mcp-tool-param-field">
                                                  <label className="param-field-label">
                                                    <code>{pName}</code>
                                                    <span className="param-field-type">{pProp.type || 'string'}</span>
                                                    {isRequired && <span className="param-required-star">*</span>}
                                                  </label>
                                                  <Input
                                                    type="text"
                                                    className="mcp-tool-param-input"
                                                    placeholder={pProp.description || `Enter ${pName}...`}
                                                    value={toolInputs[inputKey] || ''}
                                                    onChange={(e) => {
                                                      setToolInputs(prev => ({
                                                        ...prev,
                                                        [inputKey]: e.target.value
                                                      }));
                                                    }}
                                                  />
                                                </div>
                                              );
                                            })}
                                          </div>
                                        </div>
                                      )}

                                      {/* Execute Button Row */}
                                      <div className="mcp-tool-execute-row">
                                        <Button
                                          type="button"
                                          className="btn-secondary-sm mcp-execute-btn"
                                          onClick={() => handleExecuteTool(tool.name, tool.inputSchema)}
                                          disabled={executingTool !== null}
                                        >
                                          <Zap size={13} className={executingTool === tool.name ? 'mcp-pulse animate-spin' : ''} />
                                          {executingTool === tool.name ? 'Executing...' : 'Execute now (Interactive Test)'}
                                        </Button>
                                      </div>

                                      {/* Execution Results box */}
                                      {execResults[tool.name] && (
                                        <div className={`mcp-tool-exec-result ${execResults[tool.name].success ? 'success' : 'error'}`}>
                                          <div className="exec-result-header">
                                            <strong>Execution Result:</strong>
                                            <Button 
                                              className="btn-clear-close"
                                              onClick={() => setExecResults(prev => {
                                                const updated = { ...prev };
                                                delete updated[tool.name];
                                                return updated;
                                              })}
                                            >
                                              Close Output
                                            </Button>
                                          </div>
                                          {execResults[tool.name].loading ? (
                                            <div className="exec-loading-spinner">
                                              <Cpu size={14} className="mcp-pulse animate-spin" />
                                              Executing tool on external MCP server...
                                            </div>
                                          ) : execResults[tool.name].success ? (
                                            <pre className="exec-result-pre custom-scrollbar">
                                              {JSON.stringify(execResults[tool.name].data, null, 2)}
                                            </pre>
                                          ) : (
                                            <div className="exec-error-msg">
                                              {execResults[tool.name].error}
                                            </div>
                                          )}
                                        </div>
                                      )}
                                    </div>

                                    <div className="mcp-tool-body-right">
                                      {/* Remedy configuration inline under this specific tool */}
                                      <div className="mcp-tool-remedy-section">
                                        <label className="remedy-label">
                                          <ShieldAlert size={14} />
                                          Active Tool Remedy (on_error prompt)
                                          <Tooltip text="A prompt/guidance shown to the AI agent if this specific tool fails. Tell the agent how to fix typical errors for this tool." />
                                        </label>
                                        <textarea
                                          className="mcp-tool-remedy-textarea"
                                          value={typeof currentRemedy === 'object' ? currentRemedy.on_error : currentRemedy}
                                          onChange={(e) => {
                                            const val = e.target.value;
                                            const currentRemedies = activeServer.remedies || {};
                                            if (val.trim() === '') {
                                              const updated = { ...currentRemedies };
                                              delete updated[tool.name];
                                              updateActiveServerField('remedies', updated);
                                            } else {
                                              updateActiveServerField('remedies', {
                                                ...currentRemedies,
                                                [tool.name]: val
                                              });
                                            }
                                          }}
                                          placeholder="e.g. Ensure GITHUB_TOKEN environment variable is configured and your key has repository write permission..."
                                        />
                                      </div>
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })
                      )}
                    </div>
                  </>
                )}
              </div>
            ) : (
              /* Code Editor tab */
              <div className="mcp-editor-container-tab animate-slide-up">
                <textarea
                  className="mcp-textarea-tab"
                  value={yamlConfig}
                  onChange={(e) => setYamlConfig(e.target.value)}
                  placeholder="version: '1.0'..."
                  spellCheck="false"
                />
              </div>
            )}
          </div>

          {/* Panel Footer */}
          <div className="mcp-panel-footer">
            {status.type && (
              <div className={`mcp-status-alert ${status.type}`}>
                {status.type === 'error' && <AlertTriangle size={18} />}
                {status.type === 'success' && <CheckCircle size={18} />}
                <span>{status.message}</span>
              </div>
            )}
             <Button 
              className={`mcp-save-btn ${hasPendingChanges ? 'pending-changes' : ''}`} 
              onClick={triggerSave} 
              disabled={saving || testing}
            >
              <Save size={18} />
              {saving 
                ? 'Verifying Syntax...' 
                : testing 
                  ? 'Testing Connection...' 
                  : hasPendingChanges 
                    ? 'Verify & Save (Pending Changes)' 
                    : 'Verify & Save Configuration'}
            </Button>
          </div>
        </div>
      </div>

      {/* Configuration Import Modal */}
      {showImportModal && (
        <div className="mcp-import-modal-overlay">
          <div className="mcp-import-modal glass">
            <div className="modal-header">
              <Cpu size={22} className="text-accent" />
              <h4>Import MCP Configuration</h4>
            </div>
            <p className="modal-intro">
              Paste your existing MCP configuration (Claude Desktop <code>claude_desktop_config.json</code> JSON format or Elemm Gateway YAML format) below. All new servers will be merged seamlessly!
            </p>
            <FormGroup label="Configuration Code (JSON or YAML)" className="form-group-modal">
              <Textarea
                className="import-textarea"
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                placeholder='{ "mcpServers": { "github": { "command": "npx", ... } } }'
                spellCheck="false"
              />
            </FormGroup>
            <div className="modal-toggle-row">
              <label className="toggle-label">
                <Input 
                  type="checkbox" 
                  checked={autoMigrateVault} 
                  onChange={(e) => setAutoMigrateVault(e.target.checked)}
                />
                <span>Extract sensitive variables to Secure Vault (Highly Recommended)</span>
              </label>
            </div>
            <div className="modal-actions-row">
              <Button 
                type="button" 
                className="btn-secondary-modal" 
                onClick={() => setShowImportModal(false)}
                disabled={saving}
              >
                Cancel
              </Button>
              <Button 
                type="button" 
                className="btn-primary-modal" 
                onClick={handleImportConfig}
                disabled={saving || !importText.trim()}
              >
                {saving ? 'Importing...' : 'Import & Migrate'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MCPSettings;

