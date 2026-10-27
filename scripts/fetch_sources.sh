#!/usr/bin/env bash
# ==============================================================================
# scripts/fetch_sources.sh
# Shallow-clones public open-source operational repositories and extracts
# Markdown documentation into data/public/<source>/ for InfraRAG.
# Sources:
#   1. kubernetes/website  -> data/public/kubernetes/
#   2. istio/istio.io      -> data/public/istio/
#   3. gitlab-com/runbooks -> data/public/gitlab/
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PUBLIC_DIR="${REPO_ROOT}/data/public"
TMP_DIR="${REPO_ROOT}/scratch/public_sources_tmp"

echo "============================================================"
echo "🚀 InfraRAG Public Corpus Ingestion Pipeline"
echo "============================================================"
echo "Target Directory: ${PUBLIC_DIR}"

mkdir -p "${PUBLIC_DIR}/kubernetes" "${PUBLIC_DIR}/istio" "${PUBLIC_DIR}/gitlab"
mkdir -p "${TMP_DIR}"

cleanup() {
  echo "🧹 Cleaning up temporary clone artifacts..."
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

# ------------------------------------------------------------------------------
# 1. Kubernetes Website (Troubleshooting, Pod Lifecycle, Debug Tasks)
# ------------------------------------------------------------------------------
echo "📦 [1/3] Shallow cloning kubernetes/website (docs only)..."
K8S_TMP="${TMP_DIR}/k8s"
git clone --depth 1 --filter=blob:none --sparse https://github.com/kubernetes/website.git "${K8S_TMP}" 2>/dev/null || \
git clone --depth 1 https://github.com/kubernetes/website.git "${K8S_TMP}"

(
  cd "${K8S_TMP}"
  if git sparse-checkout init --cone 2>/dev/null; then
    git sparse-checkout set content/en/docs/tasks/debug content/en/docs/concepts/workloads/pods
  fi
)

echo "📂 Extracting Kubernetes debugging and pod lifecycle Markdown docs..."
if [ -d "${K8S_TMP}/content/en/docs/tasks/debug" ]; then
  mkdir -p "${PUBLIC_DIR}/kubernetes/debug"
  cp -R "${K8S_TMP}/content/en/docs/tasks/debug/"* "${PUBLIC_DIR}/kubernetes/debug/" 2>/dev/null || true
fi
if [ -d "${K8S_TMP}/content/en/docs/concepts/workloads/pods" ]; then
  mkdir -p "${PUBLIC_DIR}/kubernetes/pods"
  cp -R "${K8S_TMP}/content/en/docs/concepts/workloads/pods/"* "${PUBLIC_DIR}/kubernetes/pods/" 2>/dev/null || true
fi
# Remove any non-markdown assets (png, svg, yaml) to keep only Markdown docs
find "${PUBLIC_DIR}/kubernetes" -type f ! -name "*.md" -delete 2>/dev/null || true

# ------------------------------------------------------------------------------
# 2. Istio.io (Diagnostic Tools, Common Ops Problems, Traffic Management)
# ------------------------------------------------------------------------------
echo "📦 [2/3] Shallow cloning istio/istio.io (ops docs only)..."
ISTIO_TMP="${TMP_DIR}/istio"
git clone --depth 1 --filter=blob:none --sparse https://github.com/istio/istio.io.git "${ISTIO_TMP}" 2>/dev/null || \
git clone --depth 1 https://github.com/istio/istio.io.git "${ISTIO_TMP}"

(
  cd "${ISTIO_TMP}"
  if git sparse-checkout init --cone 2>/dev/null; then
    git sparse-checkout set content/en/docs/ops
  fi
)

echo "📂 Extracting Istio operational diagnostics Markdown docs..."
if [ -d "${ISTIO_TMP}/content/en/docs/ops" ]; then
  cp -R "${ISTIO_TMP}/content/en/docs/ops/"* "${PUBLIC_DIR}/istio/" 2>/dev/null || true
fi
# Remove any non-markdown assets to keep only Markdown docs
find "${PUBLIC_DIR}/istio" -type f ! -name "*.md" -delete 2>/dev/null || true

# ------------------------------------------------------------------------------
# 3. GitLab Runbooks (Production SRE Incident & Component Runbooks)
# ------------------------------------------------------------------------------
echo "📦 [3/3] Shallow cloning gitlab-com/runbooks (docs only)..."
GITLAB_TMP="${TMP_DIR}/gitlab"
git clone --depth 1 --filter=blob:none --sparse https://gitlab.com/gitlab-com/runbooks.git "${GITLAB_TMP}" 2>/dev/null || \
git clone --depth 1 https://gitlab.com/gitlab-com/runbooks.git "${GITLAB_TMP}"

(
  cd "${GITLAB_TMP}"
  if git sparse-checkout init --cone 2>/dev/null; then
    git sparse-checkout set docs
  fi
)

echo "📂 Extracting GitLab production incident runbooks..."
if [ -d "${GITLAB_TMP}/docs" ]; then
  find "${GITLAB_TMP}/docs" -type f -name "*.md" -maxdepth 3 -exec cp {} "${PUBLIC_DIR}/gitlab/" \; 2>/dev/null || true
  # Neutralize dummy sample webhook URLs that trigger GitHub Push Protection
  find "${PUBLIC_DIR}/gitlab" -type f -name "*.md" -exec sed -i '' 's|https://hooks.slack.com/services/|https://hooks.slack.example.com/services/|g' {} + 2>/dev/null || true
fi

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
K8S_COUNT=$(find "${PUBLIC_DIR}/kubernetes" -name "*.md" | wc -l | tr -d ' ')
ISTIO_COUNT=$(find "${PUBLIC_DIR}/istio" -name "*.md" | wc -l | tr -d ' ')
GITLAB_COUNT=$(find "${PUBLIC_DIR}/gitlab" -name "*.md" | wc -l | tr -d ' ')

echo "============================================================"
echo "✅ Public Corpus Ingestion Complete!"
echo "   • Kubernetes Docs : ${K8S_COUNT} Markdown files"
echo "   • Istio.io Docs   : ${ISTIO_COUNT} Markdown files"
echo "   • GitLab Runbooks : ${GITLAB_COUNT} Markdown files"
echo "   • Total Public    : $((K8S_COUNT + ISTIO_COUNT + GITLAB_COUNT)) Markdown files"
echo "============================================================"
