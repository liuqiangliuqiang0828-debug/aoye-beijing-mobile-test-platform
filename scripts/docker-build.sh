#!/bin/bash
# Docker 构建和运行
set -e

IMAGE="beijing-mobile-test-platform"
VERSION="2.1.0"

echo "🐳 构建 Docker 镜像 ${IMAGE}:${VERSION}..."
docker build -t "${IMAGE}:${VERSION}" .

echo "🚀 运行容器..."
docker run -d --name test-platform \
  -p 8000:8000 \
  "0.0.0.0" \
  "${IMAGE}:${VERSION}"

echo "✅ 访问 http://localhost:8000"
