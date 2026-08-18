from typing import Callable, Dict, List
from .base import DomainEvent

# Simple in-process event registry (later can become Celery / message bus)
_handlers: Dict[str, List[Callable]] = {}


def register_handler(event_type: str):
    def decorator(func: Callable):
        if event_type not in _handlers:
            _handlers[event_type] = []
        _handlers[event_type].append(func)
        return func
    return decorator


def publish(event: DomainEvent):
    """
    Publish a domain event to all registered handlers.
    In future this will also push to Celery / Redis Streams / Kafka.
    """
    handlers = _handlers.get(event.event_type, [])
    for handler in handlers:
        handler(event)


# def publish(event: DomainEvent, async_dispatch: bool = False):
#     persist_event(event)

#     if async_dispatch:
#         dispatch_event.delay(event.to_dict())
#     else:
#         _dispatch_sync(event)


def get_handlers(event_type: str) -> List[Callable]:
    return _handlers.get(event_type, [])