from akari import (
    AkariData,
    AkariDataSet,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


class _RootModule(AkariModule):
    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)

    def call(self, data: AkariData, params: AkariModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        self._logger.debug("RootModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)
        self._router.callModule(moduleType=params, data=data, params=None, streaming=False, callback=callback)

        return AkariDataSet()
