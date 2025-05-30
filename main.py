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
            f"Device {i}: {info['name']} (Input: {info['maxInputChannels']}, Output: {info['maxOutputChannels']})",  # noqa: G004
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
)  # type: ignore # noqa: PGH003
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
#     module_type=modules.RootModule, # noqa: ERA001
#     data=akari.AkariData(), # noqa: ERA001
#     params=sample.SampleModule, # noqa: ERA001
#     streaming=False, # noqa: ERA001
# )

# akari_router.call_module(
#     module_type=azure_openai.LLMModule, # noqa: ERA001
#     data=akari.AkariData(), # noqa: ERA001
#     params=azure_openai.LLMModuleParams(
#         model="gpt-4o-mini", # noqa: ERA001
#         messages=[
#             {"role": "user", "content": "Hello, Akari!"}, # noqa: ERA001
#             {"role": "system", "content": "You are a helpful assistant."}, # noqa: ERA001
#         ],
#         temperature=0.7, # noqa: ERA001
#         max_tokens=150, # noqa: ERA001
#         top_p=1.0, # noqa: ERA001
#         frequency_penalty=0.0, # noqa: ERA001
#         presence_penalty=0.0, # noqa: ERA001
#         stream=True, # noqa: ERA001
#     ),
#     streaming=False, # noqa: ERA001
#     callback=modules.PrintModule, # noqa: ERA001
# )


# data = akari_router.call_module(
#     module_type=gemini.LLMModule, # noqa: ERA001
#     data=akari.AkariData(), # noqa: ERA001
#     params=gemini.LLMModuleParams(
#         model="gemini-2.0-flash", # noqa: ERA001
#         messages=[
#             Content(role="user", parts=[Part.from_text("Hello, Akari!")]), # noqa: ERA001
#         ],
#     ),
#     streaming=False, # noqa: ERA001
# )


# data = akari.AkariData() # noqa: ERA001
# dataset = akari.AkariDataSet() # noqa: ERA001
# with open("input.wav", "rb") as audio_file:
#     dataset.audio = akari.AkariDataSetType(main=audio_file.read()) # noqa: ERA001
# data.add(dataset) # noqa: ERA001
# akari_router.call_module(
#     module_type=azure_openai.STTModule, # noqa: ERA001
#     data=data, # noqa: ERA001
#     params=azure_openai.STTModuleParams(
#         model="whisper", # noqa: ERA001
#         language="ja", # noqa: ERA001
#         prompt="", # noqa: ERA001
#         temperature=0.7, # noqa: ERA001
#     ),
# )

# data = akari_router.call_module(
#     module_type=azure_openai.TTSModule, # noqa: ERA001
#     data=akari.AkariData(), # noqa: ERA001
#     params=azure_openai.TTSModuleParams(
#         model="gpt-4o-mini-tts", # noqa: ERA001
#         input="あかりだよ、よろしくね!", # noqa: ERA001 fixed
#         voice="alloy", # noqa: ERA001
#         instructions="日本語で元気溌剌に話してください", # noqa: ERA001
#         response_format="wav", # noqa: ERA001
#         speed=1.0, # noqa: ERA001
#     ),
#     streaming=False, # noqa: ERA001
# )

# with open("output.wav", "wb") as audio_file:
#     audio_file.write(data.last().audio.main)  # type: ignore # noqa: ERA001,PGH003


# data = akari.AkariData() # noqa: ERA001
# dataset = akari.AkariDataSet() # noqa: ERA001
# with open("input.wav", "rb") as audio_file:
#     dataset.audio = akari.AkariDataSetType(main=audio_file.read()) # noqa: ERA001
# data.add(dataset) # noqa: ERA001
# akari_router.call_module(
#     module_type=audio.SpeakerModule, # noqa: ERA001
#     data=data, # noqa: ERA001
#     params=audio.SpeakerModuleParams(), # noqa: ERA001
#     streaming=False, # noqa: ERA001
# )


# akari_router.call_module(
#     module_type=audio.MicModule, # noqa: ERA001
#     data=akari.AkariData(), # noqa: ERA001
#     params=audio.MicModuleParams(
#         streamDurationMilliseconds=1000, # noqa: ERA001
#         destructionMilliseconds=5000, # noqa: ERA001
#         callbackParams=webrtcvad.WebRTCVadParams(), # noqa: ERA001
#         callback_callback=modules.PrintModule, # noqa: ERA001
#     ),
#     streaming=False, # noqa: ERA001
#     callback=webrtcvad.WebRTCVadModule, # noqa: ERA001
# )

