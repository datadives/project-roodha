/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: MachineLoadGauge.jsx
 * 
 * 1) Purpose: React component for rendering MachineLoadGauge UI elements.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import React from 'react';

/**
 * MachineLoadGauge - A high-contrast segmented gauge for monitoring production load.
 * @param {number} hours - Total hours of work assigned.
 * @param {boolean} isOverloaded - Whether the machine is flagged as overloaded.
 * @param {boolean} isEstimated - Whether the data is using fallbacks.
 */
export default function MachineLoadGauge({ hours = 0, isOverloaded = false, isEstimated = false }) {
  const roundedHours = Math.round(hours);
  const segments = Array.from({ length: Math.max(10, roundedHours) });

  return (
    <div className="space-y-3">
      <div className="flex items-end justify-between gap-2 px-1">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-slate-400">Backlog Pressure</p>
          <div className="mt-1 flex items-baseline gap-1">
            <span className={`text-2xl font-black font-mono ${isOverloaded ? 'text-[#FF6B00]' : 'text-orange-500'}`}>
              {hours.toFixed(1)}
            </span>
            <span className="text-xs font-bold text-slate-500 underline decoration-slate-700 decoration-2 underline-offset-4 font-mono">hrs</span>
          </div>
        </div>
        
        <div className="flex gap-2">
          {isEstimated && (
            <div className="flex items-center gap-1 rounded border border-orange-500/30 bg-orange-500/10 px-1.5 py-1 text-[9px] font-black uppercase tracking-wider text-orange-500 font-mono">
              <span className="h-1.5 w-1.5 rounded-full bg-orange-500" />
              ESTIMATED
            </div>
          )}
          {isOverloaded && (
            <div className="pulse-safety-orange rounded px-2 py-1 text-[10px] font-black uppercase tracking-widest text-[#0F172A] shadow-lg">
              OVERLOAD
            </div>
          )}
        </div>
      </div>

      <div className="flex h-10 w-full gap-1.5 rounded-xl border border-slate-700 bg-[#0F172A] p-1 shadow-inner">
        {segments.map((_, index) => {
          const isFilled = index < roundedHours;
          const isExcess = index >= 10;
          
          let bgColor = 'bg-slate-400/20';
          let borderStyle = 'border-slate-700';
          
          if (isFilled) {
            if (isExcess) {
              bgColor = 'pulse-safety-orange';
              borderStyle = 'border-[#FF6B00] border-2';
            } else {
              bgColor = 'bg-orange-500';
              borderStyle = isEstimated ? 'border-orange-400 border-b-2' : 'border-orange-600 border-b-4';
            }
          }

          return (
            <div
              key={index}
              className={`h-full flex-1 rounded-sm border-t border-x transition-all duration-500 ${bgColor} ${borderStyle} ${isFilled && !isExcess ? 'shadow-[0_0_15px_-5px_rgba(249,115,22,0.5)]' : ''}`}
            />
          );
        })}
      </div>
      
      <div className="flex justify-between px-1 text-[9px] font-bold text-slate-600 uppercase tracking-tighter">
        <span className="font-mono">0h</span>
        <span className="font-mono">5h</span>
        <span className="font-mono">10h (Cap)</span>
        {roundedHours > 10 && <span className="font-mono">{roundedHours}h</span>}
      </div>
    </div>
  );
}
