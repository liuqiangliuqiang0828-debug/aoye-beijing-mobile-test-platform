# 北京移动 Token 模型聚合平台 — 模拟测试平台

**版本**: v1.0.0  
**目标**: 严格对标北京移动征集文件五大赛道（文本/图像/视频/语音音频/多模态理解）测试标准

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置模型端点 (config/models.yaml)

# 3. 启动服务
python src/api/server.py
```

访问 `http://0.0.0.0:8000` 打开测试平台

## 目录结构

```
config/          # 赛道配置 + 模型配置
src/             # 后端代码
├── engine/      # 测试引擎
├── api/         # FastAPI 服务
└── utils/       # 工具函数
web/             # 前端 HTML/JS/CSS
```
