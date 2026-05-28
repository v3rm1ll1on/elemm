/*
 * Copyright (C) 2026 Marc Stöcker
 * Website: https://elemm.dev
 *
 * This program is licensed under the Business Source License 1.1 (BSL 1.1).
 * See the LICENSE file in the root directory for details.
 */

import React, { useState, useEffect } from 'react';
import { Shield, ShieldAlert, ShieldCheck, Zap, AlertTriangle, MessageSquare, Plus, Trash2, X, Globe } from 'lucide-react';
import Tooltip from './Tooltip';
import './Security.css';
import { API_BASE } from '../config';
import { Input, Switch, Button, FormGroup } from './ui';

// Reusable interactive Tag Input Component
const TagInput = ({ tags, onChange, placeholder, variant = 'simple' }) => {
  const [input, setInput] = useState('');

  const addTag = () => {
    const val = input.trim();
    if (val && !tags.includes(val)) {
      onChange([...tags, val]);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag();
    }
  };

  const removeTag = (indexToRemove) => {
    onChange(tags.filter((_, i) => i !== indexToRemove));
  };

  const isRegex = (tag) => tag.startsWith('re:');

  return (
    <div className="tag-input-container">
      <div className="tags-wrapper">
        {tags.map((tag, i) => (
          <span key={i} className={`tag-badge ${variant} ${isRegex(tag) ? 'regex' : ''}`}>
            {isRegex(tag) && <span className="regex-indicator">re</span>}
            {tag}
            <button className="tag-remove" onClick={() => removeTag(i)}><X size={10} /></button>
          </span>
        ))}
      </div>
      <Input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={addTag}
        placeholder={tags.length === 0 ? placeholder : "Type and press Enter..."}
        className="tag-input-field"
      />
    </div>
  );
};

