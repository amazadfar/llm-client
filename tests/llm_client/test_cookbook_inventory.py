from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COOKBOOK_DIR = ROOT / "examples"
README = ROOT / "examples" / "README.md"
RUNNER = ROOT / "scripts" / "ci" / "run_llm_client_examples.py"


def _numbered_examples() -> list[str]:
    return sorted(path.name for path in COOKBOOK_DIR.glob("[0-9][0-9]_*.py"))


def _runner_examples() -> set[str]:
    module = ast.parse(RUNNER.read_text(encoding="utf-8"))
    values: dict[str, list[str]] = {}
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {"CORE_EXAMPLES", "APPLICATION_EXAMPLES"}:
                values[target.id] = list(ast.literal_eval(node.value))
    return set(values["CORE_EXAMPLES"]) | set(values["APPLICATION_EXAMPLES"])


def _uncapped_generation_calls() -> list[str]:
    failures: list[str] = []
    for path in sorted(COOKBOOK_DIR.glob("[0-9][0-9]_*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if not isinstance(node, ast.Call):
                continue
            keyword_names = {keyword.arg for keyword in node.keywords if keyword.arg}
            has_expanded_kwargs = any(keyword.arg is None for keyword in node.keywords)
            if isinstance(node.func, ast.Name) and node.func.id in {
                "ContentRequestEnvelope",
                "RequestSpec",
                "extract_structured",
            }:
                if "max_tokens" not in keyword_names and not has_expanded_kwargs:
                    failures.append(f"{path.name}:{node.lineno} {node.func.id}")
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr not in {
                "complete",
                "run",
                "stream",
                "respond_with_web_search",
                "respond_with_file_search",
                "respond_with_code_interpreter",
                "respond_with_shell",
                "respond_with_apply_patch",
                "respond_with_computer_use",
                "respond_with_image_generation",
                "respond_with_remote_mcp",
                "respond_with_connector",
            }:
                continue
            if node.func.attr.startswith("respond_with_"):
                if "max_tokens" not in keyword_names and not has_expanded_kwargs:
                    failures.append(f"{path.name}:{node.lineno} hosted {node.func.attr}")
                continue
            is_agent_call = (
                isinstance(node.func.value, ast.Name)
                and (
                    node.func.value.id == "agent"
                    or node.func.value.id.endswith("_agent")
                )
            )
            if is_agent_call and "max_tokens" not in keyword_names:
                failures.append(f"{path.name}:{node.lineno} agent {node.func.attr}")
                continue
            directly_supplies_messages = bool(node.args) and isinstance(
                node.args[0],
                (ast.List, ast.Tuple),
            )
            directly_supplies_messages = directly_supplies_messages or "messages" in keyword_names
            if directly_supplies_messages and "max_tokens" not in keyword_names:
                failures.append(f"{path.name}:{node.lineno} direct {node.func.attr}")
    return failures


def test_cookbook_examples_exist() -> None:
    assert len(_numbered_examples()) >= 62


def test_cookbook_readme_references_all_examples() -> None:
    readme = README.read_text(encoding="utf-8")
    for name in _numbered_examples():
        assert name in readme


def test_cookbook_runner_references_all_examples() -> None:
    assert _runner_examples() == set(_numbered_examples())
    assert "--subset core" in README.read_text(encoding="utf-8")
    assert "--subset application" in README.read_text(encoding="utf-8")


def test_cookbook_generation_calls_have_output_budgets() -> None:
    assert _uncapped_generation_calls() == []
