"""Tests for the linked-data helpers.

These cover the pure logic only, so they need neither an OpenAI key nor a
reachable SPARQL endpoint; every network call is stubbed.
"""
import pytest

from services import ld_utils


# --------------------------------------------------------------------------
# extract_code_blocks
# --------------------------------------------------------------------------

def test_extract_code_blocks_prefers_sparql_fences():
    text = (
        "Here you go:\n"
        "```sparql\nSELECT * WHERE { ?s ?p ?o }\n```\n"
        "```python\nprint('not this one')\n```\n"
    )
    blocks = ld_utils.extract_code_blocks(text)

    assert len(blocks) == 1
    assert "SELECT * WHERE" in blocks[0]
    assert "print(" not in blocks[0]


def test_extract_code_blocks_falls_back_to_untagged_fences():
    text = "```\nSELECT * WHERE { ?s ?p ?o }\n```"
    blocks = ld_utils.extract_code_blocks(text)

    assert len(blocks) == 1
    assert "SELECT" in blocks[0]


def test_extract_code_blocks_returns_empty_without_fences():
    assert ld_utils.extract_code_blocks("no code here") == []


# --------------------------------------------------------------------------
# post_process
# --------------------------------------------------------------------------

def test_post_process_prepends_missing_prefixes():
    query = ld_utils.post_process("```sparql\nSELECT ?s WHERE { ?s dbo:abstract ?o }\n```")

    assert "PREFIX dbo: <http://dbpedia.org/ontology/>" in query
    assert query.rstrip().endswith("SELECT ?s WHERE { ?s dbo:abstract ?o }")


def test_post_process_does_not_duplicate_declared_prefixes():
    declared = "PREFIX dbo: <http://dbpedia.org/ontology/>"
    query = ld_utils.post_process(f"{declared}\nSELECT ?s WHERE {{ ?s dbo:abstract ?o }}")

    assert query.count(declared) == 1


def test_post_process_handles_bare_queries_without_fences():
    query = ld_utils.post_process("SELECT ?s WHERE { ?s ?p ?o }")

    assert "SELECT ?s WHERE" in query


# --------------------------------------------------------------------------
# get_relations
#
# Regression guard: this used to call an undefined
# transform_sparql_json_to_dataframe, so it raised NameError on every call.
# --------------------------------------------------------------------------

def _binding(uri):
    return {"uri": {"type": "uri", "value": uri}}


def test_get_relations_extracts_property_ids(monkeypatch):
    monkeypatch.setattr(ld_utils, "execute", lambda _q: {
        "results": {"bindings": [
            _binding("http://www.wikidata.org/prop/direct/P31"),
            _binding("http://www.wikidata.org/prop/direct/P279"),
        ]}
    })

    assert ld_utils.get_relations("Q42") == ["P31", "P279"]


def test_get_relations_returns_empty_for_no_bindings(monkeypatch):
    monkeypatch.setattr(ld_utils, "execute", lambda _q: {"results": {"bindings": []}})

    assert ld_utils.get_relations("Q42") == []


def test_get_relations_returns_empty_when_the_endpoint_errors(monkeypatch):
    # `execute` reports failures as {'error': ...} rather than raising.
    monkeypatch.setattr(ld_utils, "execute", lambda _q: {"error": "boom"})

    assert ld_utils.get_relations("Q42") == []


def test_get_relations_does_not_raise_name_error(monkeypatch):
    """The original defect: any call blew up with NameError."""
    monkeypatch.setattr(ld_utils, "execute", lambda _q: {"results": {"bindings": []}})

    try:
        ld_utils.get_relations("Q42")
    except NameError as exc:  # pragma: no cover - fails the test deliberately
        pytest.fail(f"get_relations raised NameError: {exc}")


# --------------------------------------------------------------------------
# search_entity
# --------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_search_entity_reports_relations_when_the_entity_has_them(monkeypatch):
    monkeypatch.setattr(ld_utils.requests, "get", lambda *a, **k: _FakeResponse(
        {"search": [{"label": "Douglas Adams", "id": "Q42"}]}
    ))
    monkeypatch.setattr(ld_utils.fuzz, "partial_ratio", lambda a, b: 100)
    monkeypatch.setattr(ld_utils, "get_relations", lambda _uri: ["P31"])

    entities, relations = ld_utils.search_entity("Douglas Adams")

    # Previously this returned ([], []) because get_relations raised NameError
    # and the bare except swallowed it.
    assert relations == [{"Douglas Adams": "http://www.wikidata.org/prop/direct/P31"}]
    assert entities == []


def test_search_entity_reports_the_entity_when_it_has_no_relations(monkeypatch):
    monkeypatch.setattr(ld_utils.requests, "get", lambda *a, **k: _FakeResponse(
        {"search": [{"label": "Douglas Adams", "id": "Q42"}]}
    ))
    monkeypatch.setattr(ld_utils.fuzz, "partial_ratio", lambda a, b: 100)
    monkeypatch.setattr(ld_utils, "get_relations", lambda _uri: [])

    entities, relations = ld_utils.search_entity("Douglas Adams")

    assert entities == [{"Douglas Adams": "http://www.wikidata.org/entity/Q42"}]
    assert relations == []


def test_search_entity_skips_labels_below_the_similarity_threshold(monkeypatch):
    monkeypatch.setattr(ld_utils.requests, "get", lambda *a, **k: _FakeResponse(
        {"search": [{"label": "Something Else", "id": "Q1"}]}
    ))
    monkeypatch.setattr(ld_utils.fuzz, "partial_ratio", lambda a, b: 10)

    assert ld_utils.search_entity("Douglas Adams") == ([], [])


def test_search_entity_survives_a_network_failure(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("wikidata unreachable")

    monkeypatch.setattr(ld_utils.requests, "get", boom)

    assert ld_utils.search_entity("Douglas Adams") == ([], [])
