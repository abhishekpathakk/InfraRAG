# Learning Log: InfraRAG

## Summary (updated continuously)
- **Current phase:** Phase 1 (Repo Structure, Architecture & Foundation)
- **What works now:** Clean repository layout, architecture design, CI workflow skeleton, and initial learning documentation.
- **Total estimated AWS cost so far:** $0.00 (Local design & scaffolding; no AWS resources provisioned yet).

---

## Phase 1: Repo Structure, Architecture & Foundation (2026-10-27)

### What we did
1. Selected the project name: **`InfraRAG`** (DevOps & SRE Runbook Assistant).
2. Defined the complete repository layout with modular separation between ingestion, indexing, retrieval, generation, API handlers, and Terraform IaC.
3. Created [README.md](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/README.md) with an end-to-end architecture diagram in Mermaid detailing both the offline/indexing path and the online/query path.
4. Created baseline configuration files:
   - [.gitignore](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/.gitignore) (ignoring `.env`, FAISS indices, virtual environments, terraform cache)
   - [requirements.txt](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/requirements.txt) & [requirements-dev.txt](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/requirements-dev.txt) (pinned for Python 3.12: `boto3`, `faiss-cpu`, `numpy`, `pydantic`, `pytest`, `ruff`)
   - [src/config.py](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/src/config.py) with `USE_MOCK_BEDROCK=True` toggle to ensure 100% free local development.
   - Initial [learn.md](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/learn.md) to record all technical learnings, trade-offs, and interview notes.
5. Implemented the **Autonomous Loop Engineer**:
   - [AGENTS.md](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/AGENTS.md): Project agent directive enforcing zero-cost guardrails, automated test loops, and continuous logging.
   - [scripts/loop_engineer.py](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/scripts/loop_engineer.py): Automated CLI loop runner for self-checks, cost verification, and automated testing.
   - [.github/workflows/ci.yml](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/.github/workflows/ci.yml): GitHub Actions CI pipeline running ruff, pytest, and terraform validate.
6. Populated realistic incident runbooks in `data/runbooks/`:
   - [kubernetes_crashloopbackoff.md](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/data/runbooks/kubernetes_crashloopbackoff.md)
   - [kubernetes_oom_killed.md](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/data/runbooks/kubernetes_oom_killed.md)
   - [istio_503_service_unavailable.md](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/data/runbooks/istio_503_service_unavailable.md)
   - [istio_mtls_strict_failures.md](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/data/runbooks/istio_mtls_strict_failures.md)

### Concepts learned
- **RAG (Retrieval-Augmented Generation):** Rather than retraining or fine-tuning an LLM on proprietary docs (which is expensive and prone to stale facts), RAG searches relevant documents at runtime and injects them into the prompt as "open-book" context.
  - *One-line analogy:* Giving an engineer an open-book exam with the exact runbook pages clipped to the question, instead of asking them to memorize every alert manual.
- **Embeddings:** Numerical representations (vectors of floating-point numbers, e.g., 1024 dimensions in Amazon Titan Text v2) that capture the semantic meaning of text. Words/sentences with similar meaning point in similar directions in multi-dimensional space.
  - *One-line analogy:* GPS coordinates for concepts—"Pod CrashLoopBackOff" and "container restart failure" are located right next to each other on the map.
- **Vector Index (FAISS):** Facebook AI Similarity Search. A high-performance C++/Python library that performs fast nearest-neighbor lookups in vector space without running an expensive always-on database cluster.
  - *One-line analogy:* An index at the back of a textbook that lets you jump straight to the relevant pages in milliseconds, saved as a lightweight file on disk or S3.
- **Groundedness & Hallucination Prevention:** The practice of strictly constraining the LLM to only answer using provided context snippets, requiring explicit citations, and fallback ("I don't know") when the context lacks the answer.
  - *One-line analogy:* A strict courtroom witness who only testifies to what is written in the police log and answers "I cannot recall / not stated in record" otherwise.
- **Autonomous Loop Engineering:** Embedding continuous verification (lint, test, cost check, hit-rate) into an autonomous loop agent that catches regressions before human review.
  - *One-line analogy:* A pre-commit hook that doesn't just block broken code, but diagnoses the root cause and suggests the fix.

### Issues faced and how we fixed them
| Issue / error message | Root cause | Fix | How to avoid next time |
| :--- | :--- | :--- | :--- |
| Potential API cost / dependency on external keys during local dev | Cloud LLM/Embedding API calls incur per-token charges or fail without credentials | Introduced `USE_MOCK_BEDROCK=True` in `config.py` and local fallback runners | Always build an offline/local zero-cost simulation layer for rapid iteration and CI |

### Achievements
- Established clean separation of concerns (`chunker`, `embeddings`, `vector_store`, `generator`).
- Designed a 100% free local development flow and a zero-idle-cost AWS architecture (<$5/month, $0 idle).
- Created the autonomous loop engineer runner ([scripts/loop_engineer.py](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/scripts/loop_engineer.py)) and GitHub Actions CI.

### Interview talking points
- *"As a DevOps engineer, cost and operational simplicity are primary constraints. Instead of paying $70-$150/month for an always-on vector database like OpenSearch Serverless or Pinecone, I engineered InfraRAG using FAISS serialized to S3 and served via AWS Lambda. For an internal DevOps runbook library (<50,000 chunks), this yields sub-second retrieval at essentially $0 idle cost."*
- *"We chose Bedrock Titan Text Embeddings v2 with 1024 dimensions over v1 because v2 supports normalized embeddings (allowing fast inner-product cosine similarity) and significantly better semantic recall on technical DevOps jargon."*
- *"I built an autonomous loop engineer agent into the repository to enforce linting, unit testing, and retrieval evaluation on every change, ensuring zero regressions without manual toil."*

