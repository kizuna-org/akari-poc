"""Gemini LLM module."""

from __future__ import annotations

import dataclasses
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from akari_core.logger import AkariLogger
    from akari_core.module import AkariDataStreamType

from akari_core.module import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)
from google.generativeai import GenerativeModel
from google.generativeai.types import Content

_models = {
    "gemini-pro": "gemini-pro",
    "gemini-1.5-flash-latest": "gemini-1.5-flash-latest",
    # Add other models here as needed
}


@dataclasses.dataclass
class _GeminiLLMParams(AkariModuleParams):
    """Parameters for the Gemini LLM module."""

    model: str = "gemini-1.5-flash-latest"
    """The model name to use (e.g., 'gemini-1.5-flash-latest')."""
    system_instruction: str | None = None
    """System instruction for the model."""
    safety_settings: list[SafetySetting] | None = None
    """Safety settings for the model."""
    generation_config: GenerationConfig | None = None
    """Generation configuration for the model."""
    tools: list[Tool] | None = None
    """Tools to provide to the model."""
    messages_function: AkariModuleType | None = None
    """A function to generate messages from AkariData."""
    messages: list[Content] | None = None
    """Pre-generated messages to send to the model."""


_model_instances: dict[str, GenerativeModel] = {}


class _GeminiLLMModule(AkariModule):
    """Module for interacting with the Gemini LLM."""

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """Construct a _GeminiLLMModule instance."""
        super().__init__(router, logger)

    def call(
        self,
        data: AkariData,
        params: _GeminiLLMParams,
        _callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """Generate text using the Gemini LLM."""
        self._logger.debug("LLMModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        if params.messages_function:
            message_data = self._router.callModule(params.messages_function, data, None, streaming=False, callback=None)
            messages = message_data.last().allData
        else:
            messages = params.messages
        if messages is None:
            error_msg = "Messages cannot be None. Please provide a valid list of messages."
            raise ValueError(error_msg)
        if params.model not in _models:
            error_msg = f"Unsupported model: {params.model}. Available models: {list(_models.keys())}."
            raise ValueError(error_msg)
        model_name = _models[params.model]
        if model_name not in _model_instances:
            self._logger.info("Loading model: %s", model_name)
            # Assuming vertexai is already initialized elsewhere in the application
            _model_instances[model_name] = GenerativeModel(
                model_name,
                system_instruction=(
                    Content(role="system", parts=[params.system_instruction]) if params.system_instruction else None
                ),
                safety_settings=params.safety_settings,
                generation_config=params.generation_config,
                tools=params.tools,
            )
            self._logger.info("Model loaded: %s", model_name)
        model = _model_instances[model_name]

        try:
            response = model.generate_content(
                messages,
                generation_config=params.generation_config,
                safety_settings=params.safety_settings,
                tools=params.tools,
            )
            self._logger.debug("Received response from model")

            try:
                text_response = response.text
            except ValueError:
                self._logger.warning("Model response is not text.")
                text_response = ""

            result_dataset = AkariDataSet(
                text=AkariDataSetType(main=text_response),
                allData=response,
            )
            self._logger.debug("LLMModule call finished successfully")
            return result_dataset
        except Exception as e:
            self._logger.exception("Error during LLM generation: %s", e)
            error_dataset = AkariDataSet(text=AkariDataSetType(main=f"Error during LLM generation: {e!s}"))
            return error_dataset

    def stream_call(
        self,
        data: AkariData,
        params: _GeminiLLMParams,
        _callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """Stream text generation from the Gemini LLM."""
        self._logger.debug("LLMModule stream_call called")

        if params.messages_function:
            message_data = self._router.callModule(params.messages_function, data, None, streaming=False, callback=None)
            messages = message_data.last().allData
        else:
            messages = params.messages
        if messages is None:
            error_msg = "Messages cannot be None. Please provide a valid list of messages."
            raise ValueError(error_msg)
        if params.model not in _models:
            error_msg = f"Unsupported model: {params.model}. Available models: {list(_models.keys())}."
            raise ValueError(error_msg)
        model_name = _models[params.model]
        if model_name not in _model_instances:
            self._logger.info("Loading model for streaming: %s", model_name)
            # Assuming vertexai is already initialized elsewhere in the application
            _model_instances[model_name] = GenerativeModel(
                model_name,
                system_instruction=(
                    Content(role="system", parts=[params.system_instruction]) if params.system_instruction else None
                ),
                safety_settings=params.safety_settings,
                generation_config=params.generation_config,
                tools=params.tools,
            )
            self._logger.info("Model loaded for streaming: %s", model_name)
        model = _model_instances[model_name]
        result_dataset = AkariDataSet(
            text=AkariDataSetType(main="", stream=AkariDataStreamType(delta=[])),
            allData=None,
        )

        def stream_generation_thread(model, messages, params, result_dataset):
            try:
                stream = model.generate_content(
                    messages,
                    generation_config=params.generation_config,
                    safety_settings=params.safety_settings,
                    tools=params.tools,
                    stream=True,
                )
                self._logger.debug("Started streaming generation")

                full_response = []
                for chunk in stream:
                    self._logger.debug("Received chunk: %s", chunk)
                    if hasattr(chunk, "text"):
                        text_chunk = chunk.text
                        if text_chunk:
                            result_dataset.text.stream.add(text_chunk)
                            full_response.append(text_chunk)
                result_dataset.allData = (stream._result) if hasattr(stream, "_result") else None
                result_dataset.bool = AkariDataSetType(main=True)
                self._logger.debug("Streaming generation finished")

            except Exception as e:
                self._logger.exception("Error during LLM streaming generation: %s", e)
                result_dataset.text.stream.add(f"Error during LLM streaming generation: {e!s}")
                result_dataset.bool = AkariDataSetType(main=False)

        thread = threading.Thread(
            target=stream_generation_thread,
            args=(model, messages, params, result_dataset),
        )
        thread.daemon = True
        thread.start()
        return result_dataset
