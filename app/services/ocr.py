"""Read BECE results from a PDF or an image: extract text lines, then pick out subject grades."""
import io
import re
from functools import lru_cache

from app.core.calculator import CORE_SUBJECTS

# Order matters: "social studies" must be checked before "science"-like patterns.
SUBJECT_PATTERNS = [
    ("social_studies", r"social"),
    ("english", r"english"),
    ("mathematics", r"\bmath"),
    ("science", r"science"),
    ("rme", r"religious|\brme\b"),
    ("ict", r"\bict\b|information"),
    ("french", r"french"),
    ("ghanaian_language", r"ghanaian"),
    ("career_technology", r"career"),
    ("creative_arts_and_design", r"creative"),
    ("bdt", r"design and tech|\bbdt\b"),
]
_SKIP = re.compile(r"total|aggregate")
_GRADE = re.compile(r"(?<![\d.])[1-9](?![\d.])")
MAX_PDF_PAGES = 3


@lru_cache(maxsize=1)
def _engine():
    from rapidocr_onnxruntime import RapidOCR  # slow to import; load once on first use
    # Low thresholds: lone single-digit grades are otherwise often missed.
    return RapidOCR(box_thresh=0.1, text_score=0.1, unclip_ratio=2.5)


def _ocr_lines(image_bytes: bytes) -> list[str]:
    """OCR an image and join the text boxes that sit on the same row."""
    result, _elapsed = _engine()(image_bytes)
    if not result:
        return []
    items = sorted(((sum(p[1] for p in box) / 4, box[0][0], text) for box, text, _score in result))
    rows: list[list[tuple[float, str]]] = []
    last_y = None
    for y, x, text in items:
        if last_y is None or abs(y - last_y) > 12:
            rows.append([])
        rows[-1].append((x, text))
        last_y = y
    return [" ".join(t for _x, t in sorted(row)) for row in rows]


def image_lines(content: bytes) -> list[str]:
    from PIL import Image
    try:
        Image.open(io.BytesIO(content)).verify()
    except Exception:
        raise ValueError("The image could not be read.") from None
    return _ocr_lines(content)


def pdf_lines(content: bytes) -> list[str]:
    import pdfplumber
    import pypdfium2
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join((page.extract_text() or "") for page in pdf.pages[:MAX_PDF_PAGES])
    except Exception:
        raise ValueError("The PDF could not be read.") from None
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if lines:
        return lines
    # Scanned PDF: no text layer, so render the pages and OCR them.
    pdf = pypdfium2.PdfDocument(content)
    lines = []
    for index in range(min(len(pdf), MAX_PDF_PAGES)):
        buffer = io.BytesIO()
        pdf[index].render(scale=2).to_pil().save(buffer, format="PNG")
        lines += _ocr_lines(buffer.getvalue())
    return lines


def grades_from_lines(lines: list[str]) -> dict:
    """Find 'subject ... grade' rows. The grade is the last standalone digit 1-9 on the row."""
    found: dict[str, int] = {}
    for line in lines:
        lowered = line.lower()
        if _SKIP.search(lowered):
            continue
        subject = next((name for name, pattern in SUBJECT_PATTERNS if re.search(pattern, lowered)), None)
        digits = _GRADE.findall(lowered)
        if subject and digits and subject not in found:
            found[subject] = int(digits[-1])
    data = {s: found.pop(s) for s in CORE_SUBJECTS if s in found}
    data["electives"] = found
    return data
