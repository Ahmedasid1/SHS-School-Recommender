# Document ingestion for the RAG system: load, clean, chunk, and attach metadata.
"""Document ingestion: load, clean, chunk, and attach metadata."""
import re
from dataclasses import dataclass, field
from pathlib import Path

from app import config
from app.tools.matcher import School

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}
GES_SOURCE = "GES 2019 SHS list (data/schools.csv)"

# Data structure representing a text chunk with associated metadata.
@dataclass 
class Chunk:
    id: str
    text: str
    metadata: dict = field(default_factory=dict)

# Clean and normalise text for consistent chunking.
def clean_text(text: str) -> str:
    """Normalise whitespace and line endings while keeping paragraph breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# Split an over-long paragraph into smaller pieces based on sentence boundaries.
def _split_long(paragraph: str, size: int) -> list[str]:
    """Split an over-long paragraph on sentence boundaries, hard-slicing only as a last resort."""
    pieces, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
        while len(sentence) > size:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:size])
            sentence = sentence[size:]
        if current and len(current) + len(sentence) + 1 > size:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


# Pack paragraphs into chunks of at most ~size characters, carrying a short overlap forward.
def chunk_text(text: str, size: int = config.CHUNK_SIZE, overlap: int = config.CHUNK_OVERLAP) -> list[str]:
    """Pack paragraphs into chunks of at most ~size characters, carrying a short overlap forward."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", clean_text(text)) if p.strip()]
    chunks, current = [], ""
    for paragraph in paragraphs:
        for piece in _split_long(paragraph, size) if len(paragraph) > size else [paragraph]:
            if current and len(current) + len(piece) + 2 > size:
                chunks.append(current)
                tail = current[-overlap:] if overlap else ""
                tail = tail[tail.find(" ") + 1:] if " " in tail else tail
                current = f"{tail}\n\n{piece}".strip() if tail else piece
            else:
                current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks

# Read the content of a file, supporting PDF and text files.
def _read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return "\n\n".join(page.extract_text() or "" for page in pdf.pages)
    return path.read_text(encoding="utf-8")

# Generate chunks from all documents in the knowledge directory.
def document_chunks(knowledge_dir: Path = config.KNOWLEDGE_DIR) -> list[Chunk]:
    """Chunks from every supported file in the knowledge directory."""
    chunks: list[Chunk] = []
    if not knowledge_dir.is_dir():
        return chunks
    for path in sorted(knowledge_dir.iterdir()):
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        text = clean_text(_read_file(path))
        if not text:
            continue
        for i, piece in enumerate(chunk_text(text)):
            chunks.append(Chunk(
                id=f"{path.name}#{i}",
                text=piece,
                metadata={"source": path.name, "source_type": "document", "chunk_index": i},
            ))
    return chunks


# Generate chunks for each school, capturing key details for retrieval.
def school_chunks(schools: list[School]) -> list[Chunk]:
    """One short profile chunk per school so retrieval can answer questions about individual schools."""
    chunks: list[Chunk] = []
    for i, school in enumerate(schools):
        text = f"{school.name}\n{school.address}\n{school.category}\n{school.eligibility_bands}"
        chunks.append(Chunk(
            id=f"{school.name}#{i}",
            text=text,
            metadata={"source": GES_SOURCE, "source_type": "school", "chunk_index": i},
        ))
    return chunks
    chunks = []
    for i, s in enumerate(schools):
        programmes = ", ".join(p.replace("_", " ") for p in s.programmes) or "none listed"
        text = (
            f"{s.name} is a Category {s.category} {s.gender} school in the {s.region} region "
            f"({s.residency}). Programmes offered: {programmes}."
        )
        chunks.append(Chunk(
            id=f"school#{i}",
            text=text,
            metadata={"source": GES_SOURCE, "source_type": "school_profile", "school": s.name,
                      "category": s.category, "region": s.region},
        ))
    return chunks
