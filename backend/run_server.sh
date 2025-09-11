#!/bin/bash
cd /home/runner/workspace/backend
export LD_LIBRARY_PATH="/nix/store/zdpby3l6azi78sl83cpad2qjpfj25aqx-glibc-2.40-66/lib:/nix/store/54s4kb8kx5jnlwa23phj9qwp20a0hm6g-gcc-14.2.1-lib/lib:$LD_LIBRARY_PATH"
poetry run uvicorn backend_server:app --host 0.0.0.0 --port 8000 --reload
