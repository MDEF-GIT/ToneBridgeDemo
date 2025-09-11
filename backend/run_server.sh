#!/bin/bash
set -euo pipefail

# 🔍 Auto-detect environment and setup accordingly
detect_environment() {
    # Check if we're in Nix environment
    if [[ "${NIX_PATH:-}" != "" ]] || [[ "$(which python)" == *"/nix/store"* ]]; then
        echo "pure_nix"
    elif [[ -f "/etc/lsb-release" ]] && [[ "$(which python3 2>/dev/null)" != *"/nix/store"* ]]; then
        echo "ubuntu"
    else
        echo "hybrid"
    fi
}

# Determine script directory and navigate to backend
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting ToneBridge backend..."
echo "📂 Working directory: $(pwd)"

# Detect environment
ENV_TYPE=$(detect_environment)
echo "🔍 Detected environment: $ENV_TYPE"

# Environment-specific setup
case $ENV_TYPE in
    "pure_nix")
        echo "⚡ Pure Nix environment setup..."
        
        # 🧹 Clear contaminating environment variables for glibc compatibility
        unset LD_LIBRARY_PATH 2>/dev/null || true
        unset LD_PRELOAD 2>/dev/null || true
        unset LD_AUDIT 2>/dev/null || true
        unset LD_ASSUME_KERNEL 2>/dev/null || true
        unset GLIBC_TUNABLES 2>/dev/null || true
        
        echo "✅ Cleared contaminating environment variables"
        
        # Pure Nix Python with RPATH-based library detection
        PY=$(command -v python)
        echo "📍 Nix Python: $PY"
        ;;
        
    "ubuntu")
        echo "🐧 Ubuntu environment setup..."
        
        # Use system Python and set library paths
        PY=$(command -v python3)
        echo "📍 System Python: $PY"
        
        # Set system library paths
        export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/local/lib:/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
        echo "✅ System library paths configured"
        ;;
        
    "hybrid")
        echo "🔄 Hybrid environment setup..."
        
        # Try to use available Python
        if command -v python >/dev/null 2>&1; then
            PY=$(command -v python)
        elif command -v python3 >/dev/null 2>&1; then
            PY=$(command -v python3)
        else
            echo "❌ No Python interpreter found"
            exit 1
        fi
        
        echo "📍 Hybrid Python: $PY"
        
        # Safe library path setup
        export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
        ;;
esac

# Common Python environment setup
export PYTHONUNBUFFERED=1
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

# Sanity check
echo "🧪 Running Python sanity check..."
$PY -c 'import sys; print(f"✅ Python {sys.version} OK")'

# Environment-specific validation
echo "🔧 Environment validation..."
$PY -c "
import sys
import os
print(f'Environment: $ENV_TYPE')
print(f'Python: {sys.executable}')
print(f'LD_LIBRARY_PATH: {os.getenv(\"LD_LIBRARY_PATH\", \"Not set\")}')

# Test imports
try:
    import fastapi, uvicorn
    print('✅ Core packages available')
except ImportError as e:
    print(f'❌ Missing core packages: {e}')
    sys.exit(1)
"

echo "🎯 Starting ToneBridge backend server..."
echo "🌍 Environment: $ENV_TYPE"
echo "🐍 Python: $PY"

# Execute the server
exec $PY backend_server.py
