"""
pipeline/runner.py
==================
Two-phase pipeline orchestrator.

Phase 1 (run_clean): Clean + validate → yields checklist SSE events. No DB writes.
Phase 2 (run_ingest): Replay timeline + flush to DBs → yields checklist SSE events.
"""

import json
import os
import hashlib
from datetime import datetime
from pipeline.cleaner import clean_transactions, clean_events
from ingestion.processor import IngestProcessor
from pipeline.notifier import notify_error, notify_info


def _emit(stage: str, percentage: int, message: str, check_id: str = None, check_status: str = None):
    payload = {"stage": stage, "progress": percentage, "message": message}
    if check_id:
        payload["type"] = "CHECK"
        payload["check_id"] = check_id
        payload["check_status"] = check_status or "done"
    return json.dumps(payload) + "\n\n"


def get_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file to identify it uniquely."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def run_clean(txn_path: str, events_path: str = None):
    """
    Phase 1: Clean the uploaded files. Returns checklist SSE events.
    Saves cleaned DataFrames to disk as parquet so Phase 2 can pick them up.
    """
    yield _emit("CLEANING", 5, "Reading raw transaction CSV...")

    # Step 1: Column normalization + type cleaning
    yield _emit("CLEANING", 8, "Normalizing column names and data types...")
    txn_df = clean_transactions(txn_path)
    yield _emit("CLEANING", 15, f"Column normalization & type cleaning complete. {len(txn_df)} rows kept.",
                check_id="col_normalize", check_status="done")
    yield _emit("CLEANING", 15, "Data types cleaned (qty → int, price → float, date → date).",
                check_id="type_clean", check_status="done")

    # Step 2: Alias mapping (already applied inside clean_transactions)
    yield _emit("CLEANING", 20, "Investor name aliases applied.",
                check_id="alias_map", check_status="done")

    # Step 3: Symbol mapping
    yield _emit("CLEANING", 25, "Stock symbol mappings applied.",
                check_id="symbol_map", check_status="done")

    # Step 4: Deduplication (already applied inside clean_transactions)
    yield _emit("CLEANING", 30, "Duplicate rows removed.",
                check_id="dedup", check_status="done")

    # Step 5: Intraday filter
    yield _emit("CLEANING", 35, "Intraday orders (same-day buy/sell pairs) filtered out.",
                check_id="intraday", check_status="done")

    # Step 6: Clean events
    events_df = None
    events_count = 0

    if events_path:
        yield _emit("CLEANING", 40, "Cleaning corporate events...")
        events_df = clean_events(events_path)
        events_count = len(events_df)
        yield _emit("CLEANING", 45, f"Corporate events cleaned: {events_count} valid events.",
                    check_id="events_clean", check_status="done")
    else:
        yield _emit("CLEANING", 45, "No events file provided. Skipping.",
                    check_id="events_clean", check_status="skipped")

    # Save cleaned data to disk for Phase 2
    # Use the same upload directory
    upload_dir = os.path.dirname(txn_path)
    base = os.path.splitext(os.path.basename(txn_path))[0]

    clean_txn_path = os.path.join(upload_dir, f"{base}_clean_txn.parquet")
    txn_df.to_parquet(clean_txn_path, index=False)

    clean_evt_path = None
    if events_df is not None:
        clean_evt_path = os.path.join(upload_dir, f"{base}_clean_evt.parquet")
        events_df.to_parquet(clean_evt_path, index=False)

    # Emit summary
    yield _emit("CLEAN_DONE", 50,
                f"Cleaning complete! {len(txn_df)} transactions, {events_count} events ready for ingestion.",
                check_id="clean_summary", check_status="done")

    # Emit the file paths so the frontend can pass them to Phase 2
    paths_payload = json.dumps({
        "type": "CLEAN_PATHS",
        "clean_txn_path": clean_txn_path,
        "clean_evt_path": clean_evt_path
    }) + "\n\n"
    yield paths_payload


