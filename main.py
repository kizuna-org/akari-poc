import os

import dotenv
import pyaudio
import vertexai
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from google.oauth2 import service_account
from openai import AzureOpenAI
from vertexai.generative_models import Content, Part

import akari
import modules
import sample
from modules import audio, azure_openai, gemini, webrtcvad

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

credentials = service_account.Credentials.from_service_account_file(
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "",
)  # type: ignore
vertexai.init(
    location=os.getenv("GOOGLE_LOCATION") or "us-central1",
    credentials=credentials,
)


akariRouter = akari.AkariRouter(logger=akariLogger)
akariRouter.addModules(
    {
        modules.RootModule: modules.RootModule(akariRouter, akariLogger),
        modules.PrintModule: modules.PrintModule(akariRouter, akariLogger),
        modules.SerialModule: modules.SerialModule(akariRouter, akariLogger),
        sample.SampleModule: sample.SampleModule(akariRouter, akariLogger),
        azure_openai.LLMModule: azure_openai.LLMModule(akariRouter, akariLogger, client),
        azure_openai.STTModule: azure_openai.STTModule(akariRouter, akariLogger, client),
        azure_openai.TTSModule: azure_openai.TTSModule(akariRouter, akariLogger, client),
        gemini.LLMModule: gemini.LLMModule(akariRouter, akariLogger),
        audio.SpeakerModule: audio.SpeakerModule(akariRouter, akariLogger),
        audio.MicModule: audio.MicModule(akariRouter, akariLogger),
        webrtcvad.WebRTCVadModule: webrtcvad.WebRTCVadModule(akariRouter, akariLogger),
        io.SaveModule: io.SaveModule(akariRouter, akariLogger),
    }
)

# akariRouter.callModule(
#     moduleType=modules.RootModule,
#     data=akari.AkariData(),
#     params=sample.SampleModule,
#     streaming=False,
# )

# akariRouter.callModule(
#     moduleType=azure_openai.LLMModule,
#     data=akari.AkariData(),
#     params=azure_openai.LLMModuleParams(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "user", "content": "Hello, Akari!"},
#             {"role": "system", "content": "You are a helpful assistant."},
#         ],
#         temperature=0.7,
#         max_tokens=150,
#         top_p=1.0,
#         frequency_penalty=0.0,
#         presence_penalty=0.0,
#         stream=True,
#     ),
#     streaming=False,
#     callback=modules.PrintModule,
# )


# data = akariRouter.callModule(
#     moduleType=gemini.LLMModule,
#     data=akari.AkariData(),
#     params=gemini.LLMModuleParams(
#         model="gemini-2.0-flash",
#         messages=[
#             Content(role="user", parts=[Part.from_text("Hello, Akari!")]),
#         ],
#     ),
#     streaming=False,
# )


# data = akari.AkariData()
# dataset = akari.AkariDataSet()
# with open("input.wav", "rb") as audio_file:
#     dataset.audio = akari.AkariDataSetType(main=audio_file.read())
# data.add(dataset)
# akariRouter.callModule(
#     moduleType=azure_openai.STTModule,
#     data=data,
#     params=azure_openai.STTModuleParams(
#         model="whisper",
#         language="ja",
#         prompt="",
#         temperature=0.7,
#     ),
# )

# data = akariRouter.callModule(
#     moduleType=azure_openai.TTSModule,
#     data=akari.AkariData(),
#     params=azure_openai.TTSModuleParams(
#         model="gpt-4o-mini-tts",
#         input="あかりだよ、よろしくね！",
#         voice="alloy",
#         instructions="日本語で元気溌剌に話してください",
#         response_format="wav",
#         speed=1.0,
#     ),
#     streaming=False,
# )

# with open("output.wav", "wb") as audio_file:
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
        callbackParams=webrtcvad.WebRTCVadParams(),
        callback_callback=modules.PrintModule,
    ),
    streaming=False,
    callback=webrtcvad.WebRTCVadModule,
)
