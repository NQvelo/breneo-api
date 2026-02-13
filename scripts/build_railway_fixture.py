#!/usr/bin/env python3
"""
Build a single Railway-ready fixture: railway_upload.json.

Reads from an existing fixture (data.json or app_backup_from_render.json),
fixes required fields (e.g. UserSkill.created_at), and writes railway_upload.json.
Then commit, deploy, and on Railway run:

  python manage.py loaddata railway_upload.json -v 2

Usage (from project root):

  python scripts/build_railway_fixture.py
  python scripts/build_railway_fixture.py data.json
  python scripts/build_railway_fixture.py app_backup_from_render.json
"""
import json
import sys
from pathlib import Path

OUTPUT_FILE = "railway_upload.json"
DEFAULT_CREATED_AT = "2025-01-01T12:00:00Z"

# Models that require created_at (non-null in DB); we ensure the fixture has a value.
MODELS_REQUIRING_CREATED_AT = ("app.userskill",)


def patch_created_at(obj: dict) -> bool:
    """Set created_at if missing or null. Returns True if patched."""
    if obj.get("model") not in MODELS_REQUIRING_CREATED_AT:
        return False
    fields = obj.get("fields", {})
    val = fields.get("created_at")
    if val is None or val == "" or (isinstance(val, str) and len(val) < 10):
        fields["created_at"] = DEFAULT_CREATED_AT
        return True
    fields["created_at"] = fields.get("created_at") or DEFAULT_CREATED_AT
    return True


def main():
    base = Path(__file__).resolve().parent.parent
    if len(sys.argv) >= 2:
        input_name = sys.argv[1]
        path = (base / input_name) if not Path(input_name).is_absolute() else Path(input_name)
    else:
        # Default: try data.json, then app_backup_from_render.json
        path = base / "data.json"
        if not path.exists():
            path = base / "app_backup_from_render.json"
    out_path = base / OUTPUT_FILE

    if not path.exists():
        print(f"Input not found: {path}")
        print("Usage: python scripts/build_railway_fixture.py [input.json]")
        sys.exit(1)

    print(f"Loading {path}...")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("Fixture must be a JSON array.")
        sys.exit(1)

    patched = 0
    for obj in data:
        if patch_created_at(obj):
            patched += 1

    print(f"Patched created_at for {patched} records (models: {MODELS_REQUIRING_CREATED_AT})")
    print(f"Writing {out_path}...")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print(f"Done. Created {OUTPUT_FILE} ({len(data)} objects).")
    print("Next: commit, push, deploy, then on Railway run:")
    print(f"  python manage.py loaddata {OUTPUT_FILE} -v 2")


if __name__ == "__main__":
    main()
