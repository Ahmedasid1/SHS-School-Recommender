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

## Setup

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

CLI:

```
python -m app.cli --english 2 --maths 3 --science 2 --social 3 --electives rme=4 ict=2 --region ashanti
```

API:

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
(agric, business, technical, home_economics, visual_arts, general_arts, science).

Docker (starts Ollama, pulls the models, builds the index, serves the API on port 8000; the first run downloads the models):
`docker compose up --build`

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
is by environment variable (see `.env.example`).

Known limitation: `llama3.2` (3B) is a small model. It sometimes chains tool calls badly or writes a
tool call as text, so the app runs one tool per step, recovers text-form calls, validates every
argument, and suppresses leaked tool text. Answers about schools should still be checked against GES.

## Tests

```
pytest
```

The assistant tests use a scripted fake model, so they run without Ollama.
