import dataclasses
import io

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
        buffer = io.BytesIO(audio.main)
        buffer.name = "input.pcm"

        response = self.client.audio.transcriptions.create(
            model=params.model,
            file=buffer,
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
