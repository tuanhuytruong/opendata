"""Pilot worker for durable OpenData jobs.

Start separately from the API process:
    python -m worker

It executes bounded run validation jobs and records retry/cancellation state. Report
rendering remains synchronous until its complete chart-plan payload is persisted.
"""
from __future__ import annotations

import logging
import time

from run_store import DurableJobQueue, RunStore, redacted_error
from main import DATA_DIR, JOB_DIR, load_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
store = RunStore(DATA_DIR)
queue = DurableJobQueue(JOB_DIR)


def process_once() -> bool:
    job = queue.next_queued()
    if job is None:
        return False
    job_id = str(job["job_id"])
    if queue.get(job_id).get("status") == "cancelled":
        return True
    queue.update(job_id, status="running")
    try:
        # Checkpoint before and after each bounded operation; never log data/metadata.
        if queue.get(job_id).get("status") == "cancelled":
            return True
        load_run(str(job["run_id"]))
        if queue.get(job_id).get("status") == "cancelled":
            return True
        queue.update(job_id, status="completed", error=None)
        logging.info("completed job=%s kind=%s", job_id, job.get("kind"))
    except Exception as error:
        queue.fail_or_retry(job_id, redacted_error(error))
        logging.warning("job failed job=%s", job_id)
    return True


def main() -> None:
    while True:
        if not process_once():
            time.sleep(1)


if __name__ == "__main__":
    main()
