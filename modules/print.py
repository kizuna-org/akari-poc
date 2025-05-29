"""A module for printing and logging AkariData contents."""

from __future__ import annotations

import json

from akari_core.logger import AkariLogger
from akari_core.module import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


class _PrintModule(AkariModule):
    """A module for printing and logging AkariData contents."""

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """Constructs a PrintModule instance.

        Args:
            router (AkariRouter): The Akari router instance, used for potential
                inter-module communication (though not directly used in this module's
                current implementation beyond the base class).
            logger (AkariLogger): The logger instance to which the dataset
                information will be written.
        """
        super().__init__(router, logger)

    def call(
        self,
        data: AkariData,
        params: AkariModuleParams | None = None,
        _callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """Inspect and log the contents of the last AkariDataSet."""
        self._logger.debug("PrintModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        last = data.last()
        if last:
            self._logger.info("Last DataSet: %s", last)

        try:
            self._logger.info("Last Data (json): %s", json.dumps(last, indent=4))
        except Exception as e:
            self._logger.info("Could not serialize last data to json: %s, error: %s", last, e)

        for field in last.__dict__:
            if hasattr(last, field) and field != "module":
                value = getattr(last, field)
                if isinstance(value, AkariDataSetType):
                    if value.main is not None:
                        self._logger.info("%s: %s", field, value.main)
                elif value is not None:
                    self._logger.info("%s: %s", field, value)

        return data.last() if data.datasets else AkariDataSet()

    def stream_call(
        self,
        data: AkariData,
        params: AkariModuleParams | None = None,
        _callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """Process streaming data by applying logging logic from call method."""
        self._logger.debug("PrintModule stream_call called")

        last = data.last()
        if last:
            self._logger.info("Stream Last DataSet: %s", last)

        try:
            self._logger.info("Stream Last Data (json): %s", json.dumps(last, indent=4))
        except Exception as e:
            self._logger.info("Could not serialize stream last data to json: %s, error: %s", last, e)

        return data.last() if data.datasets else AkariDataSet()
