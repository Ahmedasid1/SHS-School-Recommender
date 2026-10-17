"""CLI: python -m app.cli --english 2 --maths 3 --science 2 --social 3 --electives rme=4 ict=2"""
import argparse

from app.core.recommender import recommend


def main() -> None:
    p = argparse.ArgumentParser(description="SHS school recommender")
    p.add_argument("--english", type=int, required=True)
    p.add_argument("--maths", type=int, required=True)
    p.add_argument("--science", type=int, required=True)
    p.add_argument("--social", type=int, required=True)
    p.add_argument("--electives", nargs="+", required=True, metavar="SUBJECT=GRADE")
    p.add_argument("--gender", choices=["male", "female"])
    p.add_argument("--region")
    p.add_argument("--residency", choices=["day", "boarding"])
    p.add_argument("--programme")
    p.add_argument("--limit", type=int, default=10, help="schools to show per category")
    a = p.parse_args()

    try:
        electives = {k: int(v) for k, v in (e.split("=", 1) for e in a.electives)}
        result = recommend(
            {"english": a.english, "mathematics": a.maths, "science": a.science, "social_studies": a.social},
            electives, a.gender, a.region, a.residency, a.programme,
        )
    except ValueError as exc:
        p.error(str(exc))

    print(f"Aggregate: {result['aggregate']}")
    print(f"Qualifies for categories: {', '.join(result['qualifying_categories'])}")
    print(f"Eligible schools: {result['total_schools']}")
    for cat, items in result["schools_by_category"].items():
        print(f"\nCategory {cat} ({len(items)})")
        for s in items[: a.limit]:
            print(f"  {s['school']} [{s['region']}, {s['gender']}] - {', '.join(s['programmes'])}")
        if len(items) > a.limit:
            print(f"  ... and {len(items) - a.limit} more")


if __name__ == "__main__":
    main()
