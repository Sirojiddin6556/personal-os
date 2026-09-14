import pytest
from src.main import app


def test_health():
    """Placeholder health test for CI verification."""
    assert True


def test_openapi_schema_and_routes_integrity():
    """Verify that OpenAPI schema generates without errors and all routes are present."""
    openapi_schema = app.openapi()
    assert openapi_schema is not None
    assert "paths" in openapi_schema

    paths = openapi_schema["paths"]
    # Check critical domain endpoints
    assert "/v1/finance/accounts/{account_id}/reconcile" in paths
    assert "/v1/tasks/{task_id}/complete" in paths
    assert "/v1/knowledge/search" in paths
    assert "/v1/integrations/telegram/connect" in paths
    assert "/v1/integrations/google/configure" in paths
    assert "/v1/planner/habits/{habit_id}/toggle" in paths
    assert "/v1/projects" in paths
    assert "/v1/goals" in paths
    assert "/v1/milestones" in paths


def test_docs_api_markdown_matches_openapi_routes():
    """Verify that every endpoint documented in docs/api.md exists in app.openapi() routes."""
    import re
    from pathlib import Path

    # Look for docs/api.md in repository root or relative paths
    candidates = [
        Path("../../docs/api.md").resolve(),
        Path("../docs/api.md").resolve(),
        Path("docs/api.md").resolve(),
        Path(__file__).parents[3] / "docs" / "api.md",
    ]
    api_md_path = next((p for p in candidates if p.exists()), None)
    assert api_md_path is not None, "docs/api.md file not found"

    content = api_md_path.read_text(encoding="utf-8")
    pattern = r"\b(GET|POST|PUT|PATCH|DELETE)\s+([/\w\-{}]+)"
    matches = re.findall(pattern, content)
    assert len(matches) > 30, f"Expected at least 30 documented endpoints, found {len(matches)}"

    paths = app.openapi()["paths"]
    missing = []
    for method, path in matches:
        if not path.startswith("/v1"):
            continue
        clean_path = path.rstrip("/")
        found = any(
            op_path.rstrip("/") == clean_path and method.lower() in paths[op_path]
            for op_path in paths
        )
        if not found:
            missing.append(f"{method} {path}")

    assert not missing, f"The following endpoints in docs/api.md do not exist in FastAPI app.openapi(): {missing}"

    # Bidirectional domain coverage check: ensure all main API domain prefixes are documented
    documented_paths_str = "\n".join(path for _, path in matches)
    required_prefixes = [
        "/v1/tasks",
        "/v1/finance/accounts",
        "/v1/finance/transactions",
        "/v1/knowledge/notes",
        "/v1/planner/agenda",
        "/v1/planner/habits",
        "/v1/calendar/events",
        "/v1/projects",
        "/v1/goals",
        "/v1/milestones",
        "/v1/advisor",
        "/v1/integrations/google",
        "/v1/integrations/telegram",
    ]
    for prefix in required_prefixes:
        assert prefix in documented_paths_str, f"Required domain prefix {prefix} is missing from docs/api.md"


