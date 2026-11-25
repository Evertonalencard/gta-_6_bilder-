"""Observer: barramento de eventos desacopla o dominio da interface."""
from collections import defaultdict
from typing import Callable

CITY_CHANGED = "city_changed"
BUDGET_CHANGED = "budget_changed"
ROAD_EVENT_STARTED = "road_event_started"
ROAD_EVENT_ENDED = "road_event_ended"
CYCLE_ADVANCED = "cycle_advanced"
RUSH_FINISHED = "rush_finished"


class EventBus:
    def __init__(self):
        self._subs = defaultdict(list)

    def subscribe(self, topic: str, callback: Callable[..., None]):
        self._subs[topic].append(callback)

    def publish(self, topic: str, **payload):
        for cb in list(self._subs[topic]):
            cb(**payload)
