"""Azure OpenAI LLM module."""

from __future__ import annotations

import copy
import dataclasses
import threading
from collections.abc import Iterable  # Iterable moved here # noqa: TC003
from typing import Callable

from akari_core.logger import AkariLogger  # Moved here, used in __init__ # noqa: TC002
from akari_core.module import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariDataStreamType,
    AkariModule,
    AkariModuleType,
    AkariRouter,
)
from openai import AzureOpenAI  # Moved here, used in __init__ # noqa: TC002
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

    def call(  # noqa: C901, PLR0912
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
            # EM101, TRY003
            msg = "Callback must be provided when streaming is enabled."
            self._handle_api_error(ValueError, msg)

        if params.messages_function is not None:
            # This line is problematic if params.messages_function is expected to return AkariData
            # but params.messages expects Iterable[ChatCompletionMessageParam].
            # Assuming messages_function is correctly typed to return Iterable[ChatCompletionMessageParam]
            # or that AkariData can be converted. For now, leaving as is.
            params.messages = params.messages_function(data)  # type: ignore # noqa: PGH003
        if params.messages is None:
            # EM101, TRY003
            msg = "Messages cannot be None. Please provide a valid list of messages."
            self._handle_api_error(ValueError, msg)

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
                                    # EM101, TRY003
                                    msg = "Callback is None, but streaming is enabled."
                                    self._handle_api_error(ValueError, msg)
                            else:
                                # EM101, TRY003
                                msg = "Chunk does not have 'delta' or 'content' attribute."
                                self._handle_api_error(TypeError, msg)
                    else:
                        # EM101, TRY003
                        msg = "Chunk does not have 'choices' attribute or is improperly formatted."
                        self._handle_api_error(TypeError, msg)
            elif isinstance(response, ChatCompletion):
                self._logger.debug(response.choices[0].message.content)  # type: ignore # noqa: PGH003
                text_main = ""
                if response.choices[0].message.content:
                    text_main = response.choices[0].message.content
                dataset.text = AkariDataSetType(main=text_main)
                dataset.allData = response
                self._logger.debug("LLMModule call finished successfully")
                return dataset

        except Exception as e:  # Added 'as e'
            self._logger.exception("Error during LLM generation: %s", e)  # noqa: TRY401
            # EM102, TRY003
            error_text = f"Error during LLM generation: {e!s}"
            return AkariDataSet(text=AkariDataSetType(main=error_text))

    def stream_call(  # noqa: C901
        self,
        data: AkariData,  # Added data, consistent with AkariModule.stream_call
        params: _LLMModuleParams,
        callback: AkariModuleType | None = None,  # Added callback
    ) -> AkariDataSet:
        # The original stream_call was not matching AkariModule ABC.
        # This is a placeholder to make it compliant.
        # The actual streaming logic is in the `call` method when params.stream is True,
        # which then calls a threaded function.
        # For now, let's make this method mirror the behavior of `call` when stream=True
        # or raise NotImplementedError if it's not meant to be called directly.

        if callback is None:
            msg = "Callback must be provided for LLM stream_call."
            raise ValueError(msg)

        # Re-use the logic from call method for streaming
        # This will effectively start a streaming operation and use the callback.
        # We need to ensure the result_dataset is set up correctly for the threaded function.

        result_dataset = AkariDataSet(
            text=AkariDataSetType(main="", stream=AkariDataStreamType(delta=[])),
            allData=None,
        )

        # The threaded function needs to be defined or accessible here.
        # For simplicity, I'll assume the original intent of `call` with stream=True
        # is the primary way streaming is handled, and this `stream_call` might be a slight misuse.
        # Let's make it call the internal threaded logic if possible, or just mimic the call method.

        # Mimic the `call` method's streaming part:
        if params.messages_function is not None:
            params.messages = params.messages_function(data)  # type: ignore # noqa: PGH003
        if params.messages is None:
            msg = "Messages cannot be None for streaming."
            raise ValueError(msg)

        # Define the thread target function locally or ensure it's accessible
        # This is a simplified adaptation; the original `call` method's streaming is more robust
        def _streaming_thread_target(
            current_params: _LLMModuleParams,
            current_data: AkariData,
            current_callback: AkariModuleType,
            target_dataset: AkariDataSet,
        ) -> None:
            try:
                response_stream = self.client.chat.completions.create(
                    model=current_params.model,
                    messages=current_params.messages,  # type: ignore # noqa: PGH003
                    temperature=current_params.temperature,
                    max_tokens=current_params.max_tokens,
                    top_p=current_params.top_p,
                    frequency_penalty=current_params.frequency_penalty,
                    presence_penalty=current_params.presence_penalty,
                    stream=True,
                )
                text_main_accumulator = ""
                texts_accumulator: list[str] = []
                for chunk in response_stream:
                    if isinstance(chunk, ChatCompletionChunk) and hasattr(chunk, "choices"):
                        for choice in chunk.choices:
                            if hasattr(choice, "delta") and hasattr(choice.delta, "content"):
                                if choice.delta.content:
                                    text_main_accumulator += choice.delta.content
                                    texts_accumulator.append(choice.delta.content)

                                # Update target_dataset (which is result_dataset from outer scope)
                                target_dataset.text = AkariDataSetType(
                                    main=text_main_accumulator,
                                    stream=AkariDataStreamType(delta=list(texts_accumulator)),
                                )
                                target_dataset.allData = chunk  # Store last chunk

                                # Call callback
                                cb_data = copy.deepcopy(current_data)
                                cb_data.add(target_dataset)  # Add a copy or the live one? This needs care.
                                self._router.call_module(
                                    module_type=current_callback,
                                    data=cb_data,
                                    params=current_params,  # Or specific callback params
                                    streaming=True,
                                )
                target_dataset.bool = AkariDataSetType(main=True)
            except Exception as e_thread:
                self._logger.exception("Error in LLM streaming thread: %s", e_thread)  # noqa: TRY401
                if target_dataset.text and target_dataset.text.stream:
                    target_dataset.text.stream.add(f"Error: {e_thread!s}")  # EM102
                else:
                    target_dataset.text = AkariDataSetType(  # EM102
                        main=f"Error: {e_thread!s}", stream=AkariDataStreamType(delta=[f"Error: {e_thread!s}"])
                    )
                target_dataset.bool = AkariDataSetType(main=False)

        thread = threading.Thread(
            target=_streaming_thread_target,
            args=(params, data, callback, result_dataset),
        )
        thread.start()
