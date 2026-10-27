"""
Embeddings Provider for InfraRAG.

Supports:
1. Amazon Bedrock Titan Text Embeddings v2 (1024-dim, unit normalized).
2. Mock Embedding Provider (100% Free, offline local mode for zero-cost dev/test).
"""

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
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
    100% Free offline local embedding generator.
    Produces deterministic 1024-dimensional unit-normalized vectors.
    Uses semantic term weighting so related DevOps concepts (e.g., OOMKilled, memory, exit 137)
    have high cosine similarity.
    Works with numpy or pure Python standard library.
    """

    def __init__(self, dimension: int = 1024):
        self._dim = dimension
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

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> list[float]:
        normalized_text = text.lower()
        vec = [0.0] * self._dim

        tokens = normalized_text.split()
        for token in tokens:
            seed = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self._dim
            vec[seed] += 0.3

        for bucket_start, patterns in self._compiled_clusters:
            for pat in patterns:
                if pat.search(normalized_text):
                    for b in range(bucket_start, bucket_start + 65):
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

            self._client = boto3.client("bedrock-runtime", region_name=self._region)
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


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Factory returns Mock or AWS Bedrock provider based on configuration."""
    if settings.USE_MOCK_BEDROCK:
        logger.info("Using 100% Free MockEmbeddingProvider for zero-cost execution.")
        return MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
    return BedrockTitanEmbeddingProvider(
        region_name=settings.AWS_REGION,
        model_id=settings.BEDROCK_EMBEDDING_MODEL_ID,
        dimension=settings.EMBEDDING_DIMENSION,
    )
