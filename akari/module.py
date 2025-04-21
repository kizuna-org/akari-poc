from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import akari.data as data
import akari.logger as logger

if TYPE_CHECKING:
    import akari.router as router

AkariModuleParams = Any
AkariModuleType = type["AkariModule"]


class AkariModule(ABC):
    def __init__(self, router: router.MainRouter, logger: logger.AkariLogger) -> None:
        self._router = router
        self._logger = logger

    @abstractmethod
    def call(
        self, data: data.AkariData, params: AkariModuleParams, callback: AkariModuleType | None = None
    ) -> data.AkariDataSet:
        pass
