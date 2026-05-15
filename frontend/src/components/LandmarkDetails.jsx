import React, { useState, useMemo } from 'react';
import './LandmarkDetails.css';
import { 
  Terminal, Layers, RefreshCw, Globe, Database, BookOpen, Check, Copy, Zap, Cpu, AlertCircle, Code, Play, Info
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

// --- Sub-Components ---

const ParameterCard = ({ param, isHygiene }) => (
  <div className={`param-card ${isHygiene ? 'hygiene' : ''}`}>
    <div className="p-header" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '6px', marginBottom: '8px' }}>
      <span className="p-name">{param.name}</span>
      <span className="p-type">{param.type}</span>
      {param.required && <span className="p-req badge-micro" style={{background: '#ef4444', marginLeft: 'auto'}}>Required</span>}
      {param.location && <span className="p-loc badge-micro" style={{background: '#4b5563', marginLeft: param.required ? '0' : 'auto'}}>{param.location}</span>}
    </div>
    <div className="p-desc">{param.description || "No description."}</div>
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

const SchemaExplorer = ({ schema }) => {
  const [path, setPath] = useState([]);
  const [copyFeedback, setCopyFeedback] = useState(null);
  
  const currentSchema = useMemo(() => {
    let curr = schema;
    for (const part of path) {
      if (curr.type === 'object' && curr.properties?.[part]) {
        curr = curr.properties[part];
      } else if (curr.type === 'array' && curr.items) {
        curr = curr.items;
      }
    }
    return curr;
  }, [schema, path]);

  const copyPath = (fieldName) => {
    const fullPath = [...path, fieldName].join('.');
    navigator.clipboard.writeText(fullPath);
    setCopyFeedback(fullPath);
    setTimeout(() => setCopyFeedback(null), 2000);
  };

  const renderGrid = (s) => {
    if (!s) return null;

    let fields = [];
    if (s.type === 'object' && s.properties) {
      fields = Object.entries(s.properties).map(([name, prop]) => ({
        name,
        type: prop.type || 'any',
        description: prop.description,
        raw: prop
      }));
    } else if (s.type === 'array' && s.items) {
      // Direct dive into array items to avoid double 'items' path
      return renderGrid(s.items);
    }

    if (fields.length === 0) {
      return <div style={{ color: '#34d399', fontFamily: 'monospace', padding: '12px' }}>{s.type || 'any'}</div>;
    }

    return (
      <div className="param-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
        {fields.map(f => {
          const isDrillable = f.type === 'object' || f.type === 'array';
          return (
            <div 
              key={f.name} 
              className={`param-card return-card ${isDrillable ? 'drillable' : ''}`}
              onClick={() => {
                if (isDrillable) {
                  setPath([...path, f.name]);
                } else {
                  copyPath(f.name);
                }
              }}
              style={{ 
                background: 'rgba(255,255,255,0.02)', 
                border: '1px solid rgba(255,255,255,0.05)',
                cursor: 'pointer',
                position: 'relative',
                overflow: 'hidden'
              }}
            >
              <div className="p-header" style={{ marginBottom: '4px', display: 'flex', justifyContent: 'space-between' }}>
                <span className="p-name" style={{ color: '#fca5a5' }}>{f.name}</span>
                <span className="p-type" style={{ color: '#34d399' }}>{f.type}</span>
              </div>
              {f.description && <div className="p-desc" style={{ fontSize: '11px', opacity: 0.6 }}>{f.description}</div>}
              <div style={{ position: 'absolute', bottom: '4px', right: '6px', opacity: 0.4 }}>
                 {isDrillable ? <Layers size={10} /> : <Copy size={10} />}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="schema-explorer-container" style={{ position: 'relative' }}>
      {/* Feedback Toast */}
      {copyFeedback && (
        <div style={{ 
          position: 'absolute', top: '-40px', right: '0', background: '#6366f1', color: 'white', 
          padding: '4px 12px', borderRadius: '20px', fontSize: '10px', fontWeight: 'bold',
          zIndex: 10, animation: 'fadeInOut 2s forwards'
        }}>
          PATH COPIED: {copyFeedback}
        </div>
      )}

      {/* Breadcrumbs */}
      <div className="schema-breadcrumbs" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', fontSize: '11px', color: '#94a3b8' }}>
        <span 
          onClick={() => setPath([])} 
          style={{ cursor: 'pointer', color: path.length === 0 ? '#6366f1' : 'inherit', fontWeight: path.length === 0 ? 'bold' : 'normal' }}
        >
          ROOT
        </span>
        {path.map((part, i) => (
          <React.Fragment key={i}>
            <span style={{ opacity: 0.3 }}>/</span>
            <span 
              onClick={() => setPath(path.slice(0, i + 1))}
              style={{ 
                cursor: 'pointer', 
                color: i === path.length - 1 ? '#6366f1' : 'inherit',
                fontWeight: i === path.length - 1 ? 'bold' : 'normal'
              }}
            >
              {part.toUpperCase()}
            </span>
          </React.Fragment>
        ))}
      </div>
      
      {/* Current Grid */}
      <div className="schema-view-animate">
        {renderGrid(currentSchema)}
      </div>
    </div>
  );
};

// --- Main Component ---

const LandmarkDetails = ({ 
  selectedLandmark, landmarkData, signature, instructions, memoryBank, onExecute, executing, executionResult, renderFormattedText, error, loading 
}) => {
  const [testerParams, setTesterParams] = useState({});
  const [copied, setCopied] = useState(false);

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
      {/* Header */}
      <div className="mi-header-row">
        <div className="mi-header-main">
           <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
              <div className="badge-micro">{(landmarkData?.isTool || landmarkData?.is_tool) ? 'Executable Tool' : 'Area Namespace'}</div>
              {landmarkData?.meta?.method && <div className="badge-micro" style={{background: '#3b82f6'}}>{landmarkData.meta.method}</div>}
              {landmarkData?.meta?.path && <div className="badge-micro" style={{background: '#1f2937', color: '#9ca3af', fontFamily: 'monospace'}}>{landmarkData.meta.path}</div>}
              {landmarkData?.meta?.operation_type && <div className="badge-micro" style={{background: '#8b5cf6'}}>{landmarkData.meta.operation_type}</div>}
           </div>
           <h1 className="mi-header-title">{typeof selectedLandmark === 'string' ? selectedLandmark.split(/[:_]/).pop() : 'Node'}</h1>
           <p className="mi-header-desc">{landmarkData?.description || "Technical landmark node in the topology."}</p>
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
          <>
            {signature && (
              <Section title="Technical Signature" icon={Code}>
                <pre className="signature-box">{signature}</pre>
              </Section>
            )}

            {(normalParams.length > 0 || combinedHygiene.length > 0) && (
              <Section title="Parameter Grid" icon={Layers}>
                <div className="param-grid">
                  {normalParams.map(p => <ParameterCard key={p.name} param={p} />)}
                  {combinedHygiene.map(p => <ParameterCard key={p.name} param={p} isHygiene />)}
                </div>
              </Section>
            )}

            {(landmarkData?.returns || landmarkData?.remedy || (landmarkData?.outputSchema && Object.keys(landmarkData.outputSchema).length > 0)) && (
              <Section title="Returns & Expected Schema" icon={Info}>
                 <div className="returns-remedy-box" style={{ background: 'rgba(255,255,255,0.03)', padding: '16px', borderRadius: '12px', fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '16px', border: '1px solid rgba(255,255,255,0.05)' }}>
                    {landmarkData?.returns && landmarkData.returns !== 'any' && (
                      <div><strong style={{color: '#94a3b8', display: 'block', marginBottom: '4px', fontSize: '11px', textTransform: 'uppercase'}}>Return Type:</strong> <code style={{ color: '#34d399' }}>{landmarkData.returns}</code></div>
                    )}
                    {landmarkData?.remedy && <div><strong style={{color: '#94a3b8', display: 'block', marginBottom: '4px', fontSize: '11px', textTransform: 'uppercase'}}>Remedy:</strong> <span style={{ color: '#f472b6' }}>{landmarkData.remedy}</span></div>}
                    
                    {landmarkData?.outputSchema && Object.keys(landmarkData.outputSchema).length > 0 && (
                      <div className="output-schema-section">
                        <strong style={{color: '#6366f1', display: 'block', marginBottom: '12px', fontSize: '11px', textTransform: 'uppercase'}}>Response Structure:</strong>
                        <div className="output-schema-viz">
                          <SchemaExplorer schema={landmarkData.outputSchema} />
                        </div>
                      </div>
                    )}
                 </div>
              </Section>
            )}

            {(landmarkData?.isTool || landmarkData?.is_tool) && (
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
                    <div className="tester-grid">
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
                  <div className="execution-result custom-scrollbar">
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
                        <pre>{JSON.stringify(executionResult.data || executionResult, null, 2)}</pre>
                      </div>
                    )}
                  </div>
                )}
              </Section>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default LandmarkDetails;
