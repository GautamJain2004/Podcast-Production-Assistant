"""
A2A message broker with two modes:
- in-process asyncio mode (default) using asyncio.Queue per topic
- Redis-backed pub/sub mode (if REDIS_URL environment variable present)

Provides:
- async publish(topic, message)
- async subscribe(topic, handler)  # handler is async function(message)
- sync wrappers: publish_sync, subscribe_sync for blocking code
- run_in_thread() to run the broker's event loop in a background thread if needed
"""

import os
import asyncio
import json
import logging
import threading
from typing import Any, Callable, Dict, Optional, Coroutine, Awaitable

logger = logging.getLogger("a2a_broker")
logger.addHandler(logging.NullHandler())

REDIS_URL = os.getenv("REDIS_URL") or os.getenv("A2A_BROKER_REDIS_URL") or None

# Try import redis.asyncio only if needed
_redis = None
if REDIS_URL:
    try:
        import redis.asyncio as aioredis  # type: ignore
        _redis = aioredis
    except Exception:
        logger.warning("redis.asyncio not available; Redis mode will fail if REDIS_URL is set")


class Broker:
    """
    In-process + Redis-backed A2A broker.
    """

    def __init__(self, pipeline_order: Optional[list] = None):
        # pipeline_order: optional ordered list of agent names for auto-forwarding
        self.pipeline_order = pipeline_order or []
        self._queues: Dict[str, asyncio.Queue] = {}
        self._subscribers: Dict[str, list] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._redis_client = None
        self._redis_tasks = []
        self._running = False

    # ---------------------
    # Startup / loop helpers
    # ---------------------
    def ensure_loop(self):
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def start_background_loop(self):
        """Run the broker loop in a background thread (useful for sync code)."""
        if self._thread and self._thread.is_alive():
            return

        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._running = True
            logger.info("Starting broker event loop in background thread")
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop_background_loop(self):
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._running = False

    # ---------------------
    # Redis helpers
    # ---------------------
    async def _ensure_redis(self):
        if not REDIS_URL:
            return None
        if not _redis:
            raise RuntimeError("redis.asyncio is required for Redis broker mode but is not installed.")
        if self._redis_client is None:
            self._redis_client = _redis.from_url(REDIS_URL)
        return self._redis_client

    # ---------------------
    # Publish / subscribe
    # ---------------------
    async def publish(self, topic: str, message: Any) -> None:
        """
        Publish a message to a topic. The message will be JSON-serialized.
        """
        msg_text = json.dumps(message, default=str)
        if REDIS_URL:
            redis = await self._ensure_redis()
            await redis.publish(topic, msg_text)
            logger.debug(f"[broker] Redis publish to {topic}")
            return

        # in-process: put on queue and call subscribers
        q = self._queues.setdefault(topic, asyncio.Queue())
        await q.put(message)
        # notify subscribers by scheduling their handlers
        if topic in self._subscribers:
            for handler in list(self._subscribers[topic]):
                asyncio.create_task(handler(message))
        # Note: Pipeline auto-forwarding is now handled by agent wrappers
        # to avoid duplicate message delivery

    async def subscribe(self, topic: str, handler: Callable[[Any], Awaitable[None]]) -> None:
        """
        Subscribe an async handler to a topic.
        Handler signature: async def handler(message)
        """
        if REDIS_URL:
            redis = await self._ensure_redis()
            sub = redis.pubsub()
            await sub.subscribe(topic)

            async def _redis_loop():
                logger.info(f"[broker] Redis subscription loop started for {topic}")
                async for item in sub.listen():
                    if item is None:
                        continue
                    if item.get("type") != "message":
                        continue
                    data = item.get("data")
                    try:
                        message = json.loads(data)
                    except Exception:
                        message = data
                    await handler(message)

            task = asyncio.create_task(_redis_loop())
            self._redis_tasks.append(task)
            return

        # in-process mode
        self._subscribers.setdefault(topic, []).append(handler)

    # ---------------------
    # Synchronous wrappers
    # ---------------------
    def publish_sync(self, topic: str, message: Any) -> None:
        """Blocking publish wrapper usable from sync code."""
        loop = self._loop or asyncio.get_event_loop()
        if loop.is_running():
            # schedule in running loop
            fut = asyncio.run_coroutine_threadsafe(self.publish(topic, message), loop)
            fut.result(timeout=30)
        else:
            # run until complete
            loop.run_until_complete(self.publish(topic, message))

    def subscribe_sync(self, topic: str, handler: Callable[[Any], None]) -> None:
        """
        Subscribe a synchronous handler from sync code.
        The sync handler will be run in a threadpool via loop.run_in_executor.
        """
        async def _wrap(message):
            # run sync handler in threadpool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, handler, message)

        loop = self._loop or asyncio.get_event_loop()
        if loop.is_running():
            coro = self.subscribe(topic, _wrap)
            asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=30)
        else:
            loop.run_until_complete(self.subscribe(topic, _wrap))

    # ---------------------
    # Pipeline helper
    # ---------------------
    async def _maybe_forward_pipeline(self, topic: str, message: Any):
        """
        If the message contains a 'next' key, publish to that topic.
        Otherwise, if pipeline_order is provided, forward to the next agent in pipeline_order.
        """
        # message expected to be dict-like
        next_topic = None
        if isinstance(message, dict):
            next_topic = message.get("next")
        if next_topic:
            await self.publish(next_topic, message)
            return

        # auto-forward using pipeline_order
        if self.pipeline_order:
            try:
                idx = self.pipeline_order.index(topic)
                if idx is not None and idx + 1 < len(self.pipeline_order):
                    await self.publish(self.pipeline_order[idx + 1], message)
            except ValueError:
                # topic not in pipeline
                pass

    # ---------------------
    # Utilities
    # ---------------------
    def set_pipeline(self, pipeline: list):
        self.pipeline_order = pipeline

    def shutdown(self):
        self.stop_background_loop()
        # cancel redis tasks
        for t in self._redis_tasks:
            t.cancel()

# ---------------------
# Global broker singleton
# ---------------------
_global_broker: Optional[Broker] = None


def get_global_broker(pipeline_order: Optional[list] = None) -> Broker:
    global _global_broker
    if _global_broker is None:
        _global_broker = Broker(pipeline_order=pipeline_order)
    return _global_broker
