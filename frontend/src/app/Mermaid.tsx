"use client";
import React, { useEffect, useRef, useState, useId } from 'react';
import mermaid from 'mermaid';
import { ZoomIn, ZoomOut, RefreshCcw } from 'lucide-react';

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
});

export default function Mermaid({ chart }: { chart: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartId = useId().replace(/:/g, '');
  const [scale, setScale] = useState(1);

  useEffect(() => {
    if (containerRef.current) {
      mermaid.render(`mermaid-${chartId}`, chart)
        .then(result => {
          if (containerRef.current) {
            containerRef.current.innerHTML = result.svg;
            // Force svg to be responsive but allow scaling
            const svg = containerRef.current.querySelector('svg');
            if (svg) {
              svg.style.maxWidth = '100%';
              svg.style.height = 'auto';
            }
          }
        })
        .catch(err => {
          console.error("Mermaid render error:", err);
          if (containerRef.current) {
             containerRef.current.innerHTML = `<p style="color:red">Mermaid Render Error</p><pre>${chart}</pre>`;
          }
        });
    }
  }, [chart]);

  return (
    <div style={{ position: 'relative', margin: '2rem 0', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', background: 'rgba(0,0,0,0.3)', overflow: 'hidden' }} className="mermaid-zoom-container">
      
      {/* Scrollable Container */}
      <div style={{ overflow: 'auto', padding: '2rem', minHeight: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div ref={containerRef} style={{ transform: `scale(${scale})`, transformOrigin: 'center center', transition: 'transform 0.2s ease-out' }} />
      </div>

      {/* Controls Float Bottom Right */}
      {/* html2pdf-ignore is a neat class to ignore these buttons while printing PDF */}
      <div data-html2canvas-ignore style={{ position: 'absolute', bottom: '1rem', right: '1rem', display: 'flex', gap: '0.5rem', background: 'rgba(0,0,0,0.6)', padding: '0.5rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', backdropFilter: 'blur(4px)', zIndex: 10 }}>
        <button onClick={() => setScale(s => Math.max(0.5, s - 0.2))} style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', padding: '0.25rem', display: 'flex', alignItems: 'center' }} title="Yakınlaştır (-)">
          <ZoomOut size={18} />
        </button>
        <button onClick={() => setScale(1)} style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', padding: '0.25rem', display: 'flex', alignItems: 'center' }} title="Sıfırla">
          <RefreshCcw size={16} />
        </button>
        <button onClick={() => setScale(s => Math.min(3, s + 0.2))} style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', padding: '0.25rem', display: 'flex', alignItems: 'center' }} title="Uzaklaştır (+)">
          <ZoomIn size={18} />
        </button>
      </div>
    </div>
  );
}
