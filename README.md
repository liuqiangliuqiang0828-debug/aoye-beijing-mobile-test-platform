# 北京移动 Token 模型聚合平台 — 模拟测试系统

**版本**: v2.1.0  
**目标**: 严格对标北京移动征集文件 **六大赛道**（文本/图像/视频/语音音频/多模态理解/行业专用大模型）测试标准

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置模型端点 (config/models.yaml)

# 3. 启动服务
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
# 或
./scripts/run.sh
```

访问 `http://0.0.0.0:8000` 打开测试平台

## 快速测试

```bash
./scripts/quick_test.sh
```

## 目录结构

```
config/            # 赛道配置 + 模型配置
├── tracks/        # 按赛道拆分的测试标准
│   ├── text.yaml
│   ├── image.yaml
│   ├── video.yaml
│   ├── audio.yaml
│   ├── multimodal.yaml
│   └── industry.yaml
├── models.yaml    # 13+ 候选模型端点配置
├── tracks.yaml    # 汇总配置
src/               # 后端代码
├── engine/        # 测试引擎
│   ├── generator.py   # 测试用例生成器
│   └── runner.py  # 执行引擎
├── api/           # FastAPI 服务
│   └── server.py
└── utils/         # 工具函数
    ├── config_loader.py  # 配置加载
    ├── metrics.py        # 指标采集
    └── report_generator.py  # 报告生成
web/               # 前端 HTML/CSS/JS
reports/           # 生成的 HTML/JSON 报告
scripts/           # 运维脚本
tests/             # 单元测试
docs/              # 设计文档
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/config/models/summary` | 模型汇总 |
| GET | `/api/config/models` | 全部模型 |
| GET | `/api/config/tracks` | 赛道列表 |
| POST | `/api/test/run-all` | 启动全部赛道测试 |
| POST | `/api/test/run-track/{track}` | 启动指定赛道 |
| GET | `/api/metrics/summary` | 实时指标 |
| GET | `/api/results` | 测试历史 |
| GET | `/api/report` | 生成的报告 |

## 六大赛道

1. **文本大模型服务** — 生成速度、上下文窗口、首字时延、RPM/TPM
2. **图像生成大模型服务** — 分辨率、格式、QPM、合规水印
3. **视频生成大模型服务** — 分辨率+编码、FPS、并行处理
4. **语音与音频类服务** — ASR/TTS 时延、QPM、翻译准确度
5. **多模态理解服务** — 多模态对话、图像/视频理解 QPM
6. **行业专用大模型服务** — 领域基准准确率、可用性、数据合规

## 部署环境

- **运行环境**: 本地模拟，后续可切换至北京移动沙箱
- **访问地址**: `http://<server_ip>:8000`

## Docker 部署

```bash
docker build -t beijing-mobile-test .
docker run -d -p 8000:8000 beijing-mobile-test
```

---

对标北京移动 2026年 Token 模型聚合平台合作伙伴征集文件
