import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_fixture(name: str) -> Any:
    return load_json(FIXTURES / name)


SHARED_RISK_CASES: list[dict[str, Any]] = load_json(REPO_ROOT / "shared" / "risk_cases.json")[
    "cases"
]
