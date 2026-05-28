"""
FastAPI 主服务 - v2.1 增强版
提供 REST API、Web UI、结果持久化、设置管理
"""

import asyncio
import os
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.engine.runner import TestRunner
from src.engine.generator import TestCaseGenerator
from src.utils.config_loader import ConfigLoader
from src.utils.report_generator import ReportGenerator

# ────────── App ──────────
app = FastAPI(
    title="北京移动 Token 测试平台",
    version="2.1.0",
    description="严格对标北京移动征集文件六大赛道模拟测试系统",
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# Global state
runner: Optional[TestRunner] = None
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

report_gen = ReportGenerator(REPORTS_DIR)
RUNNING_TRACKS: Dict[str, asyncio.Task] = {}


# ────────── Models ──────────
class ModelConfigUpdate(BaseModel):
    id: str
    base_url: str = ""
    api_key: str = ""
    model_name: str = ""
    enabled: bool = True


class ModelBatchUpdate(BaseModel):
    models: List[ModelConfigUpdate]


class TrackRunRequest(BaseModel):
    concurrent: int = 10
    track: Optional[str] = None


# ────────── Helpers ──────────
def _save_results(data: dict):
    try:
        prev = {}
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE, 'r') as f:
                prev = json.load(f)
        prev[data['run_id']] = data
        os.makedirs(os.path.dirname(RESULTS_FILE) or '.', exist_ok=True)
        with open(RESULTS_FILE, 'w') as f:
            json.dump(prev, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _load_results() -> dict:
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r') as f:
            return json.load(f)
    return {}


def _save_settings(data: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE) or '.', exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {"default_concurrent": 10}


# ────────── Startup ──────────
@app.on_event("startup")
async def on_startup():
    global runner
    runner = TestRunner()
    print(f"[INFO] Token Test Platform v2.1.0 started")
    print(f"[INFO] 模型总数: {runner.config_loader.get_models_summary()['total']}")


# ────────── Models API ──────────
@app.get("/api/config/models/summary")
async def api_get_models_summary():
    """获取模型汇总信息"""
    return runner.config_loader.get_models_summary()


@app.get("/api/config/tracks")
async def api_get_tracks():
    return {"tracks": runner.config_loader.get_all_tracks_include_industry()}


@app.get("/api/config/models")
async def api_get_models():
    models = runner.config_loader.get_all_models()
    return {
        "total": len(models),
        "models_by_track": runner.config_loader.resolve_model_configs(),
        "models": models,
    }


@app.get("/api/config/models/{track}")
async def api_get_models_by_track(track: str):
    models = runner.config_loader.get_models_by_track(track)
    enabled = [m for m in models if m.get("enabled", True)]
    return {"track": track, "total": len(models), "enabled": len(enabled), "models": enabled}


# ────────── Settings ──────────
@app.get("/api/settings")
async def api_get_settings():
    settings = _load_settings()
    settings.setdefault("default_concurrent", 10)
    settings.setdefault("track_triage_sla", {})
    settings.setdefault("track_detail_sla", {})
    settings.setdefault("models", {})
    return settings


@app.put("/api/settings")
async def api_set_settings(data: dict):
    _save_settings(data)
    return {"status": "ok"}


@app.post("/api/settings/models/{model_id}")
async def api_update_model_settings(model_id: str, cfg: ModelConfigUpdate):
    existing = _load_settings()
    models_cfg = existing.get("models", {})
    models_cfg[model_id] = {
        "base_url": cfg.base_url, "api_key": cfg.api_key,
        "model_name": cfg.model_name, "enabled": cfg.enabled,
    }
    existing["models"] = models_cfg
    _save_settings(existing)
    return {"status": "ok"}


@app.post("/api/settings/models/batch")
async def api_update_models_batch(data: ModelBatchUpdate):
    existing = _load_settings()
    models_cfg = existing.get("models", {})
    for m in data.models:
        models_cfg[m.id] = {
            "base_url": m.base_url, "api_key": m.api_key,
            "model_name": m.model_name, "enabled": m.enabled,
        }
    existing["models"] = models_cfg
    _save_settings(existing)
    return {"status": "ok", "updated": len(data.models)}


# ────────── Test Control ──────────
@app.post("/api/test/run-all")
async def api_run_all_tracks(req: TrackRunRequest = TrackRunRequest()):
    """执行所有 6 大赛道"""
    if not runner:
        raise HTTPException(503, "Runner not initialized")
    run_id = f"RUN-ALL-{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    async def _run_all():
        result = await runner.run_all_tracks(req.concurrent)
        result["run_id"] = run_id
        result["status"] = "completed"
        result["completed_at"] = datetime.now().isoformat()
        _save_results(result)
        return result

    task = asyncio.create_task(_run_all())
    RUNNING_TRACKS[run_id] = task
    return {"run_id": run_id, "status": "running", "track": "all"}


@app.post("/api/test/run-track/{track}")
async def api_run_track(track: str, req: TrackRunRequest = TrackRunRequest()):
    """执行指定赛道"""
    if not runner:
        raise HTTPException(503, "Runner not initialized")
    all_tracks = runner.config_loader.get_all_tracks_include_industry()
    if track not in all_tracks:
        raise HTTPException(400, f"未知赛道: {track}，可用: {', '.join(all_tracks)}")

    run_id = f"RUN-{track.upper()}-{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    async def _run():
        result = await runner.run_track(track, req.concurrent)
        result["run_id"] = run_id
        _save_results(result)
        return result

    task = asyncio.create_task(_run())
    RUNNING_TRACKS[run_id] = task
    return {"run_id": run_id, "status": "running", "track": track}


@app.post("/api/test/run-model/{model_id}/{track}")
async def api_run_single_model(model_id: str, track: str):
    """只运行单个模型的某个赛道"""
    if not runner:
        raise HTTPException(503, "Runner not initialized")
    all_models = [m["id"] for m in runner.config_loader.get_all_models()]
    if model_id not in all_models:
        raise HTTPException(404, f"未找到模型: {model_id}")

    run_id = f"RUN-{model_id}-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    result = await runner.run_model_single(model_id, track)
    result["run_id"] = run_id
    _save_results(result)
    return result


@app.post("/api/test/cancel-all")
async def api_cancel_all():
    for tid, task in RUNNING_TRACKS.items():
        task.cancel()
    RUNNING_TRACKS.clear()
    if runner:
        runner.collector.reset()
    return {"status": "cancelled"}


# ────────── Metrics ──────────
@app.get("/api/metrics/summary")
async def api_get_metrics_summary():
    if not runner:
        raise HTTPException(503, "Runner not initialized")
    return runner.collector.get_summary()


@app.get("/api/metrics/{track}")
async def api_get_metrics_by_track(track: str):
    if not runner:
        raise HTTPException(503, "Runner not initialized")
    tm = runner.collector.get_track_metrics(track)
    return {track: {mid: m.to_dict() for mid, m in tm.items()}}


# ────────── Results ──────────
@app.get("/api/results")
async def api_get_results():
    return {"runs": _load_results(), "count": len(_load_results())}


@app.get("/api/results/latest")
async def api_get_latest_results():
    results = _load_results()
    if not results:
        return {"has_results": False, "runs": []}
    sorted_runs = sorted(results.values(), key=lambda x: x.get("completed_at", ""))
    latest_runs = sorted_runs[-3:] if len(sorted_runs) > 3 else sorted_runs
    return {"has_results": True, "runs": latest_runs, "count": len(sorted_runs)}


@app.get("/api/results/model/{model_id}")
async def api_get_model_results(model_id: str, track: str = None):
    results = _load_results()
    model_runs = []
    for run_id, data in results.items():
        if not isinstance(data, dict):
            continue
        if track and data.get("track") != track:
            continue
        model_results = data.get("results", {}).get(model_id, [])
        if model_results:
            model_runs.append({"run_id": run_id, "results": model_results})
    if not model_runs:
        return {"model_id": model_id, "has_results": False, "runs": []}

    all_metrics = []
    for mr in model_runs:
        all_metrics.extend(mr.get("results", []))

    return {
        "model_id": model_id, "has_results": True,
        "run_count": len(model_runs), "request_count": len(all_metrics),
        "raw_runs": model_runs,
    }


# ────────── Reports ──────────
@app.get("/api/report")
async def api_get_report_files():
    reports_dir = report_gen.output_dir
    if not os.path.exists(reports_dir):
        return {"reports": []}
    files = sorted([f for f in os.listdir(reports_dir) if f.endswith(('.html', '.json'))])
    return {"reports": files, "reports_dir": reports_dir}


# ────────── Health ──────────
@app.get("/api/health")
async def api_health():
    return {
        "status": "ok", "version": "2.1.0",
        "total_models": runner.config_loader.get_models_summary().get("total", 0) if runner else 0,
        "tracks": runner.config_loader.get_all_tracks_include_industry() if runner else [],
        "endpoints": len(app.routes),
    }


# ────────── Web UI ──────────
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    web_dir = os.path.join(os.path.dirname(__file__), "..", "..", "web")
    index_path = os.path.join(web_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Web UI not found</h1>"


web_dir = os.path.join(os.path.dirname(__file__), "..", "..", "web")
if os.path.exists(web_dir):
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

# Serve HTML reports directly
if os.path.exists(REPORTS_DIR):
    app.mount("/reports", StaticFiles(directory=REPORTS_DIR), name="reports")
