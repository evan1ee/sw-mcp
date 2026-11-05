"""Tests for part_files helpers (Task 9b)."""

from cad_application.jobs.part_files import failed_path, partial_path, working_path


def test_part_files_paths() -> None:
    target = r"C:\Work\bracket.SLDPRT"
    job_id = "job_01H1234567890ABCDEFGHJKMNP"

    assert (
        working_path(target, job_id)
        == r"C:\Work\bracket.job_01H1234567890ABCDEFGHJKMNP.building.SLDPRT"
    )
    assert (
        failed_path(target, job_id)
        == r"C:\Work\bracket.job_01H1234567890ABCDEFGHJKMNP.failed.SLDPRT"
    )
    assert (
        partial_path(target, job_id)
        == r"C:\Work\bracket.job_01H1234567890ABCDEFGHJKMNP.partial.SLDPRT"
    )


def test_part_files_lowercase_extension() -> None:
    target = r"D:\Data\part.sldprt"
    job_id = "job_123"

    assert working_path(target, job_id) == r"D:\Data\part.job_123.building.SLDPRT"
    assert failed_path(target, job_id) == r"D:\Data\part.job_123.failed.SLDPRT"
    assert partial_path(target, job_id) == r"D:\Data\part.job_123.partial.SLDPRT"
