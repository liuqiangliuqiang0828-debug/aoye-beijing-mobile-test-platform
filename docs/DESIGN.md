# 北京移动 Token 测试平台 — 实现文档 v0.2

**版本**: v2.1.0  
**日期**: 2026-05-28  
**本地源码**: `/tmp/aoye-beijing-mobile-test-platform`  
**GitHub**: `liuqiangliuqiang0828-debug/aoye-beijing-mobile-test-platform`

---

## 已实现功能汇总

### Phase 1: 基础设施 ✅
- [x] GitHub 仓库初始化
- [x] 项目骨架搭建（完整目录结构）
- [x] Dockerfile + 部署脚本
- [x] 依赖管理（requirements.txt + pyproject.toml）
- [x] Git workflow（commit/push）

### Phase 2: 核心功能 ✅
- [x] 赛道1：文本大模型测试用例生成（短/中/长/超长，4类~40条用例/模型）
- [x] 赛道2：图像生成测试用例（landscape/portrait/square/ultrawide）
- [x] 赛道3：视频生成测试用例（占位，等待具体端点）
- [x] 赛道4：音频 TTS/ASR 测试用例
- [x] 赛道5：多模态理解测试用例
- [x] 赛道6：行业专用大模型 QA + 数据合规测试用例（新增！）
- [x] 流式 + 非流式模型调用闭环
- [x] 实时监控面板（自动刷新，5秒间隔）
- [x] API 服务器 + 对接接口（13个端点）
- [x] 报告自动生成（HTML + JSON）
- [x] 6赛道 YAML 配置拆分
- [x] 单元测试（TestConfigLoader, TestGenerator, TestMetrics, TestReport）

### Phase 3: 增强（进行中）
- [ ] 对接北京移动正式沙箱环境
- [ ] 与现有调度平台接口联调
- [ ] 性能优化（万级并发）

---

## 架构变更

### v2.0 → v2.1 变更

| 项目 | v2.0 | v2.1 |
|------|------|------|
| 赛道数 | 5 | **6**（新增行业专用） |
| 赛道配置 | tracks.yaml 单文件 | **tracks/ 子目录 + tracks.yaml** |
| 模型配置 | 手动硬编码模型ID | **ConfigLoader + models.yaml** |
| 前端 UI | 基础 Dashboard | **完整 Sidebar 导航 + 5个面板** |
| 报告 | 手动生成 | **自动 HTML + JSON 报告** |
| 容器化 | ❌ | ✅ Dockerfile |
| 测试 | ❌ | ✅ pytest 全量测试 |
| 行业赛道 | ❌ | ✅ QA + 合规两种子类型 |

### 文件数量

- Python 源码: 8 文件
- 配置 YAML: 8 文件  
- 前端 JS: 1 文件
- 前端 CSS: 1 文件
- 前端 HTML: 1 文件
- 测试: 1 文件
- 脚本: 3 文件（setup/run/quick_test）
- 文档: BUILDING.md + DESIGN.md
- 图像: 📊 3 张计划图（GTO+COT+SAMP）

---

## 已知限制

1. **视频赛道**: 测试用例已生成，但具体端点对接待后续版本
2. **ASR 赛道**: 需要实际音频文件上传，当前标记为 skipped
3. **图片赛道**: 需 SD WebUI 或 OpenAI images API 端点
4. **指标对标**: 基线数据需实际运行后从 vLLM 采集
5. **GTO/COT/SAMP**: 架构设计图待生成

---

## 下一步

| 步骤 | 任务 | 预计 |
|------|------|------|
| 1 | 运行 quick_test.sh 验证全部通过 | 现在 |
| 2 | _commit + push | 现在 |
| 3 | 生成 GTO/COT/SAMP 三张图 | 文档说明后 |
| 4 | 本地启动测试，验证 Web UI | 配置模型端点后 |
| 5 | 对接 b-mobile 实际测试环境 | 待博贝静移动侧提供 |
