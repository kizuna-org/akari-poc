"""Azure OpenAI LLM module."""

from __future__ import annotations

import copy
import dataclasses
import threading
from typing import TYPE_CHECKING, Callable

# TC003: Iterable should be in type checking block
if TYPE_CHECKING:
    from collections.abc import Iterable

    from akari_core.logger import AkariLogger

    # TC002: AzureOpenAI should be inside type checking block
    from openai import AzureOpenAI

# TC004: AkariDataStreamType should be outside type checking block
from akari_core.module import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariDataStreamType,
    AkariModule,
    AkariModuleType,
    AkariRouter,
)
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessageParam,
)


@dataclasses.dataclass
class _LLMModuleParams:
    """Configures requests to the Azure OpenAI Chat Completion API.

    Specifies the target model, conversation history (either directly or via a
    function), and various parameters controlling the generation process such as
    creativity (temperature), response length (max_tokens), and streaming behavior.

    Attributes:
        model (str): Identifier of the Azure OpenAI model to be used for chat
            completion (e.g., "gpt-4o-mini", "gpt-35-turbo").
        messages (Optional[Iterable[ChatCompletionMessageParam]]): A sequence of
            message objects representing the conversation history. Each message
            should conform to the `ChatCompletionMessageParam` structure. This
            attribute is used if `messages_function` is not provided or returns None.
        messages_function: Callable[[AkariData], Iterable[ChatCompletionMessageParam]] | None = None
        temperature: float = 1.0
        max_tokens: int = 1024
        top_p: float = 1.0
        frequency_penalty: float = 0.0
        presence_penalty: float = 0.0
        stream: bool = False
    """

    model: str
    messages: Iterable[ChatCompletionMessageParam] | None = None
    messages_function: Callable[[AkariData], Iterable[ChatCompletionMessageParam]] | None = None
    temperature: float = 1.0
    max_tokens: int = 1024
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stream: bool = False


