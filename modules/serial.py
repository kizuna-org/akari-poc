import dataclasses

from akari import (
    AkariData,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _SerialModuleParamModule:
    moduleType: AkariModuleType
    moduleParams: AkariModuleParams
    moduleCallback: AkariModuleType | None = None


@dataclasses.dataclass
class _SerialModuleParams:
    modules: list[_SerialModuleParamModule]


class _SerialModule(AkariModule):
    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)

    def call(self, data: AkariData, params: _SerialModuleParams, callback: AkariModuleType | None = None) -> AkariData:
        for module in params.modules:
            data = self._router.callModule(
                moduleType=module.moduleType,
                data=data,
                params=module.moduleParams,
                callback=module.moduleCallback,
                streaming=False,
            )

        return data