const Security = () => {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);

  // Remedy creation local state
  const [newRemedyKey, setNewRemedyKey] = useState('');
  const [newRemedyVal, setNewRemedyVal] = useState('');

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
      
      // Ensure strict structure
      if (!data.security) data.security = {};
      const fields = [
        'disallowed_patterns', 'disallowed_landmarks', 'disallowed_actions',
        'allowed_landmarks', 'allowed_actions', 'allowed_methods', 'custom_remedies'
      ];
      fields.forEach(f => {
        if (!data.security[f]) data.security[f] = (f === 'custom_remedies' ? {} : []);
      });
      if (data.security.enforce_whitelist === undefined) data.security.enforce_whitelist = false;
      if (data.security.prevent_key_leakage === undefined) data.security.prevent_key_leakage = true;

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

  const updateSecurity = (field, value) => {
    setConfig(prev => ({
      ...prev,
      security: {
        ...prev.security,
        [field]: value
      }
    }));
  };

  const updateRemedy = (key, val) => {
    const newRemedies = { ...config.security.custom_remedies, [key]: val };
    if (val === '') delete newRemedies[key];
    updateSecurity('custom_remedies', newRemedies);
  };

  const addCustomRemedy = () => {
    if (!newRemedyKey.trim() || !newRemedyVal.trim()) return;
    updateRemedy(newRemedyKey.trim(), newRemedyVal.trim());
    setNewRemedyKey('');
    setNewRemedyVal('');
  };

  if (loading) return <div className="loading-state">Loading Security Policy...</div>;

  return (
    <div className="security-container animate-fade-in">
      <div className="security-header">
        <div className="page-title">
          <Shield size={24} className="text-accent" />
          <h2>Security Governance</h2>
        </div>
        <div className="policy-indicator">
          <div className={`status-dot ${config.security.enforce_whitelist ? 'shield-active' : 'shield-standard'}`}></div>
          <span>{config.security.enforce_whitelist ? 'Zero-Trust Policy' : 'Standard Policy'}</span>
        </div>
      </div>

      {/* Mode Banner */}
      <div className={`security-mode-banner glass ${config.security.enforce_whitelist ? 'active-whitelist' : ''}`}>
        <div className="mode-info">
          <div className="icon-wrapper">
            {config.security.enforce_whitelist ? <ShieldCheck size={28} className="text-success animate-pulse" /> : <ShieldAlert size={28} className="text-warning" />}
          </div>
          <div>
            <h3>{config.security.enforce_whitelist ? 'Zero-Trust (Default Deny)' : 'Standard Rules (Default Allow)'}</h3>
            <p>{config.security.enforce_whitelist 
              ? 'All tools are strictly blocked unless they are explicitly registered in the authorized list below.' 
              : 'All tools are allowed by default, except for items matching your blacklists or regex patterns.'}
            </p>
          </div>
        </div>
        <div className="mode-toggle-zone">
          <span className="mode-label">Zero-Trust Mode</span>
          <Switch 
            checked={config.security.enforce_whitelist} 
            onChange={(e) => updateSecurity('enforce_whitelist', e.target.checked)} 
          />
        </div>
      </div>

      {/* 3-Column Grid */}
      <div className="security-dashboard-grid">
        
        {/* Column 1: Whitelist Guard */}
        <div className={`security-column-card glass ${!config.security.enforce_whitelist ? 'dimmed' : ''}`}>
          <div className="card-header">
            <ShieldCheck size={18} className="text-success" />
            <h3>Authorized Scope (Whitelist)</h3>
            {!config.security.enforce_whitelist && <span className="inactive-badge">Inactive</span>}
          </div>
          <div className="card-body">
            <FormGroup label={<>Allowed Landmarks <Tooltip text="Broad functional areas allowed in Zero-Trust mode." /></>} className="form-group-custom">
              <TagInput 
                tags={config.security.allowed_landmarks} 
                onChange={(tags) => updateSecurity('allowed_landmarks', tags)}
                placeholder="e.g. weather, public"
                variant="success"
              />
            </FormGroup>
            <FormGroup label={<>Allowed Actions <Tooltip text="Specific tool/endpoint IDs permitted in Zero-Trust mode." /></>} className="form-group-custom">
              <TagInput 
                tags={config.security.allowed_actions} 
                onChange={(tags) => updateSecurity('allowed_actions', tags)}
                placeholder="e.g. users:get_profile"
                variant="success"
              />
            </FormGroup>
          </div>
        </div>

        {/* Column 2: Blacklist Guard */}
        <div className="security-column-card glass">
          <div className="card-header">
            <AlertTriangle size={18} className="text-warning" />
            <h3>Explicit Blacklists</h3>
          </div>
          <div className="card-body">
            <FormGroup label={<>Disallowed Landmarks <Tooltip text="Block entire namespaces or categories (e.g. banking)." /></>} className="form-group-custom">
              <TagInput 
                tags={config.security.disallowed_landmarks} 
                onChange={(tags) => updateSecurity('disallowed_landmarks', tags)}
                placeholder="e.g. admin, finance"
                variant="warning"
              />
            </FormGroup>
            <FormGroup label={<>Disallowed Actions <Tooltip text="Specific tool names or full IDs to blacklist." /></>} className="form-group-custom">
              <TagInput 
                tags={config.security.disallowed_actions} 
                onChange={(tags) => updateSecurity('disallowed_actions', tags)}
                placeholder="e.g. iplookup, reset_key"
                variant="warning"
              />
            </FormGroup>
          </div>
        </div>

        {/* Column 3: Rules & Protocols */}
        <div className="security-column-card glass">
          <div className="card-header">
            <Globe size={18} className="text-accent" />
            <h3>Guard Rails & HTTP</h3>
          </div>
          <div className="card-body">
            <FormGroup label={<>Restricted Patterns <Tooltip text="Checks tool names AND argument values. Use 're:pattern' for Regex." /></>} className="form-group-custom">
              <TagInput 
                tags={config.security.disallowed_patterns} 
                onChange={(tags) => updateSecurity('disallowed_patterns', tags)}
                placeholder="e.g. re:.*secret.*, rm -rf"
                variant="danger"
              />
            </FormGroup>
            
            <div className="form-group-custom" style={{ marginTop: '20px', marginBottom: '15px', paddingBottom: '12px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <label>Data Loss Prevention (DLP) <Tooltip text="Automatically scrubs all vault secrets from LLM responses to prevent leakage. Turn off only for debugging." /></label>
              <div style={{ display: 'flex', alignItems: 'center', marginTop: '10px' }}>
                <Switch 
                  checked={config.security.prevent_key_leakage} 
                  onChange={(e) => updateSecurity('prevent_key_leakage', e.target.checked)} 
                />
                <span style={{ marginLeft: '12px', fontSize: '13px', color: config.security.prevent_key_leakage ? '#22c55e' : '#94a3b8', fontWeight: config.security.prevent_key_leakage ? '500' : 'normal' }}>
                  {config.security.prevent_key_leakage ? 'Active (Secrets Scrubbed)' : 'Disabled (Keys Visible)'}
                </span>
              </div>
            </div>

            <div className="form-group-custom" style={{ marginBottom: '20px', paddingBottom: '15px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <label>Global UI Policy Masking <Tooltip text="When active, the Visualizer Landmark TreeView and Token Analyzer will persistently filter out all blocked/disallowed endpoints based on this security policy." /></label>
              <div style={{ display: 'flex', alignItems: 'center', marginTop: '10px' }}>
                <Switch 
                  checked={config.ui?.simulate_security_policy || false} 
                  onChange={(e) => {
                    const nextUi = { ...(config.ui || {}), simulate_security_policy: e.target.checked };
                    setConfig(prev => ({
                      ...prev,
                      ui: nextUi
                    }));
                  }} 
                />
                <span style={{ marginLeft: '12px', fontSize: '13px', color: config.ui?.simulate_security_policy ? 'var(--accent-primary)' : '#94a3b8', fontWeight: config.ui?.simulate_security_policy ? '600' : 'normal' }}>
                  {config.ui?.simulate_security_policy ? 'Active (Strict UI Masking)' : 'Disabled (All Tools Visible)'}
                </span>
              </div>
            </div>
            
            <div className="form-group-custom">
              <label>Allowed HTTP Methods</label>
              <div className="horizontal-methods-group">
                {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map(method => {
                  const isAllowed = (config.security.allowed_methods || []).includes(method);
                  return (
                    <button 
                      key={method} 
                      className={`method-toggle-btn ${isAllowed ? 'allowed' : 'blocked'}`}
                      onClick={() => {
                        const current = config.security.allowed_methods || [];
                        const next = isAllowed ? current.filter(m => m !== method) : [...current, method];
                        updateSecurity('allowed_methods', next);
                      }}
                    >
                      <div className="method-status-icon">
                        {isAllowed ? <ShieldCheck size={12} /> : <X size={12} />}
                      </div>
                      {method}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* Row 3: Custom Remedies Manager */}
      <div className="remedies-card-large glass">
        <div className="card-header">
          <MessageSquare size={18} className="text-accent" />
          <h3>Custom Remediation Messages</h3>
        </div>
        <div className="card-body">
          <div className="remedies-table-container">
            {Object.keys(config.security.custom_remedies).length === 0 ? (
              <div className="empty-remedies-state">
                No custom remedies configured. Blocked tools will show a generic security error.
              </div>
            ) : (
              <table className="remedies-table">
                <thead>
                  <tr>
                    <th>Landmark / Action / Pattern</th>
                    <th>Custom Guide Message (Shown to LLM Agent)</th>
                    <th style={{ width: '80px', textAlign: 'center' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(config.security.custom_remedies).map(([key, msg]) => (
                    <tr key={key}>
                      <td className="remedy-key-cell"><code>{key}</code></td>
                      <td>
                        <Input 
                          type="text" 
                          value={msg} 
                          onChange={(e) => updateRemedy(key, e.target.value)} 
                          className="table-remedy-input"
                        />
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <Button variant="icon" className="btn-icon-delete" onClick={() => updateRemedy(key, '')}>
                          <Trash2 size={15} />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Quick Add Remedy */}
          <div className="remedy-quick-add-form">
            <h4><Plus size={16} className="text-accent" /> Configure New Guidance</h4>
            <div className="quick-add-row">
              <Input 
                type="text" 
                placeholder="ID (e.g. admin, rm -rf)" 
                value={newRemedyKey} 
                onChange={(e) => setNewRemedyKey(e.target.value)}
                className="quick-add-input-key"
              />
              <Input 
                type="text" 
                placeholder="Remedy message to return when blocked..." 
                value={newRemedyVal} 
                onChange={(e) => setNewRemedyVal(e.target.value)}
                className="quick-add-input-val"
              />
              <Button className="btn-primary-compact" onClick={addCustomRemedy}>
                <Plus size={14} /> Add Rule
              </Button>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export default Security;
