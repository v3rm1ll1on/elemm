import React, { useState, useEffect, useRef } from 'react';
import { Key, Plus, Trash2, Eye, EyeOff, Globe, Clock, Shield, Info } from 'lucide-react';
import Slide2Delete from './Slide2Delete';

const Tooltip = ({ text }) => (
  <div className="tooltip-wrapper">
    <Info size={14} className="info-icon" />
    <span className="tooltip-text">{text}</span>
  </div>
);

const Vault = () => {
  const [vaultItems, setVaultItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);
  const [showKeys, setShowKeys] = useState({});
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    fetchVault();
  }, []);

  // Auto-Save effect
  useEffect(() => {
    if (loading) return;
    const timer = setTimeout(() => saveVault(vaultItems), 500);
    return () => clearTimeout(timer);
  }, [vaultItems]);

  const fetchVault = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8090/api/v1/vault');
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
    }
  };

  const saveVault = async (items) => {
    setSaving(true);
    try {
      // Transform back to map for backend
      const vaultMap = {};
      items.forEach(item => {
        const { id, host, ...config } = item;
        vaultMap[host] = config;
      });

      await fetch('http://127.0.0.1:8090/api/v1/vault', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(vaultMap)
      });
      setLastSaved(new Date().toLocaleTimeString());
    } catch (e) { console.error(e); }
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

  const deleteVaultEntry = (id) => {
    setVaultItems(prev => prev.filter(item => item.id !== id));
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
        <p>Manage API keys and authentication tokens for external sites. The gateway will automatically inject these credentials based on the hostname.</p>
      </div>

      <div className="vault-actions">
        <button className="btn-secondary" onClick={addVaultEntry}>
          <Plus size={16} /> Add New Credential
        </button>
      </div>

      <div className="vault-grid">
        {vaultItems.map((item) => (
          <div key={item.id} className={`vault-card glass ${deletingId === item.id ? 'deleting-mode' : ''}`}>
            {deletingId === item.id && (
              <Slide2Delete 
                onConfirm={() => {
                  deleteVaultEntry(item.id);
                  setDeletingId(null);
                }}
                onCancel={() => setDeletingId(null)}
              />
            )}
            <div className="vault-card-header">
              <Globe size={18} className="text-accent" />
              <input 
                className="host-input"
                value={item.host} 
                onChange={(e) => updateVaultEntry(item.id, 'host', e.target.value)}
                placeholder="api.hostname.com"
              />
              <button className="btn-icon text-error" onClick={() => setDeletingId(item.id)}>
                <Trash2 size={16} />
              </button>
            </div>
            <div className="vault-card-body">
              <div className="form-row">
                <div className="form-group">
                  <label>Auth Type <Tooltip text="The authentication method used by the target host." /></label>
                  <select 
                    value={item.type || 'apiKey'} 
                    onChange={(e) => updateVaultEntry(item.id, 'type', e.target.value)}
                  >
                    <option value="apiKey">API Key</option>
                    <option value="bearer">Bearer Token</option>
                    <option value="basic">Basic Auth</option>
                  </select>
                </div>
                {item.type === 'apiKey' && (
                  <div className="form-group">
                    <label>Location <Tooltip text="Where to inject the key in the request." /></label>
                    <select 
                      value={item.in || 'query'} 
                      onChange={(e) => updateVaultEntry(item.id, 'in', e.target.value)}
                    >
                      <option value="query">URL Query</option>
                      <option value="header">HTTP Header</option>
                    </select>
                  </div>
                )}
              </div>
              
              <div className="form-group" style={{ opacity: item.type !== 'apiKey' ? 0.6 : 1 }}>
                <label>
                  {item.type === 'apiKey' ? 'Parameter Name' : 'Identifier'}
                  <Tooltip text={item.type === 'apiKey' 
                    ? "The key name (e.g. 'api_key' or 'X-API-Key')." 
                    : "For Bearer/Basic, this is fixed to 'Authorization'."} 
                  />
                </label>
                <input 
                  value={item.type === 'apiKey' ? (item.name || 'key') : 'Authorization'} 
                  onChange={(e) => item.type === 'apiKey' && updateVaultEntry(item.id, 'name', e.target.value)}
                  placeholder="e.g. X-API-Key"
                  readOnly={item.type !== 'apiKey'}
                />
              </div>

              <div className="form-group">
                <label>Credential Value <Tooltip text="Your secret token or password." /></label>
                <div className="password-input-wrapper">
                  <input 
                    type={showKeys[item.id] ? 'text' : 'password'}
                    value={item.value || ''} 
                    onChange={(e) => updateVaultEntry(item.id, 'value', e.target.value)}
                    placeholder="••••••••••••••••"
                  />
                  <button 
                    className="btn-icon visibility-toggle"
                    onClick={() => setShowKeys({...showKeys, [item.id]: !showKeys[item.id]})}
                  >
                    {showKeys[item.id] ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}
        {vaultItems.length === 0 && (
          <div className="empty-vault glass">
            <Key size={48} className="text-secondary opacity-20" />
            <p>No credentials stored in vault.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Vault;
