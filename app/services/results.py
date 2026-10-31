"""Parse an uploaded results file (JSON or CSV) into Grades."""
import csv
import io
import json

from pydantic import ValidationError

from app.core.calculator import CORE_SUBJECTS
from app.schemas import Grades

MAX_UPLOAD_BYTES = 100_000


class ResultsParseError(ValueError):
    pass


def _from_csv(text: str) -> dict:
    rows = csv.reader(io.StringIO(text))
    data: dict = {"electives": {}}
    for i, row in enumerate(rows, 1):
        if not row or not "".join(row).strip():
            continue
        if len(row) != 2:
            raise ResultsParseError(f"Line {i}: expected 'subject,grade'")
        subject, grade = row[0].strip().lower().replace(" ", "_"), row[1].strip()
        if i == 1 and subject == "subject":
            continue
        try:
            value = int(grade)
        except ValueError:
            raise ResultsParseError(f"Line {i}: grade must be a whole number") from None
        if subject in CORE_SUBJECTS:
            data[subject] = value
        else:
            data["electives"][subject] = value
    return data


def parse_upload(filename: str, content: bytes) -> Grades:
    if len(content) > MAX_UPLOAD_BYTES:
        raise ResultsParseError("File is too large.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ResultsParseError("File must be UTF-8 text.") from None

    name = filename.lower()
    if name.endswith(".json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise ResultsParseError("Invalid JSON.") from None
        if not isinstance(data, dict):
            raise ResultsParseError("JSON must be an object.")
    elif name.endswith(".csv"):
        data = _from_csv(text)
    else:
        raise ResultsParseError("Only .csv and .json files are supported.")

    try:
        return Grades(**data)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise ResultsParseError(problems) from None
