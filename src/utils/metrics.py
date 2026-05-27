"""
测试运行指标采集器
实时采集每条请求的性能数据（TTFT、全量耗时、token数、错误码等）
"""

import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class RequestMetric:
    """单条请求的指标"""
    test_case_id: str
    model_id: str
    request_start: float = 0.0
    first_token_time: float = 0.0  # TTFT (Time To First Token)
    request_end: float = 0.0
    output_tokens: int = 0
    input_tokens: int = 0
    status: str = "pending"  # pending/success/error/timeout
    error_message: str = ""
    http_status: int = 0
    response_size: int = 0
    streaming: bool = False

    @property
    def ttft(self) -> float:
        if self.first_token_time and self.request_start:
            return self.first_token_time - self.request_start
        return 0.0

    @property
    def total_duration(self) -> float:
        if self.request_end and self.request_start:
            return self.request_end - self.request_start
        return 0.0

    @property
    def generate_duration(self) -> float:
        """纯生成时长（不含首字等待）"""
        if self.first_token_time and self.request_end and self.first_token_time:
            return self.request_end - self.first_token_time
        return 0.0

    @property
    def speed(self) -> float:
        """生成速度 (token/s)"""
        dur = self.generate_duration
        if dur > 0 and self.output_tokens > 0:
            return self.output_tokens / dur
        return 0.0


@dataclass
class TrackMetrics:
    """某个赛道在某模型上的汇总指标"""
    track: str
    model_id: str
    metrics: List[RequestMetric] = field(default_factory=list)

    @property
    def total_requests(self) -> int:
        return len(self.metrics)

    @property
    def success_count(self) -> int:
        return sum(1 for m in self.metrics if m.status == "success")

    @property
    def error_count(self) -> int:
        return sum(1 for m in self.metrics if m.status in ("error", "timeout"))

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.success_count / self.total_requests) * 100

    @property
    def avg_ttft(self) -> float:
        ttfts = [m.ttft for m in self.metrics if m.ttft > 0]
        return sum(ttfts) / len(ttfts) if ttfts else 0.0

    @property
    def p50_ttft(self) -> float:
        return self._percentile([m.ttft for m in self.metrics if m.ttft > 0], 50)

    @property
    def p90_ttft(self) -> float:
        return self._percentile([m.ttft for m in self.metrics if m.ttft > 0], 90)

    @property
    def p95_ttft(self) -> float:
        return self._percentile([m.ttft for m in self.metrics if m.ttft > 0], 95)

    @property
    def p99_ttft(self) -> float:
        return self._percentile([m.ttft for m in self.metrics if m.ttft > 0], 99)

    @property
    def avg_speed(self) -> float:
        speeds = [m.speed for m in self.metrics if m.speed > 0]
        return sum(speeds) / len(speeds) if speeds else 0.0

    @property
    def p70_speed(self) -> float:
        return self._percentile([m.speed for m in self.metrics if m.speed > 0], 70)

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.error_count / self.total_requests) * 100

    def _percentile(self, values: List[float], p: int) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        k = (len(sorted_vals) - 1) * (p / 100)
        f = int(k)
        c = f + 1
        if c >= len(sorted_vals):
            return sorted_vals[-1]
        return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track": self.track,
            "model_id": self.model_id,
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": round(self.success_rate, 2),
            "error_rate": round(self.error_rate, 2),
            "avg_ttft_ms": round(self.avg_ttft * 1000, 2),
            "p50_ttft_ms": round(self.p50_ttft * 1000, 2),
            "p90_ttft_ms": round(self.p90_ttft * 1000, 2),
            "p95_ttft_ms": round(self.p95_ttft * 1000, 2),
            "p99_ttft_ms": round(self.p99_ttft * 1000, 2),
            "avg_speed_toks": round(self.avg_speed, 2),
            "p70_speed_toks": round(self.p70_speed, 2),
        }


class MetricsCollector:
    """全局指标采集器"""

    def __init__(self):
        self._track_metrics: Dict[str, Dict[str, TrackMetrics]] = {}

    def record(self, metric: RequestMetric):
        track = self._infer_track_from_model(metric.model_id)
        if track not in self._track_metrics:
            self._track_metrics[track] = {}
        if metric.model_id not in self._track_metrics[track]:
            self._track_metrics[track][metric.model_id] = TrackMetrics(
                track=track, model_id=metric.model_id
            )
        self._track_metrics[track][metric.model_id].metrics.append(metric)

    def get_track_metrics(self, track: str) -> Dict[str, TrackMetrics]:
        return self._track_metrics.get(track, {})

    def get_all_metrics(self) -> Dict[str, Dict[str, Dict]]:
        result = {}
        for track, models in self._track_metrics.items():
            result[track] = {mid: tm.to_dict() for mid, tm in models.items()}
        return result

    def get_summary(self) -> Dict[str, Any]:
        summary = {"tracks": {}, "overall": {}}
        totals = {"total_requests": 0, "success_count": 0, "error_count": 0, "tokens_generated": 0}
        for track, models in self._track_metrics.items():
            track_summary = {}
            for mid, tm in models.items():
                track_summary[mid] = tm.to_dict()
                totals["total_requests"] += tm.total_requests
                totals["success_count"] += tm.success_count
                totals["error_count"] += tm.error_count
                totals["tokens_generated"] += sum(m.output_tokens for m in tm.metrics)
            summary["tracks"][track] = track_summary
        summary["overall"] = totals
        return summary

    def _infer_track_from_model(self, model_id: str) -> str:
        """从 model_id 推断赛道"""
        model_id_lower = model_id.lower()
        track_map = {
            "qwen3.5": "text", "qwen3-32b": "text", "glm-4.7": "text",
            "flux": "image", "sd35": "image", "kokoro": "image",
            "open-sora": "video", "cogvideox": "video", "wan2.1": "video",
            "f5-tts": "audio", "cosyvoice": "audio", "whisper": "audio",
            "sensevoice": "audio", "moshi": "audio",
            "qwen3-vl": "multimodal", "internvl3": "multimodal", "llava": "multimodal",
        }
        for keyword, track in track_map.items():
            if keyword in model_id_lower:
                return track
        return "text"  # 默认归入文本

    def reset(self):
        self._track_metrics.clear()
