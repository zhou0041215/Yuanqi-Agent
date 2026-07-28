"""Regression tests guarding medical knowledge-graph completeness.

These tests are import-light: they stub the ``neo4j`` driver so the data
seeds can be imported without a live database, and otherwise assert against
the script/schema source text. They protect the fixes that reconnected the
previously-dropped catalog data (food / therapy / disease properties) and the
expanded, source-backed trusted publish set.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = AGENT_ROOT / "scripts"
RESOURCES = AGENT_ROOT / "resources"
SRC = AGENT_ROOT / "src" / "yuanqi_agent"


def _load_module(path: Path):
    """Import a standalone script, stubbing heavy optional deps."""
    if "neo4j" not in sys.modules:
        stub = types.ModuleType("neo4j")
        stub.GraphDatabase = object
        stub.AsyncGraphDatabase = object
        stub.RoutingControl = object
        sys.modules["neo4j"] = stub
    spec = importlib.util.spec_from_file_location(f"_kgtest_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    # Register before exec so dataclass field-type resolution can see the module.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ── Expanded, source-backed trusted publish set ───────────────────────────

def test_trusted_publish_set_expanded_and_sourced():
    publish = _load_module(SCRIPTS / "publish_trusted_medical_subset.py")
    seeds = publish.SEEDS
    assert len(seeds) >= 24, "trusted disease set should be broadly expanded"
    names = [seed.name for seed in seeds]
    assert len(names) == len(set(names)), "no duplicate diseases"
    for seed in seeds:
        assert seed.source_uri.startswith("https://www.who.int/"), seed.name
        assert seed.summary.strip(), seed.name


def test_trusted_drug_class_entries_sourced_without_dosing():
    publish = _load_module(SCRIPTS / "publish_trusted_medical_subset.py")
    drugs = publish.DRUG_SEEDS
    assert len(drugs) >= 8
    drug_names = [drug.name for drug in drugs]
    assert len(drug_names) == len(set(drug_names))
    for drug in drugs:
        assert drug.category.strip()
        assert drug.summary.strip()
        assert str(drug.source_uri).startswith("https://")
        # Trusted starter records never carry executable dosing instructions.
        for banned in (" mg", "每日一次", "每次", "用法用量"):
            assert banned not in drug.summary, f"{drug.name}: {banned}"
    label_drugs = [drug for drug in drugs if drug.warnings]
    assert {drug.name for drug in label_drugs} >= {"阿莫西林", "头孢丙烯分散片"}
    assert all("dailymed.nlm.nih.gov" in str(drug.source_uri) for drug in label_drugs)


# ── Importer reconnects food / therapy / disease properties ───────────────

def test_importer_writes_reconnected_relations_and_nodes():
    source = (SCRIPTS / "import_disease_kb.py").read_text(encoding="utf-8")
    for relation in ("HAS_THERAPY", "RECOMMENDED_EAT", "AVOID_EAT", "RECOMMENDED_RECIPE"):
        assert relation in source, relation
    for label in ('("Food", foods)', '("Therapy", cures)'):
        assert label in source, label
    for prop in ("category", "yibao_status", "cost_money", "get_prob", "get_way", "drug_detail"):
        assert prop in source, prop


# ── Catalog governance covers the new entities ────────────────────────────

def test_standardize_governs_food_and_therapy():
    source = (SCRIPTS / "standardize_medical_catalog.py").read_text(encoding="utf-8")
    assert '"Food"' in source and '"Therapy"' in source
    for relation in ("HAS_THERAPY", "RECOMMENDED_EAT", "AVOID_EAT", "RECOMMENDED_RECIPE"):
        assert relation in source, relation


def test_versioned_retrieval_exclusions_reach_graph_and_vector_pipelines():
    standardize = (SCRIPTS / "standardize_medical_catalog.py").read_text(encoding="utf-8")
    graph = (SRC / "retrieval" / "graph.py").read_text(encoding="utf-8")
    documents = (SRC / "retrieval" / "medical_documents.py").read_text(encoding="utf-8")

    assert "get_knowledge_governance_policy" in standardize
    assert "retrievalStatus = 'EXCLUDED'" in standardize
    assert "retrievalStatus" in graph
    assert "retrievalStatus" in documents


# ── Schema declares the new catalog labels ────────────────────────────────

def test_schema_declares_food_and_therapy_constraints():
    source = (RESOURCES / "neo4j-schema.cypher").read_text(encoding="utf-8")
    assert "FOR (node:Food) REQUIRE node.name IS UNIQUE" in source
    assert "FOR (node:Therapy) REQUIRE node.name IS UNIQUE" in source


# ── Index-time and query-time embeddings share one factory ────────────────

def test_indexer_and_runtime_use_shared_embedding_factory():
    indexer = (SCRIPTS / "index_medical_knowledge.py").read_text(encoding="utf-8")
    api = (SRC / "api.py").read_text(encoding="utf-8")
    embedding = (SRC / "retrieval" / "embedding.py").read_text(encoding="utf-8")
    # The factory exists and both call sites use it.
    assert "def build_embedding_provider(" in embedding
    assert "build_embedding_provider(" in indexer
    assert "build_embedding_provider(" in api
    # Neither call site hardcodes the offline hash embedding anymore, which would
    # let index-time and query-time vectors drift into different spaces.
    assert "DeterministicHashEmbedding(" not in indexer
    assert "DeterministicHashEmbedding(" not in api


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("all tests passed")
