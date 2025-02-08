from functools import lru_cache
from typing import Dict, Any
import time

class SimpleCache:
    def __init__(self, ttl: int = 300):  # 5 minutes TTL
        self.cache: Dict[str, Any] = {}
        self.ttl = ttl
        self.timestamps: Dict[str, float] = {}

    def get(self, key: str) -> Any:
        if key in self.cache:
            if time.time() - self.timestamps[key] < self.ttl:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None

    def set(self, key: str, value: Any):
        self.cache[key] = value
        self.timestamps[key] = time.time()

cache = SimpleCache()

# Use in visualization endpoint
@router.get("/plot/{symbol}")
async def get_plot(symbol: str, start_date: str, end_date: str, period: str):
    cache_key = f"{symbol}:{start_date}:{end_date}:{period}"
    
    if cached_result := cache.get(cache_key):
        return cached_result
        
    result = await generate_plot(symbol, start_date, end_date, period)
    cache.set(cache_key, result)
    return result 