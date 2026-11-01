# SHS School Recommender

Given a BECE candidate's grades, computes the aggregate (4 core subjects + best 2 electives),
estimates eligible school categories using aggregate cutoffs, and lists matching SHSs and programmes.

> **Important:** the Category A/B/C aggregate cutoffs are an unofficial heuristic, not an official
> CSSPS rule. CSSPS categories classify schools, and placement depends on candidate performance,
> school/programme choices, and available spaces. This tool does not predict placement or guarantee
> admission.

## School data

`data/schools.csv` contains 584 schools from the 2019 Ghana Education Service (GES) list. The
project owner confirms this is the updated GES data being used for the project. The repository
does not record when the source file was obtained. The data was extracted with
`scripts/extract_pdf.py`; automated tests check for missing fields, duplicate school names,
and invalid category, gender, residency, or programme values. These checks validate the CSV's
structure and consistency, not the source's accuracy.

The extraction and cleaning is also documented step by step in
`notebooks/clean_schools_pdf.ipynb`, which reads `data/raw/ges_shs_list.pdf` and writes
`data/schools_notebook.csv` (it needs `pdfplumber`, plus `jupyter` to run it).

The current heuristic uses maximum aggregates of 10 for Category A, 20 for Category B, and 54
for Category C. A candidate is estimated to meet a category cutoff when their aggregate is at or
below that value. These values are configurable in `app/core/calculator.py`; they should not be
interpreted as official eligibility or placement cutoffs. The API labels the output
`estimated_categories` and includes a `category_estimate_note` and `placement_note`.

## Overview

| Part | Where | What it does |
|------|-------|--------------|
| Chat page | `app/static/chat.html`, served at `/` | Enter or upload BECE grades, confirm them, chat with the assistant |
| Results API | `app/api/routes.py`, `app/services/results.py` | `/results/manual` and `/results/upload` validate grades and return the aggregate |
| Grades contract | `app/schemas.py` | The single `Grades` model used by manual entry, uploads, `/recommend` and `/chat` |
| Assistant | `app/services/assistant.py`, `app/tools/` | Tool-calling loop over a local Ollama model |
| Core logic | `app/core/`, `app/tools/matcher.py` | Aggregate calculation and school matching over `data/schools.csv` |

## Setup

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` includes `python-multipart`, which FastAPI needs for file uploads, and
`rapidocr-onnxruntime` for reading images and scanned PDFs.

## Usage

CLI:

```
python -m app.cli --english 2 --maths 3 --science 2 --social 3 --electives rme=4 ict=2 --region ashanti
```

API and chat page (open `http://localhost:8000/`; interactive API docs are at `/docs`):

```
uvicorn main:app --reload
```

`POST /recommend` with JSON:

```json
{"english": 2, "mathematics": 3, "science": 2, "social_studies": 3,
 "electives": {"rme": 4, "ict": 2}, "gender": "female", "region": "Ashanti",
 "residency": "day", "programme": "science"}
```

Optional filters: `gender` (male/female), `region`, `residency` (day/boarding), `programme`
(agric, business, technical, home_economics, visual_arts, general_arts, science). `region` must be
a region name from the data (for example `Greater Accra`); `Accra` is accepted as an alias.

Grades are validated by `app/schemas.py`: the four core subjects must be integers from 1 to 9, at
least 2 electives are required (grades 1-9), and elective names are lowercased with spaces turned
into underscores.

Docker (starts Ollama, pulls the models, builds the index, serves the API on port 8000; the first run downloads the models):

```
docker compose up --build
```

## AI assistant (Ollama + RAG)

`POST /ask` with `{"message": "..."}` returns `{"answer", "sources", "tool_calls"}`. A local Ollama
model (default `llama3.2`) chooses tools and writes the explanation; all facts come from code or
retrieval:

| Tool | Backed by |
|------|-----------|
| `compute_aggregate` | the aggregate calculator |
| `find_schools` / `recommend_schools` | the school matcher over `data/schools.csv` |
| `search_knowledge` | RAG over `data/knowledge/` and per-school profiles |

