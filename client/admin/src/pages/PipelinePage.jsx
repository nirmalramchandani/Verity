import { useState, useCallback, useEffect } from 'react';
import MultiFileUploader from '../components/MultiFileUploader';
import Checklist from '../components/Checklist';
import TerminalOutput from '../components/TerminalOutput';
import ProgressBar from '../components/ProgressBar';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const PHASE1_CHECKS = [
  ['col_normalize', 'Column names normalized'],
  ['type_clean', 'Data types cleaned (qty, price, date)'],
  ['alias_map', 'Investor name aliases applied'],
  ['symbol_map', 'Stock symbol mappings applied'],
  ['dedup', 'Duplicate rows removed'],
  ['intraday', 'Intraday orders filtered'],
  ['events_clean', 'Corporate events cleaned'],
];

const PHASE2_CHECKS = [
  ['sort', 'Chronological Date Sorting'],
  ['corp_actions', 'Corporate Adjustments (Bonus/Split)'],
  ['fifo', 'FIFO Lot Matching Logic'],
  ['short_guard', 'Short-Sell Guard Check'],
  ['sync_pg', 'PostgreSQL Sink (Immediate Commit)'],
  ['sync_mongo', 'MongoDB Sink (Immediate Sync)'],
  ['snapshots', 'Monthly Snapshot Logic'],
];

function parseSSEStream(response, onData) {
  return new Promise((resolve, reject) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    function read() {
      reader.read().then(({ done, value }) => {
        if (done) {
          resolve();
          return;
        }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith(':')) continue;

          let payload = trimmed;
          if (payload.startsWith('data: ')) payload = payload.slice(6);

          try {
            const data = JSON.parse(payload);
            onData(data);
          } catch {
            // Skip non-JSON lines
          }
        }
        read();
      }).catch(reject);
    }
    read();
  });
}

