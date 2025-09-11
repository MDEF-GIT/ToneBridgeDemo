#!/bin/bash
cd /home/runner/workspace/backend

# ⚡ Fast Pure Nix Environment Setup (No Slow Searches)
echo "🚀 Setting up Pure Nix environment..."

# 🎯 Use standard system library paths (much faster)
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

# 🔧 Add essential Nix lib paths directly (no searching)
NIX_PYTHON_LIB=$(dirname $(dirname $(which python)))/lib
if [ -d "$NIX_PYTHON_LIB" ]; then
    export LD_LIBRARY_PATH="$NIX_PYTHON_LIB:$LD_LIBRARY_PATH"
    echo "✅ Added Python lib: $NIX_PYTHON_LIB"
fi

# 🌟 Set Python environment
export PYTHONUNBUFFERED=1
export PYTHONPATH="/home/runner/workspace/backend:$PYTHONPATH"

echo "✅ Library paths configured:"
echo "   /usr/lib/x86_64-linux-gnu (system libstdc++)"
echo "   $NIX_PYTHON_LIB (Nix Python)"

echo "🎯 Starting ToneBridge backend server..."

# 🐍 Direct Python execution (Pure Nix)
python backend_server.py
