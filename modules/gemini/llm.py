import dataclasses
from typing import Iterable

from vertexai.generative_models import Content, GenerativeModel

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
    AkariModule,
    AkariModuleType,
    MainRouter,
)

_models: dict[str, GenerativeModel] = {}


@dataclasses.dataclass
class _LLMModuleParams:
    model: str
    messages: Iterable[Content]


class _LLMModule(AkariModule):
    def __init__(self, router: MainRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)

    def call(self, data: AkariData, params: _LLMModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        self._logger.debug("LLMModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)
        self._logger.debug("Callback: %s", callback)

        if params.model not in _models:
            _models[params.model] = GenerativeModel(params.model)

        model = _models[params.model]
        response = model.generate_content(params.messages)

        dataset = AkariDataSet()
        dataset.text = AkariDataSetType(main=response.text)
        dataset.allData = response
        return dataset
