/*
 * Copyright (C) 2026 Marc Stöcker
 * Website: https://elemm.dev
 *
 * This program is licensed under the Business Source License 1.1 (BSL 1.1).
 * See the LICENSE file in the root directory for details.
 */

import React, { useState, useMemo, useEffect, useRef } from 'react';
import { 
  ChevronRight, Database, Copy, Check, Clock, Cpu, 
  ArrowRight, ShieldAlert, Layers, Terminal, Activity, 
  Play, HelpCircle, FileText, ArrowRightLeft, ArrowUpRight,
  TrendingUp, RefreshCw, GitPullRequest, ArrowDown,
  Search, X
} from 'lucide-react';
import './ObservabilityConsole.css';

// --- Sub-Component: Safe JSON Display with Highlighting ---
const SafeJsonDisplay = ({ data, fullSize }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  if (!data) return <span className="text-muted">N/A</span>;
  
  let displayString = '';
  let isJson = false;
  
  if (typeof data === 'string') {
    const cleaned = data.trim();
    if (cleaned.startsWith('{') || cleaned.startsWith('[')) {
      isJson = true;
      try {
        const parsed = JSON.parse(cleaned);
        displayString = JSON.stringify(parsed, null, 2);
      } catch (e) {
        // Truncated or incomplete JSON string - highlight it raw!
        displayString = cleaned;
      }
    } else {
      displayString = data;
    }
  } else if (typeof data === 'object') {
    isJson = true;
    try {
      displayString = JSON.stringify(data, null, 2);
    } catch (e) {
      displayString = String(data);
      isJson = false;
    }
  } else {
    displayString = String(data);
  }

  const handleCopy = (e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(displayString).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const highlightJson = (jsonStr) => {
    if (!jsonStr) return '';
    const htmlEscaped = jsonStr.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return htmlEscaped.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, (match) => {
      let cls = 'json-number';
      if (/^"/.test(match)) {
        if (/:$/.test(match)) cls = 'json-key';
        else cls = 'json-string';
      } else if (/true|false/.test(match)) cls = 'json-boolean';
      else if (/null/.test(match)) cls = 'json-null';
      return `<span class="${cls}">${match}</span>`;
    });
  };

  const renderFormattedText = (text) => {
    if (!text) return '';
    let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    // Highlight Code Blocks (``` ... ```)
    html = html.replace(/```(?:typescript|json|javascript)?([\s\S]*?)```/g, (match, code) => {
      return `<div class="embedded-code-block">${code.trim()}</div>`;
    });

    // Highlight Inline Headers (### ...)
    html = html.replace(/^(#{1,6})\s+(.*)$/gm, (match, hashes, content) => {
      const level = hashes.length;
      return `<div class="md-header h${level}">${content}</div>`;
    });

    // Highlight Bold (** ... **)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    return html;
  };

  return (
    <div className="json-container-modern-wrapper">
      <button className={`copy-json-btn ${copied ? 'copied' : ''}`} onClick={handleCopy} title="Copy to clipboard">
        {copied ? <Check size={11} /> : <Copy size={11} />}
        <span>{copied ? 'COPIED' : 'COPY'}</span>
      </button>

      <div className={`json-container-modern ${isExpanded ? 'expanded' : ''}`}>
        {isJson ? (
          <pre className="json-display" dangerouslySetInnerHTML={{ __html: highlightJson(displayString) }} />
        ) : (
          <div className="json-display markdown-body" dangerouslySetInnerHTML={{ __html: renderFormattedText(displayString) }} />
        )}
      </div>
      {(fullSize || displayString.length > 500) && (
        <button className="show-full-btn" onClick={() => setIsExpanded(!isExpanded)}>
          {isExpanded ? 'SHOW LESS' : fullSize ? `SHOW FULL (${(fullSize/1024).toFixed(1)} KB)` : 'SHOW FULL'}
        </button>
      )}
    </div>
  );
};

