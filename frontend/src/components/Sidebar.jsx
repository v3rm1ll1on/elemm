/*
 * Copyright (C) 2026 Marc Stöcker
 * Website: https://elemm.dev
 *
 * This program is licensed under the Business Source License 1.1 (BSL 1.1).
 * See the LICENSE file in the root directory for details.
 */

import React, { useState } from 'react';
import { 
  LayoutDashboard, 
  Key, 
  Search, 
  Settings, 
  Activity,
  Shield,
  ChevronRight,
  Cpu
} from 'lucide-react';
import './Sidebar.css';

const Sidebar = ({ activeTab, setActiveTab, isOnline }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const hoverTimeout = React.useRef(null);

  const handleMouseEnter = () => {
    hoverTimeout.current = setTimeout(() => {
      setIsExpanded(true);
    }, 250); // 250ms Delay gegen versehentliches 'Zucken'
  };

  const handleMouseLeave = () => {
    if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    setIsExpanded(false);
  };

  const menuItems = [
    { id: 'dashboard', icon: <LayoutDashboard size={20} />, label: 'Dashboard' },
    { id: 'manifest', icon: <Search size={20} />, label: 'Manifest Debugger' },
    { id: 'security', icon: <Shield size={20} />, label: 'Security' },
    { id: 'vault', icon: <Key size={20} />, label: 'Vault / Auth' },
    { id: 'mcp', icon: <Cpu size={20} />, label: 'MCP Servers' },
    { id: 'tokens', icon: <Activity size={20} />, label: 'Token Analysis' },
    { id: 'settings', icon: <Settings size={20} />, label: 'Settings' },
  ];

  return (
    <div 
      className={`sidebar glass ${isExpanded ? 'expanded' : ''}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div className="sidebar-header">
        <div className="logo-wrapper">
          <div className="logo-glow"></div>
          <img 
            src="/elemm-logo.webp" 
            alt="Elemm Logo" 
            className={`logo-img expanded ${isExpanded ? 'visible' : 'hidden'}`}
          />
          <img 
            src="/elemm-el.webp" 
            alt="Elemm" 
            className={`logo-img collapsed ${!isExpanded ? 'visible' : 'hidden'}`}
          />
        </div>
      </div>

      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
            onClick={() => setActiveTab(item.id)}
          >
            <div className="icon-container">{item.icon}</div>
            {isExpanded && <span className="nav-label">{item.label}</span>}
            {activeTab === item.id && <div className="active-indicator" />}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div className={`status-dot ${isOnline ? 'online' : 'offline'}`}></div>
          {isExpanded && <span className="status-text">{isOnline ? 'Gateway Online' : 'Gateway Offline'}</span>}
        </div>
        {isExpanded && (
          <div className="license-info" style={{ fontSize: '10px', opacity: 0.5, marginTop: '4px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '4px', width: '100%' }}>
            © 2026 Marc Stöcker<br />
            Licensed under BSL 1.1
          </div>
        )}
      </div>
    </div>
  );
};

export default Sidebar;
