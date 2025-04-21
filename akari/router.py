import copy
from typing import Dict

import akari.data as data
import akari.logger as logger
import akari.module as module


class MainRouter:
    def __init__(self, logger: logger.AkariLogger) -> None:
        self._modules: Dict[module.AkariModuleType, module.AkariModule] | None = None
        self._logger = logger

    def setModules(self, modules: Dict[module.AkariModuleType, module.AkariModule]) -> None:
        self._modules = modules

    def callModule(
        self,
        moduleType: module.AkariModuleType,
        data: data.AkariData,
        params: module.AkariModuleParams,
        with_stream: bool,
        callback: module.AkariModuleType | None = None,
    ) -> data.AkariData:
        if self._modules is None:
            raise ValueError("Modules not set in router.")

        inputData = copy.deepcopy(data)

        selected_module = self._modules[moduleType]
        if selected_module is None:
            raise ValueError(f"Module {moduleType} not found in router.")

        self._logger.debug(
            "\n\n[Router] Module %s: %s", "streaming" if with_stream else "calling", selected_module.__class__.__name__
        )

        if with_stream:
            dataset = selected_module.stream_call(inputData, params, callback)
        else:
            dataset = selected_module.call(inputData, params, callback)

        data.add(dataset)

        return data
