from akari import (
    AkariData,
    AkariDataSet,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    MainRouter,
)


class SampleModule(AkariModule):
    def __init__(self, router: MainRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)

    def call(self, data: AkariData, params: AkariModuleParams) -> AkariDataSet:
        self._logger.debug("SampleModule called")
        self._logger.debug("Data:", data)
        self._logger.debug("Params:", params)
        return AkariDataSet()