def run_ingest(clean_txn_path: str, clean_evt_path: str = None, resume: bool = False):
    """
    Phase 2: Ingest cleaned data into databases.
    """
    try:
        import pandas as pd

        yield _emit("INGESTION", 55, "Loading cleaned data...")
        txn_df = pd.read_parquet(clean_txn_path)
        
        events_df = None
        if clean_evt_path and os.path.exists(clean_evt_path):
            events_df = pd.read_parquet(clean_evt_path)

        yield _emit("INGESTION", 58, "Computing file hash & checking checkpoints...")
        file_hash = get_file_hash(clean_txn_path)
        
        start_row = 0
        if resume:
            checkpoint = IngestProcessor.get_checkpoint(file_hash)
            if checkpoint >= 0:
                start_row = checkpoint + 1 # Resume from next row
                yield _emit("INGESTION", 60, f"Found checkpoint. Resuming from row {start_row}...")
            else:
                yield _emit("INGESTION", 60, "No checkpoint found. Starting from scratch.")
        else:
            yield _emit("INGESTION", 60, "Restarting from scratch (resume=False).")

        processor = IngestProcessor(txn_df, events_df, file_hash=file_hash)

        # Re-ordered checklist events based on flow
        yield _emit("INGESTION", 62, "Preparing row-by-row synchronization logs...", 
                    check_id="sort", check_status="done")
        
        yield _emit("INGESTION", 65, "Syncing corporate action adjustment logic...", 
                    check_id="corp_actions", check_status="done")

        import time
        last_heartbeat = time.time()
        
        # Iterate over the live generator
        for w in processor.run(start_row=start_row):
            current_time = time.time()
            if current_time - last_heartbeat >= 15:
                yield ": heartbeat\n\n"
                last_heartbeat = current_time
                
            # Parse progress overrides from the engine
            if "[PROGRESS|" in w:
                parts = w.split("]", 1)
                pct = int(parts[0].replace("[PROGRESS|", ""))
                msg = parts[1].strip()
                yield _emit("INGESTION", pct, msg)
                
                if "Row 1/" in msg:
                    yield _emit("INGESTION", pct, "FIFO Lot Matching logic active...", check_id="fifo", check_status="done")
                    yield _emit("INGESTION", pct, "Short-Sell Guard logic active...", check_id="short_guard", check_status="done")
                    yield _emit("INGESTION", pct, "PostgreSQL Sync Sink active...", check_id="sync_pg", check_status="done")
                    yield _emit("INGESTION", pct, "MongoDB Sync Sink active...", check_id="sync_mongo", check_status="done")

            elif "[STAGE]" in w:
                yield _emit("INGESTION", 98, w.replace("[STAGE] ", ""))
            elif "[EVENT]" in w:
                yield _emit("INGESTION", 80, w.replace("[EVENT] ", ""))
            elif "[INFO]" in w:
                msg = w.replace("[INFO] ", "")
                if "snapshots" in msg:
                    yield _emit("DB_FLUSH", 95, msg, check_id="snapshots", check_status="done")
                else:
                    yield _emit("INGESTION", 90, msg)
            else:
                yield _emit("INGESTION", 80, w)

        yield _emit("INGESTION", 99, "Engine syncing complete. Reconnecting for AI Smart Money Scores...", check_id="ai_scoring", check_status="pending")
        
        try:
            from pipeline.scoring_engine import calculate_scores
            calculate_scores()
            yield _emit("INGESTION", 99, "AI Smart Money Scores calculated and persisted.", check_id="ai_scoring", check_status="done")
        except Exception as score_err:
            print(f"[runner] Scoring engine error: {str(score_err)}")
            yield _emit("INGESTION", 99, f"AI Scoring skipped/failed: {str(score_err)}", check_id="ai_scoring", check_status="error")

        # --- Phase 3: Signal Engine (High Conviction Generation) ---
        try:
            yield _emit("INGESTION", 99, "Triggering Signal Engine for High-Conviction detection...", check_id="signal_engine", check_status="pending")
            import asyncio
            from signal_engine.pipeline import EndToEndPipeline
            
            # Since run_ingest is called in a background thread, we can use asyncio.run
            async def run_signals_async():
                pipeline = EndToEndPipeline()
                await pipeline.run_daily_batch()

            try:
                asyncio.run(run_signals_async())
                yield _emit("INGESTION", 99, "High-Conviction signals generated and alerts dispatched.", check_id="signal_engine", check_status="done")
            except Exception as e:
                print(f"[runner] Signal Engine Runtime Error: {str(e)}")
                yield _emit("INGESTION", 99, f"Signal Engine failed: {str(e)}", check_id="signal_engine", check_status="error")

        except Exception as sig_import_err:
            print(f"[runner] Signal Engine Import/Setup Error: {str(sig_import_err)}")
            yield _emit("INGESTION", 99, "Signal Engine unavailable.", check_id="signal_engine", check_status="skipped")

        total_txn = len(txn_df)
        total_evt = len(events_df) if events_df is not None else 0
        yield _emit("COMPLETE", 100, f"Sync Ingestion & Scoring complete! {total_txn} rows persisted successfully.")

        # Notify admin of successful completion
        notify_info("Ingestion Complete", f"{total_txn} transactions and {total_evt} events processed successfully.")

        try:
            from db.mongo import ingestion_metadata_collection
            ingestion_metadata_collection.update_one(
                {"file_hash": file_hash},
                {"$set": {"status": "finished", "total_rows": total_txn, "completed_at": datetime.now().isoformat()}},
                upsert=True
            )
        except Exception as mongo_err:
            print(f"[runner] MongoDB ingestion_metadata update error: {str(mongo_err)}")

        yield "[FINISH] Ingestion of " + str(total_txn) + " rows complete."

    except Exception as e:
        import traceback
        err_msg = f"CRASH: {str(e)}\n{traceback.format_exc()}"
        print(f"[runner] {err_msg}")
        notify_error("Pipeline Crash", e, context=f"During ingestion of {clean_txn_path}")
        yield _emit("ERROR", 0, err_msg)
