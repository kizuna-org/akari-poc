import json
from typing import Any

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
    AkariModule,
    AkariModuleType,
    AkariRouter,
)


class _PrintModule(AkariModule):
    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)

    def call(self, data: AkariData, params: Any, callback: AkariModuleType | None = None) -> AkariDataSet:
        self._logger.debug("PrintModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        try:
            self._logger.debug("Last Data: %s", json.dumps(data.last(), indent=4))
        except:
            self._logger.debug("Last Data: %s", repr(data.last()))

        return AkariDataSet()

    def stream_call(self, data: AkariData, params: Any, callback: AkariModuleType | None = None) -> AkariDataSet:
        self._logger.debug("PrintModule stream_call called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        last = data.last()
        try:
            self._logger.debug("Last Data: %s", json.dumps(last, indent=4))
        except:
            self._logger.debug("Last Data: %s", last)

        for field in last.__dict__:
            if hasattr(last, field):
                value = getattr(last, field)
                if isinstance(value, AkariDataSetType):
                    if value.main is not None:
                        self._logger.debug("%s: %s", field, value.main)
                else:
                    if value is not None:
                        self._logger.debug("%s: %s", field, value)

        return AkariDataSet()
