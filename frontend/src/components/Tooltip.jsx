/*
 * Copyright (C) 2026 Marc Stöcker
 * Website: https://elemm.dev
 *
 * This program is licensed under the Business Source License 1.1 (BSL 1.1).
 * See the LICENSE file in the root directory for details.
 */

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
