# SHS School Recommender

Given a BECE candidate's grades, computes the aggregate (4 core subjects + best 2 electives),
works out which school categories (A/B/C) they qualify for, and lists the eligible SHSs and programmes.

> **Note:** the category aggregate limits in `app/core/calculator.py` are placeholders
> and must be replaced with the official CSSPS bands. School data comes from a 2019 list
> (`data/schools.csv`, extracted by `scripts/extract_pdf.py`) and has not been fully verified.

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
