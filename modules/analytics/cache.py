"""
Simple cache for analytics results (5-minute TTL)
"""
import time

class AnalyticsCache:
    def __init__(self, ttl=300):  # 5 minutes
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key):
        """Get cached value if not expired"""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                print(f">> Cache HIT for {key}")
                return value
            else:
                print(f">> Cache EXPIRED for {key}")
                del self.cache[key]
        else:
            print(f">> Cache MISS for {key}")
        return None
    
    def set(self, key, value):
        """Set cache value with current timestamp"""
        self.cache[key] = (value, time.time())
        print(f">> Cache SET for {key}")
    
    def clear(self):
        """Clear all cache"""
        self.cache.clear()
        print(">> Cache CLEARED")

# Global cache instance
analytics_cache = AnalyticsCache(ttl=300)  # 5 minutes
