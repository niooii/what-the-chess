from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass
class PlayerState:
    name: str
    id: int = 0
    color: Optional[str] = None  # 'white' or 'black'
    ready: bool = False
    connected_at: float = 0.0

    async def replicate(self, server, event_type: str):
        await server.broadcast({"type": event_type, "player": asdict(self)}, self.id)

