"""The tool list Claude sees: every tool is wired up, every group is complete, every combination builds.
(1.0.34 shipped a group with no description: every single request crashed. This file exists so that can't happen again.)"""
import itertools
import json

import pytest

import tools


def _names(specs):
    return [s["name"] for s in specs]


def test_spec_names_unique():
    names = _names(tools.TOOL_SPECS)
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate tool names: {dupes}"


def test_every_spec_has_a_function():
    missing = [n for n in _names(tools.TOOL_SPECS) if n not in tools.FUNCS]
    assert not missing, f"tools Claude can call that have no function: {missing}"


def test_specs_are_valid_json_schema_shapes():
    for s in tools.TOOL_SPECS:
        assert s.get("description"), f"{s['name']} has no description"
        sch = s.get("input_schema", {})
        assert sch.get("type") == "object", f"{s['name']} input_schema must be an object"
        for req in sch.get("required", []):
            assert req in sch.get("properties", {}), f"{s['name']} requires '{req}' but doesn't define it"
        json.dumps(s)                                              # must serialise for the API


def test_grouped_tools_exist():
    names = set(_names(tools.TOOL_SPECS))
    for g, members in tools.TOOL_GROUPS.items():
        for n in members:
            assert n in names, f"group '{g}' lists '{n}', which isn't a tool"


def test_every_group_has_hints_except_apps():
    for g in tools.TOOL_GROUPS:
        if g == "apps":
            continue
        assert g in tools.GROUP_HINTS, f"group '{g}' has no GROUP_HINTS regex, so it can never be picked from what you say"


@pytest.mark.parametrize("size", [0, 1, 2, 3])
def test_every_group_combination_builds(size):
    groups = list(tools.TOOL_GROUPS)
    for combo in itertools.combinations(groups, size):
        loaded = set(combo)
        specs = tools.lean_specs(loaded)
        more = tools.more_tools_spec(loaded)
        all_specs = specs + ([more] if more else [])
        json.dumps(all_specs)
        names = _names(all_specs)
        assert len(names) == len(set(names)), f"duplicate tools with groups {combo}"


def test_more_tools_mentions_every_group_by_description():
    d = tools.more_tools_spec(set())["description"]
    for g in tools.TOOL_GROUPS:
        if g == "apps":
            continue
        assert f"{g} (" in d, f"more_tools doesn't describe group '{g}'"
        assert f"{g} ({g})" not in d, f"group '{g}' has no human description in more_tools_spec"


@pytest.mark.parametrize("text,group", [
    ("when I open dead by daylight turn the lights red", "automation"),
    ("what can I cook with eggs", "life"),
    ("how's nvidia doing", "stocks"),
    ("make me a budget spreadsheet", "computer"),
    ("play my playlist on spotify", "media"),
])
def test_group_hints(text, group):
    assert group in tools.groups_for(text)


def test_unknown_tool_is_a_message_not_a_crash():
    assert "Unknown tool" in tools.run_tool("definitely_not_a_tool", {})


def test_a_crashing_tool_is_reported_not_raised(monkeypatch):
    def boom(**_):
        raise RuntimeError("kaboom")
    monkeypatch.setitem(tools.FUNCS, "zz_boom", boom)
    out = tools.run_tool("zz_boom", {})
    assert "failed" in out and "kaboom" in out
