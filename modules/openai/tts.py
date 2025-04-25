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
    MainRouter,
)


@dataclasses.dataclass
class TTSModuleParams:
    model: str
    input: str
    voice: str
    instructions: str | None
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "mp3"
    speed: float = 1.0


class TTSModule(AkariModule):
    def __init__(self, router: MainRouter, logger: AkariLogger, client: AzureOpenAI) -> None:
        super().__init__(router, logger)
        self.client = client

    def call(self, data: AkariData, params: TTSModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        self._logger.debug("TTSModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        response = self.client.audio.speech.create(
            model=params.model,
            input=params.input,
            voice=params.voice,
            instructions=params.instructions if params.instructions else "",
            response_format=params.response_format,
            speed=params.speed,
        )

        dataset = AkariDataSet()
        dataset.audio = AkariDataSetType(main=response.read())
        dataset.allData = response
        return dataset
