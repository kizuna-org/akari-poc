from akari import AkariData, AkariDataSet, AkariModule, AkariModuleParams, MainRouter


class RootModule(AkariModule):
    def __init__(self, router: MainRouter) -> None:
        super().__init__(router)

    def call(self, data: AkariData, params: AkariModuleParams) -> AkariDataSet:
        print("RootModule called")
        print("Data:", data)
        print("Params:", params)
        self._router.callModule(params, data, None)

        return AkariDataSet()
