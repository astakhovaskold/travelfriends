"""Protect boundaries rather than implementation-specific method names."""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def test_application_layers_do_not_execute_queries_or_import_transport():
    violations = []
    for directory in ("services", "api", "integrations/telegram"):
        for path in (APP / directory).glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if (
                        directory == "services"
                        and isinstance(node, ast.Import)
                        and any(alias.name.startswith("app.api") for alias in node.names)
                ):
                    violations.append(f"{path.name}:{node.lineno} imports API")
                if (
                        directory == "services"
                        and isinstance(node, ast.ImportFrom)
                        and (node.module or "").startswith("app.api")
                ):
                    violations.append(f"{path.name}:{node.lineno} imports API")
                if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr in ("execute", "exec_driver_sql", "commit", "rollback")
                ):
                    violations.append(f"{path.name}:{node.lineno} executes or ends a transaction")
    assert not violations, "\n".join(violations)


def test_repositories_do_not_own_transactions_or_business_errors():
    violations = []
    for path in (APP / "repositories").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                    ("app.services", "app.api", "fastapi", "aiogram")
            ):
                violations.append(f"{path.name}:{node.lineno} imports application or transport")
            if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("commit", "rollback")
            ):
                violations.append(f"{path.name}:{node.lineno} ends a transaction")
            if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in ("db", "HTTPException")
            ):
                violations.append(f"{path.name}:{node.lineno} owns transaction or business error")
    assert not violations, "\n".join(violations)
