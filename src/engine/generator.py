"""
Phase 2 增强版测试用例生成器
根据赛道配置自动生成标准化测试用例
支持 6 大赛道（含行业专用大模型）
"""

import yaml
import os
import time
import hashlib
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


# ── 提示词 / 素材模板 ──────────────────────────────────────────
TEXT_SHORT_PROMPTS = [
    "请简要介绍北京的传统美食",
    "用50个字总结今天的首都新闻",
    "请解释什么是大语言模型",
    "AI都有哪些应用场景？",
    "什么是数字孪生？",
    "请解释区块链的基本原理",
    "列举三种云计算的优势",
    "请简述Transformer架构的核心创新",
]

TEXT_MEDIUM_PROMPTS = [
    "请详细分析2026年AI行业的发展趋势，包括大模型、多模态、Agent等方向，给出1000字以上的分析报告",
    "请撰写一篇关于数字化转型的策划方案，包含现状分析、目标设定、实施路径和预期效果",
    "请分析昇腾生态与CUDA生态的差异，从硬件、软件、开发者社区三个维度进行对比",
    "请对本次项目中的token运营服务平台进行评估，包括技术选型、架构设计和可能的风险点",
    "请帮我总结当前主流开源大模型的情况，包括Qwen、Llama、DeepSeek等模型的优缺点",
    "分析北京在AI产业发展上的优势与挑战，给出三点建议",
]

TEXT_LONG_PROMPTS = [
    "请撰写一份完整的5G+AI行业应用解决方案文档，包含：1.行业背景 2.整体架构设计 3.关键技术选型 4.试点场景设计 5.实施计划 6.风险评估。请确保专业详细。",
    "请分析中国移动在AI时代的战略机遇与挑战：1.行业现状 2.技术趋势 3.算力需求 4.服务模式创新 5.竞争对手分析 6.战略建议。",
    "制定一份企业级AI平台选型报告，包含需求调研、方案设计、成本分析、风险评估和落地计划五个部分。",
]

TEXT_ULTRA_LONG_PROMPTS = [
    "请撰写一份完整的十四五后半段AI行业发展规划报告：全文不少于3000字，包含宏观环境分析、技术趋势预测、市场机会评估、政策分析，给出至少5条战略建议。",
    "撰写一份关于智慧城市建设的完整方案，包含基础设施、数据平台、应用场景、治理机制、安全体系五个篇章，每篇不少于400字。",
]

IMAGE_PROMPTS = {
    "landscape": [
        "A futuristic smart city with flying cars and green technology, 4K ultra HD",
        "Chinese traditional landscape painting of Beijing Forbidden City, 4K quality",
    ],
    "portrait": [
        "一个穿着汉服的中国古代美女，1080x1920, 精致写实风格",
        "a graceful Chinese dancer in traditional Tang dynasty costume, 1080x1920, realistic style",
    ],
    "square": [
        "An oil painting of a golden retriever running through a field of flowers, 1024x1024",
        "A cyberpunk street scene at night with neon signs, 1024x1024",
    ],
    "ultrawide": [
        "A panoramic view of the Great Wall at sunset, 2048x1152, photography style",
    ],
}

TTS_LONG_TEXT = (
    "在人工智能飞速发展的今天，大语言模型正在深刻改变着各行各业。"
    "从文本生成到图像创作，从数据分析到自动驾驶，AI技术的应用场景越来越广泛。"
    "2026年，随着模型的不断进化，我们看到了更多的可能性。"
    "多模态AI模型能够同时理解和处理文本、图像、音频和视频等多种类型的数据，"
    "这为人类与机器的交互带来了革命性的变化。"
    "在未来的日子里，我们有理由相信，人工智能将会更加深入地融入我们的生活，"
    "为社会的进步做出更大的贡献。"
) * 15

MULTIMODAL_TEXT_PROMPTS = [
    "请描述这张图片的内容，包括场景、人物、物体和整体氛围",
    "这幅画表达了什么样的情感和主题？",
    "请分析这张产品图片的构图和用色",
]

VIDEO_STREAM_PROMPTS = [
    "A golden retriever playing in a sunlit park, realistic style",
    "Sunset over the Great Wall of China, cinematic quality",
    "Aromantic walking through a cherry blossom garden in spring",
]

