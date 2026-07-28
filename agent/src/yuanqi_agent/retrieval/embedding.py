import hashlib
import math
import re
from typing import TYPE_CHECKING, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from yuanqi_agent.errors import AgentError

if TYPE_CHECKING:
    from yuanqi_agent.config import Settings


class EmbeddingProvider(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class DeterministicHashEmbedding:
    """Offline development embedding; production can inject a semantic provider."""

    def __init__(self, dimensions: int):
        if dimensions < 64:
            raise ValueError("dimensions must be at least 64")
        self.dimensions = dimensions

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        normalized = text.strip().lower()
        if not normalized:
            raise ValueError("text must not be blank")
        tokens = self._tokens(normalized)
        if not tokens:
            tokens = [normalized]
        vector = [0.0] * self.dimensions
        for token in tokens[:2_000]:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            bucket = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector]

    @staticmethod
    def _tokens(text: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9]+", text)
        for run in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]+", text):
            tokens.extend(run)
            tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
        return tokens


class _EmbeddingItem(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    index: int = Field(ge=0)
    embedding: list[float]


class _EmbeddingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    data: list[_EmbeddingItem]


class HttpEmbeddingProvider:
    """OpenAI-compatible embedding client bound to one configured endpoint."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        model: str,
        dimensions: int,
        api_key: str | None = None,
    ):
        self._client = client
        self._endpoint = endpoint
        self._model = model
        self._dimensions = dimensions
        self._api_key = api_key

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("embedding input must contain non-blank text")
        if len(texts) > 256 or any(len(text) > 20_000 for text in texts):
            raise ValueError("embedding batch exceeds the configured safety limit")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = await self._client.post(
                self._endpoint,
                headers=headers,
                json={
                    "model": self._model,
                    "input": texts,
                    "dimensions": self._dimensions,
                    "encoding_format": "float",
                },
            )
            response.raise_for_status()
            payload = _EmbeddingResponse.model_validate_json(response.content)
            vectors = [item.embedding for item in sorted(payload.data, key=lambda item: item.index)]
            self._validate_vectors(vectors, len(texts))
            return vectors
        except (httpx.HTTPError, ValidationError, ValueError) as exc:
            raise AgentError(
                "EMBEDDING_UNAVAILABLE",
                "The configured embedding service returned an invalid response",
                status_code=502,
            ) from exc

    def _validate_vectors(self, vectors: list[list[float]], expected_count: int) -> None:
        if len(vectors) != expected_count:
            raise ValueError("embedding response count mismatch")
        if any(len(vector) != self._dimensions for vector in vectors):
            raise ValueError("embedding response dimension mismatch")
        if any(not math.isfinite(value) for vector in vectors for value in vector):
            raise ValueError("embedding response contains a non-finite number")


def build_embedding_provider(
    settings: "Settings",
    *,
    timeout_seconds: float,
) -> tuple[EmbeddingProvider, httpx.AsyncClient | None]:
    """Single source of truth for choosing the embedding backend.

    Returns the provider and the httpx client that owns its connection (or
    ``None`` for the offline hash provider, which needs no client). The caller
    is responsible for closing a returned client.

    Index-time and query-time embeddings MUST come from this one function: if
    documents are indexed with the hash embedding but queried with a semantic
    service (or vice versa), the two vector spaces do not match and vector
    recall silently degrades to noise.
    """
    if settings.embedding_api_url is not None:
        client = httpx.AsyncClient(timeout=timeout_seconds, trust_env=False)
        api_key = (
            settings.embedding_api_key.get_secret_value()
            if settings.embedding_api_key
            else None
        )
        provider = HttpEmbeddingProvider(
            client,
            str(settings.embedding_api_url),
            settings.embedding_model,
            settings.embedding_dimensions,
            api_key,
        )
        return provider, client
    return DeterministicHashEmbedding(settings.embedding_dimensions), None
