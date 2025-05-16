import copy
import dataclasses
import time
from typing import Dict

import akari.data as akari_data
import akari.logger as logger
import akari.module as module


@dataclasses.dataclass
class _AkariRouterLoggerOptions:
    info: bool = False
    duration: bool = False


class _AkariRouter:
    def __init__(self, logger: logger._AkariLogger, options: _AkariRouterLoggerOptions | None = None) -> None:
        if options is None:
            options = _AkariRouterLoggerOptions()
        self._modules: Dict[module._AkariModuleType, module._AkariModule] = {}
        self._logger = logger
        self._options = options

    def addModules(self, modules: Dict[module._AkariModuleType, module._AkariModule]) -> None:
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

        if self._options.info:
            self._logger.info(
                "\n\n[Router] Module %s: %s",
                "streaming" if streaming else "calling",
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
