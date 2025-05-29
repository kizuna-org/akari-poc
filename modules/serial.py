"""Module for executing a series of Akari modules sequentially."""

from __future__ import annotations

import dataclasses

from akari_core.logger import AkariLogger
from akari_core.module import (
    AkariData,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _SerialModuleParamModule:
    """Define a step in the serial module pipeline."""

    module_type: AkariModuleType
    module_params: AkariModuleParams
    module_callback: AkariModuleType | None = None


@dataclasses.dataclass
class _SerialModuleParams(AkariModuleParams):
    """Parameters for the SerialModule."""

    modules: list[_SerialModuleParamModule]
    """List of module configurations to execute in sequence."""


class _SerialModule(AkariModule):
    """Execute a list of modules in sequence."""

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """Construct a _SerialModule instance."""
        super().__init__(router, logger)

    def call(
        self,
        data: AkariData,
        params: _SerialModuleParams,
        _callback: AkariModuleType | None = None,
    ) -> AkariData:
        """Process an AkariData object sequentially through configured modules."""
        self._logger.debug("SerialModule called")
        current_data = data

        for module_config in params.modules:
            self._logger.debug(
                "Calling module: %s with params: %s",
                module_config.module_type,
                module_config.module_params,
            )
            result_data_set = self._router.callModule(
                module_config.module_type,
                current_data,
                module_config.module_params,
                streaming=False,
                callback=module_config.module_callback,
            )
            if result_data_set:
                current_data.add(result_data_set)

        self._logger.debug("SerialModule finished")
        return current_data

    def stream_call(
        self,
        data: AkariData,
        params: _SerialModuleParams,
        _callback: AkariModuleType | None = None,
    ) -> AkariData:
        """Process an AkariData object sequentially through configured modules.

        Although named stream_call, this implementation currently iterates
        through modules in a blocking manner similar to call.
        True streaming would require managing concurrent module execution or
        a different pipeline architecture.
        """
        self._logger.debug("SerialModule stream_call called")
        current_data = data

        for module_config in params.modules:
            self._logger.debug(
                "Streaming calling module: %s with params: %s",
                module_config.module_type,
                module_config.module_params,
            )
            result_data_set = self._router.callModule(
                module_config.module_type,
                current_data,
                module_config.module_params,
                streaming=True,
                callback=module_config.module_callback,
            )
            if result_data_set:
                current_data.add(result_data_set)

        self._logger.debug("SerialModule stream_call finished")
        return current_data
