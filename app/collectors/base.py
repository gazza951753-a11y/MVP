from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CollectResult:
    platforms: list[dict] = field(default_factory=list)
    mentions: list[dict] = field(default_factory=list)


class Collector(ABC):
    name: str = "base"

    @abstractmethod
    def collect(self) -> CollectResult:
        raise NotImplementedError
