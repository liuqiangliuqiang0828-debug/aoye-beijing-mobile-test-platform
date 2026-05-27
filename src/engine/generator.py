"""
测试用例生成器
根据赛道配置自动生成标准化测试用例
"""

import yaml
import os
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# ── 提示词 / 素材模板 ──────────────────────────────────────────
MULTIMODAL_PROMPTS = {
    "image_desc": [
        "请描述这张图片的内容，包括场景、人物、物体和整体氛围",
        "这幅画表达了什么样的情感和主题？",
    ],
    "video_qa": [
        "请分析这个视频的主要内容，包括场景变化、人物动作和整体叙事",
    ],
}

TEXT_PROMPTS = {
    "short": [
        "请简要介绍北京的传统美食",
        "用50个字总结今天的首都新闻",
        "请解释什么是大语言模型",
        "AI都有哪些应用场景？",
        "什么是数字孪生？",
    ],
    "medium": [
        "请详细分析2026年AI行业的发展趋势，包括大模型、多模态、Agent等方向，给出1000字以上的分析报告",
        "请撰写一篇关于数字化转型的策划方案，包含现状分析、目标设定、实施路径和预期效果",
        "请分析昇腾生态与CUDA生态的差异，从硬件、软件、开发者社区三个维度进行对比",
        "请对本次项目中的token运营服务平台进行评估，包括技术选型、架构设计和可能的风险点",
        "请帮我总结当前主流开源大模型的情况，包括Qwen、Llama、DeepSeek等模型的优缺点",
    ],
    "long": [
        "请撰写一份完整的5G+AI行业应用解决方案文档，包含：1.行业背景 2.整体架构设计 3.关键技术选型 4.试点场景设计 5.实施计划 6.风险评估。请确保专业详细。",
        "请分析中国移动在AI时代的战略机遇与挑战：1.行业现状 2.技术趋势 3.算力需求 4.服务模式创新 5.竞争对手 6.战略建议。",
    ],
    "ultra_long": [
        "请撰写一份完整的十四五后半段AI行业发展规划报告：全文不少於3000字，包含宏覌环境分析、技术趨勢预测、市场机会评估、政策分析，给出至少5条战略建议。",
    ],
}

IMAGE_PROMPTS = {
    "1080p": [
        "A futuristic smart city with flying cars and green technology",
        "Chinese traditional painting style of Beijing Forbidden City, 4K quality",
    ],
    "square": ["An oil painting of a golden retriever running through a field of flowers, 1024x1024"],
    "portrait": ["一个穿着汉服的中国古代美女，1080x1920, 精致写实风格"],
}

TTS_LONG_TEXT = "在人工智能飞速发展的今天，大语言模型正在深刻改变着各行各业。从文本生成到图像创作，从数据分析到自动驾驶，AI技术的应用场景越来越广泛。2026年，随着模型的不断进化，我们看到了更多的可能性。多模态AI模型能够同时理解和处理文本、图像、音频和视频等多种类型的数据，这为人类与机器的交互带来了革命性的变化。在未来的日子里，我们有理由相信，人工智能将会更加深入地从各个方面融入我们的生活，为社会的进步做出更大的贡献。" * 15

MULTIMODAL_PROMPTS = {
    "image_desc": [
        "请描述这张图片的内容，包括场景、人物、物体和整体氛围",
        "这幅画表达了什么样的情感和主题？",
    ],
    "video_qa": ["请分析这个视频的主要内容，包括场景变化、人物动作和整体叙事"],
}


@dataclass
class TestCase:
    id: str
    name: str
    track: str
    sub_track: Optional[str] = None
    model_id: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    expected: Dict[str, Any] = field(default_factory=dict)
    category: str = ""


