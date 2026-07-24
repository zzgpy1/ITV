# src/managers/__init__.py
"""管理器模块"""

from src.managers.source_manager import SourceManager
from src.managers.candidate_manager import CandidateManager
from src.managers.stable_manager import StableManager
from src.managers.quality_manager import QualityManager

__all__ = [
    "SourceManager",
    "CandidateManager",
    "StableManager",
    "QualityManager",
]
