from akari import AkariData, AkariModule, AkariModuleParams, MainRouter


class SampleModule(AkariModule):
    def __init__(self, router: MainRouter) -> None:
        super().__init__(router)

    def call(self, data: AkariData, params: AkariModuleParams) -> AkariData:
        print("SampleModule called")
        print("Data:", data)
        print("Params:", params)
        return data
