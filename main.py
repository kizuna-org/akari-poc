import os

import dotenv
import pyaudio
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

import akari
import modules
import sample
from modules import audio, openai

dotenv.load_dotenv()


akariLogger = akari.getLogger("Akari")

akariLogger.info("Hello, Akari!")


def list_audio_devices() -> None:
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        akariLogger.debug(
            f"Device {i}: {info['name']} (Input: {info['maxInputChannels']}, Output: {info['maxOutputChannels']})"
        )
    p.terminate()


list_audio_devices()


token_provider = get_bearer_token_provider(
    DefaultAzureCredential(exclude_managed_identity_credential=True), "https://cognitiveservices.azure.com/.default"
)

client = AzureOpenAI(
    api_version="2024-10-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT") or "",
    azure_ad_token_provider=token_provider,
)


akariRouter = akari.MainRouter(logger=akariLogger)
akariRouter.setModules(
    {
        modules.RootModule: modules.RootModule(akariRouter, akariLogger),
        modules.PrintModule: modules.PrintModule(akariRouter, akariLogger),
        sample.SampleModule: sample.SampleModule(akariRouter, akariLogger),
        openai.LLMModule: openai.LLMModule(akariRouter, akariLogger, client),
        openai.STTModule: openai.STTModule(akariRouter, akariLogger, client),
        openai.TTSModule: openai.TTSModule(akariRouter, akariLogger, client),
        audio.SpeakerModule: audio.SpeakerModule(akariRouter, akariLogger),
        audio.MicModule: audio.MicModule(akariRouter, akariLogger),
    }
)

akariRouter.callModule(
    moduleType=modules.RootModule,
    data=akari.AkariData(),
    params=sample.SampleModule,
    streaming=False,
)

# akariRouter.callModule(
#     moduleType=openai.LLMModule,
#     data=akari.AkariData(),
#     params=openai.LLMModuleParams(
#         model = "gpt-4o-mini",
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

# data = akari.AkariData()
# dataset = akari.AkariDataSet()
# with open("input.mp3", "rb") as audio_file:
#     dataset.audio = akari.AkariDataSetType(main=audio_file.read())
# data.add(dataset)
# akariRouter.callModule(
#     moduleType=openai.STTModule,
#     data=data,
#     params=openai.STTModuleParams(
#         model="whisper",
#         language="ja",
#         prompt="",
#         temperature=0.7,
#     ),
# )

# data = akariRouter.callModule(
#     moduleType=openai.TTSModule,
#     data=akari.AkariData(),
#     params=openai.TTSModuleParams(
#         model="gpt-4o-mini-tts",
#         input="あかりだよ、よろしくね！",
#         voice="alloy",
#         instructions="日本語で元気溌剌に話してください",
#         response_format="wav",
#         speed=1.0,
#     ),
#     streaming=False,
# )

# with open("output.mp3", "wb") as audio_file:
#     audio_file.write(data.last().audio.main)  # type: ignore


# data = akari.AkariData()
# dataset = akari.AkariDataSet()
# with open("input.wav", "rb") as audio_file:
#     dataset.audio = akari.AkariDataSetType(main=audio_file.read())
# data.add(dataset)
# akariRouter.callModule(
#     moduleType=audio.SpeakerModule,
#     data=data,
#     params=audio.SpeakerModuleParams(),
#     streaming=False,
# )


akariRouter.callModule(
    moduleType=audio.MicModule,
    data=akari.AkariData(),
    params=audio.MicModuleParams(
        streamDurationMilliseconds=1000,
        destructionMilliseconds=5000,
        callbackParams=audio.SpeakerModuleParams(),
    ),
    streaming=False,
    callback=audio.SpeakerModule,
)
