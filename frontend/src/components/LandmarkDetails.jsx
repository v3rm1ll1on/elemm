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

            {(landmarkData?.returns || landmarkData?.remedy) && (
              <Section title="Returns & Remedy" icon={Info}>
                 <div className="returns-remedy-box" style={{ background: 'rgba(255,255,255,0.05)', padding: '12px', borderRadius: '6px', fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {landmarkData?.returns && <div><strong style={{color: '#94a3b8'}}>Returns:</strong> <code style={{ color: '#34d399', marginLeft: '8px' }}>{landmarkData.returns}</code></div>}
                    {landmarkData?.remedy && <div><strong style={{color: '#94a3b8'}}>Remedy:</strong> <span style={{ color: '#f472b6', marginLeft: '8px' }}>{landmarkData.remedy}</span></div>}
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
