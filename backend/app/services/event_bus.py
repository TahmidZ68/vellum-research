import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis

from app.core.config import get_settings


class ResearchEventBus:
    """
    Event bus for streaming live research progress to SSE clients.
    Supports Redis Pub/Sub + list history in ARQ mode and in-memory fan-out in inline/test mode.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)

    @staticmethod
    def _channel_name(run_id: str) -> str:
        return f"ora:run:{run_id}:events"

    @staticmethod
    def _history_key(run_id: str) -> str:
        return f"ora:run:{run_id}:history"

    async def publish(
        self,
        run_id: UUID | str,
        event_type: str,
        stage: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run_key = str(run_id)
        payload: dict[str, Any] = {
            "run_id": run_key,
            "event": event_type,
            "stage": stage,
            "message": message,
            "data": data or {},
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Always keep local history & notify local subscribers
        self._history[run_key].append(payload)
        if len(self._history[run_key]) > 200:
            self._history[run_key] = self._history[run_key][-200:]

        for queue in list(self._subscribers.get(run_key, ())):
            await queue.put(payload)

        settings = get_settings()
        if settings.TASK_QUEUE_MODE == "arq":
            try:
                client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                encoded = json.dumps(payload)
                await client.rpush(self._history_key(run_key), encoded)
                await client.expire(self._history_key(run_key), 86400)
                await client.publish(self._channel_name(run_key), encoded)
                await client.aclose()
            except Exception:
                # Never crash research pipeline if Redis pubsub fails transiently
                pass

        return payload

    async def subscribe(self, run_id: UUID | str) -> AsyncGenerator[dict[str, Any], None]:
        run_key = str(run_id)
        settings = get_settings()

        if settings.TASK_QUEUE_MODE == "arq":
            try:
                client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                pubsub = client.pubsub()
                await pubsub.subscribe(self._channel_name(run_key))
                history_items = await client.lrange(self._history_key(run_key), 0, -1)
                for item in history_items:
                    yield json.loads(item)

                while True:
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if msg and msg.get("data"):
                        parsed = json.loads(msg["data"])
                        yield parsed
                        if parsed.get("event") in {"run_completed", "run_failed", "run_cancelled"}:
                            break
                    else:
                        await asyncio.sleep(0.25)
                await pubsub.unsubscribe(self._channel_name(run_key))
                await pubsub.aclose()
                await client.aclose()
                return
            except Exception:
                # Fallback to in-memory subscriber if Redis isn't reachable
                pass

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers[run_key].add(queue)
        try:
            for past_event in list(self._history.get(run_key, [])):
                yield past_event
                if past_event.get("event") in {"run_completed", "run_failed", "run_cancelled"}:
                    return

            while True:
                event = await queue.get()
                yield event
                if event.get("event") in {"run_completed", "run_failed", "run_cancelled"}:
                    break
        finally:
            self._subscribers[run_key].discard(queue)

    def clear_history(self, run_id: UUID | str) -> None:
        self._history.pop(str(run_id), None)


event_bus = ResearchEventBus()
