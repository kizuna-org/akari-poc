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
    api_version="2024-08-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT") or "",
    azure_ad_token_provider=token_provider,
)


akariRouter = akari.MainRouter()
akariRouter.setModules(
    {
        modules.RootModule: modules.RootModule(akariRouter),
        sample.SampleModule: sample.SampleModule(akariRouter),
        openai.LLMModule: openai.LLMModule(akariRouter, client),
    }
)

akariRouter.callModule(
    moduleType=modules.RootModule,
    data=akari.AkariData(),
    params=sample.SampleModule,
)

akariRouter.callModule(
    moduleType=openai.LLMModule,
    data=akari.AkariData(),
    params=openai.LLMModuleParams(
        messages=[
            {"role": "user", "content": "Hello, Akari!"},
            {"role": "system", "content": "You are a helpful assistant."},
        ],
        temperature=0.7,
        max_tokens=150,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        stream=False,
    ),
)