RAG: documents (`.md`, `.txt`, `.pdf`) in `data/knowledge/` are chunked (800 characters, 100 overlap),
embedded with `nomic-embed-text`, and stored in `data/index/index.json` (cosine search, cached in
memory). Passages scoring below `RAG_MIN_SCORE` (default 0.65, calibrated on sample queries) are
discarded, so the assistant says it has no information instead of guessing. Sources are returned
with each answer.

Local run (Ollama must be running with the models pulled):

```
ollama pull llama3.2
ollama pull nomic-embed-text
python -m app.rag.build_index
uvicorn main:app --reload
```

Re-run `python -m app.rag.build_index` after changing anything in `data/knowledge/`. Configuration
is by environment variable (`LLM_MODEL`, `EMBED_MODEL`, `PROMPT_VERSION`, ...; see `.env.example`).
The chat model must support Ollama tool calling: for example `llama3:latest` is rejected with
"does not support tools", while `llama3.2` works. If you change `EMBED_MODEL`, rebuild the index.

Known limitation: `llama3.2` (3B) is a small model. It sometimes chains tool calls badly, writes a
tool call as text, or sends junk arguments (such as the string `"null"` for an unused filter). The
app therefore runs one tool per step, recovers text-form calls (including slightly malformed JSON),
validates every argument, treats null-like filters as unset, suppresses leaked tool text, and (in
`/chat`) fills in the user's confirmed grades itself instead of trusting the model's arguments. It
can still add school names of its own, so check answers about schools against GES.

## Chat page and results upload

Open `http://localhost:8000/` after starting the server. Enter BECE grades manually or upload a
results file, press **Confirm Grades** (you see the aggregate and estimated categories), then ask
questions. Confirmed grades are sent with every chat message and used by the assistant's tools, so
you are not asked for them again. Chat sessions (grades and the last 20 messages, up to 500
sessions) are kept in memory only and are lost on restart.

`POST /ask` is stateless; `POST /chat` adds the session and confirmed grades.

| Endpoint | Purpose |
|----------|---------|
| `POST /results/manual` | JSON grades (same shape as `/recommend`); returns the normalised grades, aggregate and estimated categories |
| `POST /results/upload` | multipart `file` (`.csv`/`.json`, UTF-8, max 100 KB; or `.pdf`/`.png`/`.jpg`/`.jpeg`, max 5 MB); parsed in memory, never stored; same response |
| `POST /chat` | `{"session_id", "message", "grades"?}`; returns `{"answer", "sources", "tool_calls"}` |

Upload formats: JSON with the same shape as `/recommend`, or CSV with `subject,grade` rows. The four
core subjects are `english`, `mathematics`, `science` and `social_studies`; every other row is an
elective (at least 2 are required, grades 1-9):

```csv
subject,grade
English,2
Mathematics,3
Science,2
Social Studies,3
RME,4
ICT,2
```

PDF and image results (`.pdf`, `.png`, `.jpg`, `.jpeg`, max 5 MB) are read by `app/services/ocr.py`:
text PDFs are read with `pdfplumber`; scanned PDFs and images go through `rapidocr-onnxruntime`
(pure pip, no system OCR install; its models are bundled). Each row is matched to a subject name
(for example "Integrated Science" -> `science`) and the last single digit 1-9 on the row is taken
as the grade; rows containing "total" or "aggregate" are ignored. OCR is not perfectly reliable
(it can miss a lone digit), so the page fills the form with what was read and asks the user to
check it. If too little is read, the API returns 422 and the user enters grades manually. Subject
names the reader does not know (see `SUBJECT_PATTERNS`) are ignored. Uploads are parsed in memory
and are not stored, and the results are personal data, so avoid logging them.

## Tests

```
pytest
```

The assistant tests use a scripted fake model, so they run without Ollama. `tests/test_results.py`
covers uploads, manual entry, the chat session, the chat page and the tool-argument recovery.