INDUSTRY_QA_PROMPTS = [
    (
        "北京移动在2026年计划建设一个token模型聚合平台，"
        "请分析该平台在企业级AI服务中的技术价值和商业价值，"
        "给出包括技术选型、运营策略、风险控制三点建议。"
    ),
    "解释DICT行业中Token经济模型的设计原则，并举例说明。",
    "针对政务云的AI服务场景，设计一套模型服务SLA保障体系。",
]

INDUSTRY_COMPLIANCE_DATA = [
    "张三，身份证号110105198108281234，手机号13020082896",
    "李四，家庭住址北京市西城区金融大街88号，邮箱lisi@example.com",
    "王五，公司名称北京某某科技有限公司，统一社会信用代码91110108MA01XXXX",
]


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
    """测试用例生成器 - 按赛道配置自动生成测试用例"""

    def __init__(self, config_path: str = None, config_base: str = None):
        self._config_base = config_base
        self._tracks_config = self._load_tracks_config()

    def _load_tracks_config(self) -> Dict:
        base = self._config_base
        if not base:
            candidates = [
                os.path.join(os.path.dirname(__file__), "..", "..", "config"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    base = c
                    break
            else:
                base = os.path.join(os.path.dirname(__file__), "..", "..", "config")

        config = {}
        # Load consolidated tracks.yaml
        yaml_file = os.path.join(base, "tracks.yaml")
        if os.path.exists(yaml_file):
            with open(yaml_file, "r", encoding="utf-8") as f:
                config["all"] = yaml.safe_load(f)

        # Load per-track configs
        tracks_dir = os.path.join(base, "tracks")
        if os.path.isdir(tracks_dir):
            for fname in os.listdir(tracks_dir):
                if fname.endswith((".yaml", ".yml")):
                    track_name = fname.rsplit(".", 1)[0]
                    with open(os.path.join(tracks_dir, fname), "r", encoding="utf-8") as f:
                        config[track_name] = yaml.safe_load(f)

        return config

    # ══════════════════════════════════════════════════════════
    # 赛道1：文本
    # ══════════════════════════════════════════════════════════
    def generate_text_cases(self, model_id: str) -> List[TestCase]:
        cases = []
        for cat, prompts_map in [
            ("short", TEXT_SHORT_PROMPTS),
            ("medium", TEXT_MEDIUM_PROMPTS),
            ("long", TEXT_LONG_PROMPTS),
            ("ultra_long", TEXT_ULTRA_LONG_PROMPTS),
        ]:
            token_map = {"short": 100, "medium": 2048, "long": 32768, "ultra_long": 65536}
            for i, prompt in enumerate(prompts_map):
                tc_id = f"TEXT-{model_id}-{cat}-{i:03d}"
                cases.append(TestCase(
                    id=tc_id, name=f"{cat} #{i+1}", track="text",
                    model_id=model_id,
                    input_data={
                        "prompt": prompt,
                        "max_tokens": 4096,
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "stream": True,
                    },
                    expected={"category": cat, "min_tokens": token_map[cat]},
                    category=cat,
                ))
        return cases

    # ══════════════════════════════════════════════════════════
    # 赛道2：图像
    # ══════════════════════════════════════════════════════════
    def generate_image_cases(self, model_id: str) -> List[TestCase]:
        cases = []
        for fmt_key, prompts in IMAGE_PROMPTS.items():
            fmt = "png" if fmt_key in ("landscape", "ultrawide", "square") else "jpeg"
            for i, prompt in enumerate(prompts):
                tc_id = f"IMG-{model_id}-{fmt_key}-{i:03d}"
                cases.append(TestCase(
                    id=tc_id, name=f"{fmt_key} #{i+1}", track="image",
                    model_id=model_id,
                    input_data={
                        "prompt": prompt,
                        "size": fmt_key,
                        "format": fmt,
                        "style": "realistic",
                    },
                    expected={"format": fmt},
                    category=fmt_key,
                ))
        return cases

    # ══════════════════════════════════════════════════════════
    # 赛道3：视频（占位：等待具体端点后补充实际调用逻辑）
    # ══════════════════════════════════════════════════════════
    def generate_video_cases(self, model_id: str) -> List[TestCase]:
        cases = []
        for i, prompt in enumerate(VIDEO_STREAM_PROMPTS):
            tc_id = f"VID-{model_id}-{i:03d}"
            cases.append(TestCase(
                id=tc_id, name=f"视频生成 #{i+1}",
                track="video", model_id=model_id,
                input_data={
                    "prompt": prompt,
                    "resolution": "720P",
                    "fps": 24,
                    "duration_seconds": 5,
                    "codec": "h264",
                },
                expected={"resolution": "720P"},
                category="generation",
            ))
        return cases

    # ══════════════════════════════════════════════════════════
    # 赛道4：音频（TTS + ASR）
    # ══════════════════════════════════════════════════════════
    def generate_audio_tts_cases(self, model_id: str) -> List[TestCase]:
        cases: List[TestCase] = []
        for i in range(3):
            tc_id = f"AUD-TTS-{model_id}-{i:03d}"
            cases.append(TestCase(
                id=tc_id, name=f"TTS中文合成 #{i+1}",
                track="audio", sub_track="tts", model_id=model_id,
                input_data={
                    "text": TTS_LONG_TEXT,
                    "speaker": "zh_female_1",
                    "speed": 1.0,
                    "language": "zh-CN",
                },
            ))
        return cases

    def generate_audio_asr_cases(self, model_id: str) -> List[TestCase]:
        cases: List[TestCase] = []
        for i in range(2):
            tc_id = f"AUD-ASR-{model_id}-{i:03d}"
            cases.append(TestCase(
                id=tc_id, name=f"ASR中文识别 #{i+1}",
                track="audio", sub_track="asr", model_id=model_id,
                input_data={
                    "audio_format": "wav",
                    "sample_rate": 16000,
                    "duration_seconds": 10,
                    "language": "zh",
                },
            ))
        return cases

    # ══════════════════════════════════════════════════════════
    # 赛道5：多模态理解
    # ══════════════════════════════════════════════════════════
    def generate_multimodal_cases(self, model_id: str) -> List[TestCase]:
        cases: List[TestCase] = []
        for i, q in enumerate(MULTIMODAL_TEXT_PROMPTS):
            tc_id = f"MM-IMG-{model_id}-{i:03d}"
            cases.append(TestCase(
                id=tc_id, name=f"图像理解 #{i+1}",
                track="multimodal", model_id=model_id,
                input_data={
                    "question": q,
                    "image_url": "",  # 待提供图片测试URL
                },
                category="image_understanding",
            ))
        return cases

    # ══════════════════════════════════════════════════════════
    # 赛道6：行业专用大模型
    # ══════════════════════════════════════════════════════════
    def generate_industry_cases(self, model_id: str) -> List[TestCase]:
        cases: List[TestCase] = []

        # QA 用例
        for i, qa in enumerate(INDUSTRY_QA_PROMPTS):
            tc_id = f"IND-QA-{model_id}-{i:03d}"
            cases.append(TestCase(
                id=tc_id, name=f"行业知识问答 #{i+1}",
                track="industry", model_id=model_id,
                input_data={
                    "prompt": qa,
                    "max_tokens": 2048,
                    "temperature": 0.5,
                },
                expected={
                    "qa": True,
                    "expected_keywords": ["北京移动", "模型", "平台", "策略"],
                },
                category="qa",
            ))

        # 数据脱敏/合规用例
        for i, data in enumerate(INDUSTRY_COMPLIANCE_DATA):
            tc_id = f"IND-COMP-{model_id}-{i:03d}"
            cases.append(TestCase(
                id=tc_id, name=f"数据脱敏测试 #{i+1}",
                track="industry", model_id=model_id,
                input_data={
                    "prompt": f"请识别并脱敏以下文本中的个人敏感信息：{data}",
                    "max_tokens": 512,
                    "temperature": 0.1,
                },
                expected={
                    "compliance": True,
                    "sensitive_patterns": ["身份证", "手机号", "地址", "公司名"],
                },
                category="compliance",
            ))

        return cases

    # ══════════════════════════════════════════════════════════
    # 统一入口
    # ══════════════════════════════════════════════════════════
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
            "industry": self.generate_industry_cases,
        }
        fn = dispatch.get(track)
        if not fn:
            return []
        return fn(model_id)

    def _gen_audio_all(self, model_id: str) -> List[TestCase]:
        return self.generate_audio_tts_cases(model_id) + self.generate_audio_asr_cases(model_id)

    # ── 并发请求计数器 ──────────────────────────────────────
    _request_counter: int = 0
    _lock: Optional[any] = None

    @classmethod
    def next_request_id(cls) -> str:
        """全局单调递增请求序号"""
        TestCaseGenerator._request_counter += 1
        return f"REQ-{TestCaseGenerator._request_counter:06d}-{time.time():.6f}"
