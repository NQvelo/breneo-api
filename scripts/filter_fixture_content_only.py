#!/usr/bin/env python
"""
Read app_backup_from_render.json and write a fixture with only "content" models
that do not depend on auth.User (so loaddata works into a fresh local DB).
"""
import json
import sys
from pathlib import Path

# Models that don't have FK to User - safe to load without auth.User
CONTENT_MODELS = {
    "app.skill",
    "app.careercategory",
    "app.careerquestion",
    "app.careeroption",
    "app.dynamictechquestion",
    "app.dynamicsoftskillsquestion",
    "app.job",
}

# Order matters for FKs: category -> question -> option; skill before job M2M
ORDER = [
    "app.skill",
    "app.careercategory",
    "app.careerquestion",
    "app.careeroption",
    "app.dynamictechquestion",
    "app.dynamicsoftskillsquestion",
    "app.job",
]


def main():
    base = Path(__file__).resolve().parent.parent
    path_in = base / "app_backup_from_render.json"
    path_out = base / "app_backup_content_only.json"

    if not path_in.exists():
        print(f"Missing: {path_in}", file=sys.stderr)
        sys.exit(1)

    with open(path_in) as f:
        data = json.load(f)

    by_model = {}
    for obj in data:
        model = obj["model"]
        by_model.setdefault(model, []).append(obj)

    out = []
    for model in ORDER:
        out.extend(by_model.get(model, []))

    with open(path_out, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote {len(out)} records to {path_out}")


if __name__ == "__main__":
    main()
