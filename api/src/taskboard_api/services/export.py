"""CSV export of a project's tasks."""

import csv
import io
from collections.abc import Iterable, Mapping
from uuid import UUID

from taskboard_api.models import Task, User

CSV_COLUMNS = (
    "id",
    "title",
    "description",
    "status",
    "priority",
    "assignee",
    "assignee_email",
    "due_date",
    "labels",
    "created_at",
    "updated_at",
)
# A leading character that makes spreadsheet software evaluate the cell as a formula.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def neutralise(value: str) -> str:
    """Prevent CSV/formula injection by prefixing risky cells with an apostrophe."""
    if value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


class TaskCsvWriter:
    def render(self, tasks: Iterable[Task], users: Mapping[UUID, User]) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        writer.writerow(CSV_COLUMNS)
        for task in tasks:
            assignee = users.get(task.assignee_id) if task.assignee_id else None
            row = (
                str(task.id),
                task.title,
                task.description,
                task.status.value,
                task.priority.value,
                assignee.display_name if assignee else "",
                assignee.email if assignee else "",
                task.due_date.isoformat() if task.due_date else "",
                ";".join(task.labels),
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
            )
            writer.writerow([neutralise(cell) for cell in row])
        return buffer.getvalue()
