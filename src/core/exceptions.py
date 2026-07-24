# src/core/exceptions.py
"""自定义异常"""

from src.infrastructure.logger import get_logger


class IPTVError(Exception):
    """基础异常"""
    pass


class ConfigError(IPTVError):
    """配置错误"""
    pass


class DatabaseError(IPTVError):
    """数据库错误"""
    pass


class FetchError(IPTVError):
    """获取源失败"""
    pass


class ParseError(IPTVError):
    """解析失败"""
    pass


class ValidationError(IPTVError):
    """验证失败"""
    pass


class SpeedTestError(IPTVError):
    """测速失败"""
    pass


class ChannelNotFoundError(IPTVError):
    """频道未找到"""
    pass


class FixedSourceError(IPTVError):
    """固定源错误"""
    pass


def handle_exception(exc: Exception, context: str = "") -> None:
    """统一异常处理"""
    logger = get_logger(__name__)
    
    if isinstance(exc, IPTVError):
        logger.error(f"{context}: {exc}")
    else:
        logger.exception(f"{context}: {exc}")
