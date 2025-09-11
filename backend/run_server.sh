#!/bin/bash
set -euo pipefail
cd /home/runner/workspace/backend

echo "🚀 Starting ToneBridge backend with Pure Nix environment..."

# 🧹 Clear all contaminating environment variables that cause glibc conflicts
unset LD_LIBRARY_PATH 2>/dev/null || true
unset LD_PRELOAD 2>/dev/null || true
unset LD_AUDIT 2>/dev/null || true
unset LD_ASSUME_KERNEL 2>/dev/null || true
unset GLIBC_TUNABLES 2>/dev/null || true

echo "✅ Cleared contaminating environment variables"

# 🐍 Safe Pure Nix Python execution with RPATH-based library detection
echo "🔍 Locating Python interpreter..."
PY=$(command -v python)
echo "📍 Found Python at: $PY"

echo "🧪 Running Python sanity check..."
$PY -c 'import sys; print(f"✅ Python {sys.version} OK")'

# 🌟 Set clean Python environment
export PYTHONUNBUFFERED=1
export PYTHONPATH="/home/runner/workspace/backend:${PYTHONPATH:-}"

echo "🎯 Starting ToneBridge backend server..."
echo "📂 Working directory: $(pwd)"
echo "🐍 Python executable: $PY"

# 🚀 Execute with pure Nix closure (RPATH handles all libraries automatically)
exec $PY backend_server.py
