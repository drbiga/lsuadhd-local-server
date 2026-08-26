import asyncio
import logging
import traceback

"""
Reconciliation of missing feedbacks is done in two stages:

Phase 1 Upload:
- Compare the feedbacks in the local feedback.db against what already exists in the cloud
- Upload each missing feedback (Personal Analytics data + screenshot) to the cloud, where
  it sits UNLABELED for now
- Uploads run up to STORE_CONCURRENCY (8) at a time

Phase 2 Finalize:
- "Finalize" is a backend endpoint that does the OCR + labeling. The backend doesn't start
  this on its own so the local server must call finalize to enable it
- For each finalize call:
  -> OCR up to FINALIZE_BATCH (8) not-yet-labeled feedbacks (2 screenshots at a time to
    Tesseract), getting each one's ScreenAnalyzer prediction + saves those predictions
  -> "Replays" the whole session: goes thru all feedbacks in order, rebuilds the
    activity-gap counter, and computes/saves the final label (from PA focus states + 
    OCR/ScreenAnalyzer predictions)
  -> We prompt 8 at a time continuously because more than that would likely cause the HTTP
    request to timeout.
- Local server LOOPS finalize until nothing is pending, capped at FINALIZE_MAX_ROUNDS (40) 
  so it can't go on forever if something is stuck (e.g. an OCR that keeps failing).

As an example: for a 99-feedback session upload all 99 (8 at a time), then call finalize ~13 times
(8 labeled per round) until 0 remain
"""

STORE_CONCURRENCY = 8
FINALIZE_BATCH = 8
FINALIZE_MAX_ROUNDS = 40


async def count_pending_feedbacks(session_service, repository, iam_session) -> int:
    """
    Count how many locally-saved feedbacks the cloud has not fully recovered yet. 
    Used to decide whether a sync is needed and, after a sync, whether it
    actually finished.
    """
    student_name = iam_session.user.username
    try:
        session_seqnums = await repository.get_local_session_seqnums(student_name)
    except Exception:
        logging.error(
            f"[ reconcile ] Could not read local sessions: {traceback.format_exc()}"
        )
        return 0

    pending = 0
    for session_seqnum in session_seqnums:
        try:
            cloud_ids = set(
                await session_service.get_cloud_feedback_ids(student_name, session_seqnum)
            )
            local_rows = await repository.get_feedbacks_for_session(
                student_name, session_seqnum
            )
            pending += sum(1 for row in local_rows if row["id"] not in cloud_ids)
        except Exception:
            logging.error(
                f"[ reconcile ] Error checking session {session_seqnum}: {traceback.format_exc()}"
            )
    return pending


async def reconcile_pending_feedbacks(session_service, repository, iam_session) -> dict:
    """
    Catch the cloud up with the local backup for the logged-in student, in the 2 phases
    described in the initial comment at the top of this file.

    This function is idempotent and safe! Already-recovered feedbacks are skipped by the backend, a
    missing screenshot file is reported and skipped, and a finalize that times out can simply be
    run again. Whether the sync is fully complete is determined by re-checking
    count_pending_feedbacks afterwards.

    Returns a summary: {"feedbacks_recovered": int, "sessions_synced": list[int], "unrecoverable": list}
    """
    student_name = iam_session.user.username

    try:
        session_seqnums = await repository.get_local_session_seqnums(student_name)
    except Exception:
        logging.error(
            f"[ reconcile ] Could not read local sessions: {traceback.format_exc()}"
        )
        return {"feedbacks_recovered": 0, "sessions_synced": [], "unrecoverable": []}

    feedbacks_recovered = 0
    sessions_synced: list[int] = []
    unrecoverable: list = []  # (session_seqnum, feedback_id) that could not be recovered

    for session_seqnum in session_seqnums:
        try:
            cloud_ids = set(
                await session_service.get_cloud_feedback_ids(student_name, session_seqnum)
            )
            local_rows = await repository.get_feedbacks_for_session(
                student_name, session_seqnum
            )
            missing_rows = [row for row in local_rows if row["id"] not in cloud_ids]
            if not missing_rows:
                continue

            logging.info(
                f"[ reconcile ] Session {session_seqnum}: pushing {len(missing_rows)} missing feedback(s)"
            )

            # Phase 1: push all missing feedbacks
            slots = asyncio.Semaphore(STORE_CONCURRENCY)

            async def store_one(row):
                async with slots:
                    try:
                        await session_service.store_feedback(
                            student_name, session_seqnum, row
                        )
                    except FileNotFoundError:
                        unrecoverable.append((session_seqnum, row["id"]))
                        logging.error(
                            f"[ reconcile ] Screenshot file missing for feedback id={row['id']} "
                            f"session={session_seqnum}; cannot recover: {row['screenshot']}"
                        )
                    except Exception:
                        unrecoverable.append((session_seqnum, row["id"]))
                        logging.error(
                            f"[ reconcile ] Failed to store feedback id={row['id']} "
                            f"session={session_seqnum}: {traceback.format_exc()}"
                        )

            await asyncio.gather(*(store_one(row) for row in missing_rows))

            # Phase 2:
            missing_ids = {row["id"] for row in missing_rows}
            cloud_ids: set = set()
            prev_pending = None
            for _ in range(FINALIZE_MAX_ROUNDS):
                errored = False
                try:
                    await session_service.finalize_session(
                        student_name, session_seqnum, limit=FINALIZE_BATCH
                    )
                except Exception:
                    errored = True
                    logging.error(
                        f"[ reconcile ] Finalize batch error for session {session_seqnum} "
                        f"(continuing): {traceback.format_exc()}"
                    )
                cloud_ids = set(
                    await session_service.get_cloud_feedback_ids(student_name, session_seqnum)
                )
                pending = sum(1 for row_id in missing_ids if row_id not in cloud_ids)
                if pending == 0:
                    break
                # Note: A completed call that made no progress means the rest can't be labeled (e.g. OCR
                # permanently failing). An error call may still have persisted work, so we should give it
                # another round before giving up.
                if not errored and prev_pending is not None and pending >= prev_pending:
                    logging.error(
                        f"[ reconcile ] Session {session_seqnum} stalled at {pending} pending; stopping"
                    )
                    break
                prev_pending = pending

            sessions_synced.append(session_seqnum)
            feedbacks_recovered += sum(1 for row_id in missing_ids if row_id in cloud_ids)
            for row_id in missing_ids:
                if row_id not in cloud_ids:
                    unrecoverable.append((session_seqnum, row_id))
        except Exception:
            logging.error(
                f"[ reconcile ] Error reconciling session {session_seqnum}: {traceback.format_exc()}"
            )

    return {
        "feedbacks_recovered": feedbacks_recovered,
        "sessions_synced": sessions_synced,
        "unrecoverable": unrecoverable,
    }
