"""
InfraRAG Streamlit Web UI.

A modern, low-overhead SRE & DevOps runbook assistant interface.
"""

import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import streamlit as st  # noqa: E402
from src.chain import RAGChain  # noqa: E402
from src.config import settings  # noqa: E402

# Page configuration
st.set_page_config(
    page_title="InfraRAG | DevOps & SRE Copilot",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for rich aesthetics
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #FF9900 0%, #326CE5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #8892b0;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #1e222d;
        border-radius: 8px;
        padding: 12px;
        border: 1px solid #2e3440;
    }
    .citation-badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        background-color: #2e3440;
        color: #00d2ff;
        font-family: monospace;
        font-size: 0.85rem;
        margin-right: 6px;
        margin-bottom: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_rag_chain() -> RAGChain:
    chain = RAGChain()
    # Ingest runbooks if not already loaded
    cache_file = settings.CACHE_DIR / "chunks.json"
    if cache_file.exists():
        chain.vector_store.load_local(settings.CACHE_DIR)
    else:
        chain.ingest_directory(settings.DATA_DIR)
        chain.vector_store.save_local(settings.CACHE_DIR)
    return chain


def main():
    st.markdown('<div class="main-header">⚡ InfraRAG: DevOps & SRE Assistant</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Zero-cost, grounded Q&A over Kubernetes, Istio, and DevOps incident runbooks with strict source citations.</div>',
        unsafe_allow_html=True,
    )

    chain = get_rag_chain()

    # Sidebar controls & metrics
    with st.sidebar:
        st.header("⚙️ System Status")
        mode = "100% Free / Mock Mode" if settings.USE_MOCK_BEDROCK else "AWS Bedrock (ap-south-1)"
        st.info(f"**Execution Mode:**\n{mode}")
        st.write(f"**Indexed Chunks:** {len(chain.vector_store.chunks)}")
        st.write("**Source Runbooks:** 4 Markdown files")
        st.write("**Target Spend:** $0.00 / Free Tier")

        st.divider()

        if st.button("🔄 Re-index Runbooks", use_container_width=True):
            with st.spinner("Re-chunking and rebuilding FAISS index..."):
                count = chain.ingest_directory(settings.DATA_DIR)
                chain.vector_store.save_local(settings.CACHE_DIR)
                st.success(f"Indexed {count} chunks!")
                st.rerun()

        st.divider()
        st.markdown(
            "### 💡 Sample Prompts\n"
            "- *What causes Exit Code 137?*\n"
            "- *How do I triage CrashLoopBackOff?*\n"
            "- *What do Envoy UF flags mean in Istio 503s?*\n"
            "- *How to configure STRICT mTLS bypass for metrics?*\n"
            "- *How to bake a cake?* (Refusal test)"
        )

    # Main Query Interface
    col1, col2 = st.columns([4, 1])
    with col1:
        user_query = st.text_input(
            "Incident / Runbook Query",
            placeholder="e.g., What causes container Exit Code 137 in Kubernetes?",
            label_visibility="collapsed",
        )
    with col2:
        search_clicked = st.button("Ask Assistant", type="primary", use_container_width=True)

    if (search_clicked or user_query) and user_query.strip():
        with st.spinner("Retrieving relevant runbook chunks and generating grounded response..."):
            response = chain.answer_question(user_query.strip())

        # Response container
        st.subheader("📋 Response")

        # Confidence tag
        if response.confidence == "high":
            st.success(f"**Confidence:** HIGH (Grounded in {len(response.citations)} runbook sections)")
        else:
            st.warning("**Confidence:** LOW / UNGROUNDED")

        st.markdown(response.answer)

        # Source Citations
        if response.citations:
            st.subheader("📎 Source Citations")
            for cit in response.citations:
                st.markdown(
                    f"- 📄 **`{cit.source_file}`** | Section: *{cit.section_title}* | Chunk: `{cit.chunk_id}` | Similarity Score: **{cit.relevance_score:.4f}**"
                )

        # Latency & Cost Metrics
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Total Latency", f"{response.latency_ms:.1f} ms")
        with m2:
            st.metric("Retrieval Latency", f"{response.retrieval_latency_ms:.1f} ms")
        with m3:
            st.metric("Generation Latency", f"{response.generation_latency_ms:.1f} ms")
        with m4:
            st.metric("Estimated Cost", f"${response.estimated_cost_usd:.6f}")

        # Retrieved Chunks inspection
        with st.expander("🔍 View Raw Retrieved Context Chunks"):
            for i, chunk in enumerate(response.retrieved_chunks, 1):
                st.markdown(f"**Chunk {i} ({chunk.source_file} - {chunk.section_title})**")
                st.code(chunk.content, language="markdown")


if __name__ == "__main__":
    main()
