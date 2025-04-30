import copy
from typing import Dict

import akari.data as data
import akari.logger as logger
import akari.module as module


class _MainRouter:
    def __init__(self, logger: logger._AkariLogger) -> None:
        self._modules: Dict[module._AkariModuleType, module._AkariModule] | None = None
        self._logger = logger

    def setModules(self, modules: Dict[module._AkariModuleType, module._AkariModule]) -> None:
        self._modules = modules

    def callModule(
        self,
        moduleType: module._AkariModuleType,
        data: data._AkariData,
        params: module._AkariModuleParams,
        streaming: bool,
        callback: module._AkariModuleType | None = None,
    ) -> data._AkariData:
        """
        Args:
            streaming (bool): 呼び出し元がストリームしているかどうかのフラグ(=呼び出し先がストリームするかどうかの制御)
        """
        if self._modules is None:
            raise ValueError("Modules not set in router.")

        inputData = copy.deepcopy(data)

        selected_module = self._modules[moduleType]
        if selected_module is None:
            raise ValueError(f"Module {moduleType} not found in router.")

        self._logger.debug(
            "\n\n[Router] Module %s: %s",
            "streaming" if streaming else "calling",
            selected_module.__class__.__name__,
        )

        if streaming:
            dataset = selected_module.stream_call(inputData, params, callback)
        else:
            dataset = selected_module.call(inputData, params, callback)

        data.add(dataset)

        return data
