/*
 * Copyright (C) 2026 Marc Stöcker
 * Website: https://elemm.dev
 *
 * This program is licensed under the Business Source License 1.1 (BSL 1.1).
 * See the LICENSE file in the root directory for details.
 */

import React, { useState, useEffect, useRef } from 'react';
import { Key, Plus, Trash2, Eye, EyeOff, Globe, Clock, Shield, Info } from 'lucide-react';
import './Vault.css';
import Slide2Delete from './Slide2Delete';
import Tooltip from './Tooltip';
import { API_BASE } from '../config';
import { Input, Select, FormGroup, Button } from './ui';

const decodeBasicAuth = (value) => {
  if (!value) return { username: '', password: '' };
  try {
    const decoded = atob(value);
    const colonIdx = decoded.indexOf(':');
    if (colonIdx !== -1) {
      return {
        username: decoded.substring(0, colonIdx),
        password: decoded.substring(colonIdx + 1)
      };
    }
  } catch (e) {
    // Fallback
  }
  return { username: '', password: value };
};

const encodeBasicAuth = (username, password) => {
  try {
    return btoa(`${username}:${password}`);
  } catch (e) {
    return '';
  }
};

const Vault = () => {
  const [vaultItems, setVaultItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);
  const [showKeys, setShowKeys] = useState({});
  const [deletingId, setDeletingId] = useState(null);
  const [error, setError] = useState(null);
  const isRestoring = useRef(false);

  useEffect(() => {
    fetchVault();
  }, []);

  // Auto-Save effect
  useEffect(() => {
    if (loading) return;
    if (isRestoring.current) {
      // Skip auto-saving this update since it's a restore from the backend!
      isRestoring.current = false;
      return;
    }
    const timer = setTimeout(() => saveVault(vaultItems), 500);
    return () => clearTimeout(timer);
  }, [vaultItems]);

  const fetchVault = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/vault`);
      const data = await res.json();
      // Transform map to array with stable IDs
      const items = Object.entries(data).map(([host, entry]) => ({
        id: Math.random().toString(36).substr(2, 9),
        host,
        ...entry
      }));
      setVaultItems(items);
      setLoading(false);
    } catch (e) {
      console.error("Failed to fetch vault", e);
      setLoading(false);
      isRestoring.current = false;
    }
  };

  const saveVault = async (items) => {
    setSaving(true);
    setError(null);
    try {
      // Transform back to map for backend
      const vaultMap = {};
      items.forEach(item => {
        const { id, host, ...config } = item;
        vaultMap[host] = config;
      });

      const res = await fetch(`${API_BASE}/api/v1/vault`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(vaultMap)
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to save vault.");
      }
      setLastSaved(new Date().toLocaleTimeString());
    } catch (e) {
      console.error(e);
      setError(e.message || "Failed to save vault.");
      // Mark that we are actively restoring
      isRestoring.current = true;
      // Automatic restore by refetching
      fetchVault();
    }
    setSaving(false);
  };

  const addVaultEntry = () => {
    setVaultItems([
      ...vaultItems,
      { 
        id: Math.random().toString(36).substr(2, 9), 
        host: `new-api-${Date.now()}.com`, 
        type: 'apiKey', 
        name: 'key', 
        value: '', 
        in: 'query' 
      }
    ]);
  };

  const updateVaultEntry = (id, field, value) => {
    setVaultItems(prev => prev.map(item => 
      item.id === id ? { ...item, [field]: value } : item
    ));
  };

  const updateBasicAuth = (id, field, val, currentItem) => {
    const { username, password } = decodeBasicAuth(currentItem.value || '');
    const newUsername = field === 'username' ? val : username;
    const newPassword = field === 'password' ? val : password;
    const encoded = encodeBasicAuth(newUsername, newPassword);
    updateVaultEntry(id, 'value', encoded);
  };

  const deleteVaultEntry = (id) => {
    setVaultItems(prev => prev.filter(item => item.id !== id));
  };

  const confirmDelete = async (host, id) => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/vault/check-delete/${encodeURIComponent(host)}`);
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "This credential cannot be deleted.");
      }
      deleteVaultEntry(id);
    } catch (e) {
      console.error(e);
      setError(e.message || "Failed to delete credential.");
    } finally {
      setDeletingId(null);
    }
  };

  if (loading) return <div className="loading-state">Accessing Secure Vault...</div>;

  return (
    <div className="vault-container animate-fade-in">
      <div className="settings-header">
        <div className="page-title">
          <Key size={24} className="text-accent" />
          <h2>Elemm Vault</h2>
        </div>
        <div className="sync-status">
          {saving ? (
            <span className="syncing"><Clock size={14} className="spin" /> Syncing...</span>
          ) : lastSaved ? (
            <span className="synced">Last synced {lastSaved}</span>
          ) : (
            <span className="ready">Secure</span>
          )}
        </div>
      </div>

      <div className="vault-intro glass">
        <Shield size={20} className="text-accent" />
        <p>Manage API keys and authentication tokens. They are injected automatically based on target hostname, <strong>or can be securely referenced in MCP Server configs using the <code>vault:KEY_NAME</code> syntax</strong>.</p>
      </div>

      {error && (
        <div className="vault-error-banner glass animate-fade-in">
          <Info size={20} className="text-error" />
          <p>{error}</p>
          <button className="close-btn" onClick={() => setError(null)}>×</button>
        </div>
      )}

      <div className="vault-actions">
        <Button variant="secondary" onClick={addVaultEntry}>
          <Plus size={16} /> Add New Credential
        </Button>
      </div>

      <div className="vault-grid">
        {vaultItems.map((item) => (
          <div key={item.id} className={`vault-card type-${(item.type || 'apiKey').toLowerCase()} glass ${deletingId === item.id ? 'deleting-mode' : ''}`}>
            {deletingId === item.id && (
              <Slide2Delete 
                onConfirm={() => confirmDelete(item.host, item.id)}
                onCancel={() => setDeletingId(null)}
              />
            )}
            <div className="vault-card-header">
              {item.type === 'envVar' ? (
                <Key size={18} className="text-accent" />
              ) : (
                <Globe size={18} className="text-accent" />
              )}
              <Input 
                className="host-input"
                value={item.host} 
                onChange={(e) => updateVaultEntry(item.id, 'host', e.target.value)}
                placeholder={item.type === 'envVar' ? "VARIABLE_NAME (e.g. GITHUB_TOKEN)" : "api.hostname.com or GITHUB_TOKEN"}
              />
              <Button variant="icon" className="text-error" onClick={() => setDeletingId(item.id)}>
                <Trash2 size={16} />
              </Button>
            </div>
            <div className="vault-card-body">
              <div className={item.type === 'apiKey' ? "form-row" : ""}>
                <FormGroup label={<>Auth Type <Tooltip text="The authentication method used by the target host." /></>}>
                  <Select 
                    value={item.type || 'apiKey'} 
                    onChange={(e) => updateVaultEntry(item.id, 'type', e.target.value)}
                  >
                    <option value="apiKey">API Key</option>
                    <option value="bearer">Bearer Token</option>
                    <option value="basic">Basic Auth</option>
                    <option value="envVar">Environment Variable (MCP)</option>
                  </Select>
                </FormGroup>
                {item.type === 'apiKey' && (
                  <FormGroup label={<>Location <Tooltip text="Where to inject the key in the request." /></>}>
                    <Select 
                      value={item.in || 'query'} 
                      onChange={(e) => updateVaultEntry(item.id, 'in', e.target.value)}
                    >
                      <option value="query">URL Query</option>
                      <option value="header">HTTP Header</option>
                    </Select>
                  </FormGroup>
                )}
              </div>
              
              {item.type !== 'envVar' && (
                <FormGroup className={item.type !== 'apiKey' ? 'readonly-group' : ''} label={
                  <>
                    <span>{item.type === 'apiKey' ? 'Parameter Name' : 'Identifier'}</span>
                    <Tooltip text={item.type === 'apiKey' 
                      ? "The key name (e.g. 'api_key' or 'X-API-Key')." 
                      : "For Bearer/Basic, this is fixed to 'Authorization'."} 
                    />
                  </>
                }>
                  <Input 
                    value={item.type === 'apiKey' ? (item.name || 'key') : 'Authorization'} 
                    onChange={(e) => item.type === 'apiKey' && updateVaultEntry(item.id, 'name', e.target.value)}
                    placeholder="e.g. X-API-Key"
                    readOnly={item.type !== 'apiKey'}
                  />
                </FormGroup>
              )}

              {item.type === 'basic' ? (
                <div className="form-row">
                  <FormGroup label={<>Username <Tooltip text="The HTTP Basic Auth username." /></>}>
                    <Input 
                      value={decodeBasicAuth(item.value).username} 
                      onChange={(e) => updateBasicAuth(item.id, 'username', e.target.value, item)}
                      placeholder="username"
                    />
                  </FormGroup>
                  <FormGroup label={<>Password <Tooltip text="The HTTP Basic Auth password." /></>}>
                    <div className="password-input-wrapper">
                      <Input 
                        type={showKeys[item.id] ? 'text' : 'password'}
                        value={decodeBasicAuth(item.value).password} 
                        onChange={(e) => updateBasicAuth(item.id, 'password', e.target.value, item)}
                        placeholder="••••••••"
                      />
                      <Button 
                        variant="icon"
                        className="visibility-toggle"
                        onClick={() => setShowKeys({...showKeys, [item.id]: !showKeys[item.id]})}
                      >
                        {showKeys[item.id] ? <EyeOff size={16} /> : <Eye size={16} />}
                      </Button>
                    </div>
                  </FormGroup>
                </div>
              ) : (
                <FormGroup label={<>Credential Value <Tooltip text="Your secret token or password." /></>}>
                  <div className="password-input-wrapper">
                    <Input 
                      type={showKeys[item.id] ? 'text' : 'password'}
                      value={item.value || ''} 
                      onChange={(e) => updateVaultEntry(item.id, 'value', e.target.value)}
                      placeholder="••••••••••••••••"
                    />
                    <Button 
                      variant="icon"
                      className="visibility-toggle"
                      onClick={() => setShowKeys({...showKeys, [item.id]: !showKeys[item.id]})}
                    >
                      {showKeys[item.id] ? <EyeOff size={16} /> : <Eye size={16} />}
                    </Button>
                  </div>
                </FormGroup>
              )}
            </div>
          </div>
        ))}
        {vaultItems.length === 0 && (
          <div className="empty-vault glass">
            <Shield size={64} className="empty-vault-icon" />
            <p>Secure Vault is empty. Add your first external API credential to enable automatic injection.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Vault;
