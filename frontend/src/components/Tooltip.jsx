import React from 'react';
import { Info } from 'lucide-react';

const Tooltip = ({ text }) => {
  if (!text) return null;
  
  return (
    <div className="tooltip-wrapper">
      <Info size={14} className="info-icon" />
      <div className="tooltip-text">
        {text}
      </div>
    </div>
  );
};

export default Tooltip;
