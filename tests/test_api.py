from fastapi.testclient import TestClient

from app.core.recommender import recommend
from main import app

CORE = {"english": 2, "mathematics": 3, "science": 2, "social_studies": 3}


def test_recommend_function():
    r = recommend(CORE, {"rme": 4, "ict": 2}, region="Ashanti")
    assert r["aggregate"] == 16
    assert r["estimated_categories"] == ["B", "C"]
    assert "unofficial aggregate cutoffs" in r["category_estimate_note"]
    assert "not a CSSPS placement prediction" in r["placement_note"]
    assert r["total_schools"] == sum(len(v) for v in r["schools_by_category"].values())


def test_api():
    c = TestClient(app)
    body = {**CORE, "electives": {"rme": 4, "ict": 2}, "gender": "female"}
    r = c.post("/recommend", json=body)
    assert r.status_code == 200 and r.json()["aggregate"] == 16
    assert r.json()["estimated_categories"] == ["B", "C"]
    bad = c.post("/recommend", json={**body, "english": 12})
    assert bad.status_code == 422
