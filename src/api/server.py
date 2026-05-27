"""
FastAPI 主服务
提供 REST API + 静态 Web 页面
"""

import asyncio
import os
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime

from src.engine.runner import TestRunner
from src.engine.generator import TestCaseGenerator
from src.utils.config_loader import ConfigLoader
from src.utils.report_generator import ReportGenerator


# ────────── App ──────────
app = FastAPI(
    title="北京移动 Token 测试平台",
    version="1.0.0",
    description="严格对标北京移动征集文件五大赛道模拟测试系统",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global runner
runner: Optional[TestRunner] = None
report_gen = ReportGenerator()


# ────────── 初始化 ──────────
@app.on_event("startup")
async def on_startup():
    global runner
    runner = TestRunner()
    print("[INFO] Test Platform started")


# ────────── 配置查询 API ──────────
@app.get("/api/config/tracks")
async def api_get_tracks():
    """获取所有赛道"""
    return {"tracks": runner.config_loader.get_all_tracks()}


@app.get("/api/config/models")
async def api_get_models():
    """获取所有模型"""
    models = runner.config_loader.get_all_models()
    return {
        "total": len(models),
        "models_by_track": runner.config_loader.resolve_model_configs(),
        "models": models,
    }


@app.get("/api/config/models/{track}")
async def api_get_models_by_track(track: str):
    """获取某赛道下的模型列表"""
    models = runner.config_loader.get_models_by_track(track)
    enabled = [m for m in models if m.get("enabled", True)]
    return {
        "track": track,
        "total": len(models),
        "enabled": len(enabled),
        "models": enabled,
    }


# ────────── 测试控制 API ──────────
@app.post("/api/test/run-all")
async def api_run_all_tracks(concurrent: int = 10):
    """执行所有可用赛道"""
    if not runner:
        raise HTTPException(503, "Runner not initialized")
    result = await runner.run_all_tracks(concurrent)
    # 生成报告
    report_path = report_gen.generate_html_report(
        result.get("tracks", {}), result
    )
    return {
        "status": result.get("status"),
        "report_path": report_path,
    }


@app.post("/api/test/run-track/{track}")
async def api_run_track(track: str, concurrent: int = 10):
    """执行指定赛道"""
    if not runner:
        raise HTTPException(503, "Runner not initialized")
    if track not in runner.config_loader.get_all_tracks():
        raise HTTPException(400, "Unknown track: %s" % track)

    result = await runner.run_track(track, concurrent)
    report_path = report_gen.generate_html_report(
        {track: result}, result, run_id=result.get("run_id")
    )
    return {
        "status": result.get("status"),
        "run_id": result.get("run_id"),
        "report_path": report_path,
    }


@app.post("/api/test/run-model/{model_id}/{track}")
async def api_run_single_model(model_id: str, track: str, concurrent: int = 1):
    """只跑单个模型的单赛道"""
    if not runner:
        raise HTTPException(503, "Runner not initialized")
    model_cfg = runner.config_loader.get_model_by_id(model_id)
    if not model_cfg:
        raise HTTPException(404, "Model not found: %s" % model_id)

    result = await runner.run_model_single(model_id, track)
    return result


@app.post("/api/test/cancel-all")
async def api_cancel_all():
    """取消所有运行中测试"""
    runner.collector.reset()
    return {"status": "cancelled"}


# ────────── 指标查询 API ──────────
@app.get("/api/metrics/summary")
async def api_get_metrics_summary():
    """获取所有采集指标的汇总"""
    if not runner:
        raise HTTPException(503, "Runner not initialized")
    return runner.get_current_metrics()


@app.get("/api/metrics/{track}")
async def api_get_metrics_by_track(track: str):
    """获取某赛道的指标"""
    if not runner:
        raise HTTPException(503, "Runner not initialized")
    tm = runner.collector.get_track_metrics(track)
    return {track: {mid: m.to_dict() for mid, m in tm.items()}}


# ────────── 报告查询 API ──────────
@app.get("/api/report")
async def api_get_report_files():
    """获取所有生成的报告文件"""
    reports_dir = report_gen.output_dir
    if not os.path.exists(reports_dir):
        return {"reports": []}
    files = sorted([
        f for f in os.listdir(reports_dir)
        if f.endswith(('.html', '.json'))
    ])
    return {
        "reports": files,
        "reports_dir": reports_dir,
    }


@app.get("/api/health")
async def api_health():
    """健康检查"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "endpoint": "http://192.168.3.12:8000",
    }


# ────────── Web UI ──────────
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    """返回测试平台 Web UI"""
    web_dir = os.path.join(os.path.dirname(__file__), "..", "..", "web")
    index_path = os.path.join(web_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Web UI not found</h1>"


# Mount static files
web_dir = os.path.join(os.path.dirname(__file__), "..", "..", "web")
if os.path.exists(web_dir):
    app.mount("/static", StaticFiles(directory=web_dir), name="static")
