import dataclasses
import io

from openai import AzureOpenAI

from akari import AkariData, AkariDataSet, AkariDataSetType, AkariModule, MainRouter


@dataclasses.dataclass
class STTModuleParams:
    model: str
    language: str | None
    prompt: str | None
    temperature: float


class STTModule(AkariModule):
    def __init__(self, router: MainRouter, client: AzureOpenAI) -> None:
        super().__init__(router)
        self.client = client

    def call(self, data: AkariData, params: STTModuleParams) -> AkariDataSet:
        print("STTModule called")
        print("Data:", data)
        print("Params:", params)

        audio = data.last().audio
        if audio is None:
            raise ValueError("Audio data is missing or empty.")
        buffer = io.BytesIO(audio.main)
        buffer.name = "input.mp3"

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
