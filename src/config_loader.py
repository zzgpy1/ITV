import os
import yaml
from pathlib import Path
from typing import Any, Dict

class Config:
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self._data = {}
        self.load()

    def load(self):
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._data = yaml.safe_load(f) or {}
        # 环境变量覆盖（大写前缀）
        for key, value in self._data.items():
            env_val = os.getenv(key.upper())
            if env_val is not None:
                # 尝试转换类型
                if isinstance(value, bool):
                    self._data[key] = env_val.lower() in ('true', '1', 'yes')
                elif isinstance(value, int):
                    self._data[key] = int(env_val)
                elif isinstance(value, float):
                    self._data[key] = float(env_val)
                else:
                    self._data[key] = env_val
        # 处理路径
        for key in ['root_dir', 'data_dir', 'output_dir', 'subscribe_file', 'whitelist_file', 'blacklist_file', 'alias_file', 'demo_file']:
            if key in self._data:
                self._data[key] = Path(self._data[key])

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            return super().__getattr__(name)
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"Config has no attribute '{name}'")

    def to_dict(self) -> Dict:
        return self._data.copy()

# 全局单例
config = Config()
