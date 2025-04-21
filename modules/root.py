from akari import (
    AkariData,
    AkariDataSet,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    MainRouter,
)


class RootModule(AkariModule):
    def __init__(self, router: MainRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)

    def call(self, data: AkariData, params: AkariModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        self._logger.debug("RootModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)
        self._router.callModule(params, data, None)

        return AkariDataSet()
