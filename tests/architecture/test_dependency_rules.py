"""Architecture fitness functions — enforce Clean Architecture dependency rules.

Rules:
- signals/, scoring/, ranking/, alerts/ must NOT import from api/ or jobs/
- api/ must NOT import from signals/, scoring/, ranking/, alerts/ directly
  (must go through storage/ only)
- normalization/ must NOT import from storage/, signals/, scoring/, ranking/, alerts/
- ingestion/ must NOT import from signals/, scoring/, ranking/, alerts/, api/
- storage/ must NOT import from signals/, scoring/, ranking/, alerts/, api/, ingestion/
"""

import ast
from pathlib import Path

APP_DIR = Path(__file__).parent.parent.parent / "backend" / "app"

FORBIDDEN_IMPORTS: dict[str, list[str]] = {
    "signals": ["app.api", "app.jobs"],
    "scoring": ["app.api", "app.jobs"],
    "ranking": ["app.api", "app.jobs"],
    "alerts": ["app.api", "app.jobs"],
    "normalization": ["app.storage", "app.signals", "app.scoring", "app.ranking", "app.alerts"],
    "ingestion": ["app.signals", "app.scoring", "app.ranking", "app.alerts", "app.api"],
    "storage": ["app.signals", "app.scoring", "app.ranking", "app.alerts", "app.api", "app.ingestion"],
}


def get_imports(filepath: Path) -> list[str]:
    """Return all module names imported in a Python file."""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def test_no_forbidden_imports() -> None:
    """No module may import from a layer it depends on in the wrong direction."""
    violations: list[str] = []

    for module, forbidden in FORBIDDEN_IMPORTS.items():
        module_dir = APP_DIR / module
        if not module_dir.exists():
            continue
        for pyfile in module_dir.rglob("*.py"):
            imports = get_imports(pyfile)
            for imp in imports:
                for forbidden_prefix in forbidden:
                    if imp == forbidden_prefix or imp.startswith(forbidden_prefix + "."):
                        rel = pyfile.relative_to(APP_DIR.parent.parent)
                        violations.append(
                            f"{rel}: imports '{imp}' (forbidden for module '{module}')"
                        )

    assert not violations, (
        "Architecture boundary violations detected:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