class _LLMModule(AkariModule):
    """Integrates with Azure OpenAI's chat completion service to generate text-based responses.

    Leverages an AzureOpenAI client to send chat prompts (a sequence of messages)
    to a specified language model. It supports both standard blocking requests
    for complete responses and streaming requests where response chunks are
    processed via a callback module. The module allows for dynamic construction
    of the message history based on incoming AkariData.
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger, client: AzureOpenAI) -> None:
        """Constructs an _LLMModule instance.

        Args:
            router (AkariRouter): The Akari router instance, used for invoking
                callback modules during streaming operations.
            logger (AkariLogger): The logger instance for recording operational
                details, debugging information, and API responses.
            client (AzureOpenAI): An initialized instance of the `AzureOpenAI`
                client, pre-configured with API keys and endpoint information.
        """
        super().__init__(router, logger)
        self.client = client

    def _handle_api_error(self, error_type: type[Exception], message: str) -> None:
        """Helper function to raise API-related errors.

        Args:
            error_type: The type of exception to raise (e.g., ValueError, TypeError).
            message: The error message.
        """
        raise error_type(message)

    def call(
        self,
        data: AkariData,
        params: _LLMModuleParams,
        callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """Sends a request to the Azure OpenAI Chat Completion API and processes the response.

        The method determines the conversation history either from `params.messages`
        or by invoking `params.messages_function` with the input `data`.
        It then makes a call to `client.chat.completions.create`.

        If `params.stream` is True:
            - A `callback` module must be provided.
            - The method iterates through response chunks. Each chunk containing
              content is appended to a growing `text_main` and added to a list
              of `texts`. An `AkariDataSet` with the current `text_main` and
              the stream of `texts` is created and sent to the `callback` module
              via the router in a non-blocking way (though the router call itself
              might be blocking).
        If `params.stream` is False:
            - The method waits for the full API response.
            - The content of the first choice's message is extracted as `text_main`.

        In both cases, the resulting `text_main` and the raw API response
        (or the last chunk for streaming) are stored in the returned `AkariDataSet`.

        Args:
            data (AkariData): The input `AkariData` object. This is primarily used
                if `params.messages_function` is set, to dynamically build the
                list of messages for the API call.
            params (_LLMModuleParams): An object containing all necessary parameters
                for the API call, such as model name, messages, temperature,
                and streaming preference.
            callback (Optional[AkariModuleType]): The Akari module type to be invoked
                with each response chunk if `params.stream` is True. This callback
                module receives a copy of the input `data` augmented with the
                current streaming `AkariDataSet`.

        Returns:
            AkariDataSet: An `AkariDataSet` where:
                - `text.main` contains the complete generated text.
                - `text.stream` (if streamed) contains the list of text chunks received.
                - `allData` contains the raw `ChatCompletion` object (for non-streaming)
                  or the last `ChatCompletionChunk` object (for streaming).

        Raises:
            ValueError: If `params.stream` is True but `callback` is None, or if
                `params.messages` is None and `params.messages_function` also
                results in None messages.
            TypeError: If an API response chunk in streaming mode does not conform
                to the expected structure (missing `choices`, `delta`, or `content`),
                or if the non-streaming response is not a `ChatCompletion` object.
        """
        self._logger.debug("LLMModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)
        self._logger.debug("Callback: %s", callback)

        if params.stream and callback is None:
            callback_error_msg = "Callback must be provided when streaming is enabled."
            self._handle_api_error(ValueError, callback_error_msg)

        if params.messages_function is not None:
            params.messages = params.messages_function(data)
        if params.messages is None:
            messages_error_msg = "Messages cannot be None. Please provide a valid list of messages."
            self._handle_api_error(ValueError, messages_error_msg)

        try:
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
                                    call_data = copy.deepcopy(data)
                                    call_data.add(dataset)
                                    self._router.callModule(
                                        moduleType=callback,
                                        data=call_data,
                                        params=params,
                                        streaming=True,
                                    )
                                else:
                                    callback_none_error = "Callback is None, but streaming is enabled."
                                    self._handle_api_error(ValueError, callback_none_error)
                            else:
                                delta_content_error = "Chunk does not have 'delta' or 'content' attribute."
                                self._handle_api_error(TypeError, delta_content_error)
                    else:
                        choices_error = "Chunk does not have 'choices' attribute or is improperly formatted."
                        self._handle_api_error(TypeError, choices_error)
            elif isinstance(response, ChatCompletion):
                self._logger.debug(response.choices[0].message.content)
                text_main = ""
                if response.choices[0].message.content:
                    text_main = response.choices[0].message.content
                dataset.text = AkariDataSetType(main=text_main)
                dataset.allData = response
                self._logger.debug("LLMModule call finished successfully")
                return dataset

        except Exception:
            self._logger.exception("Error during LLM generation: %s")
            error_msg = f"Error during LLM generation: {Exception!s}"
            return AkariDataSet(text=AkariDataSetType(main=error_msg))

    def stream_call(
        self,
        model: str,
        messages: list[ChatCompletionMessageParam],
        params: _LLMModuleParams,
        result_dataset: AkariDataSet,
    ) -> None:
        def stream_generation_thread(
            model: str,
            messages: list[ChatCompletionMessageParam],
            params: _LLMModuleParams,
            result_dataset: AkariDataSet,
        ) -> None:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=params.temperature,
                    max_tokens=params.max_tokens,
                    top_p=params.top_p,
                    frequency_penalty=params.frequency_penalty,
                    presence_penalty=params.presence_penalty,
                    stream=True,
                )

                full_response = []
                for chunk in response:
                    self._logger.debug("Received chunk: %s", chunk)
                    if hasattr(chunk, "text"):
                        text_chunk = chunk.text
                        if text_chunk:
                            result_dataset.text.stream.add(text_chunk)
                            full_response.append(text_chunk)
                result_dataset.allData = (response._result) if hasattr(response, "_result") else None  # noqa: SLF001
                result_dataset.bool = AkariDataSetType(main=True)
                self._logger.debug("Streaming generation finished")

            except Exception:
                self._logger.exception("Error during LLM streaming generation: %s")
                error_msg = f"Error during LLM streaming generation: {Exception!s}"
                result_dataset.text.stream.add(error_msg)
                result_dataset.bool = AkariDataSetType(main=False)

        thread = threading.Thread(
            target=stream_generation_thread,
            args=(model, messages, params, result_dataset),
        )
        thread.start()
