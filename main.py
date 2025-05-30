import logging
import os

import dotenv
import pyaudio
import vertexai
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from google.cloud import speech, texttospeech
from google.oauth2 import service_account
from openai import AzureOpenAI

import akari
import modules
import sample
from modules import audio, azure_openai, gemini, google, io, performance, webrtcvad

dotenv.load_dotenv()


akari_logger = akari.getLogger(
    "Akari",
    logging.INFO,
)

akari_logger.info("Hello, Akari!")


def list_audio_devices() -> None:
    """Enumerates and logs details of all audio devices discoverable by PyAudio.

    Initializes the PyAudio library to query for available audio hardware.
    For each detected device, it logs its unique index, human-readable name,
    maximum number of input channels, and maximum number of output channels.
    This information is logged at the DEBUG level using the globally configured
    Akari logger. This utility is helpful for debugging audio configurations or
    allowing users to select specific audio devices. The PyAudio instance is
    properly terminated before the function exits.
    """
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        akari_logger.info(
            f"Device {i}: {info['name']} (Input: {info['maxInputChannels']}, Output: {info['maxOutputChannels']})",
        )
    p.terminate()


list_audio_devices()


token_provider = get_bearer_token_provider(
    DefaultAzureCredential(exclude_managed_identity_credential=True),
    "https://cognitiveservices.azure.com/.default",
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

speech_client = speech.SpeechClient(credentials=credentials)
tts_client = texttospeech.TextToSpeechClient(credentials=credentials)

akari_router = akari.AkariRouter(
    logger=akari_logger,
    options=akari.AkariRouterLoggerOptions(info=False, duration=True),
)
akari_router.add_modules(
    {
        modules.RootModule: modules.RootModule(akari_router, akari_logger),
        modules.PrintModule: modules.PrintModule(akari_router, akari_logger),
        modules.SerialModule: modules.SerialModule(akari_router, akari_logger),
        sample.SampleModule: sample.SampleModule(akari_router, akari_logger),
        azure_openai.LLMModule: azure_openai.LLMModule(akari_router, akari_logger, client),
        azure_openai.TTSModule: azure_openai.TTSModule(akari_router, akari_logger, client),
        google.GoogleSpeechToTextStreamModule: google.GoogleSpeechToTextStreamModule(
            akari_router,
            akari_logger,
            speech_client,
        ),
        google.GoogleTextToSpeechModule: google.GoogleTextToSpeechModule(akari_router, akari_logger, tts_client),
        gemini.LLMModule: gemini.LLMModule(akari_router, akari_logger),
        audio.SpeakerModule: audio.SpeakerModule(akari_router, akari_logger),
        audio.MicModule: audio.MicModule(akari_router, akari_logger),
        webrtcvad.WebRTCVadModule: webrtcvad.WebRTCVadModule(akari_router, akari_logger),
        io.SaveModule: io.SaveModule(akari_router, akari_logger),
        performance.VADSTTLatencyMeter: performance.VADSTTLatencyMeter(akari_router, akari_logger),
    },
)

# akari_router.call_module(
#     module_type=modules.RootModule,
#     data=akari.AkariData(),
#     params=sample.SampleModule,
#     streaming=False,
# )

# akari_router.call_module(
#     module_type=azure_openai.LLMModule,
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


# data = akari_router.call_module(
#     module_type=gemini.LLMModule,
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
# akari_router.call_module(
#     module_type=azure_openai.STTModule,
#     data=data,
#     params=azure_openai.STTModuleParams(
#         model="whisper",
#         language="ja",
#         prompt="",
#         temperature=0.7,
#     ),
# )

# data = akari_router.call_module(
#     module_type=azure_openai.TTSModule,
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
# akari_router.call_module(
#     module_type=audio.SpeakerModule,
#     data=data,
#     params=audio.SpeakerModuleParams(),
#     streaming=False,
# )


# akari_router.call_module(
#     module_type=audio.MicModule,
#     data=akari.AkariData(),
#     params=audio.MicModuleParams(
#         streamDurationMilliseconds=1000,
#         destructionMilliseconds=5000,
#         callbackParams=webrtcvad.WebRTCVadParams(),
#         callback_callback=modules.PrintModule,
#     ),
#     streaming=False,
#     callback=webrtcvad.WebRTCVadModule,
# )

### 対話
# akariRouter.callModule(
#     moduleType=audio.MicModule,
#     data=akari.AkariData(),
#     params=audio.MicModuleParams(
#         streamDurationMilliseconds=100,
#         destructionMilliseconds=5000,
#         # input_device_index=3,
#         callbackParams=modules.SerialModuleParams(
#             modules=[
#                 modules.SerialModuleParamModule(
#                     moduleType=google.STTModule,
#                     moduleParams=google.STTModuleParams(
#                         model="default",
#                         language="ja-JP",
#                         prompt="",
#                         temperature=0.7,
#                     ),
#                 ),
#                 modules.SerialModuleParamModule(
#                     moduleType=azure_openai.LLMModule,
#                     moduleParams=azure_openai.LLMModuleParams(
#                         model="gpt-4o-mini",
#                         messages_function=lambda data: [
#                             {
#                                 "role": "user",
#                                 "content": (
#                                     data.last().text.main  # type: ignore
#                                     if data.last() and data.last().text
#                                     else "Hello, Akari!"
#                                 ),
#                             },
#                             {"role": "system", "content": "You are a helpful assistant."},
#                         ],
#                         temperature=0.7,
#                     ),
#                 ),
#                 modules.SerialModuleParamModule(
#                     moduleType=azure_openai.TTSModule,
#                     moduleParams=azure_openai.TTSModuleParams(
#                         model="gpt-4o-mini-tts",
#                         voice="alloy",
#                         instructions="日本語で元気溌剌に話してください",
#                         speed=1.0,
#                     ),
#                 ),
#                 modules.SerialModuleParamModule(
#                     moduleType=audio.SpeakerModule,
#                     moduleParams=audio.SpeakerModuleParams(
#                         # output_device_index=1,
#                     ),
#                 ),
#             ]
#         ),
#         callback_callback=modules.SerialModule,
#     ),
#     streaming=False,
#     callback=modules.SerialModule,
# )

# akariRouter.callModule(
#     moduleType=audio.MicModule,
#     data=akari.AkariData(),
#     params=audio.MicModuleParams(
#         streamDurationMilliseconds=100,
#         destructionMilliseconds=5000,
#         callbackParams=performance.VADSTTLatencyMeterConfig(
#             stt_module=google.GoogleSpeechToTextStreamModule,
#             stt_module_params=google.GoogleSpeechToTextStreamParams(),
#             vad_module=webrtcvad.WebRTCVadModule,
#             vad_module_params=webrtcvad.WebRTCVadParams(),
#             callback_params=modules.SerialModuleParams(
#                 modules=[
#                     modules.SerialModuleParamModule(
#                         moduleType=modules.PrintModule,
#                         moduleParams=None,
#                     ),
#                     # modules.SerialModuleParamModule(
#                     #     moduleType=azure_openai.LLMModule,
#                     #     moduleParams=azure_openai.LLMModuleParams(
#                     #         model="gpt-4o-mini",
#                     #         messages_function=lambda data: [
#                     #             {
#                     #                 "role": "user",
#                     #                 "content": (
#                     #                     data.last().text.main  # type: ignore
#                     #                     if data.last() and data.last().text
#                     #                     else "Hello, Akari!"
#                     #                 ),
#                     #             },
#                     #             {"role": "system", "content": "You are a helpful assistant."},
#                     #         ],
#                     #         temperature=0.7,
#                     #     ),
#                     # ),
#                     # modules.SerialModuleParamModule(
#                     #     moduleType=azure_openai.TTSModule,
#                     #     moduleParams=azure_openai.TTSModuleParams(
#                     #         model="gpt-4o-mini-tts",
#                     #         voice="alloy",
#                     #         instructions="日本語で元気溌剌に話してください",
#                     #         speed=1.0,
#                     #     ),
#                     # ),
#                     # modules.SerialModuleParamModule(
#                     #     moduleType=audio.SpeakerModule,
#                     #     moduleParams=audio.SpeakerModuleParams(
#                     #         # output_device_index=1,
#                     #     ),
#                     # ),
#                 ]
#             ),
#         ),
#         callback_callback=modules.SerialModule,
#     ),
#     streaming=False,
#     callback=performance.VADSTTLatencyMeter,
# )

data = akari.AkariData()
dataset = akari.AkariDataSet()
dataset.text = akari.AkariDataSetType(main="Hello, Akari!")
data.add(dataset)
akari_router.call_module(
    module_type=modules.SerialModule,
    data=data,
    params=modules.SerialModuleParams(
        modules=[
            modules.SerialModuleParamModule(module_type=modules.PrintModule, moduleParams=None),
            modules.SerialModuleParamModule(
                module_type=google.GoogleTextToSpeechModule,
                moduleParams=google.GoogleTextToSpeechParams(
                    voice_name="ja-JP-Chirp3-HD-Kore",
                    callback_params=audio.SpeakerModuleParams(
                        # output_device_index=6,
                    ),
                ),
                module_callback=audio.SpeakerModule,
            ),
        ],
    ),
    streaming=False,
)

# akari_router.call_module(
#     module_type=modules.SerialModule,
#     data=data,
#     params=modules.SerialModuleParams(
#         modules=[
#             modules.SerialModuleParamModule(module_type=modules.PrintModule, moduleParams=None),
#             modules.SerialModuleParamModule(
#                 module_type=azure_openai.TTSModule,
#                 moduleParams=azure_openai.TTSModuleParams(
#                     model="gpt-4o-mini-tts",
#                     voice="alloy",
#                     instructions="日本語で元気溌剌に話してください",
#                     speed=1.0,
#                 ),
#             ),
#             modules.SerialModuleParamModule(module_type=audio.SpeakerModule, moduleParams=audio.SpeakerModuleParams()),
#         ]
#     ),
#     streaming=False,
# )
