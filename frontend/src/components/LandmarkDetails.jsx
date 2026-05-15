import React, { useState, useMemo } from 'react';
import './LandmarkDetails.css';
import { 
  Terminal, 
  Layers, 
  ArrowRight, 
  RefreshCw, 
  Globe, 
  Database, 
  BookOpen, 
  Check, 
  Copy,
  Info,
  Zap,
  Cpu,
  AlertCircle,
  Code,
  Layout,
  Play
} from 'lucide-react';

// --- Constants ---
const HYGIENE_PARAMS = [
  { name: '_select', type: 'string', description: 'Fields to return (comma-separated). Use dot-notation for nested objects.', location: 'protocol' },
  { name: '_filter', type: 'string', description: 'Basic equality filter (e.g. status:active).', location: 'protocol' },
  { name: '_limit', type: 'number', description: 'Max number of items to return.', location: 'protocol' }
];

// --- Utilities ---
const castValue = (value, type) => {
  if (!value || value === "") return undefined;
  if (type === 'number' || type === 'integer') return Number(value);
  if (type === 'boolean') return value === 'true' || value === true;
  return value;
};

// --- Sub-Components ---

const ParameterCard = ({ param, isHygiene }) => (
  <div className={`param-card-modern ${isHygiene ? 'hygiene' : ''}`}>
    <div className="p-header">
      <div className="p-name-tag">
        <span className="p-name">{param.name}</span>
        {param.required && <span className="p-req-badge" style={{color: '#ef4444', fontSize: '10px'}}>*</span>}
      </div>
      <div className="p-meta">
        <span className="p-type-pill">{param.type}</span>
        {param.location && (
          <span className={`p-loc-badge loc-${param.location.toLowerCase()}`}>
            {param.location === 'protocol' ? 'PROT' : param.location.toUpperCase()}
          </span>
        )}
      </div>
    </div>
    <div className="p-desc">
      {param.description || (isHygiene ? "Standard Elemm protocol parameter." : "No description provided.")}
    </div>
  </div>
);

const TesterField = ({ param, value, onChange }) => (
  <div className="tester-field">
    <label className="tester-label">
      <span>{param.name}</span>
      <span className="p-type-pill">{param.type}</span>
    </label>
    {param.type === 'boolean' ? (
      <select className="tester-input" value={value || ''} onChange={e => onChange(e.target.value)}>
        <option value="">Select...</option>
        <option value="true">true</option>
        <option value="false">false</option>
      </select>
    ) : (
      <input 
        type={param.type === 'number' ? 'number' : 'text'}
        className="tester-input"
        placeholder={`Enter ${param.name}...`}
        value={value || ''}
        onChange={e => onChange(e.target.value)}
      />
    )}
  </div>
);

const Section = ({ title, icon: Icon, children, action }) => (
  <div className="spec-section-card">
    <div className="spec-card-header">
      <div className="spec-card-title">
        <Icon size={14} />
        <span>{title}</span>
      </div>
      {action && <div>{action}</div>}
    </div>
    <div className="spec-card-body">
      {children}
    </div>
  </div>
);

// --- Main Components ---

