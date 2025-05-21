import dataclasses
import io
import wave

from openai import AzureOpenAI

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
class _STTModuleParams:
    """Specifies configuration for audio transcription requests to the Azure OpenAI STT service.

    Details include the AI model to use, language hints for improved accuracy,
    contextual prompts, temperature for controlling randomness, and physical
    properties of the input audio stream.

    Attributes:
        model (str): Identifier of the Azure OpenAI STT model to be employed for
            transcription (e.g., "whisper-1").
        language (Optional[str]): The ISO-639-1 code for the language spoken in the
            audio (e.g., "en" for English, "ja" for Japanese). Providing this can
            enhance transcription accuracy and reduce latency. If `None`, the service
            may attempt to auto-detect the language.
        prompt (Optional[str]): A textual prompt that can be used to guide the
            transcription model, potentially improving accuracy for specific terms,
            names, or styles, or to provide context from a previous audio segment.
            The prompt should be in the same language as the audio.
        temperature (float): Controls the randomness of the transcription process,
            affecting word choice when alternatives exist. Values are typically
            between 0 and 1. Lower values (e.g., 0.2) yield more deterministic
            and common results, while higher values (e.g., 0.8) produce more varied
            but potentially less accurate output.
        channels (int): The number of audio channels present in the input audio
            data (e.g., 1 for mono, 2 for stereo). This information is crucial for
            correctly interpreting the raw audio bytes. Defaults to 1 (mono).
        sample_width (int): The size of each audio sample in bytes (e.g., 2 for
            16-bit audio, 1 for 8-bit audio). This, along with `channels` and `rate`,
            defines the audio format. Defaults to 2 (16-bit).
        rate (int): The sampling rate (or frame rate) of the input audio in Hertz
            (samples per second), such as 16000, 24000, or 44100. This must match
            the actual sample rate of the audio data. Defaults to 24000 Hz.
    """

    model: str
    language: str | None
    prompt: str | None
    temperature: float
    channels: int = 1
    sample_width: int = 2
    rate: int = 24000


class _STTModule(AkariModule):
    """Performs audio-to-text transcription by leveraging Azure OpenAI's speech recognition capabilities.

    Takes raw audio data (expected as PCM bytes) from an AkariDataSet,
    encapsulates it into a WAV format in-memory buffer, and then sends this
    audio to the configured Azure OpenAI STT model for transcription. The
    resulting text is then placed back into an AkariDataSet.
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger, client: AzureOpenAI) -> None:
        """Constructs an _STTModule instance.

        Args:
            router (AkariRouter): The Akari router instance, used for base module
                initialization.
            logger (AkariLogger): The logger instance for recording operational
                details and debugging information.
            client (AzureOpenAI): An initialized instance of the `AzureOpenAI`
                client, pre-configured for accessing the speech-to-text service.
        """
        super().__init__(router, logger)
        self.client = client

    def call(self, data: AkariData, params: _STTModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        """Converts spoken audio, provided as raw PCM data, into written text using the configured Azure OpenAI STT model.

        The method expects audio data to be present in `data.last().audio.main`.
        This data is then wrapped into a WAV audio format in an in-memory buffer.
        This WAV data is subsequently sent to the Azure OpenAI audio transcriptions API.
        The transcription result (as plain text) is then stored in a new
        `AkariDataSet`.

        Args:
            data (AkariData): The `AkariData` object containing the input audio.
                The audio bytes are expected in `data.last().audio.main`.
            params (_STTModuleParams): Configuration parameters for the transcription,
                such as the STT model name, language, prompt, temperature, and
                audio properties (channels, sample width, rate).
            callback (Optional[AkariModuleType]): An optional callback module. This
                parameter is currently not used by the STTModule.

        Returns:
            AkariDataSet: An `AkariDataSet` where:
                - `text.main` contains the transcribed text as a string.
                - `allData` holds the raw response object from the Azure OpenAI API.

        Raises:
            ValueError: If `data.last().audio` is None or does not contain
                audio data.
            OpenAIError: If the Azure OpenAI API call fails for any reason
                (e.g., authentication, network issues, invalid parameters).
        """
        self._logger.debug("STTModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        audio = data.last().audio
        if audio is None:
            raise ValueError("Audio data is missing or empty.")

        pcm_buffer = io.BytesIO(audio.main)
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(params.channels)
            wav_file.setsampwidth(params.sample_width)
            wav_file.setframerate(params.rate)
            wav_file.writeframes(pcm_buffer.read())

        wav_buffer.seek(0)
        wav_buffer.name = "input.wav"

        response = self.client.audio.transcriptions.create(
            model=params.model,
            file=wav_buffer,
            language=params.language if params.language else "",
            prompt=params.prompt if params.prompt else "",
            response_format="text",
            temperature=params.temperature,
        )

        text_main = str(response)

        dataset = AkariDataSet()
        dataset.text = AkariDataSetType(main=text_main)
        dataset.allData = response
        return dataset
