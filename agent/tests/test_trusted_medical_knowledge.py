from yuanqi_agent.trusted_medical_knowledge import (
    get_knowledge_governance_policy,
    get_trusted_drug,
    get_trusted_drug_catalog,
)


def test_versioned_governance_policy_uses_exact_entities() -> None:
    policy = get_knowledge_governance_policy()

    assert policy.schema_version == 1
    assert policy.policy_version
    assert policy.excludes("Disease:口腔干燥综合征", "口腔干燥综合征")
    assert policy.excludes("Drug:复方氯己定含漱液", "复方氯己定含漱液")
    assert policy.excludes(
        "Symptom:口干",
        "口干",
        ["口腔干燥综合征", "口干"],
    )
    assert not policy.excludes(
        "Disease:口腔黏膜病",
        "提及复方氯己定含漱液的口腔黏膜病",
    )


def test_trusted_drug_catalog_is_versioned_and_source_backed() -> None:
    catalog = get_trusted_drug_catalog()
    amoxicillin = get_trusted_drug("阿莫西林")

    assert catalog.schema_version == 1
    assert catalog.knowledge_version > 0
    assert amoxicillin is not None
    assert amoxicillin.warnings
    assert "dailymed.nlm.nih.gov" in str(amoxicillin.source_uri)
