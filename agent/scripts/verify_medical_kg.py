"""End-to-end verification for the medical knowledge graph.

Run this AFTER the data pipeline against a live Neo4j:

    cd agent
    .\\.venv\\Scripts\\python.exe scripts\\import_disease_kb.py --file data/medical.json
    .\\.venv\\Scripts\\python.exe scripts\\standardize_medical_catalog.py
    .\\.venv\\Scripts\\python.exe scripts\\publish_trusted_medical_subset.py
    .\\.venv\\Scripts\\python.exe scripts\\verify_medical_kg.py

It checks four things end-to-end:
  1. The reconnected catalog data is present (Food / Therapy nodes and the
     HAS_THERAPY / RECOMMENDED_EAT / AVOID_EAT / RECOMMENDED_RECIPE relations).
  2. The expanded trusted publish set is user-visible (>=24 published diseases,
     >=10 governed drug-class entries) via the REAL production retrieval Cypher
     imported from yuanqi_agent.retrieval.
  3. The browse layer can reach Food / Therapy for a published disease.
  4. Versioned knowledge exclusions and trusted drug-label warnings reached Neo4j.

Exit code is non-zero if any assertion fails, so it doubles as a smoke gate.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# The medical Cypher intentionally coalesces camelCase and snake_case property
# fallbacks (sourceUri/source_uri, reviewStatus/governanceStatus, ...). On a graph
# that uses only one naming, Neo4j emits benign "property does not exist"
# notifications for the unused branch. These are not errors; silence just those
# notification logs so real problems stay visible.
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

EXPECTED_PUBLISHED_DISEASES = 24
EXPECTED_DRUG_CLASSES = 10
NEW_RELATIONS = ("HAS_THERAPY", "RECOMMENDED_EAT", "AVOID_EAT", "RECOMMENDED_RECIPE")

# Import the real production Cypher so this verifies what users actually hit.
try:
    from yuanqi_agent.retrieval.graph import GRAPH_SEARCH_QUERY, Neo4jGraphRetriever
    from yuanqi_agent.retrieval.medical_documents import (
        MEDICAL_DOCUMENT_QUERY,
        build_disease_document,
    )
    from yuanqi_agent.trusted_medical_knowledge import (
        get_knowledge_governance_policy,
        get_trusted_drug_catalog,
    )

    _PRODUCTION_QUERIES = True
except Exception as exc:  # pragma: no cover - only when run outside the venv
    print(f"[warn] could not import production queries ({exc}); running graph-only checks")
    _PRODUCTION_QUERIES = False


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def ok(self, label: str, condition: bool, detail: str = "") -> None:
        status = "PASS" if condition else "FAIL"
        print(f"  [{status}] {label}{(' — ' + detail) if detail else ''}")
        if not condition:
            self.failures.append(label)


def _terms(query: str) -> list[str]:
    if _PRODUCTION_QUERIES:
        return Neo4jGraphRetriever._terms(query)  # exercise the real tokenizer
    return [query]


def verify(uri: str, username: str, password: str, database: str) -> int:
    checks = Checks()
    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        driver.verify_connectivity()
        print(f"[ok] connected to {uri}\n")
        with driver.session(database=database) as session:
            # ── Inventory ─────────────────────────────────────────────
            print("Node counts by label:")
            node_counts = {
                r["label"]: r["cnt"]
                for r in session.run(
                    "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt "
                    "ORDER BY cnt DESC"
                )
            }
            for label, cnt in node_counts.items():
                print(f"    {label}: {cnt}")
            print("Relationship counts by type:")
            rel_counts = {
                r["type"]: r["cnt"]
                for r in session.run(
                    "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS cnt "
                    "ORDER BY cnt DESC"
                )
            }
            for rel_type, cnt in rel_counts.items():
                print(f"    {rel_type}: {cnt}")
            print()

            # ── 1. Reconnected catalog data ───────────────────────────
            print("1) Reconnected catalog data:")
            checks.ok("Food nodes present", node_counts.get("Food", 0) > 0,
                      f"{node_counts.get('Food', 0)} nodes")
            checks.ok("Therapy nodes present", node_counts.get("Therapy", 0) > 0,
                      f"{node_counts.get('Therapy', 0)} nodes")
            for rel in NEW_RELATIONS:
                checks.ok(f"{rel} relations present", rel_counts.get(rel, 0) > 0,
                          f"{rel_counts.get(rel, 0)} edges")
            print()

            # ── 2. Expanded trusted publish set ───────────────────────
            print("2) Trusted publish set (governed, HTTPS-sourced):")
            published_diseases = session.run(
                """
                MATCH (d:Disease)
                WHERE toUpper(coalesce(d.reviewStatus, '')) IN ['PUBLISHED','APPROVED']
                  AND coalesce(d.sourceUri, '') STARTS WITH 'https://'
                RETURN count(d) AS cnt
                """
            ).single()["cnt"]
            checks.ok(
                f"published diseases >= {EXPECTED_PUBLISHED_DISEASES}",
                published_diseases >= EXPECTED_PUBLISHED_DISEASES,
                f"{published_diseases} published",
            )
            drug_classes = session.run(
                """
                MATCH (r:Drug)
                WHERE toUpper(coalesce(r.reviewStatus, '')) IN ['PUBLISHED','APPROVED']
                  AND coalesce(r.sourceUri, '') STARTS WITH 'https://'
                  AND coalesce(r.category, '') <> ''
                RETURN count(r) AS cnt
                """
            ).single()["cnt"]
            checks.ok(
                f"governed drug-class entries >= {EXPECTED_DRUG_CLASSES}",
                drug_classes >= EXPECTED_DRUG_CLASSES,
                f"{drug_classes} drugs with category",
            )

            if _PRODUCTION_QUERIES:
                rows = session.run(
                    GRAPH_SEARCH_QUERY,
                    allowed_labels=["Disease", "Symptom", "Drug", "Department", "Exam"],
                    terms=_terms("糖尿病"),
                    query="糖尿病",
                    seed_limit=5,
                    neighbor_limit=12,
                    limit=8,
                ).data()
                checks.ok(
                    "production graph retrieval returns results for 糖尿病",
                    len(rows) > 0,
                    f"{len(rows)} candidates",
                )
                docs = session.run(MEDICAL_DOCUMENT_QUERY).data()
                checks.ok(
                    "MEDICAL_DOCUMENT_QUERY yields published disease docs",
                    len(docs) >= EXPECTED_PUBLISHED_DISEASES,
                    f"{len(docs)} docs",
                )
                if docs:
                    built = build_disease_document(docs[0])
                    checks.ok(
                        "build_disease_document produces indexable doc",
                        bool(built.get("content")) and built.get("source_uri", "").startswith("https://"),
                        built.get("title", ""),
                    )
            print()

            # ── 3. Browse layer reaches Food / Therapy ────────────────
            print("3) Browse layer reaches new catalog relations for 糖尿病:")
            browse = session.run(
                """
                MATCH (d:Disease {name: '糖尿病'})
                  -[r:HAS_THERAPY|RECOMMENDED_EAT|AVOID_EAT|RECOMMENDED_RECIPE]->(n)
                RETURN type(r) AS rel, count(DISTINCT n) AS cnt
                ORDER BY rel
                """
            ).data()
            for row in browse:
                print(f"    糖尿病 -[{row['rel']}]-> {row['cnt']} nodes")
            checks.ok(
                "糖尿病 exposes food/therapy catalog neighbors",
                any(row["cnt"] > 0 for row in browse),
                f"{len(browse)} relation types",
            )
            print()

            # ── 4. Versioned governance resources reached Neo4j ──────
            print("4) Versioned retrieval exclusions and drug-label warnings:")
            if _PRODUCTION_QUERIES:
                governance = get_knowledge_governance_policy()
                excluded_keys = {
                    row["entityKey"]
                    for row in session.run(
                        """
                        MATCH (n)
                        WHERE n.entityKey IN $entity_keys
                          AND n.retrievalStatus = 'EXCLUDED'
                        RETURN n.entityKey AS entityKey
                        """,
                        entity_keys=[
                            item.entity_key for item in governance.excluded_entities
                        ],
                    )
                }
                expected_excluded = {
                    item.entity_key for item in governance.excluded_entities
                }
                checks.ok(
                    "all governed exclusions are marked in Neo4j",
                    excluded_keys == expected_excluded,
                    f"{len(excluded_keys)}/{len(expected_excluded)} entities",
                )

                trusted_drugs = get_trusted_drug_catalog()
                warning_drugs = {
                    item.name for item in trusted_drugs.drugs if item.warnings
                }
                published_warning_drugs = {
                    row["name"]
                    for row in session.run(
                        """
                        MATCH (r:Drug)
                        WHERE r.name IN $names
                          AND size(coalesce(r.warnings, [])) > 0
                          AND coalesce(r.sourceUri, '') STARTS WITH 'https://'
                        RETURN r.name AS name
                        """,
                        names=sorted(warning_drugs),
                    )
                }
                checks.ok(
                    "trusted label warnings are published to Neo4j",
                    published_warning_drugs == warning_drugs,
                    f"{len(published_warning_drugs)}/{len(warning_drugs)} drugs",
                )
    finally:
        driver.close()

    print("\n" + "=" * 56)
    if checks.failures:
        print(f"RESULT: FAIL — {len(checks.failures)} check(s) failed:")
        for name in checks.failures:
            print(f"  - {name}")
        return 1
    print("RESULT: PASS — knowledge graph is complete and governed.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="neo4j://localhost:17687")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--password", default="yuanqi-local")
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()
    raise SystemExit(verify(args.uri, args.username, args.password, args.database))


if __name__ == "__main__":
    main()
