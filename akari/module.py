from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import akari.data as data
import akari.logger as logger

if TYPE_CHECKING:
    import akari.router as router

_AkariModuleParams = Any
_AkariModuleType = type["AkariModule"]


class _AkariModule(ABC):
    def __init__(self, router: router._MainRouter, logger: logger._AkariLogger) -> None:
        self._router = router
        self._logger = logger

    @abstractmethod
    def call(
        self, data: data._AkariData, params: _AkariModuleParams, callback: _AkariModuleType | None = None
    ) -> data._AkariDataSet:
        pass

    def stream_call(
        self, data: data._AkariData, params: _AkariModuleParams, callback: _AkariModuleType | None = None
    ) -> data._AkariDataSet:
        raise NotImplementedError("stream_call is not implemented in this module.")