class TestCaseGenerator:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "config", "tracks.yaml"
        )
        self.tracks_config = self._load_config()

    def _load_config(self) -> Dict:
        with open(self.config_path, "r", encoding="utf8") as f:
            return yaml.safe_load(f)

    # ── 文本 ─────────────────────────────────────────────────────
    def generate_text_cases(self, model_id: str) -> List[TestCase]:
        cases = []
        for cat, prompts in TEXT_PROMPTS.items():
            token_map = {"short": 100, "medium": 2048, "long": 32768, "ultra_long": 65536}
            for i, prompt in enumerate(prompts):
                tc_id = f"TEXT-{model_id}-{cat}-{i}"
                cases.append(TestCase(
                    id=tc_id, name=f"{cat} #{i+1}", track="text",
                    model_id=model_id,
                    input_data={"prompt": prompt, "max_tokens": 4096,
                                "temperature": 0.7, "top_p": 0.9},
                    expected={"category": cat}, category=cat,
                ))
        return cases

    # ── 图像 ─────────────────────────────────────────────────────
    def generate_image_cases(self, model_id: str) -> List[TestCase]:
        cases = []
        for res_key, prompts in IMAGE_PROMPTS.items():
            fmt = "png" if res_key != "portrait" else "jpeg"
            for i, prompt in enumerate(prompts):
                tc_id = f"IMG-{model_id}-{res_key}-{i}"
                cases.append(TestCase(
                    id=tc_id, name=f"{res_key} #{i+1}", track="image",
                    model_id=model_id,
                    input_data={"prompt": prompt, "size": res_key,
                                "format": fmt, "style": "realistic"},
                    expected={"format": fmt}, category=res_key,
                ))
        return cases

    # ── 视频 ─────────────────────────────────────────────────────
    def generate_video_cases(self, model_id: str) -> List[TestCase]:
        cases = []
        video_prompts = {
            "720P": ["A golden retriever playing in the park", "Sunset over the Great Wall"],
            "1080P": ["A futuristic city skyline at night", "A serene Japanese garden in spring"],
        }
        for res, prompts in video_prompts.items():
            for i, prompt in enumerate(prompts):
                tc_id = f"VID-{model_id}-{res}-{i}"
                cases.append(TestCase(
                    id=tc_id, name=f"{res} #{i+1}", track="video",
                    model_id=model_id,
                    input_data={"prompt": prompt, "resolution": res,
                                "fps": 24, "duration_seconds": 5, "codec": "h264"},
                    expected={"resolution": res}, category=res,
                ))
        return cases

    # ── 音频 ─────────────────────────────────────────────────────
    def generate_audio_tts_cases(self, model_id: str) -> List[TestCase]:
        cases = []
        for i in range(3):
            tc_id = f"AUD-TTS-{model_id}-{i}"
            cases.append(TestCase(
                id=tc_id, name=f"TTS中文合成 #{i+1}",
                track="audio", sub_track="tts", model_id=model_id,
                input_data={"text": TTS_LONG_TEXT, "speaker": "zh_female_1",
                            "speed": 1.0, "language": "zh-CN"},
            ))
        return cases

    def generate_audio_asr_cases(self, model_id: str) -> List[TestCase]:
        cases = []
        for i in range(2):
            tc_id = f"AUD-ASR-{model_id}-{i}"
            cases.append(TestCase(
                id=tc_id, name=f"ASR中文识别 #{i+1}",
                track="audio", sub_track="asr", model_id=model_id,
                input_data={"audio_format": "wav", "sample_rate": 16000,
                            "duration_seconds": 10, "language": "zh"},
            ))
        return cases

    # ── 多模态 ───────────────────────────────────────────────────
    def generate_multimodal_cases(self, model_id: str) -> List[TestCase]:
        cases = []
        for i, q in enumerate(MULTIMODAL_PROMPTS["image_desc"]):
            tc_id = f"MM-IMG-{model_id}-{i}"
            cases.append(TestCase(
                id=tc_id, name=f"图像理解 #{i+1}", track="multimodal",
                model_id=model_id,
                input_data={"question": q, "image_url": ""},
                category="image_understanding",
            ))
        for i, q in enumerate(MULTIMODAL_PROMPTS["video_qa"]):
            tc_id = f"MM-VID-{model_id}-{i}"
            cases.append(TestCase(
                id=tc_id, name=f"视频理解 #{i+1}", track="multimodal",
                model_id=model_id,
                input_data={"question": q, "video_url": ""},
                category="video_understanding",
            ))
        return cases

    # ── 统一入口 ─────────────────────────────────────────────────
    def generate_cases_for_model(
        self, model_id: str, track: str, model_config: Dict
    ) -> List[TestCase]:
        """根据赛道名分发到具体生成方法"""
        dispatch = {
            "text": self.generate_text_cases,
            "image": self.generate_image_cases,
            "video": self.generate_video_cases,
            "audio": self._gen_audio_all,
            "multimodal": self.generate_multimodal_cases,
        }
        fn = dispatch.get(track)
        if not fn:
            return []
        return fn(model_id)

    def _gen_audio_all(self, model_id: str) -> List[TestCase]:
        tts = self.generate_audio_tts_cases(model_id)
        asr = self.generate_audio_asr_cases(model_id)
        return tts + asr
