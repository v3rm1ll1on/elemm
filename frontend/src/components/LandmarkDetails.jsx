import React, { useState, useMemo, useEffect, useRef } from 'react';
import './LandmarkDetails.css';
import { 
  Terminal, Layers, RefreshCw, Globe, Database, BookOpen, Check, Copy, Zap, Cpu, AlertCircle, Code, Play, Info, ChevronDown, Eye, EyeOff, Folder
} from 'lucide-react';

// --- Constants ---
const HYGIENE_PARAMS = [
  { name: '_select', type: 'string', description: 'Fields to return.', location: 'protocol' },
  { name: '_filter', type: 'string', description: 'Basic filter.', location: 'protocol' },
  { name: '_limit', type: 'number', description: 'Limit results.', location: 'protocol' }
];

const castValue = (value, type) => {
  if (!value || value === "") return undefined;
  if (type === 'number' || type === 'integer') return Number(value);
  if (type === 'boolean') return value === 'true' || value === true;
  return value;
};

const isSignatureUseful = (sig) => {
  if (!sig) return false;
  const trimmed = sig.trim();
  if (trimmed.length === 0) return false;
  
  if (trimmed.includes('Structured Profile for')) return false;
  
  const lines = trimmed.split('\n').map(l => l.trim()).filter(l => l.length > 0);
  if (lines.length <= 4 && lines.every(l => 
    l.startsWith('//') || 
    l.startsWith('/*') || 
    l.startsWith('*') || 
    l.startsWith('*/') || 
    l.startsWith('###') || 
    l.startsWith('```')
  )) {
    return false;
  }
  
  return true;
};

const normalizeType = (t) => {
  if (!t) return 'any';
  const clean = t.toLowerCase().trim();
  if (clean === 'dict' || clean === 'dictionary' || clean === 'map') return 'object';
  if (clean === 'list') return 'array';
  return t;
};

const parseReturnsToSchema = (returns, existingSchema) => {
  if (existingSchema && existingSchema.properties && Object.keys(existingSchema.properties).length > 0) {
    return existingSchema;
  }
  if (existingSchema && existingSchema.items && existingSchema.items.properties) {
    return existingSchema;
  }
  
  if (!returns || typeof returns !== 'string') return existingSchema;
  
  const cleanReturns = returns.trim();
  
  // Case 1: Direct object syntax like "{status: string, district: string, category: string, tool: string, metadata: dict}"
  if (cleanReturns.startsWith('{') && cleanReturns.endsWith('}')) {
    const inner = cleanReturns.slice(1, -1).trim();
    const pairs = inner.split(',');
    const properties = {};
    
    pairs.forEach(pair => {
      const parts = pair.split(':');
      if (parts.length >= 2) {
        const name = parts[0].trim();
        const type = parts.slice(1).join(':').trim();
        properties[name] = {
          type: normalizeType(type),
          description: ''
        };
      }
    });
    
    if (Object.keys(properties).length > 0) {
      return {
        type: 'object',
        properties
      };
    }
  }

  // Case 2: Array of object syntax like "Array<{ field: type }>" or "[{ field: type }]"
  const arrayMatch = cleanReturns.match(/^(?:Array<|\[)\s*\{([^}]+)\}\s*(?:>|\])$/i);
  if (arrayMatch) {
    const inner = arrayMatch[1].trim();
    const pairs = inner.split(',');
    const properties = {};
    
    pairs.forEach(pair => {
      const parts = pair.split(':');
      if (parts.length >= 2) {
        const name = parts[0].trim();
        const type = parts.slice(1).join(':').trim();
        properties[name] = {
          type: normalizeType(type),
          description: ''
        };
      }
    });
    
    if (Object.keys(properties).length > 0) {
      return {
        type: 'array',
        items: {
          type: 'object',
          properties
        }
      };
    }
  }
  
  return existingSchema;
};

const hasStructuredSchema = (schema) => {
  if (!schema) return false;
  if (schema.properties && Object.keys(schema.properties).length > 0) return true;
  if (schema.items && (schema.items.properties && Object.keys(schema.items.properties).length > 0)) return true;
  return false;
};

const getSimplifiedTypeName = (schema, originalReturns) => {
  if (!schema) return originalReturns || 'any';
  
  if (schema.type === 'array') {
    if (originalReturns && (originalReturns.startsWith('[') || originalReturns.startsWith('Array<')) && !originalReturns.includes('{')) {
      return originalReturns;
    }
    return 'Array<Object>';
  }
  
  if (schema.type === 'object') {
    if (originalReturns && !originalReturns.includes('{') && originalReturns !== 'object') {
      return originalReturns;
    }
    return 'Object';
  }
  
  return originalReturns || schema.type || 'any';
};

// --- Sub-Components ---