// --- Sub-Component: Tool Call Item in History ---
const CallItem = ({ group, children = [], depth = 0, config, onSelect }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [showPayload, setShowPayload] = useState(false);
  
  const mainCall = group.find(ev => (ev.action?.startsWith('CALL:') || ev.last_action?.startsWith('CALL:')));
  const mainReturn = group.find(ev => (ev.action?.startsWith('RETURN:') || ev.last_action?.startsWith('RETURN:')));
  const displayEvent = mainCall || mainReturn || group[0];
  
  const actionName = displayEvent?.action?.replace(/^(CALL:|RETURN:)\s*/, '') || 
                     displayEvent?.last_action?.replace(/^(CALL:|RETURN:)\s*/, '') || 'Unknown';

  const duration = mainReturn?.duration_ms || group.reduce((max, ev) => Math.max(max, ev.duration_ms || 0), 0);

  // Recursive Token Aggregation
  const getAggregatedTokens = (node) => {
    const nodeGroup = node.group || [];
    const nodeChildren = node.children || [];
    
    let ownIn = nodeGroup.reduce((sum, ev) => sum + (ev.tokens_in || 0), 0);
    let ownOut = nodeGroup.reduce((sum, ev) => sum + (ev.tokens_out || 0), 0);
    let ownCharsIn = nodeGroup.reduce((sum, ev) => sum + (ev.chars_in || 0), 0);
    let ownCharsOut = nodeGroup.reduce((sum, ev) => sum + (ev.chars_out || 0), 0);
    
    let totalIn = ownIn;
    let totalOut = ownOut;
    let totalCharsIn = ownCharsIn;
    let totalCharsOut = ownCharsOut;
    
    nodeChildren.forEach(child => {
      const childMetrics = getAggregatedTokens(child);
      totalIn += childMetrics.totalIn;
      totalOut += childMetrics.totalOut;
      totalCharsIn += childMetrics.totalCharsIn;
      totalCharsOut += childMetrics.totalCharsOut;
    });
    
    return { ownIn, ownOut, totalIn, totalOut, ownCharsIn, ownCharsOut, totalCharsIn, totalCharsOut };
  };

  const getToolTheme = (name) => {
    if (name.includes('execute_sequence')) return 'theme-sequence';
    if (name.includes('call_action')) return 'theme-action';
    if (name.includes('inspect') || name.includes('manifest')) return 'theme-discovery';
    return 'theme-default';
  };

  const toolTheme = getToolTheme(actionName);
  
  const formatActionTitle = (name) => {
    const match = name.match(/\(([^)]+)\)/);
    if (match) {
      const base = name.split('(')[0];
      return <>{base}(<strong>{match[1]}</strong>)</>;
    }
    return name;
  };

  const input = group.find(ev => ev.input !== undefined && ev.input !== null)?.input;
  const output = group.find(ev => ev.output !== undefined && ev.output !== null)?.output;
  const fullSize = mainReturn?.full_size || group.find(ev => ev.full_size)?.full_size;

  const { ownIn, ownOut, totalIn, totalOut, ownCharsIn, ownCharsOut, totalCharsIn, totalCharsOut } = getAggregatedTokens({ group, children });
  
  // Robust status aggregation for History Call Items
  const status = useMemo(() => {
    const rawOutputStr = output ? (typeof output === 'string' ? output : JSON.stringify(output)) : '';
    const hasOutputError = rawOutputStr && (
      rawOutputStr.includes('"status": "error"') || 
      rawOutputStr.includes('"status":"error"') || 
      rawOutputStr.includes('"_PROTOCOL_ERROR"')
    );
    if (hasOutputError) return 'error';
    return mainReturn?.status || (group.find(ev => ev.status === 'error') ? 'error' : 'success');
  }, [group, mainReturn, output]);

  const displayMode = config?.ui?.display_mode || 'tokens';

  const formatTraffic = (tokens, chars) => {
    const formatNum = (n) => n > 999 ? (n/1000).toFixed(1) + 'k' : n;
    if (displayMode === 'chars') return `${formatNum(chars)} ch`;
    if (displayMode === 'both') return `${formatNum(tokens)}t (${formatNum(chars)}c)`;
    return formatNum(tokens);
  };

  return (
    <div className={`call-tree-node depth-${depth} ${toolTheme}`}>
      <div className={`console-call-card ${status} ${isOpen ? 'expanded' : ''}`}>
        <div className="card-header" onClick={() => {
          const nextOpen = !isOpen;
          setIsOpen(nextOpen);
          if (nextOpen && children.length === 0) {
            setShowPayload(true);
          } else if (!nextOpen) {
            setShowPayload(false);
          }
        }}>
          <div className="header-left">
            <div className="status-indicator-dot"></div>
            <span className="time">{displayEvent?.timestamp ? new Date(displayEvent.timestamp * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) : '--:--:--'}</span>
            <span className="action-title">
              {depth > 0 && <span className="step-index-pill">{actionName.match(/Step (\d+):/)?.[1] || depth}</span>}
              {formatActionTitle(actionName.replace(/Step \d+: /, ''))}
            </span>
          </div>
          
          <div className="header-right">
            <div className="meta-group">
              {duration > 0 && <div className="duration-tag">{duration}ms</div>}
              {displayEvent?.request_id && (
                <button 
                  className="btn-inspect-micro" 
                  onClick={(e) => { e.stopPropagation(); onSelect(displayEvent.request_id); }}
                  title="Open in real-time Live Inspector"
                >
                  <ArrowUpRight size={12} />
                  <span>INSPECT</span>
                </button>
              )}
            </div>

            <div className="metrics-group">
              {children.length > 0 && (
                <button 
                  className={`payload-toggle ${showPayload ? 'active' : ''}`}
                  onClick={(e) => { e.stopPropagation(); setShowPayload(!showPayload); }}
                  title="Toggle Input/Output Data"
                >
                  <Database size={12} />
                  <span>DATA</span>
                </button>
              )}
              
              <div className="token-pills-modern">
                <div className="t-pill in" title={`Own: ${ownIn}t / ${ownCharsIn}c | Total: ${totalIn}t / ${totalCharsIn}c`}>
                  <span className="t-label">IN</span>
                  <span className="t-value">{formatTraffic(totalIn, totalCharsIn)}</span>
                </div>
                <div className="t-pill out" title={`Own: ${ownOut}t / ${ownCharsOut}c | Total: ${totalOut}t / ${totalCharsOut}c`}>
                  <span className="t-label">OUT</span>
                  <span className="t-value">{formatTraffic(totalOut, totalCharsOut)}</span>
                </div>
              </div>
              <span className={`status-badge-modern ${status}`}>{status}</span>
              <span className={`chevron-modern ${isOpen ? 'open' : ''}`}>
                <ChevronRight size={14} />
              </span>
            </div>
          </div>
        </div>

        {isOpen && (showPayload || children.length > 0) && (
          <div className="card-body">
            {children.length > 0 && (
              <div className="sequence-data-header">
                <button 
                  className={`sequence-data-toggle ${showPayload ? 'active' : ''}`}
                  onClick={(e) => { e.stopPropagation(); setShowPayload(!showPayload); }}
                >
                  <Database size={12} />
                  <span>{showPayload ? 'HIDE SEQUENCE JSON' : 'SHOW FULL SEQUENCE JSON'}</span>
                </button>
              </div>
            )}

            {showPayload && (
              <div className="payload-section animate-fade-in">
                <div className="payload-box">
                  <label>Arguments / Input <span className="step-duration">local: {formatTraffic(ownIn, ownCharsIn)}</span></label>
                  <div className="json-container-modern">
                    <SafeJsonDisplay data={input} />
                  </div>
                </div>
                <div className="payload-box">
                  <label>Result / Output <span className="step-duration">local: {formatTraffic(ownOut, ownCharsOut)}</span></label>
                  <div className="json-container-modern">
                    <SafeJsonDisplay data={output} fullSize={fullSize} />
                  </div>
                </div>
              </div>
            )}
            
            {children.length > 0 && (
              <div className="children-container">
                <div className="tree-line"></div>
                {children.map((child, idx) => (
                  <CallItem 
                    key={child.id || idx} 
                    group={child.group} 
                    children={child.children} 
                    depth={depth + 1}
                    config={config}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// --- Helper: Render Beautified Step/Sequence Errors ---
const renderErrorContent = (output) => {
  if (!output) return <p>The step execution returned an error. Check inputs or variables.</p>;
  
  let parsedOutput = null;
  let isJsonParseSuccess = false;

  if (typeof output === 'object') {
    parsedOutput = output;
    isJsonParseSuccess = true;
  } else if (typeof output === 'string') {
    try {
      const cleaned = output.trim();
      if (cleaned.startsWith('{') || cleaned.startsWith('[')) {
        parsedOutput = JSON.parse(cleaned);
        isJsonParseSuccess = true;
      }
    } catch (e) {
      isJsonParseSuccess = false;
    }
  }

  // Case 1: Successfully Parsed JSON Array
  if (isJsonParseSuccess && Array.isArray(parsedOutput)) {
    const failedSteps = parsedOutput.filter(step => 
      step.error || 
      step.result?.status === 'error' || 
      step.result?._PROTOCOL_ERROR
    );

    if (failedSteps.length > 0) {
      return (
        <div className="error-steps-list">
          {failedSteps.map((step, idx) => {
            const stepNum = step.step !== undefined ? step.step + 1 : idx + 1;
            const actionName = step.action || 'Unknown Action';
            const errMsg = step.error || step.result?.message || step.result?.error || JSON.stringify(step.result || step);
            const remedy = step.result?.remedy;

            return (
              <div key={idx} className="error-step-item">
                <div className="err-step-hdr">
                  <span className="err-step-badge">Step {stepNum}</span>
                  <strong className="err-step-action">{actionName}</strong>
                </div>
                <div className="err-step-msg">{errMsg}</div>
                {remedy && (
                  <div className="err-step-remedy animate-fade-in">
                    <strong>💡 Remedy:</strong> {remedy}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      );
    }
  }

  // Case 2: Successfully Parsed JSON Single Object
  if (isJsonParseSuccess && typeof parsedOutput === 'object' && parsedOutput !== null) {
    const errMsg = parsedOutput.error || parsedOutput.message || parsedOutput.result?.message || parsedOutput.result?.error;
    const remedy = parsedOutput.remedy || parsedOutput.result?.remedy;

    if (errMsg) {
      return (
        <div className="error-single-item">
          <div className="err-step-msg">{errMsg}</div>
          {remedy && (
            <div className="err-step-remedy animate-fade-in">
              <strong>💡 Remedy:</strong> {remedy}
            </div>
          )}
        </div>
      );
    }
  }

  // Case 3: Robust Fallback for Truncated JSON Strings (via regular expressions)
  if (typeof output === 'string') {
    const trimmed = output.trim();
    
    // A. Parse truncated sequence step arrays via regex splitting
    if (trimmed.includes('"step":') || trimmed.includes('"stepIndex"')) {
      const parts = trimmed.split(/\{\s*"step":\s*/);
      const regexResults = [];

      parts.forEach((part, idx) => {
        if (idx === 0) return; // Skip everything before the first "step"
        
        const stepNumMatch = part.match(/^(\d+)/);
        const stepNum = stepNumMatch ? parseInt(stepNumMatch[1]) + 1 : idx;

        const hasErr = part.includes('"status": "error"') || 
                        part.includes('"status":"error"') || 
                        part.includes('"_PROTOCOL_ERROR"') || 
                        part.includes('"status": "fail"') || 
                        part.includes('"status":"fail"');

        if (hasErr) {
          const actionMatch = part.match(/"action":\s*"([^"]+)"/);
          const msgMatch = part.match(/"message":\s*"([^"]+)"/) || part.match(/"error":\s*"([^"]+)"/);
          const remedyMatch = part.match(/"remedy":\s*"([^"]+)"/);

          regexResults.push({
            step: stepNum,
            action: actionMatch ? actionMatch[1] : 'Unknown Action',
            message: msgMatch ? msgMatch[1] : 'Execution failed.',
            remedy: remedyMatch ? remedyMatch[1] : null
          });
        }
      });

      if (regexResults.length > 0) {
        return (
          <div className="error-steps-list">
            {regexResults.map((step, idx) => (
              <div key={idx} className="error-step-item">
                <div className="err-step-hdr">
                  <span className="err-step-badge">Step {step.step}</span>
                  <strong className="err-step-action">{step.action}</strong>
                </div>
                <div className="err-step-msg">{step.message}</div>
                {step.remedy && (
                  <div className="err-step-remedy animate-fade-in">
                    <strong>💡 Remedy:</strong> {step.remedy}
                  </div>
                )}
              </div>
            ))}
          </div>
        );
      }
    }

    // B. Parse truncated single object errors via regex
    const msgMatch = trimmed.match(/"message":\s*"([^"]+)"/) || trimmed.match(/"error":\s*"([^"]+)"/);
    const remedyMatch = trimmed.match(/"remedy":\s*"([^"]+)"/);

    if (msgMatch) {
      return (
        <div className="error-single-item">
          <div className="err-step-msg">{msgMatch[1]}</div>
          {remedyMatch && (
            <div className="err-step-remedy animate-fade-in">
              <strong>💡 Remedy:</strong> {remedyMatch[1]}
            </div>
          )}
        </div>
      );
    }
  }

  // Ultimate Fallback: Render original plain text / preformatted raw output
  return <pre className="err-raw-pre">{typeof output === 'string' ? output : JSON.stringify(output, null, 2)}</pre>;
};

// --- Sub-Component: Interactive Live Trace Inspector ---
const ActiveTraceInspector = ({ activeItem, config, onBack }) => {
  const [activeStepIndex, setActiveStepIndex] = useState(null); // null = Main Call

  const mainCall = activeItem.group.find(ev => (ev.action?.startsWith('CALL:') || ev.last_action?.startsWith('CALL:')));
  const mainReturn = activeItem.group.find(ev => (ev.action?.startsWith('RETURN:') || ev.last_action?.startsWith('RETURN:')));
  const rootEvent = mainCall || mainReturn || activeItem.group[0];
  
  const fullActionName = rootEvent?.action?.replace(/^(CALL:|RETURN:)\s*/, '') || 
                         rootEvent?.last_action?.replace(/^(CALL:|RETURN:)\s*/, '') || 'Unknown';
  
  const cleanToolName = (name) => {
    return name.replace(/Step \d+: /, '');
  };

  const getToolThemeClass = (name) => {
    if (name.includes('execute_sequence')) return 'sequence';
    if (name.includes('call_action')) return 'action';
    if (name.includes('inspect') || name.includes('manifest')) return 'discovery';
    return 'default';
  };

  const themeClass = getToolThemeClass(fullActionName);

  const rawInput = activeItem.group.find(ev => ev.input !== undefined && ev.input !== null)?.input;
  const rawOutput = activeItem.group.find(ev => ev.output !== undefined && ev.output !== null)?.output;

  const parsedSteps = useMemo(() => {
    let inputSteps = [];
    if (rawInput) {
      if (typeof rawInput === 'object') {
        inputSteps = rawInput.steps || rawInput.actions || [];
      } else if (typeof rawInput === 'string') {
        try {
          const parsed = JSON.parse(rawInput);
          inputSteps = parsed.steps || parsed.actions || [];
        } catch (e) {}
      }
    }

    let outputSteps = [];
    if (rawOutput) {
      if (Array.isArray(rawOutput)) {
        outputSteps = rawOutput;
      } else if (typeof rawOutput === 'object') {
        outputSteps = rawOutput.steps || rawOutput.results || [];
      } else if (typeof rawOutput === 'string') {
        try {
          const parsed = JSON.parse(rawOutput.trim());
          if (Array.isArray(parsed)) {
            outputSteps = parsed;
          } else if (typeof parsed === 'object') {
            outputSteps = parsed.steps || parsed.results || [];
          }
        } catch (e) {}
      }
    }

    if (inputSteps.length === 0 && outputSteps.length === 0 && activeItem.children && activeItem.children.length > 0) {
      return activeItem.children.map((child, idx) => {
        const childCall = child.group.find(ev => ev.action?.startsWith('CALL:') || ev.last_action?.startsWith('CALL:'));
        const childReturn = child.group.find(ev => ev.action?.startsWith('RETURN:') || ev.last_action?.startsWith('RETURN:'));
        return {
          stepIndex: idx,
          action: childCall?.action?.replace(/^(CALL:|RETURN:)\s*/, '') || `Step ${idx + 1}`,
          alias: childCall?.alias || null,
          status: childReturn?.status || 'success',
          duration_ms: childReturn?.duration_ms || 0,
          input: child.group.find(ev => ev.input !== undefined && ev.input !== null)?.input,
          output: child.group.find(ev => ev.output !== undefined && ev.output !== null)?.output,
          isVirtual: false
        };
      });
    }

    const maxSteps = Math.max(inputSteps.length, outputSteps.length);
    const combined = [];

    for (let i = 0; i < maxSteps; i++) {
      const inp = inputSteps[i] || {};
      const outp = outputSteps.find(o => o.step === i) || outputSteps[i] || {};

      let parsedStatus = outp.status || 'success';
      // Detect error inside nested step result structure
      if (outp.error || outp.result?.status === 'error' || outp.result?._PROTOCOL_ERROR || outp.result?.status === 'fail') {
        parsedStatus = 'error';
      }

      combined.push({
        stepIndex: i,
        action: outp.action || inp.action || `Step ${i + 1}`,
        alias: outp.alias || inp.alias || null,
        status: parsedStatus,
        duration_ms: outp.duration_ms || 0,
        input: inp.parameters || inp.args || inp,
        output: outp.result || outp.output || outp.error || outp,
        isVirtual: true
      });
    }

    return combined;
  }, [rawInput, rawOutput, activeItem]);

  const duration = mainReturn?.duration_ms || activeItem.group.reduce((max, ev) => Math.max(max, ev.duration_ms || 0), 0);
  
  // Intelligent Sequence & Tool Status Resolution: If root output has an error or any step failed
  const status = useMemo(() => {
    // 1. Scan rawOutput for nested in-payload errors (e.g. status: error or _PROTOCOL_ERROR)
    let hasRootError = false;
    if (rawOutput) {
      const outputStr = typeof rawOutput === 'string' ? rawOutput : JSON.stringify(rawOutput);
      const lowerStr = outputStr.toLowerCase();
      if (lowerStr.includes('"status": "error"') || 
          lowerStr.includes('"status":"error"') || 
          lowerStr.includes('"status": "fail"') || 
          lowerStr.includes('"status":"fail"') || 
          lowerStr.includes('"_protocol_error"')) {
        hasRootError = true;
      }
    }

    // 2. Scan parsed steps for errors
    const hasStepError = parsedSteps.some(step => step.status === 'error');

    if (hasRootError || hasStepError) return 'error';
    
    return mainReturn?.status || (activeItem.group.find(ev => ev.status === 'error') ? 'error' : 'success');
  }, [parsedSteps, rawOutput, mainReturn, activeItem]);

  const displayMode = config?.ui?.display_mode || 'tokens';
  const getTotals = (node) => {
    let ownIn = node.group.reduce((sum, ev) => sum + (ev.tokens_in || 0), 0);
    let ownOut = node.group.reduce((sum, ev) => sum + (ev.tokens_out || 0), 0);
    let ownCharsIn = node.group.reduce((sum, ev) => sum + (ev.chars_in || 0), 0);
    let ownCharsOut = node.group.reduce((sum, ev) => sum + (ev.chars_out || 0), 0);
    
    let totalIn = ownIn;
    let totalOut = ownOut;
    let totalCharsIn = ownCharsIn;
    let totalCharsOut = ownCharsOut;
    
    (node.children || []).forEach(child => {
      const childTotals = getTotals(child);
      totalIn += childTotals.totalIn;
      totalOut += childTotals.totalOut;
      totalCharsIn += childTotals.totalCharsIn;
      totalCharsOut += childTotals.totalCharsOut;
    });
    
    return { ownIn, ownOut, totalIn, totalOut, ownCharsIn, ownCharsOut, totalCharsIn, totalCharsOut };
  };

  const { ownIn, ownOut, totalIn, totalOut, ownCharsIn, ownCharsOut, totalCharsIn, totalCharsOut } = getTotals(activeItem);

  const formatTrafficValue = (tokens, chars) => {
    if (displayMode === 'chars') return `${chars.toLocaleString()} chars`;
    if (displayMode === 'both') return `${tokens.toLocaleString()}t / ${chars.toLocaleString()}c`;
    return `${tokens.toLocaleString()} tokens`;
  };

  const currentSelectedData = useMemo(() => {
    if (activeStepIndex === null) {
      return {
        input: rawInput,
        output: rawOutput,
        status: status,
        duration: duration,
        targetLabel: 'ROOT: Full Sequence Scope'
      };
    }
    
    const step = parsedSteps[activeStepIndex];
    return {
      input: step?.input,
      output: step?.output,
      status: step?.status || 'success',
      duration: step?.duration_ms || 0,
      targetLabel: `STEP ${activeStepIndex + 1}: ${cleanToolName(step?.action || '')}`
    };
  }, [activeStepIndex, parsedSteps, rawInput, rawOutput, status, duration]);

  const hasSteps = parsedSteps.length > 0;

  const detectPiping = (inputObj) => {
    if (!inputObj) return null;
    const str = typeof inputObj === 'string' ? inputObj : JSON.stringify(inputObj);
    const matches = str.match(/\$step\d+(?:\[\d+\])?(?:\.[a-zA-Z0-9_]+)*/g);
    return matches ? Array.from(new Set(matches)) : null;
  };
  
  const activePipes = detectPiping(currentSelectedData.input);

  const pipingConnections = useMemo(() => {
    const connections = [];
    parsedSteps.forEach((step, idx) => {
      if (!step.input) return;
      const inputStr = JSON.stringify(step.input);
      
      parsedSteps.forEach((prevStep, prevIdx) => {
        if (prevIdx >= idx) return;
        const prevAlias = prevStep.alias;
        
        const isReferencingAlias = prevAlias && (inputStr.includes(`$${prevAlias}`) || inputStr.includes(`$${prevAlias}[`));
        const isReferencingStepIndex = inputStr.includes(`$step${prevIdx}`) || inputStr.includes(`$step${prevIdx}[`);

        if (isReferencingAlias || isReferencingStepIndex) {
          connections.push({
            from: prevIdx,
            fromName: prevAlias || `step${prevIdx}`,
            to: idx,
            toName: step.action.split('(')[0],
            variable: prevAlias ? `$${prevAlias}` : `$step${prevIdx}`
          });
        }
      });
    });
    return connections;
  }, [parsedSteps]);

  const maxStepDuration = useMemo(() => {
    return Math.max(...parsedSteps.map(s => s.duration_ms || 0), 1);
  }, [parsedSteps]);

  return (
    <div className="active-inspector-board animate-fade-in">
      {/* 1. Header Details */}
      <div className={`inspector-title-card theme-${themeClass}`}>
        <div className="title-left">
          <div className={`status-glow-dot ${status}`}></div>
          <span className="timestamp">{rootEvent?.timestamp ? new Date(rootEvent.timestamp * 1000).toLocaleTimeString() : '--:--:--'}</span>
          <h2 className="title-text">{cleanToolName(fullActionName)}</h2>
        </div>
        <div className="title-right">
          <span className={`status-badge-lg ${status}`}>{status.toUpperCase()}</span>
        </div>
      </div>

      {/* 2. Diagnostic Metrics Card Grid */}
      <div className="diagnostic-metrics-grid">
        <div className="metric-card glass-morphism">
          <div className="card-lbl"><Clock size={13} /> DURATION</div>
          <div className="card-val text-accent">{duration} <span className="val-suffix">ms</span></div>
          <div className="card-sub">{hasSteps ? `${parsedSteps.length} Steps Parsed` : 'Direct Execution'}</div>
        </div>
        <div className="metric-card glass-morphism">
          <div className="card-lbl"><ArrowRightLeft size={13} /> INPUT TRAFFIC</div>
          <div className="card-val text-info">{totalIn} <span className="val-suffix">tokens</span></div>
          <div className="card-sub">({totalCharsIn.toLocaleString()} chars raw)</div>
        </div>
        <div className="metric-card glass-morphism">
          <div className="card-lbl"><ArrowRightLeft size={13} /> OUTPUT TRAFFIC</div>
          <div className="card-val text-indigo">{totalOut} <span className="val-suffix">tokens</span></div>
          <div className="card-sub">({totalCharsOut.toLocaleString()} chars raw)</div>
        </div>
        <div className="metric-card glass-morphism">
          <div className="card-lbl"><Cpu size={13} /> CONNECTION TYPE</div>
          <div className="card-val text-success">
            {fullActionName.includes('execute_sequence') ? 'SEQUENCE' : 'NATIVE'}
          </div>
          <div className="card-sub" title={rootEvent?.request_id}>ID: {rootEvent?.request_id ? rootEvent.request_id.substring(0, 12) : 'N/A'}</div>
        </div>
      </div>

      {/* 3. Sequence Dependency and Piping Flow Map */}
      {hasSteps && pipingConnections.length > 0 && (
        <div className="pipeline-piping-flow-card glass-morphism animate-fade-in">
          <div className="flow-card-header">
            <GitPullRequest size={14} className="text-info" />
            <h3>Sequence Data Piping Map</h3>
          </div>
          <div className="piping-connections-grid">
            {pipingConnections.map((conn, cIdx) => (
              <div key={cIdx} className="piping-flow-line">
                <span className="piping-source" onClick={() => setActiveStepIndex(conn.from)}>
                  Step {conn.from + 1} (<code>{conn.fromName}</code>)
                </span>
                <span className="piping-arrow">
                  <span className="arrow-line"></span>
                  <span className="arrow-badge">{conn.variable}</span>
                  <ArrowRight size={14} className="text-info arrow-head" />
                </span>
                <span className="piping-target" onClick={() => setActiveStepIndex(conn.to)}>
                  Step {conn.to + 1} (<code>{conn.toName}</code>)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Dynamic Pipeline Timeline */}
      {hasSteps && (
        <div className="pipeline-flow-card glass-morphism">
          <div className="flow-card-header">
            <Layers size={14} className="text-accent" />
            <h3>Sequence Execution Pipeline</h3>
            <span className="flow-hint">Click a node to inspect and drill-down into step payloads</span>
          </div>

          <div className="pipeline-steps-wrapper">
            {/* Step 0: Root Main Sequence */}
            <div 
              className={`pipeline-step-node ${activeStepIndex === null ? 'active' : ''}`}
              onClick={() => setActiveStepIndex(null)}
            >
              <div className="step-circle main">
                <Terminal size={14} />
              </div>
              <div className="step-details">
                <span className="step-num">ROOT</span>
                <span className="step-name">Full Sequence Scope</span>
              </div>
              <div className="step-meta">
                <span className="step-dur">{duration}ms</span>
              </div>
            </div>

            {/* Sub Steps */}
            {parsedSteps.map((step, idx) => {
              const stepNameLabel = cleanToolName(step.action).split('(')[0];
              const stepStatus = step.status || 'success';
              const stepDuration = step.duration_ms || 0;
              const percentWidth = Math.min((stepDuration / maxStepDuration) * 100, 100);

              return (
                <div 
                  key={idx}
                  className={`pipeline-step-node ${activeStepIndex === idx ? 'active' : ''} ${stepStatus}`}
                  onClick={() => setActiveStepIndex(idx)}
                >
                  <div className="step-connector-line"></div>
                  <div className={`step-circle ${stepStatus}`}>
                    {idx + 1}
                  </div>
                  <div className="step-details">
                    <span className="step-num">
                      STEP {idx + 1} {step.alias && <span className="step-alias-tag">alias: {step.alias}</span>}
                    </span>
                    <span className="step-name" title={cleanToolName(step.action)}>{stepNameLabel}</span>
                    <div className="step-performance-track">
                      <div 
                        className={`step-performance-bar ${stepStatus}`} 
                        style={{ width: `${percentWidth}%` }}
                      ></div>
                    </div>
                  </div>
                  <div className="step-meta">
                    <span className="step-dur">{stepDuration}ms</span>
                    <span className={`step-badge-status ${stepStatus}`}></span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 5. Active Node Detail Board */}
      <div className="inspector-payload-compare glass-morphism">
        <div className="compare-header-bar">
          <div className="compare-info-group">
            <span className="compare-target">{currentSelectedData.targetLabel}</span>
            {currentSelectedData.duration > 0 && <span className="compare-dur">{currentSelectedData.duration}ms</span>}
            <span className={`compare-status-badge ${currentSelectedData.status}`}>{currentSelectedData.status.toUpperCase()}</span>
          </div>

          {activePipes && (
            <div className="piping-alert-indicator animate-pulse" title={`Uses values from: ${activePipes.join(', ')}`}>
              <ArrowRight size={12} />
              <span>PIPED INPUT DATA</span>
            </div>
          )}
        </div>

        {currentSelectedData.status === 'error' && (
          <div className="critical-error-banner animate-fade-in">
            <ShieldAlert size={20} />
            <div className="err-details">
              <strong>Step Execution Failure:</strong>
              {renderErrorContent(currentSelectedData.output)}
            </div>
          </div>
        )}

        <div className="compare-grid">
          <div className="compare-panel">
            <label className="compare-label">
              <span>Arguments / Input Payload</span>
            </label>
            <div className="compare-payload-body">
              <SafeJsonDisplay data={currentSelectedData.input} />
            </div>
          </div>

          <div className="compare-panel">
            <label className="compare-label">
              <span>Result / Output Response</span>
            </label>
            <div className="compare-payload-body">
              <SafeJsonDisplay data={currentSelectedData.output} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// --- Main Console Component ---
const ObservabilityConsole = ({ history, trace, selectedSessionId, config }) => {
  const [activeTab, setActiveTab] = useState('inspector'); // 'inspector' or 'history'
  const [selectedRequestId, setSelectedRequestId] = useState(null);
  
  // Search & Filter states for Live Activity panel
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // 'all' | 'success' | 'error' | 'pending'
  
  const scrollRef = useRef(null);

  // Grouping Logic for History (Enhanced with Recursive Tree Support)
  const groupedHistory = useMemo(() => {
    if (!history || history.length === 0) return [];
    
    const nodesMap = new Map();
    const rootNodes = [];

    history.forEach(ev => {
      if (!ev.request_id) return;
      if (!nodesMap.has(ev.request_id)) {
        nodesMap.set(ev.request_id, { id: ev.request_id, group: [], children: [] });
      }
      nodesMap.get(ev.request_id).group.push(ev);
    });

    nodesMap.forEach(node => {
      const parentId = node.group.find(ev => ev.parent_request_id)?.parent_request_id;
      if (parentId && nodesMap.has(parentId) && parentId !== node.id) {
        nodesMap.get(parentId).children.push(node);
      } else if (!parentId) {
        rootNodes.push(node);
      } else {
        rootNodes.push(node);
      }
    });

    return rootNodes.sort((a, b) => {
      const timeA = a.group[0]?.timestamp || 0;
      const timeB = b.group[0]?.timestamp || 0;
      return timeB - timeA;
    });
  }, [history]);

  // Combined and De-duplicated Live Activity Feed (History + Live Trace Stream)
  const liveFeed = useMemo(() => {
    const allEvents = [];
    
    if (history) {
      history.forEach(ev => allEvents.push(ev));
    }
    if (trace) {
      trace.forEach(ev => allEvents.push(ev));
    }

    const filteredEvents = allEvents.filter(ev => selectedSessionId === 'global' || ev.session_id === selectedSessionId);

    // 1. Group all events by request_id for robust state compilation
    const groupsMap = new Map();
    filteredEvents.forEach(ev => {
      if (!ev.request_id) return;
      if (!groupsMap.has(ev.request_id)) {
        groupsMap.set(ev.request_id, []);
      }
      groupsMap.get(ev.request_id).push(ev);
    });

    const resultFeed = [];

    // 2. Mathematically evaluate each group's lifecycle status
    groupsMap.forEach((events, reqId) => {
      // Robust error evaluation in nested sub-steps of sequence results
      const hasError = events.some(ev => {
        if (ev.status === 'error' || ev.error !== undefined) return true;
        if (ev.output) {
          const outputStr = typeof ev.output === 'string' ? ev.output : JSON.stringify(ev.output);
          const lowerStr = outputStr.toLowerCase();
          if (lowerStr.includes('"status": "error"') || 
              lowerStr.includes('"status":"error"') || 
              lowerStr.includes('"status": "fail"') || 
              lowerStr.includes('"status":"fail"') || 
              lowerStr.includes('"error":') || 
              lowerStr.includes('"_protocol_error"')) {
            return true;
          }
        }
        return false;
      });
      
      const hasReturn = events.some(ev => 
        ev.action?.startsWith('RETURN:') || 
        ev.last_action?.startsWith('RETURN:') || 
        ev.output !== undefined || 
        ev.status === 'success'
      );

      // Final status is strictly compiled: error > success > pending
      let status = 'pending';
      if (hasError) {
        status = 'error';
      } else if (hasReturn) {
        status = 'success';
      }

      // Sort chronological to fetch the latest state details
      const sortedEvents = [...events].sort((a, b) => b.timestamp - a.timestamp);
      const latestEvent = sortedEvents[0];
      
      // Calculate duration from any valid event in the group
      const durationEvent = events.find(ev => ev.duration_ms !== undefined && ev.duration_ms > 0);
      const duration = durationEvent ? durationEvent.duration_ms : 0;

      // Extract high-level action name from CALL event to avoid raw RETURN prefixes
      const callEvent = events.find(ev => ev.action?.startsWith('CALL:') || ev.last_action?.startsWith('CALL:'));
      const rawAction = callEvent?.action || callEvent?.last_action || latestEvent.action || latestEvent.last_action || 'Unknown';
      const cleanAction = rawAction.replace(/^(CALL:|RETURN:)\s*/, '');

      resultFeed.push({
        request_id: reqId,
        timestamp: latestEvent.timestamp,
        last_action: cleanAction,
        duration_ms: duration,
        status: status,
        session_id: latestEvent.session_id
      });
    });

    // 3. Sort descending by timestamp and slice to feed buffer
    return resultFeed
      .sort((a, b) => b.timestamp - a.timestamp)
      .slice(0, 100);
  }, [trace, history, selectedSessionId]);

  // Filtered live feed based on user search and status toggles
  const filteredFeed = useMemo(() => {
    return liveFeed.filter(item => {
      const matchesSearch = item.last_action.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' || item.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [liveFeed, searchTerm, statusFilter]);

  // Auto-select the latest request_id when new traces stream in
  useEffect(() => {
    if (filteredFeed.length > 0 && !selectedRequestId) {
      const latestWithId = filteredFeed.find(ev => ev.request_id);
      if (latestWithId) {
        setSelectedRequestId(latestWithId.request_id);
      }
    }
  }, [filteredFeed, selectedRequestId]);

  // Auto-scroll trace container
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [trace]);

  // Find active node based on selectedRequestId
  const activeInspectorItem = useMemo(() => {
    if (!selectedRequestId) return null;
    
    const findInTree = (nodes) => {
      for (const node of nodes) {
        if (node.id === selectedRequestId) return node;
        if (node.children && node.children.length > 0) {
          const found = findInTree(node.children);
          if (found) return found;
        }
      }
      return null;
    };
    
    const foundNode = findInTree(groupedHistory);
    if (foundNode) return foundNode;

    const traceEvent = liveFeed.find(ev => ev.request_id === selectedRequestId);
    if (traceEvent) {
      const matchingHistory = (history || []).filter(ev => ev.request_id === selectedRequestId);
      const matchingTrace = (trace || []).filter(ev => ev.request_id === selectedRequestId);
      const combinedGroup = [...matchingHistory, ...matchingTrace];
      
      return {
        id: selectedRequestId,
        group: combinedGroup.length > 0 ? combinedGroup : [traceEvent],
        children: []
      };
    }

    return null;
  }, [selectedRequestId, groupedHistory, liveFeed, history, trace]);

  const handleSelectRequest = (reqId) => {
    setSelectedRequestId(reqId);
    setActiveTab('inspector');
  };

  return (
    <div className="obs-console-wrapper">
      {/* LEFT: Interactive Live Activity Panel with Search and Filters */}
      <div className="console-panel stream-panel">
        <div className="panel-header">
          <div className="panel-title-with-icon">
            <Activity size={16} className="text-accent animate-pulse" />
            <h3>Live Activity</h3>
          </div>
          <span className="live-indicator">ACTIVE</span>
        </div>
        
        {/* Search Field */}
        <div className="stream-search-container">
          <Search size={14} className="search-icon" />
          <input 
            type="text" 
            placeholder="Search active tools..." 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="stream-search-input"
          />
          {searchTerm && (
            <button className="search-clear-btn" onClick={() => setSearchTerm('')}>
              <X size={12} />
            </button>
          )}
        </div>

        {/* Status Filter Pills */}
        <div className="stream-filter-bar">
          <button 
            className={`filter-pill ${statusFilter === 'all' ? 'active' : ''}`}
            onClick={() => setStatusFilter('all')}
          >
            All
          </button>
          <button 
            className={`filter-pill success ${statusFilter === 'success' ? 'active' : ''}`}
            onClick={() => setStatusFilter('success')}
          >
            <span className="status-dot success"></span> Success
          </button>
          <button 
            className={`filter-pill error ${statusFilter === 'error' ? 'active' : ''}`}
            onClick={() => setStatusFilter('error')}
          >
            <span className="status-dot error"></span> Errors
          </button>
          <button 
            className={`filter-pill pending ${statusFilter === 'pending' ? 'active' : ''}`}
            onClick={() => setStatusFilter('pending')}
          >
            <span className="status-dot pending"></span> Pending
          </button>
        </div>
        
        <div className="panel-content scrollable stream-scroll-container" ref={scrollRef}>
          {filteredFeed.length > 0 ? filteredFeed.map((ev, i) => {
            const isReturn = ev.status !== 'pending';
            const actionName = ev.last_action.replace(/^(CALL:|RETURN:)\s*/, '') || 'Processing...';
            const reqId = ev.request_id;
            const isSelected = reqId && selectedRequestId === reqId;
            const status = ev.status;

            return (
              <div 
                key={i} 
                className={`stream-item clickable ${isSelected ? 'active-inspect' : ''} ${status}`}
                onClick={() => reqId && handleSelectRequest(reqId)}
                title={reqId ? "Click to inspect this active request" : ""}
              >
                <div className="stream-time">
                  {new Date(ev.timestamp * 1000).toLocaleTimeString([], {hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit'})}
                </div>
                <div className="stream-content">
                  <span className="label" title={actionName}>{actionName.split('(')[0]}</span>
                  <div className="stream-badges">
                    {ev.duration_ms > 0 && <span className="dur-badge">{ev.duration_ms}ms</span>}
                    <span className={`status-indicator ${status}`}>{isReturn ? '✓' : '...'}</span>
                  </div>
                </div>
              </div>
            );
          }) : <div className="empty-state">No matching protocol events.</div>}
        </div>
      </div>

      {/* RIGHT: Workspace Panel with Tabs */}
      <div className="console-panel workspace-panel">
        <div className="panel-header flex-header">
          <div className="tab-control-group">
            <button 
              className={`console-tab-btn ${activeTab === 'inspector' ? 'active' : ''}`}
              onClick={() => setActiveTab('inspector')}
            >
              <Cpu size={14} />
              <span>Live Inspector</span>
            </button>
            <button 
              className={`console-tab-btn ${activeTab === 'history' ? 'active' : ''}`}
              onClick={() => setActiveTab('history')}
            >
              <FileText size={14} />
              <span>Full History</span>
            </button>
          </div>
          
          <div className="panel-meta-right">
            <span className="count-badge">{groupedHistory.length} Recorded Sessions</span>
          </div>
        </div>

        <div className="panel-content scrollable workspace-scroll-container">
          {activeTab === 'inspector' ? (
            activeInspectorItem ? (
              <ActiveTraceInspector 
                activeItem={activeInspectorItem} 
                config={config} 
                onBack={() => setActiveTab('history')}
              />
            ) : (
              <div className="inspector-empty-welcome">
                <HelpCircle size={44} className="welcome-icon text-accent animate-bounce" />
                <h3>No Request Selected</h3>
                <p>Select any active request from the <strong>Live Activity</strong> panel on the left or double click a session in the <strong>Full History</strong> tab to inspect arguments, return payloads, step execution pipelines, and diagnostics in real time.</p>
              </div>
            )
          ) : (
            <div className="history-timeline-list">
              {groupedHistory.length > 0 ? groupedHistory.map((item, i) => (
                <CallItem 
                  key={item.id || i} 
                  group={item.group} 
                  children={item.children} 
                  depth={0} 
                  config={config}
                  onSelect={handleSelectRequest}
                />
              )) : <div className="empty-state">No calls recorded.</div>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ObservabilityConsole;
