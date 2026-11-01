"""Parse an uploaded results file (JSON or CSV) into Grades."""
import csv
import io
import json

from pydantic import ValidationError

from app.core.calculator import CORE_SUBJECTS
from app.schemas import Grades

MAX_UPLOAD_BYTES = 100_000          # csv / json
MAX_BINARY_BYTES = 5_000_000        # pdf / images
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")


class ResultsParseError(ValueError):
    pass


def _from_scan(name: str, content: bytes) -> dict:
    from app.services import ocr
    try:
        lines = ocr.pdf_lines(content) if name.endswith(".pdf") else ocr.image_lines(content)
    except ValueError as exc:
        raise ResultsParseError(str(exc)) from None
    data = ocr.grades_from_lines(lines)
    if not lines or len(data) <= 1:
        raise ResultsParseError("No grades could be read from this file. Please enter your grades manually.")
    return data


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
    name = filename.lower()
    scanned = name.endswith((".pdf", *IMAGE_EXTENSIONS))
    if len(content) > (MAX_BINARY_BYTES if scanned else MAX_UPLOAD_BYTES):
        raise ResultsParseError("File is too large.")
    if scanned:
        data = _from_scan(name, content)
        try:
            return Grades(**data)
        except ValidationError as exc:
            raise ResultsParseError(_describe(exc) + ". Please check the file or enter your grades manually.") from None
    if not name.endswith((".csv", ".json")):
        raise ResultsParseError("Only .csv, .json, .pdf, .png, .jpg and .jpeg files are supported.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ResultsParseError("File must be UTF-8 text.") from None

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
        raise ResultsParseError("Only .csv, .json, .pdf, .png, .jpg and .jpeg files are supported.")

    try:
        return Grades(**data)
    except ValidationError as exc:
        raise ResultsParseError(_describe(exc)) from None


def _describe(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
