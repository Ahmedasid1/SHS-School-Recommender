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

Docker: `docker compose up --build`

## Tests

```
pytest
```
