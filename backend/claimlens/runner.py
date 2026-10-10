import threading

from claimlens.pipeline.run import run_pipeline


def start(case_id: str, deps) -> None:
    """Run the pipeline in the background so the upload request returns at once."""
    threading.Thread(target=run_pipeline, args=(case_id, deps), daemon=True, name=f"case-{case_id}").start()
