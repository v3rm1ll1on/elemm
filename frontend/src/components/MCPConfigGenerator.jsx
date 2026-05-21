import React, { useState, useEffect } from 'react';
import { Copy, Terminal, CheckCircle, Server } from 'lucide-react';
import { Button, Input, Select, FormGroup } from './ui';
import { API_BASE } from '../config';
import './MCPConfigGenerator.css';

const MCPConfigGenerator = () => {
  const [transport, setTransport] = useState('stdio');
  const [deploymentType, setDeploymentType] = useState('auto');
  const [url, setUrl] = useState('');
  const [clientSessionId, setClientSessionId] = useState('');
  const [copied, setCopied] = useState(false);
  const [sysEnv, setSysEnv] = useState(null);
  const [loadingEnv, setLoadingEnv] = useState(true);

  const fetchEnv = async () => {
    setLoadingEnv(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/system/env`);
      if (res.ok) {
        const data = await res.json();
        setSysEnv(data);
      }
    } catch (e) {
      console.error("Failed to load system environment for config generator", e);
    }
    setLoadingEnv(false);
  };

  useEffect(() => {
    fetchEnv();
  }, []);

  const generateConfig = () => {
    if (!sysEnv) return "";
    const { os, wsl_distro, user, executable_path, host_ip, port } = sysEnv;
    
    let command = '';
    let args = [];
    
    let baseArgs = [];
    if (clientSessionId.trim()) {
      baseArgs.push('--name', clientSessionId.trim());
    }
    
    if (transport === 'stdio') {
      baseArgs.push('--transport', 'stdio');
    } else {
      let finalUrl = url.trim() || `http://${host_ip}:${port}/sse`;
      baseArgs.push('--bridge', finalUrl);
    }

    if (deploymentType === 'docker') {
      command = 'docker';
      args = [
        "run",
        "-i",
        "--rm",
        "--network",
        "host",
        "ghcr.io/v3rm1ll1on/elemm:latest",
        "elemm-gateway",
        ...baseArgs
      ];
    } else {
      if (os === 'wsl') {
        command = 'wsl.exe';
        const cmdString = `${executable_path} ${baseArgs.join(' ')}`;
        args = [
          "-d",
          wsl_distro || "Ubuntu",
          "-u",
          user,
          "bash",
          "-c",
          cmdString
        ];
      } else {
        if (executable_path.includes(" -m ")) {
          const parts = executable_path.split(" -m ");
          command = parts[0];
          args = ["-m", parts[1], ...baseArgs];
        } else {
          command = executable_path;
          args = baseArgs;
        }
      }
    }

    const config = {
      mcpServers: {
        "elemm-gateway": {
          command,
          args
        }
      }
    };

    return JSON.stringify(config, null, 2);
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(generateConfig());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="settings-card glass config-generator-card">
      <div className="card-header">
        <Server size={20} className="text-accent" />
        <h3>Self-Hosted Client Config</h3>
      </div>
      <div className="card-body">
        <p className="desc-text">This config is auto-generated for your current deployment environment (<strong>{sysEnv?.os === 'wsl' ? `WSL: ${sysEnv?.wsl_distro}` : (sysEnv?.os || 'Detecting...')}</strong>).</p>
        
        <div className="config-generator-split">
          <div className="config-form-grid">
            <FormGroup label="Client-Session-ID (Optional)">
              <Input 
                type="text" 
                placeholder="e.g. claude-desktop-1" 
                value={clientSessionId}
                onChange={(e) => setClientSessionId(e.target.value)}
              />
            </FormGroup>

            <FormGroup label="Deployment Type">
              <Select value={deploymentType} onChange={(e) => setDeploymentType(e.target.value)}>
                <option value="auto">Native ({sysEnv?.os === 'wsl' ? `WSL: ${sysEnv?.wsl_distro}` : (sysEnv?.os || 'Auto')})</option>
                <option value="docker">Docker Container</option>
              </Select>
            </FormGroup>

            <FormGroup label="Transport Method">
              <Select value={transport} onChange={(e) => setTransport(e.target.value)}>
                <option value="stdio">STDIO (Local App)</option>
                <option value="sse">SSE (Remote over HTTP)</option>
              </Select>
            </FormGroup>

            {transport === 'sse' && (
              <FormGroup label="SSE Server URL">
                <Input 
                  type="text" 
                  placeholder={`http://localhost:${sysEnv?.port || 8000}/sse`} 
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
              </FormGroup>
            )}
          </div>

          <div className="config-output-area">
            <div className="config-header-bar">
              <span className="file-name"><Terminal size={14} /> mcp_client_config.json</span>
              <Button variant="secondary" className="action-btn" onClick={copyToClipboard}>
                {copied ? <><CheckCircle size={14} className="text-success" /> Copied</> : <><Copy size={14} /> Copy</>}
              </Button>
            </div>
            <pre className="code-block custom-scrollbar">
              <code>{generateConfig()}</code>
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MCPConfigGenerator;
