"""Search and inspect AIMRAN Library's 814 animated UI components (HTML/CSS & React)."""
import argparse
import json
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
COMPONENTS_DIR = SKILL_DIR / "components"
INDEX_PATH = SKILL_DIR / "references" / "index.json"


def main():
    parser = argparse.ArgumentParser(description="Search AIMRAN Library 814 animated UI components")
    parser.add_argument("--category", "-c", help="Category ID (e.g., liquid-glass, loaders, buttons, cards, toasts, microinteractions)")
    parser.add_argument("--query", "-q", help="Search keyword in id, name, or description")
    parser.add_argument("--id", "-i", help="Get full HTML/CSS/JS/React source for a specific component ID")
    parser.add_argument("--html-only", action="store_true", help="Only return pure HTML + CSS components")
    args = parser.parse_args()

    if args.id:
        for f in sorted(COMPONENTS_DIR.glob("*.json")):
            items = json.loads(f.read_text(encoding="utf-8"))
            for item in items:
                if item["id"] == args.id:
                    print(json.dumps(item, indent=2, ensure_ascii=False))
                    return
        print(f"Component '{args.id}' not found.")
        return

    categories = [args.category] if args.category else [p.stem for p in sorted(COMPONENTS_DIR.glob("*.json"))]
    for cat in categories:
        cat_file = COMPONENTS_DIR / f"{cat}.json"
        if not cat_file.exists():
            continue
        items = json.loads(cat_file.read_text(encoding="utf-8"))
        if args.html_only:
            items = [x for x in items if x.get("html")]
        if args.query:
            q = args.query.lower()
            items = [x for x in items if q in x["id"].lower() or q in x["name"].lower() or q in x.get("description", "").lower()]
        if items:
            print(f"=== {cat} ({len(items)} matches) ===")
            for x in items[:15]:
                print(f"  [{x['id']}] {x['name']} ({x['stack']}) - {x.get('description', '')[:80]}")


if __name__ == "__main__":
    main()

