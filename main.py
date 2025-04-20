import akari
import modules
import sample

print("Hello, Akari!")

akariRouter = akari.MainRouter()
akariRouter.setModules(
    {
        modules.RootModule: modules.RootModule(akariRouter),
        sample.SampleModule: sample.SampleModule(akariRouter),
    }
)

akariRouter.callModule(
    moduleType=modules.RootModule,
    data=akari.AkariData(),
    params=sample.SampleModule,
)
