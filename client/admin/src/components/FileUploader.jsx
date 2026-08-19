import { useRef, useState, useCallback } from 'react';

export default function FileUploader({ label, required, onFileSelect, file }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragIn = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  }, []);

  const handleDragOut = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile && droppedFile.name.endsWith('.csv')) {
      onFileSelect(droppedFile);
    }
  }, [onFileSelect]);

  const handleClick = () => {
    inputRef.current?.click();
  };

  const handleChange = (e) => {
    const selected = e.target.files?.[0];
    if (selected) onFileSelect(selected);
  };

  return (
    <div>
      <div className="flex items-center gap-sm mb-md" style={{ minHeight: 24 }}>
        <span style={{ fontWeight: 600, fontSize: '0.88rem' }}>{label}</span>
        {required && <span className="badge badge-warning">Required</span>}
        {!required && <span className="badge badge-info">Optional</span>}
      </div>
      <div
        className={`file-uploader${dragOver ? ' drag-over' : ''}`}
        onClick={handleClick}
        onDragOver={handleDrag}
        onDragEnter={handleDragIn}
        onDragLeave={handleDragOut}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          onChange={handleChange}
        />
        {file ? (
          <div className="file-info">
            <span>📄</span>
            <span>{file.name}</span>
            <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>
              ({(file.size / 1024).toFixed(1)} KB)
            </span>
          </div>
        ) : (
          <>
            <div className="upload-icon">📂</div>
            <div className="upload-text">
              Drag & drop a CSV here, or <strong>click to browse</strong>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
