import { useEffect, useRef } from 'react';

export default function TerminalOutput({ logs }) {
  const bodyRef = useRef(null);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="terminal">
      <div className="terminal-header">
        <span className="terminal-dot red" />
        <span className="terminal-dot yellow" />
        <span className="terminal-dot green" />
        <span className="terminal-title">Pipeline Output</span>
      </div>
      <div className="terminal-body" ref={bodyRef}>
        {logs.length === 0 ? (
          <div className="terminal-line" style={{ color: 'var(--text-muted)' }}>
            <span className="prompt">$</span>Waiting for pipeline to start...
          </div>
        ) : (
          logs.map((line, i) => (
            <div key={i} className="terminal-line">
              <span className="prompt">›</span>{line}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
