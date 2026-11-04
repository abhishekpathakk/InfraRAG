"""
Embeddings Provider for InfraRAG.

Supports:
1. Amazon Bedrock Titan Text Embeddings v2 (1024-dim, unit normalized).
2. Mock Embedding Provider (Offline local mode for zero-cost dev/test).
3. Sovereign Local FastEmbed Provider (BAAI/bge-small-en-v1.5, verified via post-download SHA-256).
"""

import hashlib
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


class BaseEmbeddingProvider(ABC):
    """Abstract Base Class for embedding providers."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string into a float vector."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of text strings in batch."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality."""
        pass


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Offline local embedding generator.
    Produces deterministic 1024-dimensional unit-normalized vectors.
    Uses semantic term weighting so related DevOps concepts (e.g., OOMKilled, memory, exit 137)
    have high cosine similarity.
    Works with numpy or pure Python standard library.
    """

    def __init__(self, dimension: int = 1024, use_clusters: bool = True):
        self._dim = dimension
        self.use_clusters = use_clusters
        self._concept_clusters = {
            "memory": [
                "oomkilled", "exit code 137", "sigkill", "memorypressure", "ram", "heap",
                "cgroup", "limits", "node memory", "describe node", "memory pressure", "top pod",
                "-xx:maxrampercentage",
            ],
            "crash": [
                "crashloopbackoff", "restart", "exit code 1", "exit code 139", "liveness probe",
                "readiness", "terminated", "segmentation", "segfault", "rollout", "previous",
                "crashed container", "logs --previous",
            ],
            "istio_503": [
                "503", "service unavailable", "envoy", "uf", "uc", "uo", "nr", "upstream",
                "circuit", "proxy-status", "synchronization", "istiod",
            ],
            "mtls": [
                "mtls", "peerauthentication", "strict", "destinationrule", "istio_mutual",
                "certificate", "handshake", "secret", "permissive", "portlevelmtls",
                "proxy-config secret",
            ],
            "disk_pressure": [
                "diskpressure", "ephemeral-storage", "imagefs", "nodefs",
                "evictionhard", "kubelet eviction", "disk pressure", "nodediskpressure",
            ],
            "ingress_504": [
                "504", "gateway timeout", "proxy-read-timeout", "proxy-connect-timeout",
                "504 gateway timeout",
            ],
            "docker_space": [
                "docker", "docker prune", "dangling", "build cache", "overlay2",
                "docker system prune", "no space left on device", "docker image prune",
            ],
            "aws_nlb": [
                "target.failedhealthchecks", "network load balancer", "nlb", "target group health",
                "unhealthy target", "failedhealthchecks",
            ],
            "k8s_debug": [
                "crictl", "crictl ps", "crictl logs", "crictl inspect", "cri runtime",
                "container runtime", "container runtimes",
                "ephemeral-containers", "ephemeral container", "kubectl debug",
            ],
            "istio_analyze": [
                "istioctl analyze", "istioctl-analyze",
            ],
            "gitlab_sre": [
                "teleport", "tsh db", "patroni", "patronictl", "cloudsqldatabasedown",
                "connect_to_database_console_via_teleport", "patroni failover",
            ],
        }

        import re
        self._compiled_clusters = []
        for idx, (cluster_name, keywords) in enumerate(self._concept_clusters.items()):
            patterns = []
            for kw in keywords:
                if len(kw) <= 4:
                    patterns.append(re.compile(rf"\b{re.escape(kw)}\b"))
                else:
                    patterns.append(re.compile(re.escape(kw)))
            self._compiled_clusters.append((idx * 80, patterns))

        if self.use_clusters and self._compiled_clusters:
            min_required_dim = max(bucket_start + 65 for bucket_start, _ in self._compiled_clusters)
            if self._dim < min_required_dim:
                raise ValueError(
                    f"MockEmbeddingProvider configuration error: use_clusters=True requires dimension >= {min_required_dim} "
                    f"to allocate all {len(self._compiled_clusters)} concept cluster buckets without truncation (configured dimension is {self._dim}). "
                    f"Either set dimension >= {min_required_dim} (standard is 1024) or set use_clusters=False."
                )

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> list[float]:
        normalized_text = text.lower()
        vec = [0.0] * self._dim

        tokens = normalized_text.split()
        for token in tokens:
            seed = int(hashlib.md5(token.encode("utf-8"), usedforsecurity=False).hexdigest(), 16) % self._dim
            vec[seed] += 0.3

        if self.use_clusters:
            for bucket_start, patterns in self._compiled_clusters:
                for pat in patterns:
                    if pat.search(normalized_text):
                        for b in range(bucket_start, bucket_start + 65):
                            if b < self._dim:
                                vec[b] += 15.0

        # L2-normalize vector so ||v|| = 1.0
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            return [x / norm for x in vec]
        vec[0] = 1.0
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]


class BedrockTitanEmbeddingProvider(BaseEmbeddingProvider):
    """
    Amazon Bedrock Titan Text Embeddings v2.
    Model ID: amazon.titan-embed-text-v2:0
    Dimensions: 1024
    Normalized: True (Inner Product = Cosine Similarity)
    """

    def __init__(
        self,
        region_name: str = settings.AWS_REGION,
        model_id: str = settings.BEDROCK_EMBEDDING_MODEL_ID,
        dimension: int = settings.EMBEDDING_DIMENSION,
    ):
        self._region = region_name
        self._model_id = model_id
        self._dim = dimension
        self._client: Any = None

    def _get_client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config

            boto_cfg = Config(
                retries={"mode": "adaptive", "max_attempts": 4},
                read_timeout=20,
                connect_timeout=5,
            )
            self._client = boto3.client("bedrock-runtime", region_name=self._region, config=boto_cfg)
        return self._client

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> list[float]:
        client = self._get_client()
        body = json.dumps({
            "inputText": text,
            "dimensions": self._dim,
            "normalize": True,
        })

        # Exponential backoff retry loop for AWS Bedrock rate limits
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                response = client.invoke_model(
                    modelId=self._model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=body,
                )
                response_body = json.loads(response["body"].read().decode("utf-8"))
                return response_body["embedding"]
            except Exception as e:
                err_msg = str(e)
                if "ThrottlingException" in err_msg or "Too many requests" in err_msg:
                    sleep_time = 1.0 * (2**attempt)
                    logger.warning(f"Bedrock throttled; backing off for {sleep_time:.1f}s (attempt {attempt+1}/{max_attempts})")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Failed to invoke Bedrock Titan Embeddings: {e}")
                    raise

        raise RuntimeError("Bedrock Titan Embedding failed after maximum retry attempts due to throttling.")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # Add small spacing between consecutive embeddings to prevent burst throttling
        results = []
        for t in texts:
            results.append(self.embed_text(t))
            time.sleep(0.15)
        return results


class LocalFastEmbedProvider(BaseEmbeddingProvider):
    """
    Open-Source Neural Embedding Provider using FastEmbed (ONNX Runtime).
    Default model: BAAI/bge-small-en-v1.5 (dim=384, source repo: Qdrant/bge-small-en-v1.5-onnx-Q).

    Note on Upstream Resolution & Provenance:
    FastEmbed resolves upstream repository HEAD during download. Weight integrity and immutability
    are enforced post-download via runtime SHA-256 verification on the optimized ONNX model binary
    (EXPECTED_ONNX_SHA256 = '51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431').
    Provides local neural dense embeddings without cloud API dependencies.
    """

    EXPECTED_ONNX_SHA256 = "51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431"

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        expected_sha256: str | None = EXPECTED_ONNX_SHA256,
        batch_size: int = 64,
        cache_dir: str | None = None,
    ):
        try:
            from fastembed import TextEmbedding
        except ImportError:
            raise ImportError("fastembed is required for LocalFastEmbedProvider. Install with `pip install fastembed`.")

        self.model_name = model_name
        self.batch_size = batch_size
        effective_cache = cache_dir or os.getenv("FASTEMBED_CACHE_PATH", None)

        self._model = TextEmbedding(
            model_name=model_name,
            cache_dir=effective_cache,
        )

        # Enforce fail-closed cryptographic binary integrity on the loaded ONNX model
        if expected_sha256:
            raw_model_dir = getattr(self._model.model, "_model_dir", None)
            if not raw_model_dir:
                raise RuntimeError(
                    "FastEmbed integrity check failed: model directory attribute '_model_dir' "
                    "could not be resolved from loaded TextEmbedding instance."
                )
            model_dir = Path(raw_model_dir)
            if not model_dir.exists():
                raise RuntimeError(
                    f"FastEmbed integrity check failed: resolved model directory does not exist: {model_dir}"
                )
            onnx_file = model_dir / "model_optimized.onnx"
            if not onnx_file.exists():
                candidates = list(model_dir.glob("*.onnx"))
                if candidates:
                    onnx_file = candidates[0]
                else:
                    raise RuntimeError(
                        f"FastEmbed integrity check failed: no ONNX binary found in {model_dir}"
                    )

            try:
                self.onnx_sha256 = hashlib.sha256(onnx_file.read_bytes()).hexdigest()
            except Exception as e:
                raise RuntimeError(
                    f"FastEmbed integrity check failed: unable to compute SHA-256 for {onnx_file}: {e}"
                ) from e

            if self.onnx_sha256 != expected_sha256:
                raise RuntimeError(
                    f"FastEmbed ONNX integrity violation: expected SHA-256 {expected_sha256}, "
                    f"got {self.onnx_sha256} for {onnx_file}"
                )
        else:
            raw_model_dir = getattr(self._model.model, "_model_dir", None)
            opt_model_dir = Path(raw_model_dir) if raw_model_dir else None
            if opt_model_dir and (opt_model_dir / "model_optimized.onnx").exists():
                self.onnx_sha256 = hashlib.sha256((opt_model_dir / "model_optimized.onnx").read_bytes()).hexdigest()
            else:
                self.onnx_sha256 = ""

        # Determine actual embedding dimension
        probe_emb = list(self._model.embed(["probe"]))[0]
        self._dim = len(probe_emb)

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> list[float]:
        embs = list(self._model.embed([text]))
        return [float(x) for x in embs[0]]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        embs = list(self._model.embed(texts, batch_size=self.batch_size))
        return [[float(x) for x in emb] for emb in embs]


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Factory returns Local FastEmbed, Mock, or AWS Bedrock provider based on configuration."""
    provider_type = os.getenv("EMBEDDING_PROVIDER", getattr(settings, "EMBEDDING_PROVIDER", "local")).lower()
    if provider_type in ("local", "fastembed"):
        logger.info("Using Sovereign LocalFastEmbedProvider (BAAI/bge-small-en-v1.5, 384-dim).")
        return LocalFastEmbedProvider()
    dim = int(os.getenv("EMBEDDING_DIMENSION", str(getattr(settings, "EMBEDDING_DIMENSION", 1024))))
    if provider_type == "mock" or os.getenv("USE_MOCK_BEDROCK", "").lower() in ("true", "1", "yes"):
        logger.info("Using MockEmbeddingProvider for offline execution.")
        return MockEmbeddingProvider(dimension=dim)
    return BedrockTitanEmbeddingProvider(
        region_name=settings.AWS_REGION,
        model_id=settings.BEDROCK_EMBEDDING_MODEL_ID,
        dimension=dim,
    )