### 対話 # noqa: ERA001
# akari_router.call_module(
#     module_type=audio.MicModule, # noqa: ERA001
#     data=akari.AkariData(), # noqa: ERA001
#     params=audio.MicModuleParams(
#         streamDurationMilliseconds=100, # noqa: ERA001
#         destructionMilliseconds=5000, # noqa: ERA001
#         # input_device_index=3, # noqa: ERA001
#         callbackParams=modules.SerialModuleParams(
#             modules=[
#                 modules.SerialModuleParamModule(
#                     module_type=google.STTModule, # noqa: ERA001
#                     moduleParams=google.STTModuleParams(
#                         model="default", # noqa: ERA001
#                         language="ja-JP", # noqa: ERA001
#                         prompt="", # noqa: ERA001
#                         temperature=0.7, # noqa: ERA001
#                     ),
#                 ),
#                 modules.SerialModuleParamModule(
#                     module_type=azure_openai.LLMModule, # noqa: ERA001
#                     moduleParams=azure_openai.LLMModuleParams(
#                         model="gpt-4o-mini", # noqa: ERA001
#                         messages_function=lambda data: [
#                             {
#                                 "role": "user", # noqa: ERA001
#                                 "content": (
#                                     data.last().text.main  # type: ignore # noqa: ERA001,PGH003
#                                     if data.last() and data.last().text
#                                     else "Hello, Akari!"
#                                 ),
#                             },
#                             {"role": "system", "content": "You are a helpful assistant."}, # noqa: ERA001
#                         ],
#                         temperature=0.7, # noqa: ERA001
#                     ),
#                 ),
#                 modules.SerialModuleParamModule(
#                     module_type=azure_openai.TTSModule, # noqa: ERA001
#                     moduleParams=azure_openai.TTSModuleParams(
#                         model="gpt-4o-mini-tts", # noqa: ERA001
#                         voice="alloy", # noqa: ERA001
#                         instructions="日本語で元気溌剌に話してください", # noqa: ERA001
#                         speed=1.0, # noqa: ERA001
#                     ),
#                 ),
#                 modules.SerialModuleParamModule(
#                     module_type=audio.SpeakerModule, # noqa: ERA001
#                     moduleParams=audio.SpeakerModuleParams(
#                         # output_device_index=1, # noqa: ERA001
#                     ),
#                 ),
#             ]
#         ),
#         callback_callback=modules.SerialModule, # noqa: ERA001
#     ),
#     streaming=False, # noqa: ERA001
#     callback=modules.SerialModule, # noqa: ERA001
# )

# akari_router.call_module(
#     module_type=audio.MicModule, # noqa: ERA001
#     data=akari.AkariData(), # noqa: ERA001
#     params=audio.MicModuleParams(
#         streamDurationMilliseconds=100, # noqa: ERA001
#         destructionMilliseconds=5000, # noqa: ERA001
#         callbackParams=performance.VADSTTLatencyMeterConfig(
#             stt_module=google.GoogleSpeechToTextStreamModule, # noqa: ERA001
#             stt_module_params=google.GoogleSpeechToTextStreamParams(), # noqa: ERA001
#             vad_module=webrtcvad.WebRTCVadModule, # noqa: ERA001
#             vad_module_params=webrtcvad.WebRTCVadParams(), # noqa: ERA001
#             callback_params=modules.SerialModuleParams(
#                 modules=[
#                     modules.SerialModuleParamModule(
#                         module_type=modules.PrintModule, # noqa: ERA001
#                         moduleParams=None, # noqa: ERA001
#                     ),
#                     # modules.SerialModuleParamModule(
#                     #     module_type=azure_openai.LLMModule, # noqa: ERA001
#                     #     moduleParams=azure_openai.LLMModuleParams(
#                     #         model="gpt-4o-mini", # noqa: ERA001
#                     #         messages_function=lambda data: [
#                     #             {
#                     #                 "role": "user", # noqa: ERA001
#                     #                 "content": (
#                     #                     data.last().text.main  # type: ignore # noqa: ERA001,PGH003
#                     #                     if data.last() and data.last().text
#                     #                     else "Hello, Akari!"
#                     #                 ),
#                     #             },
#                     #             {"role": "system", "content": "You are a helpful assistant."}, # noqa: ERA001
#                     #         ],
#                     #         temperature=0.7, # noqa: ERA001
#                     #     ),
#                     # ),
#                     # modules.SerialModuleParamModule(
#                     #     module_type=azure_openai.TTSModule, # noqa: ERA001
#                     #     moduleParams=azure_openai.TTSModuleParams(
#                     #         model="gpt-4o-mini-tts", # noqa: ERA001
#                     #         voice="alloy", # noqa: ERA001
#                     #         instructions="日本語で元気溌剌に話してください", # noqa: ERA001
#                     #         speed=1.0, # noqa: ERA001
#                     #     ),
#                     # ),
#                     # modules.SerialModuleParamModule(
#                     #     module_type=audio.SpeakerModule, # noqa: ERA001
#                     #     moduleParams=audio.SpeakerModuleParams(
#                     #         # output_device_index=1, # noqa: ERA001
#                     #     ),
#                     # ),
#                 ]
#             ),
#         ),
#         callback_callback=modules.SerialModule, # noqa: ERA001
#     ),
#     streaming=False, # noqa: ERA001
#     callback=performance.VADSTTLatencyMeter, # noqa: ERA001
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
                        # output_device_index=6, # noqa: ERA001
                    ),
                ),
                module_callback=audio.SpeakerModule,
            ),
        ],
    ),
    streaming=False,
)

# akari_router.call_module(
#     module_type=modules.SerialModule, # noqa: ERA001
#     data=data, # noqa: ERA001
#     params=modules.SerialModuleParams(
#         modules=[
#             modules.SerialModuleParamModule(module_type=modules.PrintModule, moduleParams=None), # noqa: ERA001
#             modules.SerialModuleParamModule(
#                 module_type=azure_openai.TTSModule, # noqa: ERA001
#                 moduleParams=azure_openai.TTSModuleParams(
#                     model="gpt-4o-mini-tts", # noqa: ERA001
#                     voice="alloy", # noqa: ERA001
#                     instructions="日本語で元気溌剌に話してください", # noqa: ERA001
#                     speed=1.0, # noqa: ERA001
#                 ),
#             ),
#             modules.SerialModuleParamModule(module_type=audio.SpeakerModule, moduleParams=audio.SpeakerModuleParams()), # noqa: ERA001,E501
#         ]
#     ),
#     streaming=False, # noqa: ERA001
# )
