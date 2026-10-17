"""Single entry point: grades in, aggregate + eligible schools out."""
from app.core.calculator import compute_aggregate, qualifying_categories
from app.tools.matcher import DEFAULT_DATA, School, load_schools, match_schools


def recommend(
    core: dict[str, int],
    electives: dict[str, int],
    gender: str | None = None,
    region: str | None = None,
    residency: str | None = None,
    programme: str | None = None,
    schools: list[School] | None = None,
) -> dict:
    aggregate = compute_aggregate(core, electives)
    categories = qualifying_categories(aggregate)
    if schools is None:
        schools = load_schools(DEFAULT_DATA)
    matches = match_schools(aggregate, schools, gender, region, residency, programme)
    by_category: dict[str, list[dict]] = {c: [] for c in categories}
    for s in matches:
        by_category[s.category].append(
            {"school": s.name, "region": s.region, "gender": s.gender,
             "residency": s.residency, "programmes": list(s.programmes)}
        )
    return {
        "aggregate": aggregate,
        "qualifying_categories": categories,
        "total_schools": len(matches),
        "schools_by_category": by_category,
    }
