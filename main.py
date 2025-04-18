import akari
import modules
import sample

print("Hello, Akari!")

akariDataSet = akari.AkariDataSet()
akariDataSet.text = akari.AkariDataSetType(
    main="Hello, Akari!", others={"greeting": "Hello, World!", "farewell": "Goodbye, World!"}
)
akariData = akari.AkariData(last=akariDataSet)

akariRouter = akari.MainRouter()
akariRouter.setModules(
    {
        modules.RootModule: modules.RootModule(akariRouter),
        sample.SampleModule: sample.SampleModule(akariRouter),
    }
)

akariRouter.callModule(
    moduleType=modules.RootModule,
    data=akari.AkariData(akari.AkariDataSet()),
    params=sample.SampleModule,
)
