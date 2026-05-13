import React from 'react';
import './GlassCard.css';

const GlassCard = ({ children, title, subtitle, className = '' }) => {
  return (
    <div className={`glass glass-card ${className}`}>
      {(title || subtitle) && (
        <div className="card-header">
          {title && <h2 className="card-title">{title}</h2>}
          {subtitle && <p className="card-subtitle">{subtitle}</p>}
        </div>
      )}
      <div className="card-content">
        {children}
      </div>
    </div>
  );
};

export default GlassCard;
