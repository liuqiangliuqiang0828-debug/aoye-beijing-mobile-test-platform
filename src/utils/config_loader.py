"""
配置加载器
读取 models.yaml 和 tracks.yaml, 按赛道 / 模型进行分组
"""

import yaml
import os
from typing import Dict, List, Any, Optional


class ConfigLoader:
    """模型 + 赛道配置加载器"""

    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "config"
        )
        self._models_config: Optional[Dict] = None

    @property
    def models_path(self) -> str:
        return os.path.join(self.base_dir, "models.yaml")

    @property
    def tracks_path(self) -> str:
        return os.path.join(self.base_dir, "tracks.yaml")

    def load_models(self) -> Dict:
        if self._models_config is None:
            with open(self.models_path, "r", encoding="utf-8") as f:
                self._models_config = yaml.safe_load(f)
        return self._models_config

    def get_all_models(self) -> List[Dict]:
        """返回所有已注册的模型配置"""
        cfg = self.load_models()
        result = []
        for key in ["text_models", "image_models", "video_models",
                     "audio_models", "multimodal_models"]:
            models = cfg.get(key, [])
            for m in models:
                m["_config_key"] = key
                result.append(m)
        return result

    def get_models_by_track(self, track: str) -> List[Dict]:
        """按赛道返回模型列表"""
        key_map = {
            "text": "text_models",
            "image": "image_models",
            "video": "video_models",
            "audio": "audio_models",
            "multimodal": "multimodal_models",
        }
        cfg = self.load_models()
        return cfg.get(key_map.get(track, ""), [])

    def get_model_by_id(self, model_id: str) -> Optional[Dict]:
        """根据 model id 查单个模型"""
        for m in self.get_all_models():
            if m.get("id") == model_id:
                return m
        return None

    def get_enabled_models_by_track(self, track: str) -> List[Dict]:
        """返回赛道内 enabled=True 的模型"""
        return [m for m in self.get_models_by_track(track)
                if m.get("enabled", True)]

    def get_all_tracks(self) -> List[str]:
        """返回所有赛道列表"""
        return ["text", "image", "video", "audio", "multimodal"]

    def resolve_model_configs(self) -> Dict[str, List[Dict]]:
        """按赛道分组 + 带 enabled 过滤，返回 {track: [models]}"""
        resolved = {}
        for track in self.get_all_tracks():
            resolved[track] = self.get_enabled_models_by_track(track)
        return resolved
