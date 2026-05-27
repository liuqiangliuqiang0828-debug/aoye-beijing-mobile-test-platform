"""
测试执行引擎 - 核心
按赛道并发调用下游模型，采集指标，判定达标情况
"""

import asyncio
import httpx
import json
import time
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.engine.generator import TestCase, TestCaseGenerator
from src.utils.metrics import MetricsCollector, RequestMetric
from src.utils.config_loader import ConfigLoader


class TestRunner:
    """测试执行引擎"""

    HTTP_TIMEOUT = 300.0  # 单请求超时 5 分钟（长生成场景）

    def __init__(self, config_base: str = None):
        self.config_loader = ConfigLoader(config_base)
        self.generator = TestCaseGenerator(config_base)
        self.collector = MetricsCollector()
        self._active_run_id: Optional[str] = None
        self._running_models: set = set()

    async def run_track(
        self,
        track: str,
        concurrent_limit: int = 10,
        run_id: str = None,
    ) -> Dict[str, Any]:
        """执行某个赛道的全部模型测试"""
        run_id = run_id or self._generate_run_id(track)
        self._active_run_id = run_id

        models = self.config_loader.get_enabled_models_by_track(track)
        if not models:
            return {
                "run_id": run_id,
                "track": track,
                "status": "skipped",
                "message": f"赛道 {track} 无可用模型配置",
            }

        semaphore = asyncio.Semaphore(concurrent_limit)
        all_results: Dict[str, List[Dict]] = {}

        async def _run_model(model_cfg: Dict):
            async with semaphore:
                model_id = model_cfg["id"]
                self._running_models.add(model_id)
                try:
                    cases = self.generator.generate_cases_for_model(
                        model_id, track, model_cfg
                    )
                    results = await self._run_test_cases(cases, model_cfg)
                    all_results[model_id] = results
                except Exception as e:
                    all_results[model_id] = [{"error": str(e)}]
                finally:
                    self._running_models.discard(model_id)

        # 并发跑所有模型
        tasks = [_run_model(m) for m in models]
        await asyncio.gather(*tasks)

        return {
            "run_id": run_id,
            "track": track,
            "status": "completed",
            "models_tested": len(all_results),
            "results": all_results,
            "summary": self.collector.get_track_metrics(track),
            "completed_at": datetime.now().isoformat(),
        }

    async def run_all_tracks(
        self, concurrent_limit: int = 10
    ) -> Dict[str, Any]:
        """执行所有可用赛道"""
        tracks = self.config_loader.get_all_tracks()
        results = {}
        for track in tracks:
            print(f"🚀 Starting track: {track}")
            result = await self.run_track(track, concurrent_limit)
            results[track] = result
            print(f"  ✅ Track {track} done ({result.get('status')})")
        return {"status": "all_completed", "tracks": results}

    async def run_model_single(
        self, model_id: str, track: str, run_id: str = None
    ) -> Dict[str, Any]:
        """只跑单个模型的单个赛道"""
        model_cfg = self.config_loader.get_model_by_id(model_id)
        if not model_cfg:
            return {"status": "error", "message": f"未找到模型: {model_id}"}

        cases = self.generator.generate_cases_for_model(
            model_id, track, model_cfg
        )
        if not cases:
            return {"status": "error", "message": f"未生成任何测试用例"}

        result = await self._run_test_cases(cases, model_cfg)
        self.collector.reset()  # 单次跑的指标独立
        return {
            "run_id": run_id or self._generate_run_id(track),
            "model_id": model_id,
            "track": track,
            "status": "completed",
            "test_cases_count": len(cases),
            "results": result,
        }

    async def _run_test_cases(
        self, cases: List[TestCase], model_cfg: Dict
    ) -> List[Dict]:
        """执行一批测试用例"""
        results = []
        for case in cases:
            try:
                metric = await self._execute_single_case(case, model_cfg)
                self.collector.record(metric)
                results.append(metric.to_dict())
            except Exception as e:
                # 记录异常
                err_metric = RequestMetric(
                    test_case_id=case.id, model_id=model_cfg["id"],
                    status="error", error_message=str(e),
                )
                self.collector.record(err_metric)
                results.append(err_metric.to_dict())
        return results

    async def _execute_single_case(
        self, tc: TestCase, model_cfg: Dict
    ) -> RequestMetric:
        """执行单条测试用例，通过 OpenAI 兼容 API 调用模型"""
        base_url = model_cfg.get("base_url", "")
        api_key = model_cfg.get("api_key", "")
        model_name = model_cfg.get("model_name", "")

        metric = RequestMetric(
            test_case_id=tc.id, model_id=model_cfg["id"],
            streaming=tc.input_data.get("stream", False),
        )
        metric.request_start = time.time()

        try:
            async with httpx.AsyncClient(timeout=self.HTTP_TIMEOUT) as client:
                # ── 文本大模型：OpenAI chat completions API ──
                if tc.track == "text":
                    body = {
                        "model": model_name,
                        "messages": [{"role": "user", "content": tc.input_data["prompt"]}],
                        "max_tokens": tc.input_data.get("max_tokens", 4096),
                        "temperature": tc.input_data.get("temperature", 0.7),
                        "top_p": tc.input_data.get("top_p", 0.9),
                        "stream": tc.streaming,
                    }
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

                    if tc.streaming:
                        # 流式请求：逐个读取 chunk
                        async with client.stream("POST", f"{base_url}/chat/completions",
                                                 json=body, headers=headers) as resp:
                            metric.http_status = resp.status_code
                            lines = []
                            first_chunk = True
                            async for line in resp.aiter_lines():
                                if first_chunk and line.strip():
                                    metric.first_token_time = time.time()
                                    first_chunk = False
                                line = line.strip()
                                if line.startswith("data: "):
                                    data_str = line[6:]
                                    if data_str.strip() == "[DONE]":
                                        break
                                    try:
                                        chunk = json.loads(data_str)
                                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            lines.append(content)
                                    except:
                                        pass
                            metric.request_end = time.time()
                            metric.status = "success" if resp.status_code == 200 else "error"
                            output = "".join(lines)
                            metric.output_tokens = len(output) // 4  # rough estimate
                            metric.response_size = len(output)
                    else:
                        # 非流式请求
                        resp = await client.post(
                            f"{base_url}/chat/completions", json=body, headers=headers
                        )
                        metric.http_status = resp.status_code
                        metric.request_end = time.time()
                        if resp.status_code == 200:
                            data = resp.json()
                            content = data["choices"][0]["message"]["content"]
                            metric.status = "success"
                            metric.output_tokens = len(content) // 4
                            # token_count from response
                            usage = data.get("usage", {})
                            metric.input_tokens = usage.get("prompt_tokens", 0)
                            metric.output_tokens = usage.get("completion_tokens", 0)
                            metric.first_token_time = time.time()  # non-streaming, mark as done immediately
                        else:
                            metric.status = "error"
                            metric.error_message = resp.text[:500]

                # ── 图像生成：OpenAI images API ──
                elif tc.track == "image":
                    body = {
                        "model": model_name,
                        "prompt": tc.input_data["prompt"],
                        "size": self._resolve_image_size(tc.input_data.get("size", "1024x1024")),
                        "n": 1,
                        "response_format": "url" if model_cfg.get("base_url", "").endswith("/v1") else "b64_json",
                    }
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                    api_url = f"{base_url}/images/generations" if "/v1" in base_url else f"{base_url}/sdapi/v1/txt2img"

                    resp = await client.post(api_url, json=body, headers=headers)
                    metric.request_end = time.time()
                    metric.http_status = resp.status_code
                    if resp.status_code == 200:
                        metric.status = "success"
                    elif resp.status_code == 500 and "/sdapi/v1" in api_url:
                        # SD WebUI 返回 500 可能是正常错误（如 prompt 有问题），尝试查日志
                        metric.status = "error"
                        metric.error_message = resp.text[:500]
                    else:
                        metric.status = "error"
                        metric.error_message = resp.text[:500]

                # ── 语音 TTS ──
                elif tc.track == "audio" and tc.sub_track == "tts":
                    body = {
                        "model": model_name,
                        "input": tc.input_data["text"],
                        "voice": tc.input_data.get("speaker", "alloy"),
                    }
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                    resp = await client.post(
                        f"{base_url}/audio/speech", json=body, headers=headers
                    )
                    metric.request_end = time.time()
                    metric.http_status = resp.status_code
                    if resp.status_code == 200:
                        metric.status = "success"
                        metric.output_tokens = len(tc.input_data["text"])
                    else:
                        metric.status = "error"
                        metric.error_message = resp.text[:500]

                # ── 语音 ASR ──
                elif tc.track == "audio" and tc.sub_track == "asr":
                    # ASR 需要实际音频文件，先标记为待开发
                    metric.status = "skipped"
                    metric.error_message = "ASR需要上传音频文件，后续版本支持"

                # ── 多模态理解 ──
                elif tc.track == "multimodal":
                    body = {
                        "model": model_name,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": tc.input_data["question"]},
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": tc.input_data.get("image_url", "")}
                                    }
                                ]
                            }
                        ],
                        "max_tokens": 1024,
                    }
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                    resp = await client.post(
                        f"{base_url}/chat/completions", json=body, headers=headers
                    )
                    metric.request_end = time.time()
                    metric.http_status = resp.status_code
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]
                        metric.status = "success"
                        metric.output_tokens = len(content) // 4
                        usage = data.get("usage", {})
                        metric.input_tokens = usage.get("prompt_tokens", 0)
                        metric.output_tokens = usage.get("completion_tokens", 0)
                    else:
                        metric.status = "error"
                        metric.error_message = resp.text[:500]

                elif tc.track == "video":
                    # 视频生成：标记为待接具体端点
                    metric.status = "skipped"
                    metric.error_message = "视频生成需对接具体端点，后续版本接入"

                else:
                    metric.status = "skipped"
                    metric.error_message = f"未实现的赛道类型: {tc.track}"

        except httpx.TimeoutException:
            metric.status = "timeout"
            metric.error_message = "请求超时"
            metric.request_end = time.time()
        except Exception as e:
            metric.status = "error"
            metric.error_message = str(e)
            metric.request_end = time.time()

        return metric

    def _resolve_image_size(self, size_hint: str) -> str:
        size_map = {
            "1080p": "1024x1024",
            "square": "1024x1024",
            "portrait": "512x1024",
        }
        return size_map.get(size_hint, "1024x1024")

    def _generate_run_id(self, track: str) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"RUN-{track.upper()}-{ts}"

    def get_current_metrics(self) -> Dict:
        """获取当前采集的指标"""
        return self.collector.get_summary()
