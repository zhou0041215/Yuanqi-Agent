"""Standardize all disease names and disease-to-department routing candidates.

This migration is deliberately non-destructive:
- legacy BELONGS_TO edges remain available for offline review;
- canonical ROUTED_TO edges are clearly marked REFERENCE_ONLY;
- only separately reviewed BELONGS_TO edges can be presented as verified facts.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from neo4j import AsyncGraphDatabase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yuanqi_agent.medical_taxonomy import (
    CATALOG_SOURCE,
    DEPARTMENTS,
    EXPLICIT_DISEASE_ROUTES,
    INVALID_DISEASE_NAMES,
    NHC_DEPARTMENT_SOURCE,
)
from yuanqi_agent.trusted_medical_knowledge import get_knowledge_governance_policy


async def standardize(uri: str, username: str, password: str, database: str) -> None:
    governance = get_knowledge_governance_policy()
    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
    try:
        await driver.verify_connectivity()
        async with driver.session(database=database) as session:
            await session.run(
                "CREATE INDEX disease_catalog_status IF NOT EXISTS "
                "FOR (d:Disease) ON (d.catalogStatus)"
            )
            await session.run(
                "CREATE INDEX department_standard IF NOT EXISTS "
                "FOR (d:Department) ON (d.standard)"
            )
            await session.run(
                """
                MATCH (d:Disease)
                WHERE NOT d.name IN $invalid_names
                SET d.catalogStatus = 'CATALOGED',
                    d.catalogSourceTitle = 'disease-kb open medical catalog',
                    d.catalogSourceUri = $catalog_source,
                    d.entityKey = coalesce(d.entityKey, 'Disease:' + d.name),
                    d.catalogSummary = CASE
                      WHEN d.desc IS NULL OR trim(d.desc) = '' THEN ''
                      ELSE substring(
                        replace(replace(d.desc, '\r', ' '), '\n', ' '),
                        0,
                        500
                      )
                    END
                """,
                catalog_source=CATALOG_SOURCE,
                invalid_names=list(INVALID_DISEASE_NAMES),
            )
            for label in ("Symptom", "Drug", "Exam", "Food", "Therapy"):
                await session.run(
                    f"""
                    MATCH (n:{label})
                    SET n.catalogStatus = 'CATALOGED',
                        n.catalogSourceTitle = 'disease-kb open medical catalog',
                        n.catalogSourceUri = $catalog_source,
                        n.entityKey = coalesce(n.entityKey, $label + ':' + n.name)
                    """,
                    catalog_source=CATALOG_SOURCE,
                    label=label,
                )
            await session.run(
                """
                MATCH (n)
                WHERE n.retrievalPolicyVersion IS NOT NULL
                REMOVE n.retrievalStatus,
                       n.retrievalPolicyVersion,
                       n.exclusionReason,
                       n.excludedAt
                """
            )
            await session.run(
                """
                MATCH (n)
                WHERE n.entityKey IN $excluded_entity_keys
                SET n.catalogStatus = 'EXCLUDED',
                    n.retrievalStatus = 'EXCLUDED',
                    n.retrievalPolicyVersion = $policy_version,
                    n.exclusionReason = $exclusion_reason,
                    n.excludedAt = datetime()
                """,
                excluded_entity_keys=[
                    item.entity_key for item in governance.excluded_entities
                ],
                policy_version=governance.policy_version,
                exclusion_reason="Excluded by versioned medical knowledge governance policy",
            )
            await session.run(
                """
                MATCH ()-[rel:HAS_SYMPTOM|TREATED_BY|REQUIRES_EXAM|COMPLICATION
                  |HAS_THERAPY|RECOMMENDED_EAT|AVOID_EAT|RECOMMENDED_RECIPE]-()
                WHERE NOT toUpper(coalesce(rel.reviewStatus, ''))
                  IN ['PUBLISHED', 'APPROVED']
                SET rel.evidenceLevel = 'REFERENCE_ONLY',
                    rel.reviewStatus = 'REFERENCE_ONLY',
                    rel.reviewed = false,
                    rel.catalogSourceTitle = 'disease-kb open medical catalog',
                    rel.catalogSourceUri = $catalog_source
                """,
                catalog_source=CATALOG_SOURCE,
            )
            await session.run(
                """
                MATCH (d:Disease)
                WHERE d.name IN $invalid_names
                SET d.catalogStatus = 'REJECTED',
                    d.rejectionReason = 'Invalid or non-medical source title'
                """,
                invalid_names=list(INVALID_DISEASE_NAMES),
            )
            for department in DEPARTMENTS:
                await session.run(
                    """
                    MERGE (canonical:Department {name: $name})
                    SET canonical.entityKey = 'Department:' + $name,
                        canonical.standard = true,
                        canonical.catalogStatus = 'STANDARDIZED',
                        canonical.departmentCode = $code,
                        canonical.parentCategory = $parent,
                        canonical.aliases = $aliases,
                        canonical.sourceTitle =
                          '国家卫生健康委员会《医疗机构诊疗科目名录》',
                        canonical.sourceUri = $source_uri,
                        canonical.knowledgeVersion = 1
                    """,
                    name=department.name,
                    code=department.code,
                    parent=department.parent,
                    aliases=list(department.aliases),
                    source_uri=NHC_DEPARTMENT_SOURCE,
                )
                source_names = [department.name, *department.aliases]
                await session.run(
                    """
                    MATCH (d:Disease)-[:BELONGS_TO]->(raw:Department)
                    WHERE raw.name IN $source_names
                    MATCH (canonical:Department {name: $canonical_name})
                    MERGE (d)-[route:ROUTED_TO]->(canonical)
                    SET route.evidenceLevel = 'REFERENCE_ONLY',
                        route.reviewStatus = 'REFERENCE_ONLY',
                        route.reviewed = false,
                        route.sourceDepartmentNames =
                          CASE
                            WHEN route.sourceDepartmentNames IS NULL
                              THEN [raw.name]
                            WHEN NOT raw.name IN route.sourceDepartmentNames
                              THEN route.sourceDepartmentNames + raw.name
                            ELSE route.sourceDepartmentNames
                          END,
                        route.sourceTitle = 'disease-kb open medical catalog',
                        route.sourceUri = $catalog_source,
                        route.standardizedAt = datetime()
                    """,
                    source_names=source_names,
                    canonical_name=department.name,
                    catalog_source=CATALOG_SOURCE,
                )

            for disease_name, department_names in EXPLICIT_DISEASE_ROUTES.items():
                await session.run(
                    """
                    MATCH (d:Disease {name: $disease_name})
                    WHERE d.catalogStatus = 'CATALOGED'
                    UNWIND $department_names AS department_name
                    MATCH (canonical:Department {
                      name: department_name,
                      standard: true
                    })
                    MERGE (d)-[route:ROUTED_TO]->(canonical)
                    SET route.evidenceLevel = 'REFERENCE_ONLY',
                        route.reviewStatus = 'REFERENCE_ONLY',
                        route.reviewed = false,
                        route.sourceDepartmentNames = ['curated-routing-fallback'],
                        route.sourceTitle = 'YuanQi catalog normalization',
                        route.sourceUri = coalesce(d.sourceUri, $catalog_source),
                        route.standardizedAt = datetime()
                    """,
                    disease_name=disease_name,
                    department_names=list(department_names),
                    catalog_source=CATALOG_SOURCE,
                )

            result = await session.run(
                """
                MATCH (d:Disease {catalogStatus: 'CATALOGED'})
                OPTIONAL MATCH (d)-[:ROUTED_TO]->(k:Department)
                WITH count(DISTINCT d) AS diseases,
                     count(DISTINCT CASE WHEN k IS NOT NULL THEN d END) AS routed
                MATCH (k:Department {standard: true})
                RETURN diseases, routed, count(k) AS departments
                """
            )
            stats = await result.single()
            print(
                f"Cataloged {stats['diseases']} diseases; "
                f"standardized {stats['departments']} departments; "
                f"routed {stats['routed']} diseases."
            )
    finally:
        await driver.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="neo4j://localhost:17687")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--password", default="yuanqi-local")
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()
    asyncio.run(standardize(args.uri, args.username, args.password, args.database))


if __name__ == "__main__":
    main()
