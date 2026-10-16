"""Bounded per-process auth admission. Multi-replica deployments also need edge limits."""
from collections import OrderedDict
from threading import Lock
import time


class AuthLimiter:
    def __init__(self, limit=30, window=60, capacity=4096):
        self.limit, self.window, self.capacity = limit, window, capacity
        self.entries = OrderedDict()
        self.lock = Lock()

    def allow(self, peer):
        now = time.monotonic()
        with self.lock:
            while self.entries and next(iter(self.entries.values()))[0] <= now:
                self.entries.popitem(last=False)
            if peer not in self.entries:
                if len(self.entries) >= self.capacity:
                    return False
                self.entries[peer] = [now + self.window, 0]
            entry = self.entries[peer]
            if entry[1] >= self.limit:
                return False
            entry[1] += 1
            return True


auth_limiter = AuthLimiter()
