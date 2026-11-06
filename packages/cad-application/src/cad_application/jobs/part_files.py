"""Helpers for temporary and intermediate part file paths (spec 8.4, design 8)."""

import ntpath


def _base_path(target: str) -> str:
    root, _ = ntpath.splitext(target)
    return root


def working_path(target: str, job_id: str) -> str:
    """The uniquely-named working part file while the job is building it."""
    base = _base_path(target)
    return f"{base}.{job_id}.building.SLDPRT"


def failed_path(target: str, job_id: str) -> str:
    """The failed part file kept when an operation or verification fails."""
    base = _base_path(target)
    return f"{base}.{job_id}.failed.SLDPRT"


def partial_path(target: str, job_id: str) -> str:
    """The partial part file kept when a job is cancelled with keep_partial."""
    base = _base_path(target)
    return f"{base}.{job_id}.partial.SLDPRT"
