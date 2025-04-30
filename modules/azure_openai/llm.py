import copy
import dataclasses
from typing import Iterable

from openai import AzureOpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessageParam,
)

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariDataStreamType,
    AkariLogger,
    AkariModule,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _LLMModuleParams:
    model: str
    messages: Iterable[ChatCompletionMessageParam]
    temperature: float = 1.0
    max_tokens: int = 1024
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stream: bool = False


class _LLMModule(AkariModule):
    def __init__(self, router: AkariRouter, logger: AkariLogger, client: AzureOpenAI) -> None:
        super().__init__(router, logger)
        self.client = client

    def call(self, data: AkariData, params: _LLMModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        self._logger.debug("LLMModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)
        self._logger.debug("Callback: %s", callback)

        if params.stream and callback is None:
            raise ValueError("Callback must be provided when streaming is enabled.")

        response = self.client.chat.completions.create(
            model=params.model,
            messages=params.messages,
            temperature=params.temperature,
            max_tokens=params.max_tokens,
            top_p=params.top_p,
            frequency_penalty=params.frequency_penalty,
            presence_penalty=params.presence_penalty,
            stream=params.stream,
        )

        dataset = AkariDataSet()
        text_main = ""
        if params.stream:
            texts: list[str] = []
            for chunk in response:
                if isinstance(chunk, ChatCompletionChunk) and hasattr(chunk, "choices"):
                    for choice in chunk.choices:
                        if hasattr(choice, "delta") and hasattr(choice.delta, "content"):
                            text_main += choice.delta.content if choice.delta.content else ""
                            if choice.delta.content is not None:
                                texts.append(choice.delta.content)
                            stream: AkariDataStreamType[str] = AkariDataStreamType(
                                delta=texts,
                            )
                            dataset.text = AkariDataSetType(main=text_main, stream=stream)
                            if callback is not None:
                                callData = copy.deepcopy(data)
                                callData.add(dataset)
                                self._router.callModule(
                                    moduleType=callback,
                                    data=callData,
                                    params=params,
                                    streaming=True,
                                )
                            else:
                                raise ValueError("Callback is None, but streaming is enabled.")
                        else:
                            raise TypeError("Chunk does not have 'delta' or 'content' attribute.")
                else:
                    raise TypeError("Chunk does not have 'choices' attribute or is improperly formatted.")
        else:
            if isinstance(response, ChatCompletion):
                self._logger.debug(response.choices[0].message.content)
                if response.choices[0].message.content:
                    text_main = response.choices[0].message.content
            else:
                raise TypeError("Response is not of type ChatCompletion.")

        dataset.text = AkariDataSetType(main=text_main)
        dataset.allData = response
        return dataset
