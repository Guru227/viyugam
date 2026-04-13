"""test_engine_declarations.py — Validate tool declarations are well-formed."""
from __future__ import annotations

from viyugam.engine.tools.declarations import ALL_DECLARATIONS


def test_all_declarations_count():
    assert len(ALL_DECLARATIONS) == 30


def test_each_declaration_has_required_fields():
    for decl in ALL_DECLARATIONS:
        assert "name" in decl, f"Missing 'name' in {decl}"
        assert "description" in decl, f"Missing 'description' in {decl.get('name', '?')}"
        assert "input_schema" in decl, f"Missing 'input_schema' in {decl['name']}"


def test_input_schemas_are_valid():
    for decl in ALL_DECLARATIONS:
        schema = decl["input_schema"]
        assert schema.get("type") == "object", f"{decl['name']} schema type != object"
        assert "properties" in schema, f"{decl['name']} missing properties"
        assert "required" in schema, f"{decl['name']} missing required"
        assert isinstance(schema["required"], list), f"{decl['name']} required not a list"


def test_no_duplicate_names():
    names = [d["name"] for d in ALL_DECLARATIONS]
    assert len(names) == len(set(names)), f"Duplicate tool names: {[n for n in names if names.count(n) > 1]}"