const LandmarkDetails = ({ 
  selectedLandmark, 
  landmarkData, 
  signature, 
  instructions,
  memoryBank,
  onExecute,
  executing,
  executionResult,
  renderFormattedText,
  error,
  loading
}) => {
  const [testerParams, setTesterParams] = useState({});
  const [copied, setCopied] = useState(false);

  // Memoized parameter list to avoid recalculation
  const { normalParams, combinedHygiene } = useMemo(() => {
    const raw = landmarkData?.parameters || [];
    const normal = raw.filter(p => !p.name.startsWith('_'));
    const inManifest = raw.filter(p => p.name.startsWith('_'));
    
    // Merge manifest hygiene with defaults
    const combined = [...inManifest];
    HYGIENE_PARAMS.forEach(def => {
      if (!combined.some(p => p.name === def.name)) combined.push(def);
    });
    
    return { normalParams: normal, combinedHygiene: combined };
  }, [landmarkData]);

  const handleExecute = () => {
    const finalPayload = {};
    [...normalParams, ...combinedHygiene].forEach(p => {
      const val = castValue(testerParams[p.name], p.type);
      if (val !== undefined) finalPayload[p.name] = val;
    });
    onExecute(selectedLandmark, finalPayload);
  };

  const handleCopySpec = () => {
    const md = `# Spec: ${selectedLandmark}\n\n${landmarkData?.description}\n\n${signature}`;
    navigator.clipboard.writeText(md).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (!selectedLandmark) return (
    <div className="empty-details-view">
      <Globe size={64} className="text-accent opacity-20" />
      <h2 className="glow-text-indigo">Satellite Link Ready</h2>
      <p className="text-muted">Select a node from the topology to begin technical inspection.</p>
    </div>
  );

  if (loading && selectedLandmark !== 'instructions') return (
    <div className="empty-details-view">
      <RefreshCw size={48} className="spin text-accent" />
      <p className="font-mono text-xs tracking-widest uppercase opacity-50">Fetching Specifications...</p>
    </div>
  );

  return (
    <div className="landmark-details-container">
      {/* Header */}
      <div className="mi-header-row">
        <div className="mi-header-left">
          <div className="mi-header-badge">
            <div className="mi-header-pulse"></div>
            <span>{landmarkData?.isTool ? 'Executable Tool' : 'Area Namespace'}</span>
          </div>
          <h1 className="mi-header-title glow-text-indigo">{selectedLandmark.split(/[:_]/).pop()}</h1>
          <p className="mi-header-desc">{landmarkData?.description || "No specific architectural data available."}</p>
        </div>
        <div className="mi-header-right">
          <button className={`btn-action-pill ${copied ? 'success' : ''}`} onClick={handleCopySpec}>
            {copied ? <Check size={14} /> : <Copy size={14} />}
            <span>{copied ? 'Copied' : 'Copy Spec'}</span>
          </button>
        </div>
      </div>

      {/* Conditional Content */}
      {selectedLandmark === 'instructions' ? (
        <div className="tester-layout">
          <Section title="Protocol Rules" icon={BookOpen}>
            <div className="markdown-body text-sm" dangerouslySetInnerHTML={{ __html: renderFormattedText(instructions) }} />
          </Section>
          {memoryBank && (
            <Section title="Memory Bank" icon={Database}>
              <div className="markdown-body text-sm font-mono text-purple-300" dangerouslySetInnerHTML={{ __html: renderFormattedText(memoryBank) }} />
            </Section>
          )}
        </div>
      ) : (
        <div className="tester-layout">
          {/* Technical Signature */}
          {signature && (
            <Section title="Technical Signature" icon={Code}>
              <pre className="signature-display">{signature}</pre>
            </Section>
          )}

          {/* Discovery Grid */}
          <Section title="Technical Discovery" icon={Layers}>
            <div className="param-grid">
              {normalParams.map(p => <ParameterCard key={p.name} param={p} />)}
              {combinedHygiene.map(p => <ParameterCard key={p.name} param={p} isHygiene />)}
            </div>
          </Section>

          {/* Live Execution */}
          {landmarkData?.isTool && (
            <Section 
              title="Live Test Execution" 
              icon={Terminal} 
              action={
                <button className="btn-action-pill" onClick={handleExecute} disabled={executing}>
                  {executing ? <RefreshCw size={14} className="spin" /> : <Play size={14} />}
                  <span>{executing ? 'Executing...' : 'Run Tool'}</span>
                </button>
              }
            >
              <div className="tester-layout">
                <div className="tester-grid">
                  {normalParams.map(p => (
                    <TesterField 
                      key={p.name} 
                      param={p} 
                      value={testerParams[p.name]} 
                      onChange={(val) => setTesterParams(prev => ({...prev, [p.name]: val}))} 
                    />
                  ))}
                </div>
                
                <div className="mt-4 pt-4 border-t border-white/5">
                  <label className="tester-label mb-4 opacity-50">Hygiene Parameters</label>
                  <div className="tester-grid">
                    {combinedHygiene.map(p => (
                      <TesterField 
                        key={p.name} 
                        param={p} 
                        value={testerParams[p.name]} 
                        onChange={(val) => setTesterParams(prev => ({...prev, [p.name]: val}))} 
                      />
                    ))}
                  </div>
                </div>

                {executionResult && (
                  <div className="tester-result-card animate-fade-in">
                    <div className="tester-result-header">
                      <div className={`status-dot-pulse ${executionResult.error ? 'error' : 'success'}`} />
                      <span className="tester-label">Result</span>
                    </div>
                    <pre className="tt-result-pre">
                      {typeof executionResult === 'object' ? JSON.stringify(executionResult, null, 2) : executionResult}
                    </pre>
                  </div>
                )}
              </div>
            </Section>
          )}
        </div>
      )}
    </div>
  );
};

export default LandmarkDetails;
