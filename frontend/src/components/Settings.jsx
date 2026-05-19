import React, { useState, useEffect } from 'react';
import { Shield, Clock, Zap } from 'lucide-react';
import Tooltip from './Tooltip';
import './Settings.css';
import { API_BASE } from '../config';

const Settings = () => {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);

  useEffect(() => {
    fetchConfig();
  }, []);

  // Auto-Save effect
  useEffect(() => {
    if (!config || loading) return;
    const timer = setTimeout(() => saveConfig(config), 500);
    return () => clearTimeout(timer);
  }, [config]);

  const fetchConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/config`);
      const data = await res.json();
      if (!data.security) data.security = {};
      if (!data.security.disallowed_actions) data.security.disallowed_actions = [];
      if (!data.security.allowed_methods || data.security.allowed_methods.length === 0) {
        data.security.allowed_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];
      }
      setConfig(data);
      setLoading(false);
    } catch (e) {
      console.error("Failed to fetch config", e);
      setLoading(false);
    }
  };

  const saveConfig = async (currentConfig) => {
    setSaving(true);
    try {
      await fetch(`${API_BASE}/api/v1/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentConfig)
      });
      setLastSaved(new Date().toLocaleTimeString());
    } catch (e) { console.error(e); }
    setSaving(false);
  };

  const updateNested = (path, value) => {
    setConfig(prev => {
      const newConfig = JSON.parse(JSON.stringify(prev));
      const parts = path.split('.');
      let current = newConfig;
      for (let i = 0; i < parts.length - 1; i++) {
        if (!current[parts[i]]) current[parts[i]] = {};
        current = current[parts[i]];
      }
      current[parts[parts.length - 1]] = value;
      return newConfig;
    });
  };

  const handleArrayChange = (path, text) => {
    const arr = text.split(',').map(s => s.trim()).filter(s => s !== '');
    updateNested(path, arr);
  };

  if (loading) return <div className="loading-state">Loading Global Config...</div>;

  return (
    <div className="settings-container animate-fade-in">
      <div className="settings-header">
        <div className="page-title">
          <Shield size={24} className="text-accent" />
          <h2>Global Configuration</h2>
        </div>
        <div className="sync-status">
          {saving ? (
            <span className="syncing"><Clock size={14} className="spin" /> Syncing...</span>
          ) : lastSaved ? (
            <span className="synced">Last synced {lastSaved}</span>
          ) : (
            <span className="ready">Active</span>
          )}
        </div>
      </div>
      
      <div className="settings-grid">
        {/* Resource Limits */}
        <div className="settings-card glass">
          <div className="card-header">
            <Zap size={20} className="text-accent" />
            <h3>Resource Limits</h3>
          </div>
          <div className="card-body">
            <div className="form-group">
              <label>Standard Limit (Chars)</label>
              <input type="number" value={config.limit_standard} onChange={(e) => updateNested('limit_standard', parseInt(e.target.value))} />
            </div>
            <div className="form-group">
              <label>Inspect Limit (Chars)</label>
              <input type="number" value={config.limit_inspect} onChange={(e) => updateNested('limit_inspect', parseInt(e.target.value))} />
            </div>
          </div>
        </div>

        {/* Execution Section */}
        <div className="settings-card glass">
          <div className="card-header">
            <Clock size={20} className="text-accent" />
            <h3>Execution Policy</h3>
          </div>
          <div className="card-body">
            <div className="form-group">
              <label>Timeout (Seconds)</label>
              <input type="number" value={config.timeout_seconds} onChange={(e) => updateNested('timeout_seconds', parseInt(e.target.value))} />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Retries</label>
                <input type="number" value={config.retry_attempts} onChange={(e) => updateNested('retry_attempts', parseInt(e.target.value))} />
              </div>
              <div className="form-group">
                <label>Delay (ms)</label>
                <input type="number" value={config.retry_delay_ms} onChange={(e) => updateNested('retry_delay_ms', parseInt(e.target.value))} />
              </div>
            </div>
          </div>
        </div>

        {/* UI & Metrics Section */}
        <div className="settings-card glass">
          <div className="card-header">
            <Zap size={20} className="text-accent" />
            <h3>UI & Metrics</h3>
          </div>
          <div className="card-body">
            <div className="form-group">
              <label>Traffic Display Mode <Tooltip text="Select how data consumption is displayed in the dashboard." /></label>
              <select 
                value={config.ui?.display_mode || 'tokens'} 
                onChange={(e) => updateNested('ui.display_mode', e.target.value)}
              >
                <option value="tokens">Tokens (Estimated)</option>
                <option value="chars">Characters (Precise)</option>
                <option value="both">Both (Combined)</option>
              </select>
            </div>
            <div className="form-group">
              <label>Char-to-Token Ratio: <strong>{config.ui?.char_to_token_ratio || 4.0}</strong> <Tooltip text="Adjust the average character-per-token count for better estimation. Standard LLMs use ~4.0." /></label>
              <input 
                type="range" 
                min="2.0" 
                max="6.0" 
                step="0.1" 
                value={config.ui?.char_to_token_ratio || 4.0} 
                onChange={(e) => updateNested('ui.char_to_token_ratio', parseFloat(e.target.value))} 
              />
              <div className="range-labels">
                <span>Tight (2.0)</span>
                <span>Standard (4.0)</span>
                <span>Loose (6.0)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;
