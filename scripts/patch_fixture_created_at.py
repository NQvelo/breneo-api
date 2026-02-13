#!/usr/bin/env python3
"""
Patch data.json so app.userskill records have created_at (required on Railway).
Run from project root: python scripts/patch_fixture_created_at.py
"""
import json
import sys
from pathlib import Path

# Default created_at for UserSkill rows that don't have it
DEFAULT_CREATED_AT = "2025-01-01T12:00:00Z"

def main():
    base = Path(__file__).resolve().parent.parent
    path = base / "data.json"
    out_path = base / "data.json"  # overwrite in place (back up first if needed)

    if not path.exists():
        print(f"Not found: {path}")
        sys.exit(1)

    print(f"Loading {path}...")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("Fixture is not a JSON array.")
        sys.exit(1)

    count = 0
    for obj in data:
        if obj.get("model") == "app.userskill":
            fields = obj.get("fields", {})
            val = fields.get("created_at")
            if val is None or val == "" or (isinstance(val, str) and len(val) < 10):
                fields["created_at"] = DEFAULT_CREATED_AT
            # Always set so output has no null (handles JSON "null" / encoding)
            fields["created_at"] = fields.get("created_at") or DEFAULT_CREATED_AT
            count += 1

    print(f"Set created_at for {count} app.userskill records")

    print(f"Writing {out_path}...")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print("Done. Redeploy and run loaddata again on Railway.")

if __name__ == "__main__":
    main()
