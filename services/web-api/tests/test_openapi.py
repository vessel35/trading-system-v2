"""Guards for the committed frontend OpenAPI contract."""

import json
from pathlib import Path

from web_api.main import app

REPOSITORY_ROOT = Path(__file__).parents[3]
COMMITTED_OPENAPI = REPOSITORY_ROOT / "apps" / "web" / "src" / "api" / "openapi.json"


def test_committed_openapi_matches_application_schema() -> None:
    generated = json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"
    committed = COMMITTED_OPENAPI.read_text(encoding="utf-8")

    assert generated == committed, (
        "apps/web/src/api/openapi.json is stale; regenerate it with "
        "services/web-api/scripts/export_openapi.py"
    )
