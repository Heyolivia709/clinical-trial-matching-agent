"""Module layering, enforced rather than documented.

Specification section 12 defines three deep modules behind small interfaces.
Specification section 15 and ADR 0007 require the report to be generated from
frozen artifacts and never to become a dependency of a reasoning module.
Specification section 4.4 requires that the matching system never receive a
Scenario Manifest.

All three are structural claims, so they are checked structurally. A comment
saying "the report is built last" does not survive a hurried afternoon; an
import that fails CI does.

`match` is listed before it exists. Listing it now means the layering decision
is already made when it arrives.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

from pydantic import BaseModel

import ctma

SRC = Path(__file__).resolve().parent.parent / "src" / "ctma"

# Subpackage -> the ctma subpackages it is allowed to import.
#
# `evaluation` and `report` appear in no other module's allowance, which is the
# point: nothing may depend on them. `evaluation` is also the only module
# permitted to read a Scenario Manifest, so keeping it un-importable keeps the
# manifest out of the matching system by construction rather than by care.
ALLOWED: dict[str, frozenset[str]] = {
    "domain": frozenset(),
    "adapters": frozenset({"domain"}),
    "policy": frozenset({"domain"}),
    "timeline": frozenset({"domain", "adapters"}),
    "agent": frozenset({"domain", "adapters", "timeline", "policy"}),
    "supervisor": frozenset({"domain", "agent"}),
    "match": frozenset({"domain", "adapters", "timeline", "agent", "supervisor", "policy"}),
    "evaluation": frozenset(
        {"domain", "adapters", "timeline", "agent", "supervisor", "policy", "match"}
    ),
    "report": frozenset({"domain"}),
}


def _subpackage(path: Path) -> str | None:
    """The ctma subpackage a source file belongs to, or None for the root init."""
    parts = path.relative_to(SRC).parts
    if parts == ("__init__.py",):
        return None
    return parts[0].removesuffix(".py")


def _imported_subpackages(path: Path) -> set[str]:
    """Every ctma subpackage this file imports from."""
    tree = ast.parse(path.read_text(), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        targets: list[str] = []
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            targets = [node.module]
        for target in targets:
            head, _, rest = target.partition(".")
            if head == "ctma" and rest:
                found.add(rest.partition(".")[0])
    return found


def _source_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def test_every_module_has_a_declared_layer() -> None:
    """A new module must state where it sits before it can be committed."""
    undeclared = {
        name
        for path in _source_files()
        if (name := _subpackage(path)) is not None and name not in ALLOWED
    }
    assert not undeclared, (
        f"add these to ALLOWED in this file, deciding what each may import: {sorted(undeclared)}"
    )


def test_imports_respect_the_declared_layering() -> None:
    violations: list[str] = []
    for path in _source_files():
        name = _subpackage(path)
        if name is None or name not in ALLOWED:
            continue
        for imported in sorted(_imported_subpackages(path) - {name}):
            if imported not in ALLOWED[name]:
                violations.append(f"{path.relative_to(SRC)} imports ctma.{imported}")
    assert not violations, "layering violations:\n  " + "\n  ".join(violations)


def test_domain_depends_on_nothing() -> None:
    """Core types are shared by every module, so they may share none of them."""
    assert ALLOWED["domain"] == frozenset()


def test_nothing_depends_on_report_or_evaluation() -> None:
    """The report is built last; the manifest reader stays out of the system."""
    for name, allowed in ALLOWED.items():
        assert "report" not in allowed, f"{name} may not import ctma.report"
        assert "evaluation" not in allowed, f"{name} may not import ctma.evaluation"


def _models() -> list[type[BaseModel]]:
    """Every Pydantic model this package defines, private ones included.

    Imported ones are skipped by module name: `BaseModel` itself is in scope
    wherever a model is declared, and it is not ours to configure.
    """
    found: dict[str, type[BaseModel]] = {}
    for info in pkgutil.walk_packages(ctma.__path__, prefix="ctma."):
        module = importlib.import_module(info.name)
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and issubclass(value, BaseModel)
                and value.__module__.startswith("ctma.")
            ):
                found[f"{value.__module__}.{value.__qualname__}"] = value
    return sorted(found.values(), key=lambda model: model.__qualname__)


def test_every_model_is_frozen_and_closed_to_unknown_fields() -> None:
    """Immutability is a requirement of the design, not a habit of the authors.

    Snapshots, expressions, candidate ranks, assessments, and runs are all
    specified as immutable, and a model that subclasses `BaseModel` directly
    instead of `Frozen` looks identical at the call site until something mutates
    a frozen artifact. `extra="forbid"` is here for the same reason: a typo in an
    authored JSON file has to fail rather than be dropped.
    """
    mutable = [
        f"{model.__module__}.{model.__qualname__}"
        for model in _models()
        if not (model.model_config.get("frozen") and model.model_config.get("extra") == "forbid")
    ]
    assert not mutable, f"these models should inherit from ctma.domain.base.Frozen: {mutable}"
