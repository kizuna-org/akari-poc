from akari import (
    AkariData,
    AkariDataSet,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    MainRouter,
)


class RootModule(AkariModule):
    def __init__(self, router: MainRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)

    def call(self, data: AkariData, params: AkariModuleParams) -> AkariDataSet:
        print("RootModule called")
        print("Data:", data)
        print("Params:", params)
        self._router.callModule(params, data, None)

        return AkariDataSet()