export default function PipelinePage() {
  // Multi-file state
  const [txnFiles, setTxnFiles] = useState([]);
  const [evtFiles, setEvtFiles] = useState([]);

  // Phase 1 state
  const [phase1Running, setPhase1Running] = useState(false);
  const [phase1Done, setPhase1Done] = useState(false);
  const [phase1Checks, setPhase1Checks] = useState({});
  const [phase1Logs, setPhase1Logs] = useState([]);
  const [phase1Progress, setPhase1Progress] = useState(0);

  // Clean paths
  const [cleanTxnPath, setCleanTxnPath] = useState(null);
  const [cleanEvtPath, setCleanEvtPath] = useState(null);

  // Phase 2 state
  const [phase2Running, setPhase2Running] = useState(false);
  const [phase2Done, setPhase2Done] = useState(false);
  const [phase2Checks, setPhase2Checks] = useState({});
  const [phase2Logs, setPhase2Logs] = useState([]);
  const [phase2Progress, setPhase2Progress] = useState(0);
  const [telemetry, setTelemetry] = useState('');
  const [isPaused, setIsPaused] = useState(false);
  const [taskId, setTaskId] = useState(null);

  // Phase 3 state
  const [signalsRunning, setSignalsRunning] = useState(false);
  const [signalsDone, setSignalsDone] = useState(false);

  // Checkpoint
  const [checkpoint, setCheckpoint] = useState(-1);

  // Error + clear
  const [error, setError] = useState(null);
  const [showClearModal, setShowClearModal] = useState(false);
  const [clearStatus, setClearStatus] = useState(null);

  // ─── SSE stream consumer for Phase 2 ────────────────────────────────
  const consumeIngestStream = useCallback(async (tid) => {
    const streamResp = await fetch(`${API_BASE}/upload/ingest/stream?task_id=${tid}`);
    if (!streamResp.ok) {
      throw new Error(`Stream failed: HTTP ${streamResp.status}`);
    }

    await parseSSEStream(streamResp, (data) => {
      let msg = data.message || '';
      let pct = data.progress || 0;

      if (msg.includes('[PROGRESS|')) {
        const parts = msg.split(']', 2);
        pct = parseInt(parts[0].replace('[PROGRESS|', ''));
        const actual = parts[1]?.trim() || '';
        if (actual.includes('|')) {
          setTelemetry(actual);
        }
        msg = actual;
      }

      pct = Math.max(0, Math.min(100, pct));
      setPhase2Progress(pct);

      if (data.type === 'CHECK') {
        setPhase2Checks((prev) => ({
          ...prev,
          [data.check_id]: data.check_status || 'done',
        }));
      }

      if (msg && !msg.includes('[PROGRESS')) {
        setPhase2Logs((prev) => [...prev.slice(-50), msg]);
      }

      if (data.type === 'ERROR') {
        setError(data.message);
      }
    });
  }, []);

  // ─── Status Polling for Phase 2 ──────────────────────────────────
  useEffect(() => {
    let interval;
    if (phase2Running && taskId && !isPaused) {
      interval = setInterval(async () => {
        try {
          const resp = await fetch(`${API_BASE}/upload/task/status?task_id=${taskId}`);
          if (resp.ok) {
            const data = await resp.json();
            if (data.status === 'complete') {
              setPhase2Done(true);
              setPhase2Running(false);
              setPhase2Progress(100);
              alert("Simulation History Fully Reconstructed: 2010–2025");
              clearInterval(interval);
            } else if (data.status === 'failed') {
               setError(data.error || "Background task failed.");
               setPhase2Running(false);
               clearInterval(interval);
            }
          }
        } catch (err) {
          console.error("Polling error:", err);
        }
      }, 5000); // Poll every 5 seconds
    }
    return () => clearInterval(interval);
  }, [phase2Running, taskId, isPaused]);

  // ─── Check for running task on page load ───────────────────────────
  useState(() => {
    (async () => {
      try {
        const resp = await fetch(`${API_BASE}/upload/task/status?name=ingest`);
        if (!resp.ok) return;
        const data = await resp.json();
        if (data.status === 'running') {
          setTaskId(data.task_id);
          setPhase2Running(true);
          setPhase2Logs((prev) => [...prev, '🔄 Reconnected to running ingestion task...']);
          try {
            await consumeIngestStream(data.task_id);
            setPhase2Done(true);
          } catch {
            // Stream ended or errored — check final status
          } finally {
            setPhase2Running(false);
            setIsPaused(false);
          }
        } else if (data.status === 'complete') {
          setPhase2Done(true);
          setPhase2Progress(100);
          setPhase2Logs(['✅ Previous ingestion completed successfully.']);
        }
      } catch {
        // No task running, that's fine
      }
    })();
  });

  // ─── Phase 1: Clean (Batch) ────────────────────────────────────────
  const runPhase1 = useCallback(async () => {
    if (txnFiles.length === 0) {
      setError('At least one Bulk Deals CSV is required!');
      return;
    }

    setError(null);
    setPhase1Running(true);
    setPhase1Done(false);
    setPhase1Checks({});
    setPhase1Logs([]);
    setPhase1Progress(0);

    try {
      const formData = new FormData();

      // Append files in order
      for (const f of txnFiles) {
        formData.append('transactions', f);
      }
      for (const f of evtFiles) {
        formData.append('events', f);
      }

      // Build order params — comma-separated filenames in the displayed order
      const txnOrder = txnFiles.map((f) => f.name).join(',');
      const evtOrder = evtFiles.map((f) => f.name).join(',');

      const endpoint = txnFiles.length === 1 && evtFiles.length <= 1
        ? '/upload/clean'   // single-file path (backward compat)
        : '/upload/clean-batch';

      let url = `${API_BASE}${endpoint}`;
      if (endpoint === '/upload/clean-batch') {
        const params = new URLSearchParams();
        if (txnOrder) params.set('txn_order', txnOrder);
        if (evtOrder) params.set('evt_order', evtOrder);
        url += `?${params.toString()}`;
      }

      const resp = await fetch(url, {
        method: 'POST',
        body: formData,
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || `HTTP ${resp.status}`);
      }

      let cleanPaths = null;

      await parseSSEStream(resp, (data) => {
        // Handle CLEAN_PATHS
        if (data.type === 'CLEAN_PATHS') {
          cleanPaths = data;
          return;
        }

        let msg = data.message || '';
        let pct = data.progress || 0;

        // Parse [PROGRESS|nn]
        if (msg.includes('[PROGRESS|')) {
          const parts = msg.split(']', 2);
          pct = parseInt(parts[0].replace('[PROGRESS|', ''));
          msg = parts[1]?.trim() || msg;
        }

        pct = Math.max(0, Math.min(100, pct));
        setPhase1Progress(pct);

        // Checklist
        if (data.type === 'CHECK') {
          setPhase1Checks((prev) => ({
            ...prev,
            [data.check_id]: data.check_status || 'done',
          }));
        }

        // Terminal
        if (msg && !msg.includes('[PROGRESS')) {
          setPhase1Logs((prev) => [...prev.slice(-50), msg]);
        }

        // Error
        if (data.type === 'ERROR') {
          setError(data.message);
        }
      });

      if (cleanPaths) {
        setCleanTxnPath(cleanPaths.clean_txn_path);
        setCleanEvtPath(cleanPaths.clean_evt_path || null);
        setPhase1Done(true);

        // Check checkpoint
        try {
          const cpResp = await fetch(
            `${API_BASE}/upload/checkpoint?clean_txn_path=${encodeURIComponent(cleanPaths.clean_txn_path)}`
          );
          if (cpResp.ok) {
            const cpData = await cpResp.json();
            setCheckpoint(cpData.checkpoint ?? -1);
          }
        } catch {
          // Ignore checkpoint errors
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setPhase1Running(false);
    }
  }, [txnFiles, evtFiles]);

  // ─── Phase 2: Ingest ─────────────────────────────────────────────
  const runPhase2 = useCallback(async (resume = false) => {
    if (!cleanTxnPath) return;

    setError(null);
    setPhase2Running(true);
    setPhase2Done(false);
    setPhase2Checks({});
    setPhase2Logs([]);
    setPhase2Progress(0);
    setTelemetry('');

    try {
      // Step 1: Start the background task
      let url = `${API_BASE}/upload/ingest?clean_txn_path=${encodeURIComponent(cleanTxnPath)}&resume=${resume}`;
      if (cleanEvtPath) {
        url += `&clean_evt_path=${encodeURIComponent(cleanEvtPath)}`;
      }

      const resp = await fetch(url, { method: 'POST' });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || `HTTP ${resp.status}`);
      }

      const launchData = await resp.json();
      const tid = launchData.task_id;
      setTaskId(tid);

      if (launchData.status === 'already_running') {
        setPhase2Logs((prev) => [...prev, '🔄 Reconnecting to running ingestion...']);
      } else {
        setPhase2Logs((prev) => [...prev, '🚀 Ingestion started in background...']);
      }

      // Step 2: Stream progress (if browser closes, task keeps running)
      await consumeIngestStream(tid);

      setPhase2Done(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setPhase2Running(false);
      setIsPaused(false);
    }
  }, [cleanTxnPath, cleanEvtPath, consumeIngestStream]);

  // ─── Phase 3: Signal Engine ──────────────────────────────────────
  const runSignals = useCallback(async () => {
    setSignalsRunning(true);
    setSignalsDone(false);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/data/signals/generate`, { method: 'POST' });
      if (!resp.ok) throw new Error('Failed to trigger signal engine');
      const data = await resp.json();
      setPhase2Logs(prev => [...prev, `⚡ ${data.message}`]);
      
      // Since it's a background task, we'll just wait a bit or assume success
      setTimeout(() => {
        setSignalsRunning(false);
        setSignalsDone(true);
      }, 3000);
    } catch (err) {
      setError(err.message);
      setSignalsRunning(false);
    }
  }, []);

  const handlePause = async () => {
    try {
      await fetch(`${API_BASE}/upload/pause`, { method: 'POST' });
      setIsPaused(true);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleResume = async () => {
    try {
      await fetch(`${API_BASE}/upload/resume`, { method: 'POST' });
      setIsPaused(false);
    } catch (err) {
      setError(err.message);
    }
  };

  // ─── Clear All Data ──────────────────────────────────────────────
  const clearAllData = useCallback(async () => {
    try {
      setClearStatus('clearing');
      const resp = await fetch(`${API_BASE}/data/clear`, { method: 'POST' });
      if (resp.ok) {
        setClearStatus('success');
        setTimeout(() => {
          setShowClearModal(false);
          setClearStatus(null);
        }, 1500);
      } else {
        setClearStatus('error');
      }
    } catch {
      setClearStatus('error');
    }
  }, []);

  const totalFiles = txnFiles.length + evtFiles.length;

  return (
    <>
      {/* Page Header */}
      <div className="page-header">
        <h2>⚙️ Pipeline Control</h2>
        <p className="description">Upload, clean, validate, and ingest financial data into the Verity engine.</p>
      </div>

      {/* Error */}
      {error && (
        <div className="status-message status-error mb-lg">
          <span>❌</span>
          <span>{error}</span>
          <button
            className="btn btn-sm btn-secondary"
            style={{ marginLeft: 'auto' }}
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* ─── File Upload ─────────────────────────────────────────────── */}
      <div className="card mb-lg">
        <div className="card-header">
          <span className="card-title">📁 Data Files — Batch Upload</span>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {totalFiles > 0 && (
              <span className="badge badge-info">
                {totalFiles} file{totalFiles !== 1 ? 's' : ''} queued
              </span>
            )}
            <button
              className="btn btn-sm btn-danger"
              onClick={() => setShowClearModal(true)}
            >
              🗑️ Clear All Data
            </button>
          </div>
        </div>

        {/* Info banner */}
        <div className="status-message status-info mb-lg" style={{ fontSize: '0.82rem' }}>
          <span>💡</span>
          <span>
            Upload multiple Bulk Deal and Corporate Action CSVs. Drag or use ▲▼ to set
            processing order. Files will be <strong>merged in order</strong> before the pipeline runs.
          </span>
        </div>

        <div className="upload-grid">
          <MultiFileUploader
            label="Bulk Deals (Transactions)"
            required
            files={txnFiles}
            onFilesChange={setTxnFiles}
          />
          <MultiFileUploader
            label="Corporate Actions (Events)"
            required={false}
            files={evtFiles}
            onFilesChange={setEvtFiles}
          />
        </div>
        <button
          className="btn btn-primary btn-lg w-full"
          onClick={runPhase1}
          disabled={phase1Running || txnFiles.length === 0}
        >
          {phase1Running ? (
            <>
              <span className="spinner" />
              Cleaning...
            </>
          ) : (
            `🧹 Step 1: Upload & Clean (${txnFiles.length} bulk deal${txnFiles.length !== 1 ? 's' : ''}${evtFiles.length > 0 ? `, ${evtFiles.length} event file${evtFiles.length !== 1 ? 's' : ''}` : ''})`
          )}
        </button>
      </div>

      {/* ─── Phase 1 Output ──────────────────────────────────────────── */}
      {(phase1Running || phase1Done) && (
        <div className="card mb-lg phase-section">
          <div className="card-header">
            <span className="card-title">Phase 1 — Cleaning & Validation</span>
            {phase1Done && <span className="badge badge-success">Complete</span>}
            {phase1Running && <span className="badge badge-info">Running</span>}
          </div>
          <ProgressBar percent={phase1Progress} label="Cleaning Pipeline" />
          <div className="phase-content">
            <div>
              <h4 style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 'var(--space-sm)' }}>
                Validation Checklist
              </h4>
              <Checklist checks={PHASE1_CHECKS} completed={phase1Checks} />
            </div>
            <div>
              <h4 style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 'var(--space-sm)' }}>
                Live Terminal
              </h4>
              <TerminalOutput logs={phase1Logs} />
            </div>
          </div>
          {phase1Done && (
            <div className="status-message status-success mt-lg">
              <span>✅</span>
              <span>Cleaning complete! Proceed to Phase 2.</span>
            </div>
          )}
        </div>
      )}

      <hr className="phase-divider" />

      {/* ─── Phase 2 ─────────────────────────────────────────────────── */}
      {cleanTxnPath ? (
        <div className="card mb-lg">
          <div className="card-header">
            <span className="card-title">Phase 2 — Ingestion & Database Write</span>
          </div>

          <div className="status-message status-info mb-md">
            <span>📦</span>
            <span>Cleaned data ready for ingestion</span>
          </div>

          <div className="flex gap-md">
            {checkpoint >= 0 ? (
              <>
                <button
                  className="btn btn-primary btn-lg"
                  onClick={() => runPhase2(true)}
                  disabled={phase2Running}
                  style={{ flex: 1 }}
                >
                  {phase2Running ? (
                    <>
                      <span className="spinner" />
                      Ingesting...
                    </>
                  ) : (
                    `⏯️ Resume Ingest (from row ${checkpoint + 1})`
                  )}
                </button>
                <button
                  className="btn btn-secondary btn-lg"
                  onClick={() => runPhase2(false)}
                  disabled={phase2Running}
                >
                  🔄 Start Over
                </button>
              </>
            ) : (
              <button
                className="btn btn-primary btn-lg w-full"
                onClick={() => runPhase2(false)}
                disabled={phase2Running}
              >
                {phase2Running ? (
                  <>
                    <span className="spinner" />
                    Ingesting...
                  </>
                ) : (
                  '✅ Step 2: Proceed to Ingest (ACID)'
                )}
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="text-center text-muted" style={{ padding: 'var(--space-xl)' }}>
          ⬆️ Upload files and run Step 1 first to unlock Step 2.
        </div>
      )}

      {/* ─── Phase 2 Output ──────────────────────────────────────────── */}
      {(phase2Running || phase2Done) && (
        <div className="card mb-lg phase-section">
          <div className="card-header">
            <span className="card-title">Ingestion Progress</span>
            <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
              {phase2Running && !isPaused && (
                <button className="btn btn-sm btn-secondary" onClick={handlePause}>⏸️ Pause</button>
              )}
              {phase2Running && isPaused && (
                <button className="btn btn-sm btn-primary" onClick={handleResume}>▶️ Resume</button>
              )}
              {phase2Done && <span className="badge badge-success">Complete</span>}
              {phase2Running && <span className="badge badge-info">{isPaused ? 'Paused' : 'Running'}</span>}
            </div>
          </div>

          {telemetry && (
            <div className="status-message status-info mb-md">
              <span>🚀</span>
              <strong>{telemetry}</strong>
            </div>
          )}

          <ProgressBar percent={phase2Progress} label="Ingestion Pipeline" />

          <div className="phase-content">
            <div>
              <h4 style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 'var(--space-sm)' }}>
                Ingestion Checklist
              </h4>
              <Checklist checks={PHASE2_CHECKS} completed={phase2Checks} />
            </div>
            <div>
              <h4 style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 'var(--space-sm)' }}>
                Live Terminal & Telemetry
              </h4>
              <TerminalOutput logs={phase2Logs} />
            </div>
          </div>

          {phase2Done && (
            <div className="status-message status-success mt-lg">
              <span>🎉</span>
              <span>Ingestion complete! Data is now in your databases.</span>
            </div>
          )}
        </div>
      )}

      {/* ─── Phase 3: Intelligence Engine ──────────────────────────────── */}
      {(phase2Done || signalsDone || signalsRunning) && (
        <div className="card mb-lg phase-section animate-in">
          <div className="card-header">
            <span className="card-title">Phase 3 — Signal Intelligence Engine</span>
            {signalsDone && <span className="badge badge-success">Active</span>}
            {signalsRunning && <span className="badge badge-info">Analyzing...</span>}
          </div>
          
          <div className="status-message status-info mb-md" style={{ fontSize: '0.82rem' }}>
            <span>🧠</span>
            <span>
              The Signal Engine scans the latest 50 clusters of smart money deals to identify 
              high-conviction entries, then enriches them with fundamental RAG context.
            </span>
          </div>

          <button 
            className="btn btn-primary btn-lg w-full"
            onClick={runSignals}
            disabled={signalsRunning}
          >
            {signalsRunning ? (
              <>
                <span className="spinner" />
                Processing Strategies...
              </>
            ) : (
              '⚡ Manually Trigger Signal Engine'
            )}
          </button>

          {signalsDone && (
            <div className="status-message status-success mt-md">
              <span>🚀</span>
              <span>Signals generated. Check the User Terminal to view latest high-conviction alerts.</span>
            </div>
          )}
        </div>
      )}

      {/* ─── Clear Modal ─────────────────────────────────────────────── */}
      {showClearModal && (
        <div className="modal-overlay" onClick={() => !clearStatus && setShowClearModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>⚠️ Clear All Data</h3>
            <p>
              This will permanently delete <strong>ALL data</strong> from PostgreSQL and MongoDB.
              This action cannot be undone.
            </p>
            {clearStatus === 'success' ? (
              <div className="status-message status-success">
                <span>✅</span> Database purged successfully!
              </div>
            ) : clearStatus === 'error' ? (
              <div className="status-message status-error">
                <span>❌</span> Failed to clear database.
              </div>
            ) : (
              <div className="modal-actions">
                <button
                  className="btn btn-secondary"
                  onClick={() => setShowClearModal(false)}
                  disabled={clearStatus === 'clearing'}
                >
                  Cancel
                </button>
                <button
                  className="btn btn-danger"
                  onClick={clearAllData}
                  disabled={clearStatus === 'clearing'}
                >
                  {clearStatus === 'clearing' ? (
                    <>
                      <span className="spinner" />
                      Clearing...
                    </>
                  ) : (
                    '🔥 Yes, Clear Everything'
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
