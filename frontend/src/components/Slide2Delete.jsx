import React, { useState, useRef, useEffect } from 'react';
import { ChevronRight, Loader2 } from 'lucide-react';

const Slide2Delete = ({ onConfirm, onCancel, label = "Slide to delete" }) => {
  const [dragX, setDragX] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [timeLeft, setTimeLeft] = useState(3);
  const trackRef = useRef(null);
  const [maxDrag, setMaxDrag] = useState(210);

  useEffect(() => {
    if (trackRef.current) {
      const trackWidth = trackRef.current.clientWidth;
      const handleElement = trackRef.current.querySelector('.slide-handle');
      const handleWidth = handleElement ? handleElement.clientWidth : 38;
      const computedMax = trackWidth - handleWidth - 8;
      setMaxDrag(computedMax > 0 ? computedMax : 210);
    }
  }, []);

  const cancelRef = useRef(onCancel);
  const confirmRef = useRef(onConfirm);

  useEffect(() => {
    cancelRef.current = onCancel;
    confirmRef.current = onConfirm;
  }, [onCancel, onConfirm]);

  useEffect(() => {
    if (isConfirming) return;
    const timer = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          cancelRef.current();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [isConfirming]);

  const handleStart = (e) => {
    if (isConfirming) return;
    setIsDragging(true);
  };

  const handleMove = (e) => {
    if (!isDragging || isConfirming) return;
    
    const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
    const trackRect = trackRef.current.getBoundingClientRect();
    let newX = clientX - trackRect.left - 20;

    newX = Math.max(0, Math.min(newX, maxDrag));
    setDragX(newX);

    if (newX >= maxDrag) {
      setIsDragging(false);
      setIsConfirming(true);
      setTimeout(() => {
        confirmRef.current();
      }, 1000);
    }
  };

  const handleEnd = () => {
    if (dragX < maxDrag) {
      setDragX(0);
    }
    setIsDragging(false);
  };

  return (
    <div className="delete-overlay animate-fade-in" onMouseUp={handleEnd} onMouseLeave={handleEnd}>
      {isConfirming ? (
        <div className="deleting-text">
          <Loader2 size={20} className="spin" />
          <span>Deleting...</span>
        </div>
      ) : (
        <>
          <h4>Confirm Deletion</h4>
          <div 
            className="slide-track" 
            ref={trackRef}
            onMouseMove={handleMove}
            onTouchMove={handleMove}
          >
            <div className="slide-label">{label}</div>
            <div className="slide-progress" style={{ width: `${dragX + 20}px` }}></div>
            <div 
              className={`slide-handle ${isDragging ? 'dragging' : ''}`}
              style={{ transform: `translateX(${dragX}px)` }}
              onMouseDown={handleStart}
              onTouchStart={handleStart}
              onMouseUp={handleEnd}
              onTouchEnd={handleEnd}
            >
              <ChevronRight size={20} />
            </div>
          </div>
          <div className="cancel-timer">
            Auto-cancel in {timeLeft}s
          </div>
        </>
      )}
    </div>
  );
};

export default Slide2Delete;
