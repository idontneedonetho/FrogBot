# events.py
import asyncio

class Signal:
    def __init__(self):
        self._subscribers = []

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def unsubscribe(self, callback):
        self._subscribers.remove(callback)

    async def emit(self, *args, **kwargs):
        for subscriber in self._subscribers:
            await subscriber(*args, **kwargs)

points_updated = Signal()
