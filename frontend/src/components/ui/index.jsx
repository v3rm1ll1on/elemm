import React from 'react';
import './UI.css';

export const Input = React.forwardRef(({ className = '', ...props }, ref) => {
  return (
    <input 
      ref={ref}
      className={`elemm-input ${className}`} 
      {...props} 
    />
  );
});
Input.displayName = 'Input';

export const Textarea = React.forwardRef(({ className = '', ...props }, ref) => {
  return (
    <textarea 
      ref={ref}
      className={`elemm-textarea ${className}`} 
      {...props} 
    />
  );
});
Textarea.displayName = 'Textarea';

export const Select = React.forwardRef(({ className = '', children, ...props }, ref) => {
  return (
    <select 
      ref={ref}
      className={`elemm-select ${className}`} 
      {...props}
    >
      {children}
    </select>
  );
});
Select.displayName = 'Select';

export const Button = React.forwardRef(({ className = '', variant = 'primary', children, ...props }, ref) => {
  const variantClass = variant ? `elemm-btn-${variant}` : '';
  return (
    <button 
      ref={ref}
      className={`elemm-btn ${variantClass} ${className}`} 
      {...props}
    >
      {children}
    </button>
  );
});
Button.displayName = 'Button';

export const FormGroup = ({ label, children, className = '' }) => {
  return (
    <div className={`elemm-form-group ${className}`}>
      {label && <label>{label}</label>}
      {children}
    </div>
  );
};

export const Slider = React.forwardRef(({ className = '', ...props }, ref) => {
  return (
    <input 
      type="range"
      ref={ref}
      className={`elemm-slider ${className}`} 
      {...props} 
    />
  );
});
Slider.displayName = 'Slider';

export const Switch = React.forwardRef(({ className = '', checked, onChange, ...props }, ref) => {
  return (
    <label className={`elemm-switch ${className}`}>
      <input 
        type="checkbox" 
        ref={ref}
        checked={checked} 
        onChange={onChange} 
        {...props} 
      />
      <span className="elemm-switch-slider"></span>
    </label>
  );
});
Switch.displayName = 'Switch';
