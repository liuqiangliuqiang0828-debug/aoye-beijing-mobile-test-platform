#!/bin/bash
# 启动测试平台
set -e
echo "🚀 启动 Token 测试平台 v2.1.0..."
cd "$(dirname "$0")/.."
uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --log-level info
