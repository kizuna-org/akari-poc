import dataclasses
from typing import Iterable

from openai import AzureOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam

from akari import AkariData, AkariDataSet, AkariDataSetType, AkariModule, MainRouter


@dataclasses.dataclass
class LLMModuleParams:
    messages: Iterable[ChatCompletionMessageParam]
    temperature: float = 1.0
    max_tokens: int = 1024
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stream: bool = False


class LLMModule(AkariModule):
    def __init__(self, router: MainRouter, client: AzureOpenAI) -> None:
        super().__init__(router)
        self.client = client

    def call(self, data: AkariData, params: LLMModuleParams) -> AkariDataSet:
        print("LLMModule called")
        print("Data:", data)
        print("Params:", params)

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=params.messages,
            temperature=params.temperature,
            max_tokens=params.max_tokens,
            top_p=params.top_p,
            frequency_penalty=params.frequency_penalty,
            presence_penalty=params.presence_penalty,
            stream=params.stream,
        )

        text_main = ""
        if params.stream:
            for chunk in response:
                if isinstance(chunk, ChatCompletion) and hasattr(chunk, "choices") and chunk.choices:
                    print(chunk.choices[0].delta.content, end="", flush=True)
                else:
                    raise TypeError("Chunk does not have 'choices' attribute or is improperly formatted.")
        else:
            if isinstance(response, ChatCompletion):
                print(response.choices[0].message.content)
                if response.choices[0].message.content:
                    text_main = response.choices[0].message.content
            else:
                raise TypeError("Response is not of type ChatCompletion.")

        dataset = AkariDataSet()
        dataset.text = AkariDataSetType(main=text_main)
        dataset.allData = response
        return dataset
