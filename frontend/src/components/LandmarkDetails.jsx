import React, { useState } from 'react';
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
  AlertCircle
} from 'lucide-react';

const ParameterDocumentation = ({ parameters }) => {
  if (!parameters || parameters.length === 0) return null;

  const sortedParams = [...parameters].sort((a, b) => {
    if (a.name.startsWith('_') && !b.name.startsWith('_')) return 1;
    if (!a.name.startsWith('_') && b.name.startsWith('_')) return -1;
    return 0;
  });

  return (
    <div className="parameter-doc-container mb-6">
      <div className="parameter-doc-title">
        <BookOpen size={14} className="text-accent" />
        <label>Technical Discovery & Parameter Documentation</label>
      </div>
      <div className="parameter-doc-grid">
        {sortedParams.map((p, i) => {
          const isHygiene = p.name.startsWith('_');
          return (
            <div key={i} className={`parameter-doc-card ${isHygiene ? 'hygiene' : ''}`}>
              <div className="parameter-doc-header">
                <div className="param-name-group">
                  <span className="param-name">{p.name}</span>
                  <span className="param-type-badge">{p.type}</span>
                  {p.location && (
                    <span className={`param-loc-badge loc-${p.location}`}>
                      {p.location === 'query' ? 'QRY' : p.location === 'path' ? 'PTH' : p.location === 'body' ? 'BDY' : p.location === 'header' ? 'HDR' : p.location.toUpperCase()}
                    </span>
                  )}
                  {isHygiene && <span className="param-loc-badge loc-protocol">PROT</span>}
                </div>
                {p.required && <span className="param-req-badge">Required</span>}
              </div>
              {p.description && (
                <div className="param-desc">{p.description}</div>
              )}
              {!p.description && isHygiene && (
                <div className="param-desc opacity-40 italic text-[10px]">Standard Elemm hygiene parameter.</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const ToolTester = ({ landmark, parameters, onExecute, executing, result }) => {
  const [params, setParams] = useState({});

  const handleExecuteClick = () => {
    const parsedParams = {};
    const allExpectedParams = [...parameters];
    
    // Ensure hygiene params are included in the logic even if not in manifest
    ['_select', '_filter', '_limit'].forEach(name => {
      if (!allExpectedParams.some(p => p.name === name)) {
        allExpectedParams.push({ name, type: name === '_limit' ? 'number' : 'string' });
      }
    });

    allExpectedParams.forEach(p => {
       if (params[p.name] !== undefined && params[p.name] !== "") {
          if (p.type === 'number' || p.type === 'integer') {
             parsedParams[p.name] = Number(params[p.name]);
          } else if (p.type === 'boolean') {
             parsedParams[p.name] = params[p.name] === 'true' || params[p.name] === true;
          } else {
             parsedParams[p.name] = params[p.name];
          }
       }
    });
    onExecute(landmark, parsedParams);
  };

  const normalParams = parameters.filter(p => !p.name.startsWith('_'));
  const manifestElemmParams = parameters.filter(p => p.name.startsWith('_'));
  
  const standardHygieneNames = ['_select', '_filter', '_limit'];
  const hygieneParams = [...manifestElemmParams];
  
  standardHygieneNames.forEach(name => {
    if (!hygieneParams.some(p => p.name === name)) {
      hygieneParams.push({ 
        name, 
        type: name === '_limit' ? 'number' : 'string', 
        required: false, 
        description: `Standard Elemm protocol ${name.slice(1)} parameter.` 
      });
    }
  });

  return (
    <div className="console-call-card theme-execute expanded mt-6">
      <div className="card-header">
        <div className="header-left">
           <Terminal size={14} className="text-accent" />
           <span className="action-title font-bold text-accent">LIVE TEST EXECUTION</span>
        </div>
        <div className="header-right">
          <button className="btn-action-pill" onClick={handleExecuteClick} disabled={executing}>
            {executing ? <RefreshCw size={14} className="spin" /> : <Terminal size={14} />}
            <span>{executing ? 'EXECUTING...' : 'TRY IT OUT'}</span>
          </button>
        </div>
      </div>
      <div className="card-body bg-black/20 p-6">
         {normalParams.length === 0 && hygieneParams.length === 0 ? (
           <div style={{color: 'rgba(255,255,255,0.4)', fontSize: '0.875rem', fontStyle: 'italic'}}>This tool takes no parameters.</div>
         ) : (
           <>
             {normalParams.length > 0 && (
               <div className="tt-grid">
                 {normalParams.map(p => (
                   <div key={p.name} className="tt-field">
                     <label className="tt-label">
                       <div className="flex items-center gap-2">
                          <span>{p.name} {p.required && <span style={{color: '#ef4444', marginLeft: '4px'}}>*</span>}</span>
                          {p.location && (
                             <span className={`param-loc-badge loc-${p.location} mini`}>
                               {p.location === 'query' ? 'QRY' : p.location === 'path' ? 'PTH' : p.location === 'body' ? 'BDY' : p.location === 'header' ? 'HDR' : p.location.toUpperCase()}
                             </span>
                          )}
                       </div>
                       <span className="tt-type-badge">{p.type}</span>
                     </label>
                     {p.type === 'boolean' ? (
                       <select 
                         className="tt-input"
                         value={params[p.name] || ''}
                         onChange={e => setParams({...params, [p.name]: e.target.value})}
                       >
                         <option value="">- Select -</option>
                         <option value="true">true</option>
                         <option value="false">false</option>
                       </select>
                     ) : (
                       <input 
                         type={p.type === 'number' || p.type === 'integer' ? 'number' : 'text'}
                         className="tt-input"
                         placeholder={`Enter ${p.name}...`}
                         value={params[p.name] || ''}
                         onChange={e => setParams({...params, [p.name]: e.target.value})}
                       />
                     )}
                   </div>
                 ))}
               </div>
             )}
             
             {hygieneParams.length > 0 && (
               <div className="mt-6 pt-4 border-t border-white/5">
                 <h5 className="flex items-center gap-1.5 text-[10px] text-accent/60 uppercase tracking-widest mb-3">
                   <Globe size={12} /> Elemm Hygiene Parameters (Protocol Native)
                 </h5>
                 <div className="tt-grid">
                   {hygieneParams.map(p => (
                     <div key={p.name} className="tt-field">
                       <label className="tt-label">
                         <span className="text-accent/80">{p.name}</span>
                         <span className="tt-type-badge" style={{background: 'rgba(255,255,255,0.05)'}}>{p.type}</span>
                       </label>
                       <input 
                         type={p.name === '_limit' ? 'number' : 'text'}
                         className="tt-input"
                         style={{borderColor: 'rgba(255,255,255,0.05)', backgroundColor: 'rgba(0,0,0,0.2)'}}
                         placeholder={`Enter ${p.name}...`}
                         value={params[p.name] || ''}
                         onChange={e => setParams({...params, [p.name]: e.target.value})}
                       />
                     </div>
                   ))}
                 </div>
               </div>
             )}
           </>
         )}

         {result && (
            <div className="tt-result-box animate-fade-in">
               <div className="tt-result-header">
                 <div className={`tt-result-dot ${result.error || result.status === 'error' ? 'error' : 'success'}`}></div>
                 <div className="tt-result-title">Execution Result</div>
               </div>
               <pre className="tt-result-pre custom-scrollbar">
                 {typeof result === 'object' ? JSON.stringify(result, null, 2) : result}
               </pre>
            </div>
         )}
      </div>
    </div>
  );
};

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
  const [copied, setCopied] = useState(false);

  const handleCopyMD = () => {
    let md = `# Landmark Spec: ${selectedLandmark}\n\n`;
    md += `**Description**: ${landmarkData?.description || "N/A"}\n\n`;
    if (landmarkData?.parameters?.length > 0) {
      md += `### Parameters\n\n| Name | Type | Required | Description |\n|---|---|---|---|\n`;
      landmarkData.parameters.forEach(p => {
        md += `| ${p.name} | ${p.type} | ${p.required ? '✅' : '❌'} | ${p.description || ""} |\n`;
      });
      md += `\n`;
    }
    if (landmarkData?.returns) {
      md += `**Returns**: ${landmarkData.returns}\n\n`;
    }
    if (signature) {
      md += `### Technical Signature\n\n\`\`\`typescript\n${signature}\n\`\`\`\n`;
    }

    navigator.clipboard.writeText(md).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (!selectedLandmark) {
    return (
      <div className="h-full flex flex-col items-center justify-center opacity-40">
        <Globe size={48} className="mb-4 text-accent" />
        <p className="text-lg font-bold">Satellite Link Ready</p>
        <p className="text-sm">Select a landmark from the topology to begin inspection.</p>
      </div>
    );
  }

  if (loading && selectedLandmark !== 'instructions') {
    return (
      <div className="h-full flex flex-col items-center justify-center">
        <RefreshCw size={48} className="spin text-accent mb-4" />
        <p className="animate-pulse font-mono text-xs tracking-widest">FETCHING SPECIFICATIONS...</p>
      </div>
    );
  }

  return (
    <div className="panel-content scrollable custom-scrollbar">
      {error && (
        <div className="m-6 p-4 bg-error/10 border border-error/20 rounded-lg flex items-start gap-3">
          <AlertCircle className="text-error mt-1" size={20} />
          <div>
            <div className="font-bold text-error">Inspection Error</div>
            <div className="text-sm opacity-80">{error}</div>
          </div>
        </div>
      )}

      <div className="p-8">
        {selectedLandmark === 'instructions' ? (
          <div className="space-y-8 animate-fade-in">
            <div className="console-call-card success expanded">
              <div className="card-header">
                <div className="header-left">
                  <BookOpen size={14} className="text-accent" />
                  <span className="action-title font-bold">PROTOCOL RULES</span>
                </div>
              </div>
              <div className="card-body bg-black/20">
                <div 
                  className="markdown-body text-sm leading-relaxed p-6 text-white/90"
                  dangerouslySetInnerHTML={{ __html: renderFormattedText(instructions || "No protocol rules defined in this manifest.") }}
                />
              </div>
            </div>

            {memoryBank && (
              <div className="console-call-card theme-discovery expanded">
                <div className="card-header">
                  <div className="header-left">
                    <Database size={14} className="text-purple-400" />
                    <span className="action-title font-bold">MEMORY BANK</span>
                  </div>
                </div>
                <div className="card-body bg-black/20">
                  <div 
                    className="p-6 font-mono text-sm text-purple-300/90 markdown-body"
                    dangerouslySetInnerHTML={{ __html: renderFormattedText(memoryBank) }}
                  />
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-8 animate-slide-up">
            <div className="mi-header-row">
              <div className="mi-header-left">
                <div className="mi-header-badge">
                  <div className="mi-header-pulse"></div>
                  <span>{landmarkData?.isTool ? 'EXECUTABLE TOOL' : 'AREA NAMESPACE'}</span>
                </div>
                <h2 className="mi-header-title glow-text">{selectedLandmark.split(/[:_]/).pop()}</h2>
                
                <div className="mi-header-desc">
                  {landmarkData?.description || "No specific architectural data available for this node."}
                </div>
              </div>

              <div className="mi-header-right">
                <div className="flex flex-col items-end gap-3">
                  <button 
                    className={`btn-action-pill ${copied ? 'success' : ''}`}
                    onClick={handleCopyMD}
                  >
                    {copied ? <Check size={14} /> : <Copy size={14} />}
                    <span>{copied ? 'SPEC COPIED' : 'COPY SPEC MD'}</span>
                  </button>
                  <div className="token-pills-modern">
                    <div className="t-pill in">
                      <span className="t-label">DEPTH</span>
                      <span className="t-value">{selectedLandmark.split(/[:_]/).length}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {landmarkData?.returns && (
              <div className="stat-pill-modern mb-6">
                <div className="flex items-center gap-3">
                  <ArrowRight size={14} className="text-pink-400" />
                  <span className="text-[10px] font-bold uppercase tracking-widest opacity-40">Expected Returns</span>
                </div>
                <span className="font-mono text-xs text-pink-300">{landmarkData.returns}</span>
              </div>
            )}

            {signature && (
              <div className="console-call-card theme-manifest expanded">
                <div className="card-header">
                  <div className="header-left">
                    <Cpu size={14} className="text-[#a855f7]" />
                    <span className="action-title font-bold">TECHNICAL MANIFEST</span>
                  </div>
                </div>
                <div className="card-body bg-black/40">
                  <div 
                    className="signature-content markdown-body p-6"
                    dangerouslySetInnerHTML={{ __html: renderFormattedText(signature) }}
                  />
                </div>
              </div>
            )}

            <ParameterDocumentation 
              parameters={landmarkData?.parameters || []} 
            />

            {landmarkData?.isTool && (
              <ToolTester 
                landmark={selectedLandmark} 
                parameters={landmarkData.parameters || []}
                onExecute={onExecute}
                executing={executing}
                result={executionResult}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default LandmarkDetails;
