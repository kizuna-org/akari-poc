import copy
from typing import Dict

import akari.data as data
import akari.module as module


class MainRouter:
    def __init__(self) -> None:
        self._modules: Dict[module.AkariModuleType, module.AkariModule] | None = None

    def setModules(self, modules: Dict[module.AkariModuleType, module.AkariModule]) -> None:
        self._modules = modules

    def callModule(
        self, moduleType: module.AkariModuleType, data: data.AkariData, params: module.AkariModuleParams
    ) -> data.AkariData:
        if self._modules is None:
            raise ValueError("Modules not set in router.")

        inputData = copy.deepcopy(data)

        selected_module = self._modules[moduleType]
        if not selected_module:
            raise ValueError(f"Module {moduleType} not found in router.")
        if not isinstance(selected_module, module.AkariModule):
            raise TypeError(f"Module {moduleType} is not an instance of AkariModule.")

        result = selected_module.call(inputData, params)

        return result
