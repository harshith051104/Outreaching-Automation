import logging
import asyncio
import fnmatch
import uuid
import time
from typing import Dict, Any, List, Callable, Awaitable, Union

logger = logging.getLogger(__name__)

class EventBus:
    """Topic-based event bus supporting wildcard subscriptions and async dispatching."""
    def __init__(self):
        # Maps topic pattern string -> List of subscriber callback functions
        self._subscribers: Dict[str, List[Callable[[str, Dict[str, Any]], Union[None, Awaitable[None]]]]] = {}
        self._lock = asyncio.Lock()

    def subscribe(self, topic_pattern: str, callback: Callable[[str, Dict[str, Any]], Union[None, Awaitable[None]]]) -> None:
        """Subscribe to a topic pattern (e.g. 'workflow.*', 'tool.executed', or '*')."""
        if topic_pattern not in self._subscribers:
            self._subscribers[topic_pattern] = []
        self._subscribers[topic_pattern].append(callback)
        logger.debug(f"EventBus: Registered subscription pattern '{topic_pattern}'")

    async def publish(self, topic: str, event_data: Dict[str, Any]) -> None:
        """Publish an event to all matching subscribers asynchronously."""
        async with self._lock:
            callbacks_to_fire = []
            
            # Enrich event data with basic metadata
            enriched_data = {
                **event_data,
                "event_id": f"evt_{uuid.uuid4()}",
                "timestamp": time.time(),
                "topic": topic
            }

            for pattern, subs in self._subscribers.items():
                if fnmatch.fnmatch(topic, pattern):
                    callbacks_to_fire.extend(subs)

            if not callbacks_to_fire:
                return

            # Fire all callbacks concurrently in task loop
            asyncio.create_task(self._dispatch(callbacks_to_fire, topic, enriched_data))

    async def _dispatch(self, callbacks: List[Callable], topic: str, data: Dict[str, Any]) -> None:
        tasks = []
        for callback in callbacks:
            try:
                import inspect
                if inspect.iscoroutinefunction(callback):
                    tasks.append(callback(topic, data))
                else:
                    # Run synchronous callbacks in executors or wrap them
                    loop = asyncio.get_event_loop()
                    tasks.append(loop.run_in_executor(None, callback, topic, data))
            except Exception as e:
                logger.error(f"EventBus: Error preparing callback for topic '{topic}': {e}")
                
        if tasks:
            # Shield execution from cancellations
            res = await asyncio.gather(*tasks, return_exceptions=True)
            for r in res:
                if isinstance(r, Exception):
                    logger.error(f"EventBus: Exception raised during event dispatch: {r}")
