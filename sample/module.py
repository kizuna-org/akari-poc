"""Sample Akari module."""

from __future__ import annotations

from akari import (
    AkariData,
    AkariDataSet,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


class _SampleModule(AkariModule):
    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)

    def call(
        self,
        data: AkariData,
        params: AkariModuleParams,
        callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        self._logger.debug("SampleModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)
        self._logger.debug("Callback: %s", callback)
        return AkariDataSet()
