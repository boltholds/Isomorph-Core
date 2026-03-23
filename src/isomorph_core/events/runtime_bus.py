from isomorph_core.events.models import RuntimeEvent


class InMemoryRuntimeBus:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def publish(self, event: RuntimeEvent) -> None:
        self.events.append(event)
