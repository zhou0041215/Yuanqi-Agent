from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from functools import lru_cache
from importlib.resources import files
from typing import Literal

from pydantic import Field, HttpUrl, model_validator

from yuanqi_agent.models import StrictModel

_RESOURCE_PACKAGE = "yuanqi_agent.resources"


class ExcludedKnowledgeEntity(StrictModel):
    entity_key: str = Field(min_length=3, max_length=300)
    title: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=500)


class KnowledgeGovernancePolicy(StrictModel):
    schema_version: Literal[1]
    policy_version: str = Field(min_length=1, max_length=50)
    curated_at: datetime
    curated_by: str = Field(min_length=1, max_length=100)
    excluded_entities: list[ExcludedKnowledgeEntity]

    @model_validator(mode="after")
    def validate_unique_exclusions(self) -> KnowledgeGovernancePolicy:
        entity_keys = [item.entity_key for item in self.excluded_entities]
        titles = [item.title for item in self.excluded_entities]
        if len(entity_keys) != len(set(entity_keys)):
            raise ValueError("excluded knowledge entity keys must be unique")
        if len(titles) != len(set(titles)):
            raise ValueError("excluded knowledge titles must be unique")
        return self

    def excludes(
        self,
        document_id: str,
        title: str,
        path_titles: Iterable[object] = (),
    ) -> bool:
        normalized_id = document_id.strip()
        normalized_title = title.strip()
        normalized_path = {str(item).strip() for item in path_titles}
        return any(
            item.entity_key == normalized_id
            or item.title == normalized_title
            or item.title in normalized_path
            for item in self.excluded_entities
        )


class TrustedDrugRecord(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=2_000)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    source_title: str = Field(min_length=1, max_length=500)
    source_uri: HttpUrl

    @model_validator(mode="after")
    def validate_source_and_warnings(self) -> TrustedDrugRecord:
        if self.source_uri.scheme != "https":
            raise ValueError("trusted drug sources must use HTTPS")
        if any(not warning.strip() for warning in self.warnings):
            raise ValueError("trusted drug warnings must not be blank")
        if len(self.warnings) != len(set(self.warnings)):
            raise ValueError("trusted drug warnings must be unique")
        return self


class TrustedDrugCatalog(StrictModel):
    schema_version: Literal[1]
    knowledge_version: int = Field(gt=0)
    curated_at: datetime
    curated_by: str = Field(min_length=1, max_length=100)
    release_status: Literal["SOURCE_BACKED_STARTER"]
    drugs: list[TrustedDrugRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_drugs(self) -> TrustedDrugCatalog:
        names = [item.name for item in self.drugs]
        if len(names) != len(set(names)):
            raise ValueError("trusted drug names must be unique")
        return self


def _resource_bytes(name: str) -> bytes:
    return files(_RESOURCE_PACKAGE).joinpath(name).read_bytes()


@lru_cache(maxsize=1)
def get_knowledge_governance_policy() -> KnowledgeGovernancePolicy:
    return KnowledgeGovernancePolicy.model_validate_json(
        _resource_bytes("knowledge_governance.v1.json")
    )


@lru_cache(maxsize=1)
def get_trusted_drug_catalog() -> TrustedDrugCatalog:
    return TrustedDrugCatalog.model_validate_json(
        _resource_bytes("trusted_drugs.v1.json")
    )


@lru_cache(maxsize=1)
def _trusted_drugs_by_name() -> dict[str, TrustedDrugRecord]:
    return {item.name: item for item in get_trusted_drug_catalog().drugs}


def get_trusted_drug(name: str) -> TrustedDrugRecord | None:
    return _trusted_drugs_by_name().get(name.strip())