const SmartCopyDropdown = ({ options, title = "Copy options" }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const containerRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleCopyOption = (e, textToCopy, index) => {
    e.stopPropagation();
    navigator.clipboard.writeText(textToCopy);
    setCopiedIndex(index);
    setTimeout(() => {
      setCopiedIndex(null);
      setIsOpen(false);
    }, 1500);
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', display: 'inline-block' }}>
      <button 
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen(!isOpen);
        }}
        style={{
          background: isOpen ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
          border: 'none',
          color: isOpen ? '#f8fafc' : '#64748b',
          cursor: 'pointer',
          padding: '5px',
          borderRadius: '6px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.15s ease',
          marginLeft: '4px'
        }}
        onMouseEnter={e => {
          if (!isOpen) {
            e.currentTarget.style.color = '#f8fafc';
            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
          }
        }}
        onMouseLeave={e => {
          if (!isOpen) {
            e.currentTarget.style.color = '#64748b';
            e.currentTarget.style.background = 'transparent';
          }
        }}
        title={title}
      >
        {copiedIndex !== null ? <Check size={12} style={{ color: '#34d399' }} /> : <Copy size={12} />}
      </button>

      {isOpen && (
        <div style={{
          position: 'absolute',
          right: '110%',
          top: '50%',
          transform: 'translateY(-50%)',
          background: '#0f172a',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '8px',
          padding: '6px',
          minWidth: '160px',
          boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5)',
          zIndex: 999999999,
          backdropFilter: 'blur(16px)',
          display: 'flex',
          flexDirection: 'column',
          gap: '2px'
        }}>
          {options.map((opt, idx) => {
            const isCopied = copiedIndex === idx;
            return (
              <button
                key={idx}
                onClick={(e) => handleCopyOption(e, opt.value, idx)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: isCopied ? '#34d399' : '#cbd5e1',
                  padding: '6px 10px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontFamily: 'sans-serif',
                  textAlign: 'left',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '8px',
                  transition: 'all 0.15s ease',
                  fontWeight: '500'
                }}
                onMouseEnter={e => {
                  if (!isCopied) {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
                    e.currentTarget.style.color = '#f8fafc';
                  }
                }}
                onMouseLeave={e => {
                  if (!isCopied) {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.color = '#cbd5e1';
                  }
                }}
              >
                <span>{opt.label}</span>
                {isCopied ? <Check size={11} style={{ color: '#34d399' }} /> : <span style={{ fontSize: '9px', color: '#64748b', fontFamily: 'monospace' }}>{opt.shortcut || ''}</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

const ParameterCopyButton = ({ param }) => {
  const type = param.type || 'string';
  const mockValue = type === 'number' ? '0' : type === 'boolean' ? 'false' : type === 'object' ? '{}' : type === 'array' ? '[]' : '""';
  
  const options = [
    { label: "Copy Name", value: param.name, shortcut: "name" },
    { label: "Copy Type", value: type, shortcut: "type" }
  ];
  
  if (param.description) {
    options.push({ label: "Copy Description", value: param.description, shortcut: "desc" });
  }
  
  options.push({ label: "Copy Mock Value", value: mockValue, shortcut: "mock" });

  return <SmartCopyDropdown options={options} title="Copy parameter details" />;
};

const SchemaCopyButton = ({ name, prop, currentPath }) => {
  const type = prop.type || 'any';
  const options = [
    { label: "Copy JSON Path", value: currentPath, shortcut: "path" },
    { label: "Copy Field Name", value: name, shortcut: "name" },
    { label: "Copy Type", value: type, shortcut: "type" },
    { label: "Copy Schema Fragment", value: JSON.stringify(prop, null, 2), shortcut: "schema" }
  ];

  return <SmartCopyDropdown options={options} title="Copy schema details" />;
};

const JsonCopyButton = ({ name, value, currentPath, valueType }) => {
  const options = [
    { label: "Copy JSON Path", value: currentPath, shortcut: "path" },
    { label: "Copy Key Name", value: String(name), shortcut: "key" },
    { label: "Copy Value", value: typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value), shortcut: "value" },
    { label: "Copy Type", value: valueType, shortcut: "type" }
  ];

  return <SmartCopyDropdown options={options} title="Copy JSON value details" />;
};

const ParameterRow = ({ param, isHygiene, isLast }) => (
  <div 
    style={{
      display: 'flex',
      alignItems: 'center',
      padding: '12px 16px',
      borderBottom: isLast ? 'none' : '1px solid rgba(255, 255, 255, 0.04)',
      gap: '16px',
      fontSize: '13px',
      transition: 'all 0.2s ease',
      position: 'relative'
    }}
    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.015)'}
    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
  >
    {/* Empty spacer to align parameter lines perfectly with SchemaRow */}
    <div style={{ width: '16px' }} />

    {/* Parameter Name */}
    <span style={{ 
      fontFamily: 'monospace', 
      fontWeight: '600', 
      color: isHygiene ? '#818cf8' : '#f43f5e' 
    }}>
      {param.name}
    </span>

    {/* Parameter Type Badge */}
    <span style={{
      fontSize: '10px',
      fontFamily: 'monospace',
      color: '#34d399',
      background: 'rgba(52, 211, 153, 0.08)',
      border: '1px solid rgba(52, 211, 153, 0.15)',
      padding: '1px 6px',
      borderRadius: '4px',
      fontWeight: '600',
      textTransform: 'uppercase',
      letterSpacing: '0.02em'
    }}>
      {param.type || 'any'}
    </span>

    {/* Location Badge (e.g. protocol / hygiene) */}
    {param.location && (
      <span style={{
        fontSize: '9px',
        fontFamily: 'monospace',
        color: '#9ca3af',
        background: 'rgba(255, 255, 255, 0.05)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        padding: '1px 6px',
        borderRadius: '4px',
        fontWeight: '600',
        textTransform: 'uppercase'
      }}>
        {param.location}
      </span>
    )}

    {/* Required Badge */}
    {param.required && (
      <span style={{ 
        fontSize: '9px',
        fontFamily: 'monospace',
        color: '#f87171',
        background: 'rgba(239, 68, 68, 0.08)', 
        border: '1px solid rgba(239, 68, 68, 0.15)',
        padding: '1px 6px', 
        borderRadius: '4px', 
        fontWeight: '700',
        textTransform: 'uppercase'
      }}>
        required
      </span>
    )}

    {/* Parameter Description */}
    <div 
      className={param.description ? "desc-tooltip-wrapper" : ""}
      style={{ 
        flex: 1, 
        minWidth: 0, 
        position: 'relative', 
        display: 'flex', 
        alignItems: 'center' 
      }}
    >
      <span style={{ 
        color: '#64748b', 
        fontSize: '12px',
        marginLeft: '8px',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        width: '100%'
      }}>
        {param.description || "No description."}
      </span>
      {param.description && (
        <div className="desc-tooltip-text">
          {param.description}
        </div>
      )}
    </div>

    {/* Copy Action */}
    <ParameterCopyButton param={param} />
  </div>
);

const Section = ({ title, icon: Icon, children, action }) => (
  <div className="details-section">
    <div className="section-header">
      <div className="section-title">
        <Icon size={14} />
        <span>{title}</span>
      </div>
      {action && <div>{action}</div>}
    </div>
    <div className="section-body">
      {children}
    </div>
  </div>
);

const augmentSchemaWithData = (schema, data) => {
  if (!schema) return null;
  if (!data) return schema;

  // Deep clone to prevent mutating original schema prop
  const newSchema = JSON.parse(JSON.stringify(schema));

  const merge = (s, d) => {
    if (!s || typeof s !== 'object') return;
    const type = normalizeType(s.type);

    if (type === 'object') {
      s.properties = s.properties || {};
      
      if (d && typeof d === 'object') {
        Object.entries(d).forEach(([key, val]) => {
          if (key.startsWith('_')) return; // Ignore protocol metadata

          if (!s.properties[key]) {
            let valType = typeof val;
            if (val === null) valType = 'any';
            else if (Array.isArray(val)) valType = 'array';
            else if (valType === 'object') valType = 'object';
            
            s.properties[key] = {
              type: normalizeType(valType),
              description: '',
              value: val
            };
          } else {
            s.properties[key].value = val;
          }

          if (s.properties[key] && typeof val === 'object' && val !== null) {
            merge(s.properties[key], val);
          }
        });
      }
    } else if (type === 'array') {
      if (Array.isArray(d) && d.length > 0) {
        s.items = s.items || { type: 'any' };
        const firstItem = d[0];
        let itemType = typeof firstItem;
        if (firstItem === null) itemType = 'any';
        else if (Array.isArray(firstItem)) itemType = 'array';
        else if (itemType === 'object') itemType = 'object';

        s.items.type = s.items.type || normalizeType(itemType);
        
        if (typeof firstItem === 'object' && firstItem !== null) {
          merge(s.items, firstItem);
        }
      }
    }
  };

  const responseData = data.data !== undefined ? data.data : data;
  merge(newSchema, responseData);
  return newSchema;
};

const SchemaRow = ({ name, prop, depth = 0, parentPath = '' }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const currentPath = parentPath ? `${parentPath}.${name}` : name;
  const type = normalizeType(prop?.type || 'any');
  
  // Check if there is a concrete live value that is empty (empty object or empty array)
  const isEmptyValue = prop?.value !== undefined && (
    (typeof prop.value === 'object' && prop.value !== null && !Array.isArray(prop.value) && Object.keys(prop.value).length === 0) ||
    (Array.isArray(prop.value) && prop.value.length === 0)
  );
  
  // Determine if this property has child properties (object or array of objects)
  let childProperties = null;
  let isArrayOfObjects = false;
  
  if (type === 'object') {
    if (prop?.properties && Object.keys(prop.properties).length > 0) {
      childProperties = prop.properties;
    } else if (!isEmptyValue) {
      // Virtual fallback for free dynamic dictionaries
      childProperties = {
        "[key]": {
          type: "any",
          description: "Dynamic key-value pair."
        }
      };
    }
  } else if (type === 'array') {
    if (prop?.items) {
      const itemType = normalizeType(prop.items.type);
      if (itemType === 'object' && prop.items.properties && Object.keys(prop.items.properties).length > 0) {
        childProperties = prop.items.properties;
        isArrayOfObjects = true;
      } else if (!isEmptyValue) {
        childProperties = {
          "[item]": {
            type: itemType || "any",
            description: prop.items.description || "Dynamic array item."
          }
        };
      }
    } else if (!isEmptyValue) {
      childProperties = {
        "[item]": {
          type: "any",
          description: "Dynamic array item."
        }
      };
    }
  }
  
  const hasChildren = childProperties && Object.keys(childProperties).length > 0;
  
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {/* Node Row */}
      <div 
        onClick={() => hasChildren && setIsExpanded(!isExpanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '12px 16px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
          gap: '16px',
          fontSize: '13px',
          cursor: hasChildren ? 'pointer' : 'default',
          transition: 'all 0.2s ease',
          paddingLeft: `${16 + depth * 24}px`,
          position: 'relative'
        }}
        onMouseEnter={e => {
          if (hasChildren) e.currentTarget.style.background = 'rgba(255,255,255,0.015)';
        }}
        onMouseLeave={e => {
          if (hasChildren) e.currentTarget.style.background = 'transparent';
        }}
      >
        {/* Indentation line */}
        {depth > 0 && (
          <div style={{
            position: 'absolute',
            left: `${8 + (depth - 1) * 24}px`,
            top: 0,
            bottom: 0,
            width: '1px',
            background: 'rgba(255, 255, 255, 0.06)'
          }} />
        )}

        {/* Expand Icon */}
        <div style={{ width: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {hasChildren && (
            <ChevronDown 
              size={14} 
              style={{ 
                transform: isExpanded ? 'rotate(0deg)' : 'rotate(-90deg)', 
                transition: 'transform 0.2s ease',
                color: isExpanded ? '#818cf8' : '#64748b' 
              }} 
            />
          )}
        </div>

        {/* Field Name */}
        <span style={{ 
          fontFamily: 'monospace', 
          fontWeight: '600', 
          color: hasChildren ? '#a5b4fc' : '#f8fafc' 
        }}>
          {name}
        </span>

        {/* Field Type Badge */}
        <span style={{
          fontSize: '10px',
          fontFamily: 'monospace',
          color: type === 'object' ? '#38bdf8' : type === 'array' ? '#c084fc' : '#34d399',
          background: type === 'object' ? 'rgba(56, 189, 248, 0.08)' : type === 'array' ? 'rgba(192, 132, 252, 0.08)' : 'rgba(52, 211, 153, 0.08)',
          border: type === 'object' ? '1px solid rgba(56, 189, 248, 0.15)' : type === 'array' ? '1px solid rgba(192, 132, 252, 0.15)' : '1px solid rgba(52, 211, 153, 0.15)',
          padding: '1px 6px',
          borderRadius: '4px',
          fontWeight: '600',
          textTransform: 'uppercase',
          letterSpacing: '0.02em'
        }}>
          {type}{isArrayOfObjects ? '[]' : ''}
        </span>

        {/* Field Description */}
        <div 
          className={prop?.description ? "desc-tooltip-wrapper" : ""}
          style={{ 
            flex: 1, 
            minWidth: 0, 
            position: 'relative', 
            display: 'flex', 
            alignItems: 'center' 
          }}
        >
          <span style={{ 
            color: '#64748b', 
            fontSize: '12px',
            marginLeft: '8px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            width: '100%'
          }}>
            {prop?.description || "No description."}
          </span>
          {prop?.description && (
            <div className="desc-tooltip-text">
              {prop.description}
            </div>
          )}
        </div>

        {/* Live Value Badge */}
        {prop?.value !== undefined && (typeof prop.value !== 'object' || isEmptyValue) && (
          <span style={{
            fontSize: '11px',
            fontFamily: 'monospace',
            color: '#34d399',
            background: 'rgba(52, 211, 153, 0.08)',
            padding: '2px 8px',
            borderRadius: '6px',
            border: '1px solid rgba(52, 211, 153, 0.15)',
            marginLeft: '8px',
            maxWidth: '250px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap'
          }} title={isEmptyValue ? (Array.isArray(prop.value) ? '[]' : '{}') : String(prop.value)}>
            Value: {isEmptyValue ? (Array.isArray(prop.value) ? '[]' : '{}') : String(prop.value)}
          </span>
        )}

        {/* Smart Copy Action */}
        <SchemaCopyButton name={name} prop={prop} currentPath={currentPath} />
      </div>

      {/* Child Nodes */}
      {hasChildren && isExpanded && (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {Object.entries(childProperties).map(([childName, childProp]) => (
            <SchemaRow 
              key={childName}
              name={childName}
              prop={childProp}
              depth={depth + 1}
              parentPath={currentPath}
            />
          ))}
        </div>
      )}
    </div>
  );
};

const SchemaExplorer = ({ schema, executionResult }) => {
  const augmentedSchema = useMemo(() => {
    return augmentSchemaWithData(schema, executionResult);
  }, [schema, executionResult]);

  if (!augmentedSchema) return null;
  
  let properties = null;
  let isArray = false;
  const type = normalizeType(augmentedSchema.type);
  
  if (type === 'object' && augmentedSchema.properties) {
    properties = augmentedSchema.properties;
  } else if (type === 'array' && augmentedSchema.items) {
    const itemType = normalizeType(augmentedSchema.items.type);
    if (itemType === 'object' && augmentedSchema.items.properties) {
      properties = augmentedSchema.items.properties;
      isArray = true;
    }
  }
  
  if (!properties || Object.keys(properties).length === 0) {
    return (
      <div style={{ 
        color: '#34d399', 
        fontFamily: 'monospace', 
        padding: '16px',
        background: 'rgba(30, 41, 59, 0.15)',
        borderRadius: '12px',
        border: '1px solid rgba(255,255,255,0.05)'
      }}>
        {normalizeType(augmentedSchema.type || 'any')}
      </div>
    );
  }
  
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      background: 'rgba(30, 41, 59, 0.15)',
      borderRadius: '12px',
      border: '1px solid rgba(255,255,255,0.05)',
      overflow: 'visible'
    }}>
      {Object.entries(properties).map(([name, prop]) => (
        <SchemaRow 
          key={name}
          name={name}
          prop={prop}
          depth={0}
          parentPath=""
        />
      ))}
    </div>
  );
};

const JsonRow = ({ name, value, depth = 0, parentPath = '' }) => {
  const [isExpanded, setIsExpanded] = useState(depth < 2);
  
  const currentPath = parentPath ? (typeof name === 'number' ? `${parentPath}[${name}]` : `${parentPath}.${name}`) : name;
  const valueType = value === null ? 'null' : Array.isArray(value) ? 'array' : typeof value;
  const isObject = valueType === 'object' || valueType === 'array';
  
  let childrenCount = 0;
  if (valueType === 'object' && value !== null) {
    childrenCount = Object.keys(value).length;
  } else if (valueType === 'array') {
    childrenCount = value.length;
  }
  
  const hasChildren = isObject && childrenCount > 0;
  
  const renderValue = () => {
    if (value === null) return <span style={{ color: '#64748b', fontFamily: 'monospace' }}>null</span>;
    if (valueType === 'boolean') return <span style={{ color: '#38bdf8', fontFamily: 'monospace' }}>{String(value)}</span>;
    if (valueType === 'number') return <span style={{ color: '#34d399', fontFamily: 'monospace' }}>{value}</span>;
    if (valueType === 'string') {
      const isLong = value.length > 60;
      const displayed = isLong ? `${value.slice(0, 57)}...` : value;
      return (
        <div 
          className={isLong ? "desc-tooltip-wrapper" : ""} 
          style={{ 
            display: 'inline-flex', 
            position: 'relative', 
            overflow: 'visible', 
            verticalAlign: 'bottom',
            maxWidth: '100%' 
          }}
        >
          <span 
            style={{ 
              color: '#f43f5e', 
              fontFamily: 'monospace',
              display: 'inline-block',
              maxWidth: '350px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}
          >
            "{displayed}"
          </span>
          {isLong && (
            <div className="desc-tooltip-text" style={{ fontFamily: 'monospace', wordBreak: 'break-all', textTransform: 'none', letterSpacing: 'normal' }}>
              {value}
            </div>
          )}
        </div>
      );
    }
    if (valueType === 'array') return <span style={{ color: '#64748b', fontSize: '12px' }}>Array [{childrenCount}]</span>;
    return <span style={{ color: '#64748b', fontSize: '12px' }}>Object ({childrenCount})</span>;
  };
  
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <div 
        onClick={() => hasChildren && setIsExpanded(!isExpanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '10px 16px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.03)',
          gap: '12px',
          fontSize: '13px',
          cursor: hasChildren ? 'pointer' : 'default',
          transition: 'all 0.2s ease',
          paddingLeft: `${16 + depth * 24}px`,
          position: 'relative'
        }}
        onMouseEnter={e => {
          if (hasChildren) e.currentTarget.style.background = 'rgba(255,255,255,0.015)';
        }}
        onMouseLeave={e => {
          if (hasChildren) e.currentTarget.style.background = 'transparent';
        }}
      >
        {depth > 0 && (
          <div style={{
            position: 'absolute',
            left: `${8 + (depth - 1) * 24}px`,
            top: 0,
            bottom: 0,
            width: '1px',
            background: 'rgba(255, 255, 255, 0.05)'
          }} />
        )}

        <div style={{ width: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {hasChildren && (
            <ChevronDown 
              size={14} 
              style={{ 
                transform: isExpanded ? 'rotate(0deg)' : 'rotate(-90deg)', 
                transition: 'transform 0.2s ease',
                color: isExpanded ? '#818cf8' : '#64748b' 
              }} 
            />
          )}
        </div>

        <span style={{ 
          fontFamily: 'monospace', 
          fontWeight: '600', 
          color: typeof name === 'number' ? '#c084fc' : '#a5b4fc' 
        }}>
          {name}
        </span>

        <span style={{ color: '#64748b' }}>:</span>

        <div style={{ 
          flex: 1, 
          overflow: 'hidden', 
          textOverflow: 'ellipsis', 
          whiteSpace: 'nowrap',
          marginLeft: '4px'
        }}>
          {renderValue()}
        </div>

        <JsonCopyButton name={name} value={value} currentPath={currentPath} valueType={valueType} />
      </div>

      {hasChildren && isExpanded && (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {valueType === 'array' ? (
            value.map((item, index) => (
              <JsonRow 
                key={index}
                name={index}
                value={item}
                depth={depth + 1}
                parentPath={currentPath}
              />
            ))
          ) : (
            Object.entries(value).map(([key, val]) => (
              <JsonRow 
                key={key}
                name={key}
                value={val}
                depth={depth + 1}
                parentPath={currentPath}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
};

const JsonInspector = ({ data }) => {
  if (!data) return null;
  
  const isObject = typeof data === 'object' && data !== null;
  
  if (!isObject) {
    return (
      <div style={{ 
        fontFamily: 'monospace', 
        padding: '16px',
        background: 'rgba(30, 41, 59, 0.15)',
        borderRadius: '12px',
        border: '1px solid rgba(255,255,255,0.05)',
        color: '#f8fafc'
      }}>
        {String(data)}
      </div>
    );
  }
  
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      background: 'rgba(0, 0, 0, 0.15)',
      borderRadius: '12px',
      border: '1px solid rgba(255,255,255,0.03)',
      overflow: 'visible'
    }}>
      {Array.isArray(data) ? (
        data.map((item, index) => (
          <JsonRow 
            key={index}
            name={index}
            value={item}
            depth={0}
            parentPath=""
          />
        ))
      ) : (
        Object.entries(data).map(([key, val]) => (
          <JsonRow 
            key={key}
            name={key}
            value={val}
            depth={0}
            parentPath=""
          />
        ))
      )}
    </div>
  );
};

// --- Main Component ---

const LandmarkDetails = ({ 
  selectedLandmark, landmarkData, allLandmarks, onSelectLandmark, signature, instructions, memoryBank, onExecute, executing, executionResult, renderFormattedText, error, loading 
}) => {
  const [testerParams, setTesterParams] = useState({});
  const [copied, setCopied] = useState(false);
  const [showSchemaDetails, setShowSchemaDetails] = useState(false);
  const [showInputDetails, setShowInputDetails] = useState(true);
  const [resultViewTab, setResultViewTab] = useState('inspector');

  useEffect(() => {
    setShowSchemaDetails(false);
    setShowInputDetails(true);
  }, [selectedLandmark]);

  const childLandmarks = useMemo(() => {
    if (!allLandmarks || !selectedLandmark) return [];
    const prefix = `${selectedLandmark}:`;
    return Object.values(allLandmarks).filter(lm => {
      if (!lm || !lm.id) return false;
      if (lm.id === selectedLandmark) return false;
      if (!lm.id.startsWith(prefix)) return false;
      const remaining = lm.id.slice(prefix.length);
      return !remaining.includes(':');
    });
  }, [allLandmarks, selectedLandmark]);

  const pathSegments = useMemo(() => {
    return typeof selectedLandmark === 'string' ? selectedLandmark.split(':') : [];
  }, [selectedLandmark]);

  const isExecutable = landmarkData?.isTool || landmarkData?.is_tool;

  const { normalParams, combinedHygiene } = useMemo(() => {
    const raw = landmarkData?.parameters || [];
    const normal = Array.isArray(raw) ? raw.filter(p => p && p.name && !p.name.startsWith('_')) : [];
    const inManifest = Array.isArray(raw) ? raw.filter(p => p && p.name && p.name.startsWith('_')) : [];
    const combined = [...inManifest];
    HYGIENE_PARAMS.forEach(def => {
      if (!combined.some(p => p.name === def.name)) combined.push(def);
    });
    return { normalParams: normal, combinedHygiene: combined };
  }, [landmarkData]);

  if (!selectedLandmark) return <div className="empty-state">Select a landmark to inspect</div>;

  return (
    <div className="landmark-details-container">
      {/* Custom styles for our elegant, CSS-based description & value tooltips */}
      <style>{`
        .desc-tooltip-wrapper {
          position: relative;
          overflow: visible !important;
        }
        .desc-tooltip-wrapper .desc-tooltip-text {
          visibility: hidden;
          opacity: 0;
          width: 320px;
          background-color: #0f172a !important;
          color: #cbd5e1 !important;
          text-align: left;
          border-radius: 12px;
          padding: 12px 16px;
          position: absolute;
          z-index: 99999999 !important;
          bottom: 130%;
          left: 50%;
          transform: translateX(-50%) translateY(6px);
          transition: opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1), transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
          transition-delay: 0s !important;
          font-size: 11px !important;
          font-weight: 400 !important;
          line-height: 1.5 !important;
          box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6) !important;
          border: 1px solid rgba(255, 255, 255, 0.1) !important;
          backdrop-filter: blur(12px);
          pointer-events: none;
          white-space: normal !important;
          word-wrap: break-word !important;
          text-transform: none !important;
          letter-spacing: normal !important;
        }
        .desc-tooltip-wrapper:hover .desc-tooltip-text {
          visibility: visible;
          opacity: 1;
          transform: translateX(-50%) translateY(0);
          transition-delay: 450ms !important;
        }
      `}</style>
      {/* Header */}
      <div className="mi-header-row">
        <div className="mi-header-main">
           <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
              <div className="badge-micro">{(landmarkData?.isTool || landmarkData?.is_tool) ? 'Executable Tool' : 'Area Namespace'}</div>
              {landmarkData?.meta?.method && <div className="badge-micro" style={{background: '#3b82f6'}}>{landmarkData.meta.method}</div>}
              {landmarkData?.meta?.path && <div className="badge-micro" style={{background: '#1f2937', color: '#9ca3af', fontFamily: 'monospace'}}>{landmarkData.meta.path}</div>}
              {landmarkData?.meta?.operation_type && <div className="badge-micro" style={{background: '#8b5cf6'}}>{landmarkData.meta.operation_type}</div>}
           </div>
           
           {pathSegments.length > 1 && (
             <div style={{ 
               display: 'flex', 
               alignItems: 'center', 
               gap: '6px', 
               marginBottom: '8px', 
               fontSize: '0.75rem', 
               color: '#64748b',
               flexWrap: 'wrap',
               fontFamily: 'monospace'
             }}>
               {pathSegments.map((segment, index) => {
                 const isLast = index === pathSegments.length - 1;
                 const parentId = pathSegments.slice(0, index + 1).join(':');
                 return (
                   <React.Fragment key={index}>
                     {index > 0 && <span style={{ opacity: 0.3, color: '#94a3b8' }}>/</span>}
                     <span
                       onClick={() => !isLast && onSelectLandmark && onSelectLandmark(parentId)}
                       style={{
                         cursor: isLast ? 'default' : 'pointer',
                         color: isLast ? '#94a3b8' : '#818cf8',
                         fontWeight: isLast ? '500' : '600',
                         textDecoration: isLast ? 'none' : 'underline',
                         textUnderlineOffset: '3px',
                         transition: 'color 0.2s ease'
                       }}
                       onMouseEnter={e => { if (!isLast) e.currentTarget.style.color = '#a5b4fc'; }}
                       onMouseLeave={e => { if (!isLast) e.currentTarget.style.color = '#818cf8'; }}
                     >
                       {segment}
                     </span>
                   </React.Fragment>
                 );
               })}
             </div>
           )}

           <h1 className="mi-header-title">{typeof selectedLandmark === 'string' ? selectedLandmark.split(/[:_]/).pop() : 'Node'}</h1>
           <p className="mi-header-desc">{landmarkData?.description || "Technical landmark node in the topology."}</p>
           {isExecutable && isSignatureUseful(signature) && (
             <div style={{ 
               marginTop: '12px', 
               background: 'rgba(15, 23, 42, 0.45)', 
               borderRadius: '8px', 
               border: '1px solid rgba(255,255,255,0.05)',
               padding: '8px 12px',
               fontSize: '0.75rem',
               fontFamily: 'JetBrains Mono, Fira Code, monospace',
               color: '#cbd5e1',
               overflowX: 'auto',
               whiteSpace: 'nowrap',
               width: 'fit-content',
               maxWidth: '100%',
               boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
             }}>
               <code style={{ color: '#38bdf8' }}>{signature.replace(/\/\*\*.*?\*\/\n?/gs, '').trim()}</code>
             </div>
           )}
        </div>
        <button className="btn-action-pill" onClick={() => {
           navigator.clipboard.writeText(signature || selectedLandmark);
           setCopied(true);
           setTimeout(() => setCopied(false), 2000);
        }}>
          {copied ? <Check size={14} /> : <Copy size={14} />}
          <span>{copied ? 'Copied' : 'Copy Spec'}</span>
        </button>
      </div>

      <div className="mi-details-content">
        {selectedLandmark === 'instructions' ? (
          <Section title="Protocol Instructions" icon={BookOpen}>
            <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderFormattedText(instructions) }} />
          </Section>
        ) : (
          (() => {
            const leftColContent = (
              <>
                {(normalParams.length > 0 || combinedHygiene.length > 0) && (() => {
                  const totalParamCount = normalParams.length + combinedHygiene.length;
                  return (
                    <Section title="Input Parameters" icon={Layers}>
                      <div className="returns-remedy-box" style={{ 
                        background: 'rgba(30, 41, 59, 0.3)', 
                        padding: '20px', 
                        borderRadius: '16px', 
                        fontSize: '13px', 
                        display: 'flex', 
                        flexDirection: 'column', 
                        gap: '16px', 
                        border: '1px solid rgba(255,255,255,0.06)',
                        backdropFilter: 'blur(10px)',
                        boxShadow: '0 4px 30px rgba(0, 0, 0, 0.2)'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', fontWeight: 'bold', letterSpacing: '0.05em'}}>Inputs Detected:</span> 
                            <span style={{ 
                              color: '#818cf8', 
                              background: 'rgba(99, 102, 241, 0.08)',
                              border: '1px solid rgba(99, 102, 241, 0.2)',
                              padding: '4px 10px',
                              borderRadius: '8px',
                              fontFamily: 'monospace',
                              fontWeight: '600',
                              fontSize: '12px',
                              display: 'inline-flex',
                              alignItems: 'center',
                              boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.05)'
                            }}>
                              {totalParamCount} {totalParamCount === 1 ? 'Parameter' : 'Parameters'}
                            </span>
                          </div>

                          <button 
                            onClick={() => setShowInputDetails(!showInputDetails)}
                            style={{
                              background: showInputDetails ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                              border: showInputDetails ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)',
                              color: showInputDetails ? '#818cf8' : '#cbd5e1',
                              padding: '6px 14px',
                              borderRadius: '10px',
                              cursor: 'pointer',
                              fontWeight: '600',
                              fontSize: '12px',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                              transition: 'all 0.2s ease',
                              outline: 'none'
                            }}
                          >
                            {showInputDetails ? <EyeOff size={14} /> : <Eye size={14} />}
                            {showInputDetails ? 'Hide Fields' : `Explore ${totalParamCount} Input Fields`}
                            <ChevronDown 
                              size={14} 
                              style={{ 
                                transform: showInputDetails ? 'rotate(180deg)' : 'rotate(0)', 
                                transition: 'transform 0.2s ease' 
                              }} 
                            />
                          </button>
                        </div>

                        {showInputDetails && (
                          <div className="output-schema-section" style={{
                            borderTop: '1px solid rgba(255,255,255,0.06)',
                            paddingTop: '20px'
                          }}>
                            <strong style={{color: '#6366f1', display: 'block', marginBottom: '14px', fontSize: '11px', textTransform: 'uppercase', fontWeight: 'bold', letterSpacing: '0.05em'}}>Parameter Structure:</strong>
                            
                            <div style={{
                              display: 'flex',
                              flexDirection: 'column',
                              background: 'rgba(30, 41, 59, 0.15)',
                              borderRadius: '12px',
                              border: '1px solid rgba(255,255,255,0.05)',
                              overflow: 'visible'
                            }}>
                              {normalParams.map((p, index) => (
                                <ParameterRow 
                                  key={p.name} 
                                  param={p} 
                                  isLast={index === normalParams.length - 1 && combinedHygiene.length === 0} 
                                />
                              ))}
                              {combinedHygiene.map((p, index) => (
                                <ParameterRow 
                                  key={p.name} 
                                  param={p} 
                                  isHygiene 
                                  isLast={index === combinedHygiene.length - 1} 
                                />
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </Section>
                  );
                })()}

                {(landmarkData?.returns || landmarkData?.remedy || (landmarkData?.outputSchema && Object.keys(landmarkData.outputSchema).length > 0)) && (() => {
                  const effectiveSchema = parseReturnsToSchema(landmarkData?.returns, landmarkData?.outputSchema);
                  const showResponseStructure = hasStructuredSchema(effectiveSchema);
                  const simplifiedType = getSimplifiedTypeName(effectiveSchema, landmarkData?.returns);
                  
                  let fieldCount = 0;
                  if (effectiveSchema) {
                    if (effectiveSchema.properties) {
                      fieldCount = Object.keys(effectiveSchema.properties).length;
                    } else if (effectiveSchema.items && effectiveSchema.items.properties) {
                      fieldCount = Object.keys(effectiveSchema.items.properties).length;
                    }
                  }

                  return (
                    <Section title="Returns & Expected Schema" icon={Info}>
                       <div className="returns-remedy-box" style={{ 
                         background: 'rgba(30, 41, 59, 0.3)', 
                         padding: '20px', 
                         borderRadius: '16px', 
                         fontSize: '13px', 
                         display: 'flex', 
                         flexDirection: 'column', 
                         gap: '16px', 
                         border: '1px solid rgba(255,255,255,0.06)',
                         backdropFilter: 'blur(10px)',
                         boxShadow: '0 4px 30px rgba(0, 0, 0, 0.2)'
                       }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
                            {simplifiedType && simplifiedType !== 'any' && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span style={{color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', fontWeight: 'bold', letterSpacing: '0.05em'}}>Return Type:</span> 
                                <span style={{ 
                                  color: '#34d399', 
                                  background: 'rgba(52, 211, 153, 0.08)',
                                  border: '1px solid rgba(52, 211, 153, 0.2)',
                                  padding: '4px 10px',
                                  borderRadius: '8px',
                                  fontFamily: 'monospace',
                                  fontWeight: '600',
                                  fontSize: '12px',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.05)'
                                }}>
                                  {simplifiedType}
                                </span>
                              </div>
                            )}

                            {showResponseStructure && (
                              <button 
                                onClick={() => setShowSchemaDetails(!showSchemaDetails)}
                                style={{
                                  background: showSchemaDetails ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                                  border: showSchemaDetails ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)',
                                  color: showSchemaDetails ? '#818cf8' : '#cbd5e1',
                                  padding: '6px 14px',
                                  borderRadius: '10px',
                                  cursor: 'pointer',
                                  fontWeight: '600',
                                  fontSize: '12px',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '6px',
                                  transition: 'all 0.2s ease',
                                  outline: 'none'
                                }}
                              >
                                {showSchemaDetails ? <EyeOff size={14} /> : <Eye size={14} />}
                                {showSchemaDetails ? 'Hide Fields' : `Explore ${fieldCount} Response Fields`}
                                <ChevronDown 
                                  size={14} 
                                  style={{ 
                                    transform: showSchemaDetails ? 'rotate(180deg)' : 'rotate(0)', 
                                    transition: 'transform 0.2s ease' 
                                  }} 
                                />
                              </button>
                            )}
                          </div>

                          {landmarkData?.remedy && (
                            <div style={{ 
                              background: 'rgba(244, 114, 182, 0.05)',
                              borderLeft: '4px solid #f472b6',
                              padding: '12px 16px',
                              borderRadius: '0 8px 8px 0',
                              marginTop: '4px'
                            }}>
                              <strong style={{color: '#f472b6', display: 'block', marginBottom: '4px', fontSize: '11px', textTransform: 'uppercase', fontWeight: 'bold'}}>Remedy:</strong> 
                              <span style={{ color: '#cbd5e1', lineHeight: '1.5' }}>{landmarkData.remedy}</span>
                            </div>
                          )}
                          
                          {showResponseStructure && showSchemaDetails && (
                            <div className="output-schema-section" style={{
                              borderTop: '1px solid rgba(255,255,255,0.06)',
                              paddingTop: '20px'
                            }}>
                              <strong style={{color: '#6366f1', display: 'block', marginBottom: '14px', fontSize: '11px', textTransform: 'uppercase', fontWeight: 'bold', letterSpacing: '0.05em'}}>Response Structure:</strong>
                              <div className="output-schema-viz" style={{
                                background: 'rgba(0, 0, 0, 0.2)',
                                borderRadius: '12px',
                                border: '1px solid rgba(255, 255, 255, 0.03)',
                                overflow: 'visible'
                              }}>
                                <SchemaExplorer schema={effectiveSchema} />
                              </div>
                            </div>
                          )}
                       </div>
                    </Section>
                  );
                })()}
              </>
            );

            if (!isExecutable) {
              return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  {childLandmarks.length > 0 && (
                    <Section title="Sub-Areas & Available Tools in this Namespace" icon={Layers}>
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                        gap: '16px',
                        marginTop: '8px'
                      }}>
                        {childLandmarks.map(child => {
                          const isChildTool = child.isTool || child.is_tool;
                          const IconComponent = isChildTool ? Play : Folder;
                          const name = child.id.split(':').pop();
                          return (
                            <div
                              key={child.id}
                              onClick={() => onSelectLandmark && onSelectLandmark(child.id)}
                              style={{
                                background: 'rgba(30, 41, 59, 0.25)',
                                border: '1px solid rgba(255, 255, 255, 0.05)',
                                borderRadius: '12px',
                                padding: '16px',
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '8px',
                                position: 'relative',
                                overflow: 'hidden'
                              }}
                              onMouseEnter={e => {
                                e.currentTarget.style.background = 'rgba(99, 102, 241, 0.08)';
                                e.currentTarget.style.borderColor = 'rgba(99, 102, 241, 0.3)';
                                e.currentTarget.style.transform = 'translateY(-2px)';
                              }}
                              onMouseLeave={e => {
                                e.currentTarget.style.background = 'rgba(30, 41, 59, 0.25)';
                                e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.05)';
                                e.currentTarget.style.transform = 'translateY(0)';
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <div style={{
                                  background: isChildTool ? 'rgba(56, 189, 248, 0.1)' : 'rgba(139, 92, 246, 0.1)',
                                  color: isChildTool ? '#38bdf8' : '#a78bfa',
                                  padding: '8px',
                                  borderRadius: '8px',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center'
                                }}>
                                  <IconComponent size={16} />
                                </div>
                                <span style={{
                                  fontWeight: '600',
                                  color: '#f8fafc',
                                  fontSize: '14px'
                                }}>
                                  {name}
                                </span>
                                <span style={{
                                  fontSize: '9px',
                                  textTransform: 'uppercase',
                                  background: isChildTool ? 'rgba(56, 189, 248, 0.15)' : 'rgba(139, 92, 246, 0.15)',
                                  color: isChildTool ? '#38bdf8' : '#a78bfa',
                                  padding: '2px 6px',
                                  borderRadius: '6px',
                                  marginLeft: 'auto',
                                  fontWeight: 'bold',
                                  letterSpacing: '0.05em'
                                }}>
                                  {isChildTool ? 'Tool' : 'Area'}
                                </span>
                              </div>
                              <p style={{
                                margin: 0,
                                color: '#94a3b8',
                                fontSize: '12px',
                                lineHeight: '1.4',
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis'
                              }}>
                                {child.description || "No description provided."}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    </Section>
                  )}
                  {childLandmarks.length === 0 && (
                    <div style={{
                      textAlign: 'center',
                      padding: '40px',
                      color: '#64748b',
                      fontSize: '14px',
                      background: 'rgba(30, 41, 59, 0.15)',
                      borderRadius: '12px',
                      border: '1px solid rgba(255, 255, 255, 0.04)'
                    }}>
                      This namespace has no child landmarks or executable tools.
                    </div>
                  )}
                </div>
              );
            }

            return (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
                gap: '24px',
                alignItems: 'start'
              }}>
                {/* Left Column: Parameter + Returns */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {leftColContent}
                </div>

                {/* Right Column: Live Execution + Results */}
                <div style={{ 
                  display: 'flex', 
                  flexDirection: 'column', 
                  gap: '20px',
                  position: 'sticky',
                  top: '24px'
                }}>
                  <Section 
                    title="Live Execution" 
                    icon={Terminal}
                    action={
                      <button className="btn-action-pill" onClick={() => {
                        const parsedParams = {};
                        const allParams = [...normalParams, ...combinedHygiene];
                        Object.entries(testerParams).forEach(([key, val]) => {
                          const pDef = allParams.find(p => p.name === key);
                          const casted = castValue(val, pDef ? pDef.type : 'string');
                          if (casted !== undefined) {
                            parsedParams[key] = casted;
                          }
                        });
                        onExecute(selectedLandmark, parsedParams);
                      }} disabled={executing}>
                        {executing ? <RefreshCw className="spin" size={14} /> : <Play size={14} />}
                        <span>{executing ? 'Running...' : 'Execute'}</span>
                      </button>
                    }
                  >
                    {normalParams.length > 0 && (
                      <>
                        <h4 style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '12px', marginTop: '0' }}>Tool Parameters</h4>
                        <div className="tester-grid" style={{ marginBottom: '24px' }}>
                          {normalParams.map(p => (
                            <div key={p.name} className="tester-field">
                              <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                {p.name}
                                {p.required && <span className="badge-micro" style={{ background: '#ef4444', padding: '2px 4px', fontSize: '8px', color: '#fff' }}>REQ</span>}
                              </label>
                              <input 
                                type="text" 
                                className="tester-input" 
                                placeholder={p.type} 
                                onChange={e => setTesterParams(prev => ({...prev, [p.name]: e.target.value}))} 
                              />
                            </div>
                          ))}
                        </div>
                      </>
                    )}

                    {combinedHygiene.length > 0 && (
                      <>
                        <h4 style={{ fontSize: '11px', color: '#6366f1', textTransform: 'uppercase', marginBottom: '12px', marginTop: '0' }}>Elemm Protocol Hygiene</h4>
                        <div className="tester-grid" style={{ marginBottom: '24px' }}>
                          {combinedHygiene.map(p => (
                            <div key={p.name} className="tester-field">
                              <label>{p.name}</label>
                              <input 
                                type="text" 
                                className="tester-input" 
                                placeholder={p.type} 
                                onChange={e => setTesterParams(prev => ({...prev, [p.name]: e.target.value}))} 
                              />
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                    
                    {executionResult && (
                      <div className="execution-result custom-scrollbar" style={{ marginTop: '0' }}>
                        {executionResult.status === 'error' || executionResult.error || executionResult.detail ? (
                          <div className="execution-error-box">
                            <div className="error-header"><AlertCircle size={16}/> Execution Failed</div>
                            {executionResult._PROTOCOL_ERROR && <div className="error-protocol-code">[{executionResult._PROTOCOL_ERROR}]</div>}
                            <div className="error-message">
                              {executionResult.message || executionResult.error || executionResult.detail || executionResult.remote_response || "An unknown error occurred during execution."}
                            </div>
                            {executionResult.remedy && (
                              <div className="error-remedy">
                                <strong style={{color: '#f472b6', marginRight: '6px'}}>REMEDY:</strong> 
                                {executionResult.remedy}
                              </div>
                            )}
                            {(executionResult._DEBUG_ECHO || (typeof executionResult === 'object' && !executionResult.message && !executionResult.error && !executionResult.detail)) && (
                              <details className="error-debug">
                                <summary>Debug Info</summary>
                                <pre>{JSON.stringify(executionResult._DEBUG_ECHO || executionResult, null, 2)}</pre>
                              </details>
                            )}
                          </div>
                        ) : (
                          <div className="execution-success-box">
                            {executionResult._HYGIENE_NOTICE && (
                              <div className="execution-hygiene-notice" style={{ marginBottom: '12px', padding: '12px', background: 'rgba(99, 102, 241, 0.1)', borderLeft: '2px solid #6366f1', borderRadius: '0 4px 4px 0' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#818cf8', fontWeight: 'bold', marginBottom: '4px' }}>
                                  <AlertCircle size={14}/> Protocol Hygiene Notice
                                </div>
                                <div style={{ color: '#c7d2fe' }}>{executionResult._HYGIENE_NOTICE}</div>
                                {executionResult.remedy && <div style={{marginTop:'8px', color:'#f472b6'}}><strong>Remedy:</strong> {executionResult.remedy}</div>}
                              </div>
                            )}
                            {/* Tab Switcher */}
                            <div style={{
                              display: 'flex',
                              gap: '4px',
                              background: 'rgba(0, 0, 0, 0.2)',
                              padding: '2px',
                              borderRadius: '8px',
                              marginBottom: '16px',
                              width: 'fit-content',
                              border: '1px solid rgba(255, 255, 255, 0.04)'
                            }}>
                              <button 
                                onClick={() => setResultViewTab('inspector')}
                                style={{
                                  background: resultViewTab === 'inspector' ? '#6366f1' : 'transparent',
                                  border: 'none',
                                  color: resultViewTab === 'inspector' ? '#ffffff' : '#94a3b8',
                                  padding: '6px 12px',
                                  borderRadius: '6px',
                                  fontSize: '11px',
                                  fontWeight: '600',
                                  cursor: 'pointer',
                                  transition: 'all 0.2s ease',
                                  outline: 'none'
                                }}
                              >
                                Object Inspector
                              </button>
                              <button 
                                onClick={() => setResultViewTab('raw')}
                                style={{
                                  background: resultViewTab === 'raw' ? '#6366f1' : 'transparent',
                                  border: 'none',
                                  color: resultViewTab === 'raw' ? '#ffffff' : '#94a3b8',
                                  padding: '6px 12px',
                                  borderRadius: '6px',
                                  fontSize: '11px',
                                  fontWeight: '600',
                                  cursor: 'pointer',
                                  transition: 'all 0.2s ease',
                                  outline: 'none'
                                }}
                              >
                                Raw JSON
                              </button>
                            </div>

                            {/* Content */}
                            {resultViewTab === 'inspector' ? (
                              <JsonInspector data={executionResult.data !== undefined ? executionResult.data : executionResult} />
                            ) : (
                              <pre style={{ margin: 0 }}>{JSON.stringify(executionResult.data || executionResult, null, 2)}</pre>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </Section>
                </div>
              </div>
            );
          })()
        )}
      </div>
    </div>
  );
};

export default LandmarkDetails;
