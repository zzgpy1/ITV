import math
import hashlib

class BloomFilter:
    def __init__(self, capacity=100000, error_rate=0.01):
        self.capacity = capacity
        self.size = int(-capacity * math.log(error_rate) / (math.log(2)**2))
        self.hash_count = int(self.size * math.log(2) / capacity)
        self.bits = bytearray(self.size)

    def _hashes(self, item):
        h1 = int(hashlib.md5(item.encode()).hexdigest(), 16)
        h2 = int(hashlib.sha1(item.encode()).hexdigest(), 16)
        for i in range(self.hash_count):
            yield (h1 + i * h2) % self.size

    def add(self, item):
        for pos in self._hashes(item):
            self.bits[pos//8] |= 1 << (pos%8)

    def contains(self, item):
        for pos in self._hashes(item):
            if not (self.bits[pos//8] & (1 << (pos%8))):
                return False
        return True
