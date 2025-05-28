import copy
import dataclasses
import os
import time
from typing import Dict

import akari.data as akari_data
import akari.logger as logger
import akari.module as module


@dataclasses.dataclass
class _AkariRouterLoggerOptions:
    """Specifies logging preferences for the AkariRouter.

    Controls the verbosity of informational messages and the tracking of
    module execution durations.

    Attributes:
        info (bool): Enables or disables logging of general informational messages
            during router operations. Defaults to False.
        duration (bool): Enables or disables logging of the execution time for
            each called module. Defaults to False.
    """

    info: bool = False
    duration: bool = False


class _AkariRouter:
    """Orchestrates the execution of Akari modules.

    Maintains a registry of available modules and dispatches calls to them
    based on their type. It handles data flow, parameter passing, streaming
    logic, and logging of module interactions. It also records metadata about
    module execution, such as timing and parameters used.
    """

    def __init__(self, logger: logger._AkariLogger, options: _AkariRouterLoggerOptions | None = None) -> None:
        """Constructs an AkariRouter instance.

        Args:
            logger (_AkariLogger): The logger instance to be used for all router
                and module logging activities.
            options (Optional[_AkariRouterLoggerOptions]): Specific configuration
                for the router's logging behavior. If None, default logging
                options are applied.
        """
        if options is None:
            options = _AkariRouterLoggerOptions()
        self._modules: Dict[module._AkariModuleType, module._AkariModule] = {}
        self._logger = logger
        self._options = options

    def addModules(self, modules: Dict[module._AkariModuleType, module._AkariModule]) -> None:
        """Registers one or more modules with the router, making them available for execution.

        Each module is added to an internal registry, keyed by its type.
        Attempting to add a module type that already exists in the registry
        will result in an error.

        Args:
            modules (Dict[_AkariModuleType, _AkariModule]): A dictionary where keys
                are module types (classes inheriting from `_AkariModule`) and values
                are instances of those modules.

        Raises:
            ValueError: If a module type included in the `modules` dictionary
                has already been registered with the router.
        """
        for moduleType, moduleInstance in modules.items():
            if moduleType not in self._modules:
                self._modules[moduleType] = moduleInstance
            else:
                raise ValueError(f"Module {moduleType} already exists in router.")

    def callModule(
        self,
        moduleType: module._AkariModuleType,
        data: akari_data._AkariData,
        params: module._AkariModuleParams,
        streaming: bool,
        callback: module._AkariModuleType | None = None,
    ) -> akari_data._AkariData:
        """Executes a specified Akari module.

        Handles data flow, parameter passing, and optional streaming callbacks.
        It also records metadata about the module's execution, such as start
        and end times, and attaches this metadata to the resulting dataset.
        A deep copy of the input `data` is made before passing it to the
        selected module to ensure data isolation if needed.

        Args:
            moduleType (module._AkariModuleType): The class type of the Akari module to execute.
            data (akari_data._AkariData): The input data object for the module.
            params (module._AkariModuleParams): The parameters to be passed to the module.
            streaming (bool): A flag indicating whether the module should be called
                in streaming mode. If True, `selected_module.stream_call` is used;
                otherwise, `selected_module.call` is used.
            callback (Optional[module._AkariModuleType]): An optional module type to be
                used as a callback by the executed module, particularly relevant
                for streaming operations.

        Returns:
            akari_data._AkariData: The `data` object, potentially modified or augmented
            with new datasets produced by the executed module.

        Raises:
            ValueError: If the router's module registry has not been initialized,
                if the requested `moduleType` is not found in the registry, or if
                the executed module returns a result of an unexpected type.
        """
        if self._modules is None:
            raise ValueError("Modules not set in router.")

        inputData = copy.deepcopy(data)

        selected_module = self._modules[moduleType]
        if selected_module is None:
            raise ValueError(f"Module {moduleType} not found in router.")

        if self._options.info:
            self._logger.info(
                "\n\n[Router] Module %s (PID: %s): %s",
                "streaming" if streaming else "calling",
                os.getpid(),
                selected_module.__class__.__name__,
            )

        startTime = time.process_time()
        if streaming:
            result = selected_module.stream_call(inputData, params, callback)
        else:
            result = selected_module.call(inputData, params, callback)
        endTime = time.process_time()

        if isinstance(result, akari_data._AkariDataSet):
            result.setModule(
                akari_data._AkariDataModuleType(moduleType, params, streaming, callback, startTime, endTime)
            )
            data.add(result)
        elif isinstance(result, akari_data._AkariData):
            result.last().setModule(
                akari_data._AkariDataModuleType(moduleType, params, streaming, callback, startTime, endTime)
            )
            data = result
        else:
            raise ValueError(f"Invalid result type: {type(result)}")

        if self._options.duration:
            self._logger.info(
                "[Router] Module %s: %s took %.2f seconds",
                "streaming" if streaming else "calling",
                selected_module.__class__.__name__,
                endTime - startTime,
            )

        return data
