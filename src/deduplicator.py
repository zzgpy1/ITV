# src/deduplicator.py
"""高效去重工具 - 布隆过滤器"""

import hashlib
import math
from typing import Optional


class BloomFilter:
    """
    简单布隆过滤器，用于高效去重
    误报率可配置，内存占用低
    """
    
    def __init__(self, capacity: int = 100000, error_rate: float = 0.01):
        """
        Args:
            capacity: 预期元素数量
            error_rate: 可接受的误报率
        """
        self.capacity = capacity
        self.error_rate = error_rate
        self.size = int(-capacity * math.log(error_rate) / (math.log(2) ** 2))
        self.hash_count = int(self.size * math.log(2) / capacity)
        self.bits = bytearray(self.size)
        self.count = 0
    
    def _hashes(self, item: str):
        """生成多个哈希值"""
        item_bytes = item.encode('utf-8')
        # 使用 double hashing 生成多个哈希
        h1 = int(hashlib.md5(item_bytes).hexdigest(), 16)
        h2 = int(hashlib.sha1(item_bytes).hexdigest(), 16)
        for i in range(self.hash_count):
            yield (h1 + i * h2) % self.size
    
    def add(self, item: str):
        """添加元素"""
        for pos in self._hashes(item):
            self.bits[pos // 8] |= 1 << (pos % 8)
        self.count += 1
    
    def contains(self, item: str) -> bool:
        """检查元素是否存在（可能有误报）"""
        for pos in self._hashes(item):
            if not (self.bits[pos // 8] & (1 << (pos % 8))):
                return False
        return True
    
    def add_and_check(self, item: str) -> bool:
        """
        添加并返回是否已存在
        Returns: True 如果已存在，False 如果新添加
        """
        exists = self.contains(item)
        if not exists:
            self.add(item)
        return exists
    
    @property
    def load_factor(self) -> float:
        """当前负载因子"""
        return self.count / self.capacity if self.capacity > 0 else 0


# 全局实例（用于频道去重）
_bloom_filter = None


def get_bloom_filter(capacity: int = 100000, error_rate: float = 0.01) -> BloomFilter:
    global _bloom_filter
    if _bloom_filter is None:
        _bloom_filter = BloomFilter(capacity, error_rate)
    return _bloom_filter
