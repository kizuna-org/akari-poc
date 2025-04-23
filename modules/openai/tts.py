import dataclasses

from openai import AzureOpenAI
from typing_extensions import Literal

from akari import AkariData, AkariDataSet, AkariDataSetType, AkariModule, MainRouter


@dataclasses.dataclass
class TTSModuleParams:
    model: str
    input: str
    voice: str
    instructions: str | None
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "mp3"
    speed: float = 1.0


class TTSModule(AkariModule):
    def __init__(self, router: MainRouter, client: AzureOpenAI) -> None:
        super().__init__(router)
        self.client = client

    def call(self, data: AkariData, params: TTSModuleParams) -> AkariDataSet:
        print("TTSModule called")
        print("Data:", data)
        print("Params:", params)

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
