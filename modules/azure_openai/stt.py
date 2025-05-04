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
    model: str
    language: str | None
    prompt: str | None
    temperature: float
    channels: int = 1
    sample_width: int = 2
    rate: int = 24000


class _STTModule(AkariModule):
    def __init__(self, router: AkariRouter, logger: AkariLogger, client: AzureOpenAI) -> None:
        super().__init__(router, logger)
        self.client = client

    def call(self, data: AkariData, params: _STTModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
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
