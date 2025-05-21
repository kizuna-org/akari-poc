import dataclasses

from openai import AzureOpenAI
from typing_extensions import Literal

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
    AkariModule,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _TTSModuleParams:
    """Configures requests to the Azure OpenAI Text-to-Speech (TTS) API.

    Specifies the voice model, desired audio output format, speech speed, and
    any specific instructions to guide the synthesis process (e.g., emotional tone).

    Attributes:
        model (str): Identifier of the Azure OpenAI TTS model to be used for speech
            synthesis (e.g., "tts-1", "tts-1-hd").
        voice (str): The name of the pre-defined voice to use for generating the
            audio. Available voices include "alloy", "echo", "fable", "onyx",
            "nova", and "shimmer".
        instructions (Optional[str]): Textual guidance provided to the TTS model
            to influence the style, tone, or delivery of the synthesized speech.
            For example, "Speak in a calm and reassuring tone."
        response_format (Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]):
            The desired file format for the output audio. Supported formats
            include MP3, Opus (for internet streaming), AAC (for digital audio
            compression), FLAC (lossless), WAV (uncompressed), and PCM (raw
            pulse-code modulation). Defaults to "pcm".
        speed (float): Controls the speed of the synthesized speech. Values can
            range from 0.25 (quarter speed) to 4.0 (quadruple speed).
            A value of 1.0 represents normal speed. Defaults to 1.0.
    """

    model: str
    voice: str
    instructions: str | None
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "pcm"
    speed: float = 1.0


class _TTSModule(AkariModule):
    """Generates audible speech from textual input by interfacing with Azure OpenAI's Text-to-Speech (TTS) capabilities.

    This module accepts text via an `AkariDataSet` and utilizes an AzureOpenAI
    client to request speech synthesis. The resulting audio data is then packaged
    back into an `AkariDataSet`.
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger, client: AzureOpenAI) -> None:
        """Constructs an _TTSModule instance.

        Args:
            router (AkariRouter): The Akari router instance, used for base module
                initialization.
            logger (AkariLogger): The logger instance for recording operational
                details and debugging information.
            client (AzureOpenAI): An initialized instance of the `AzureOpenAI`
                client, pre-configured for accessing the text-to-speech service.
        """
        super().__init__(router, logger)
        self.client = client

    def call(self, data: AkariData, params: _TTSModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        """Sends text to the Azure OpenAI TTS API and receives the synthesized audio data.

        The input text is retrieved from `data.last().text.main`. This text is then
        sent to the Azure OpenAI `audio.speech.create` endpoint with the specified
        model, voice, and other parameters. The binary audio content from the
        response is read and stored in a new `AkariDataSet`. Default audio metadata
        (channels: 1, rate: 24000) is assumed for PCM format; for other formats,
        this metadata might need external interpretation.

        Args:
            data (AkariData): The `AkariData` object from which to retrieve the
                input text. Expected in `data.last().text.main`.
            params (_TTSModuleParams): Configuration parameters for the TTS request,
                such as model, voice, response format, and speech speed.
            callback (Optional[AkariModuleType]): An optional callback module.
                This parameter is currently not used by the TTSModule.

        Returns:
            AkariDataSet: An `AkariDataSet` where:
                - `audio.main` contains the raw bytes of the synthesized audio.
                - `meta.main` contains a dictionary with default "channels" (1) and
                  "rate" (24000), primarily relevant for PCM.
                - `allData` holds the raw response object from the Azure OpenAI API.

        Raises:
            ValueError: If `data.last().text` is None or does not contain text.
            OpenAIError: If the Azure OpenAI API call fails (e.g., authentication,
                network issues, invalid parameters).
        """
        self._logger.debug("TTSModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        input_data = data.last().text
        if input_data is None:
            raise ValueError("Input data is missing or empty.")

        response = self.client.audio.speech.create(
            model=params.model,
            input=input_data.main,
            voice=params.voice,
            instructions=params.instructions if params.instructions else "",
            response_format=params.response_format,
            speed=params.speed,
        )

        dataset = AkariDataSet()
        dataset.audio = AkariDataSetType(main=response.read())
        dataset.meta = AkariDataSetType(main={"channels": 1, "rate": 24000})
        dataset.allData = response
        return dataset
