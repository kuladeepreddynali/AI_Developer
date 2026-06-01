import asyncio
import time
import sys
import os
from collections import deque

# Ensure project root is on sys.path so top-level imports like `config` work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

class GeminiRateLimiter:
    def __init__(
        self,
        max_requests_per_minute=settings.MAX_REQUESTS_PER_MINUTE,
        max_concurrent_requests=settings.MAX_CONCURRENT_REQUESTS
    ):
        self.max_requests_per_minute = max_requests_per_minute
        self.request_times = deque()

        self.semaphore = asyncio.Semaphore(
            max_concurrent_requests
        )

    async def acquire(self):

        await self.semaphore.acquire()

        while True:

            current_time = time.time()

            while (
                self.request_times
                and current_time - self.request_times[0] > 60
            ):
                self.request_times.popleft()

            if len(self.request_times) < self.max_requests_per_minute:
                self.request_times.append(current_time)
                return

            wait_time = (
                60 -
                (current_time - self.request_times[0])
            )

            await asyncio.sleep(wait_time)

    def release(self):
        self.semaphore.release()