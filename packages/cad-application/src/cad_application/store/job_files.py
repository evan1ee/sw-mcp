"""``jobs/<job_id>/job.json`` and ``journal.jsonl`` of one store (spec 13.2.2, 13.2.3)."""

import ntpath

from cad_application.ports import FileSystem
from cad_application.store.codec import decode_record, encode, encode_line
from cad_application.store.errors import StoreError, corrupt
from cad_application.store.job_records import JobRecord
from cad_application.store.journal_records import JournalRecord, StateRecord, journal_from_json

_NEWLINE = b"\n"


class JobFiles:
    """Not thread-safe by itself; ``FileStore`` serializes calls."""

    def __init__(self, fs: FileSystem, jobs_dir: str) -> None:
        self._fs = fs
        self._dir = jobs_dir
        self._tail_checked: set[str] = set()

    def _path(self, job_id: str, name: str) -> str:
        return ntpath.join(self._dir, job_id, name)

    def create(self, record: JobRecord, ts: str) -> None:
        """The first ``state`` record, then ``job.json`` (13.2.2)."""
        self._fs.make_dirs(ntpath.join(self._dir, record.job_id))
        first = StateRecord(ts, record.job_id, None, record.state, "job created")
        self.append(record.job_id, first)
        self.put(record)

    def append(self, job_id: str, record: JournalRecord) -> None:
        self._drop_torn_tail(job_id)
        try:
            self._fs.append_line(self._path(job_id, "journal.jsonl"), encode_line(record.to_json()))
        except BaseException:
            self._tail_checked.discard(job_id)  # the failed append may have left a torn line
            raise

    def _drop_torn_tail(self, job_id: str) -> None:
        """A crash can leave a final line without ``\\n``; appending after it would corrupt
        the next record, so the intact lines are rewritten atomically, once per job."""
        if job_id in self._tail_checked:
            return
        path = self._path(job_id, "journal.jsonl")
        if self._fs.stat(path) is not None:
            data = self._fs.read_bytes(path)
            if data and not data.endswith(_NEWLINE):
                self._fs.write_atomic(path, data[: data.rfind(_NEWLINE) + 1])
        self._tail_checked.add(job_id)

    def put(self, record: JobRecord) -> None:
        self._fs.write_atomic(self._path(record.job_id, "job.json"), encode(record.to_json()))

    def get(self, job_id: str) -> JobRecord | StoreError | None:
        path = self._path(job_id, "job.json")
        if self._fs.stat(path) is None:
            return None
        file = f"jobs\\{job_id}\\job.json"
        loaded = decode_record(self._fs.read_bytes(path), "JobRecord", file)
        if isinstance(loaded, StoreError):
            return loaded
        record = JobRecord.from_json(loaded)
        return record if record.job_id == job_id else corrupt("job_id", file)

    def list_ids(self) -> tuple[str, ...]:
        names = self._fs.list_dir(self._dir)
        return tuple(
            n for n in names if (s := self._fs.stat(ntpath.join(self._dir, n))) and s.is_dir
        )

    def read_journal(self, job_id: str) -> tuple[JournalRecord, ...] | StoreError:
        """A final line without ``\\n`` is a torn write and is ignored; any other unreadable
        line makes the job's records ``STORE_CORRUPT``."""
        path = self._path(job_id, "journal.jsonl")
        if self._fs.stat(path) is None:
            return ()
        file = f"jobs\\{job_id}\\journal.jsonl"
        data = self._fs.read_bytes(path)
        complete = data[: data.rfind(_NEWLINE) + 1]
        records: list[JournalRecord] = []
        for line in complete.split(_NEWLINE)[:-1]:
            loaded = decode_record(line, "JournalRecord", file)
            if isinstance(loaded, StoreError):
                return loaded
            records.append(journal_from_json(loaded))
        return tuple(records)

    def delete(self, job_id: str) -> None:
        folder = ntpath.join(self._dir, job_id)
        for name in self._fs.list_dir(folder):
            self._fs.remove(ntpath.join(folder, name))
        self._fs.remove(folder)
        self._tail_checked.discard(job_id)
