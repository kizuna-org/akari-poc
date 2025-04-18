from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import akari.data as data

if TYPE_CHECKING:
    import akari.router as router

AkariModuleParams = Any
AkariModuleType = type["AkariModule"]


class AkariModule(ABC):
    def __init__(self, router: router.MainRouter) -> None:
        self._router = router

    @abstractmethod
    def call(self, data: data.AkariData, params: AkariModuleParams) -> data.AkariData:
        pass
