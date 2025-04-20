import akari
import modules
import sample

print("Hello, Akari!")

akariDataSet = akari.AkariDataSet()
akariDataSet.text = akari.AkariDataSetType(
    main="Hello, Akari!", others={"greeting": "Hello, World!", "farewell": "Goodbye, World!"}
)
akariData = akari.AkariData()

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
