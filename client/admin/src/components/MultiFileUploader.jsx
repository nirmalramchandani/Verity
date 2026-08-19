import { useRef, useState, useCallback } from 'react';

export default function MultiFileUploader({ label, required, files, onFilesChange, accept = '.csv' }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [dragIdx, setDragIdx] = useState(null);
  const [overIdx, setOverIdx] = useState(null);

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
    const droppedFiles = Array.from(e.dataTransfer.files || []);
    const csvFiles = droppedFiles.filter((f) => f.name.endsWith('.csv'));
    if (csvFiles.length > 0) {
      onFilesChange([...files, ...csvFiles]);
    }
  }, [files, onFilesChange]);

  const handleClick = () => {
    inputRef.current?.click();
  };

  const handleChange = (e) => {
    const selected = Array.from(e.target.files || []);
    if (selected.length > 0) {
      onFilesChange([...files, ...selected]);
    }
    // Reset input so the same file can be added again
    e.target.value = '';
  };

  const removeFile = (idx) => {
    onFilesChange(files.filter((_, i) => i !== idx));
  };

  // ─── Reorder drag handlers (list items) ─────────────────────────
  const onReorderDragStart = (e, idx) => {
    setDragIdx(idx);
    e.dataTransfer.effectAllowed = 'move';
    // Prevent file-drop zone from triggering
    e.stopPropagation();
  };

  const onReorderDragOver = (e, idx) => {
    e.preventDefault();
    e.stopPropagation();
    setOverIdx(idx);
  };

  const onReorderDrop = (e, idx) => {
    e.preventDefault();
    e.stopPropagation();
    if (dragIdx === null || dragIdx === idx) {
      setDragIdx(null);
      setOverIdx(null);
      return;
    }
    const reordered = [...files];
    const [moved] = reordered.splice(dragIdx, 1);
    reordered.splice(idx, 0, moved);
    onFilesChange(reordered);
    setDragIdx(null);
    setOverIdx(null);
  };

  const onReorderDragEnd = () => {
    setDragIdx(null);
    setOverIdx(null);
  };

  // Move item up or down (button-based reorder)
  const moveItem = (idx, direction) => {
    const newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= files.length) return;
    const reordered = [...files];
    [reordered[idx], reordered[newIdx]] = [reordered[newIdx], reordered[idx]];
    onFilesChange(reordered);
  };

  return (
    <div>
      <div className="flex items-center gap-sm mb-md" style={{ minHeight: 24 }}>
        <span style={{ fontWeight: 600, fontSize: '0.88rem' }}>{label}</span>
        {required && <span className="badge badge-warning">Required</span>}
        {!required && <span className="badge badge-info">Optional</span>}
        {files.length > 0 && (
          <span className="badge badge-success" style={{ marginLeft: 'auto' }}>
            {files.length} file{files.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* File list with reorder */}
      {files.length > 0 && (
        <div className="multi-file-list">
          {files.map((file, idx) => (
            <div
              key={`${file.name}-${idx}`}
              className={`multi-file-item${dragIdx === idx ? ' dragging' : ''}${overIdx === idx ? ' drag-over-item' : ''}`}
              draggable
              onDragStart={(e) => onReorderDragStart(e, idx)}
              onDragOver={(e) => onReorderDragOver(e, idx)}
              onDrop={(e) => onReorderDrop(e, idx)}
              onDragEnd={onReorderDragEnd}
            >
              <span className="file-order-num">{idx + 1}</span>
              <span className="file-drag-handle" title="Drag to reorder">⠿</span>
              <span className="file-item-name">📄 {file.name}</span>
              <span className="file-item-size">
                ({(file.size / 1024).toFixed(1)} KB)
              </span>
              <div className="file-item-actions">
                <button
                  className="file-move-btn"
                  onClick={() => moveItem(idx, -1)}
                  disabled={idx === 0}
                  title="Move up"
                >
                  ▲
                </button>
                <button
                  className="file-move-btn"
                  onClick={() => moveItem(idx, 1)}
                  disabled={idx === files.length - 1}
                  title="Move down"
                >
                  ▼
                </button>
                <button
                  className="file-remove-btn"
                  onClick={() => removeFile(idx)}
                  title="Remove file"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Drop zone to add more files */}
      <div
        className={`file-uploader multi-file-zone${dragOver ? ' drag-over' : ''}`}
        onClick={handleClick}
        onDragOver={handleDrag}
        onDragEnter={handleDragIn}
        onDragLeave={handleDragOut}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple
          onChange={handleChange}
        />
        <div className="upload-icon">{files.length > 0 ? '➕' : '📂'}</div>
        <div className="upload-text">
          {files.length > 0
            ? <>Drop more CSVs or <strong>click to add</strong></>
            : <>Drag & drop CSV files here, or <strong>click to browse</strong></>
          }
        </div>
      </div>
    </div>
  );
}
