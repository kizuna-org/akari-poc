import os

import dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

import akari
import modules
import sample
from modules import openai

dotenv.load_dotenv()

print("Hello, Akari!")

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(exclude_managed_identity_credential=True), "https://cognitiveservices.azure.com/.default"
)

client = AzureOpenAI(
    api_version="2024-10-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT") or "",
    azure_ad_token_provider=token_provider,
)


akariRouter = akari.MainRouter()
akariRouter.setModules(
    {
        modules.RootModule: modules.RootModule(akariRouter),
        sample.SampleModule: sample.SampleModule(akariRouter),
        openai.LLMModule: openai.LLMModule(akariRouter, client),
        openai.STTModule: openai.STTModule(akariRouter, client),
    }
)

akariRouter.callModule(
    moduleType=modules.RootModule,
    data=akari.AkariData(),
    params=sample.SampleModule,
)

# akariRouter.callModule(
#     moduleType=openai.LLMModule,
#     data=akari.AkariData(),
#     params=openai.LLMModuleParams(
#         messages=[
#             {"role": "user", "content": "Hello, Akari!"},
#             {"role": "system", "content": "You are a helpful assistant."},
#         ],
#         temperature=0.7,
#         max_tokens=150,
#         top_p=1.0,
#         frequency_penalty=0.0,
#         presence_penalty=0.0,
#         stream=False,
#     ),
# )

# input audio file from ./input.mp3
data = akari.AkariData()
dataset = akari.AkariDataSet()
with open("input.mp3", "rb") as audio_file:
    dataset.audio = akari.AkariDataSetType(main=audio_file.read())
data.add(dataset)
print(os.getenv("AZURE_OPENAI_ENDPOINT"))
akariRouter.callModule(
    moduleType=openai.STTModule,
    data=data,
    params=openai.STTModuleParams(
        model="whisper",
        language="ja",
        prompt="",
        temperature=0.7,
    ),
)
