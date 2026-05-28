"""
配置加载器 Phase 2 增强版
读取 models.yaml，按赛道/模型分组
支持 6 大赛道：text, image, video, audio, multimodal, industry
"""

import yaml
import os
from typing import Dict, List, Any, Optional


class ConfigLoader:
    """模型 + 赛道配置加载器"""

    def __init__(self, base_dir: str = None):
        if base_dir:
            self.base_dir = base_dir
        else:
            candidates = [
                os.path.join(os.path.dirname(__file__), "..", "..", "config"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config"),
            ]
            for c in candidates:
                real = os.path.normpath(c)
                if os.path.exists(os.path.join(real, "models.yaml")):
                    self.base_dir = real
                    break
            else:
                self.base_dir = candidates[0]
        self._models_config: Optional[Dict] = None

    @property
    def models_path(self) -> str:
        return os.path.join(self.base_dir, "models.yaml")

    def load_models(self) -> Dict:
        if self._models_config is None:
            with open(self.models_path, "r", encoding="utf-8") as f:
                self._models_config = yaml.safe_load(f)
        return self._models_config

    def get_all_models(self) -> List[Dict]:
        cfg = self.load_models()
        result = []
        for key in ["text_models", "image_models", "video_models",
                     "audio_models", "multimodal_models", "industry_models"]:
            models = cfg.get(key, [])
            for m in models:
                m["_config_key"] = key
                result.append(m)
        return result

    def get_models_by_track(self, track: str) -> List[Dict]:
        key_map = {
            "text": "text_models",
            "image": "image_models",
            "video": "video_models",
            "audio": "audio_models",
            "multimodal": "multimodal_models",
            "industry": "industry_models",
        }
        cfg = self.load_models()
        return cfg.get(key_map.get(track, ""), [])

    def get_model_by_id(self, model_id: str) -> Optional[Dict]:
        for m in self.get_all_models():
            if m.get("id") == model_id:
                return m
        return None

    def get_enabled_models_by_track(self, track: str) -> List[Dict]:
        return [m for m in self.get_models_by_track(track)
                if m.get("enabled", True)]

    def get_all_tracks(self) -> List[str]:
        """返回5大赛道列���（兼容接口）"""
        return ["text", "image", "video", "audio", "multimodal"]

    def get_all_tracks_include_industry(self) -> List[str]:
        """返回6大赛道列表"""
        return ["text", "image", "video", "audio", "multimodal", "industry"]

    def resolve_model_configs(self) -> Dict[str, List[Dict]]:
        resolved = {}
        for track in self.get_all_tracks():
            resolved[track] = self.get_enabled_models_by_track(track)
        # Also include industry if models exist
        industry = self.get_enabled_models_by_track("industry")
        if industry:
            resolved["industry"] = industry
        return resolved

    def get_models_summary(self) -> Dict:
        """获取模型汇总信息"""
        summary = {"total": 0, "tracks": {}}
        for track in ["text", "image", "video", "audio", "multimodal", "industry"]:
            models = self.get_models_by_track(track)
            enabled = [m for m in models if m.get("enabled", True)]
            summary["tracks"][track] = {
                "total": len(models),
                "enabled": len(enabled),
                "model_ids": [m["id"] for m in enabled],
            }
            summary["total"] += len(models)
        return summary
