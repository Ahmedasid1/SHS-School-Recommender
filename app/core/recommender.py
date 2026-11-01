"""Single entry point: grades in, aggregate + eligible schools out."""
from app.core.calculator import compute_aggregate, estimated_categories
from app.tools.matcher import DEFAULT_DATA, School, load_schools, match_schools

# Recommend schools based on student grades and preferences.
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
    if schools is None:
        schools = load_schools(DEFAULT_DATA)
    categories = estimated_categories(aggregate)
    matches = match_schools(aggregate, schools, gender, region, residency, programme)
    by_category: dict[str, list[dict]] = {c: [] for c in categories}
    for s in matches:
        by_category[s.category].append(
            {"school": s.name, "region": s.region, "gender": s.gender,
             "residency": s.residency, "programmes": list(s.programmes)}
        )
    return {
        "aggregate": aggregate,
        "estimated_categories": categories,
        "total_schools": len(matches), 
        "schools_by_category": by_category,
        "category_estimate_note": (
            "Categories are estimated using unofficial aggregate cutoffs, "
            "not official CSSPS rules."
        ),
        "placement_note": (
            "This estimate is not a CSSPS placement prediction or an admission guarantee. "
            "Placement also depends on choices, performance, and available spaces."
        ),
    }
