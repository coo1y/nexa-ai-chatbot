from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

pytestmark = pytest.mark.integration


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "tests/integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def contract(openapi_spec: dict[str, Any]):  # type: ignore[no-untyped-def]
    """``contract("FileMeta", payload)`` validates a payload against openapi.yaml."""

    def validate(schema_name: str, payload: Any) -> None:
        schema = {"$ref": f"#/components/schemas/{schema_name}", "components": openapi_spec["components"]}
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)

    return validate


@pytest.fixture(scope="session")
def stream_event_schemas(openapi_spec: dict[str, Any]) -> dict[str, str]:
    events = openapi_spec["paths"]["/chat/stream"]["post"]["responses"]["200"]["content"]["text/event-stream"][
        "x-stream-events"
    ]
    return {name: ref["$ref"].rsplit("/", 1)[-1] for name, ref in events.items()}
