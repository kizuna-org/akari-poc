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
        print("SampleModule called")
        print("Data:", data)
        print("Params:", params)
        return AkariDataSet()
