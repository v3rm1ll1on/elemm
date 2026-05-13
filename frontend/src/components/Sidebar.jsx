import React, { useState } from 'react';
import { 
  LayoutDashboard, 
  Key, 
  Search, 
  History, 
  Settings, 
  Activity,
  ChevronRight
} from 'lucide-react';
import './Sidebar.css';

const Sidebar = ({ activeTab, setActiveTab }) => {
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
    { id: 'vault', icon: <Key size={20} />, label: 'Vault / Auth' },
    { id: 'history', icon: <History size={20} />, label: 'Call History' },
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
        <div className="logo-container">
          <div className="logo-glow"></div>
          <span className="logo-text">EL</span>
        </div>
        {isExpanded && <span className="brand-name">ELEMM Gateway</span>}
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

      <div className="sidebar-footer">
        <div className="status-dot online"></div>
        {isExpanded && <span className="status-text">Gateway Online</span>}
      </div>
    </div>
  );
};

export default Sidebar;
