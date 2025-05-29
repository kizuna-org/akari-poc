import copy
import dataclasses
from collections.abc import Iterable
from typing import Callable

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
        messages_function (Optional[Callable[[AkariData], Iterable[ChatCompletionMessageParam]]]):
            A callable that accepts an `AkariData` instance and returns a sequence
            of `ChatCompletionMessageParam` objects. This allows for dynamic
            construction of the conversation history based on data from previous
            pipeline steps. If provided, it takes precedence over the static `messages`
            attribute. Defaults to None.
        temperature (float): Controls the randomness of the output. Lower values
            (e.g., 0.2) make the output more deterministic and focused, while higher
            values (e.g., 0.8) make it more random and creative. Must be between
            0 and 2. Defaults to 1.0.
        max_tokens (int): The maximum number of tokens (words and punctuation)
            to generate in the chat completion. This limits the length of the
            response. Defaults to 1024.
        top_p (float): Implements nucleus sampling. The model considers only tokens
            comprising the top `top_p` probability mass. A value of 0.1 means
            only tokens from the top 10% probability distribution are considered.
            This is an alternative to temperature-based sampling. Defaults to 1.0.
        frequency_penalty (float): A value between -2.0 and 2.0. Positive values
            reduce the likelihood of the model repeating lines verbatim by penalizing
            tokens based on their existing frequency in the generated text.
            Defaults to 0.0.
        presence_penalty (float): A value between -2.0 and 2.0. Positive values
            encourage the model to introduce new topics by penalizing tokens based
            on their appearance in the text so far. Defaults to 0.0.
        stream (bool): If True, requests the API to stream back the response in
            chunks as it's generated. This requires a `callback` module to be
            configured in the `call` method to process these chunks. If False,
            the full response is received after generation is complete.
            Defaults to False.
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

    def call(self, data: AkariData, params: _LLMModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
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
              via the router in a non-blocking way (though the router call itself might be blocking).
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
            raise ValueError("Callback must be provided when streaming is enabled.")

        if params.messages_function is not None:
            params.messages = params.messages_function(data)
        if params.messages is None:
            raise ValueError("Messages cannot be None. Please provide a valid list of messages.")

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
        elif isinstance(response, ChatCompletion):
            self._logger.debug(response.choices[0].message.content)
            if response.choices[0].message.content:
                text_main = response.choices[0].message.content
        else:
            raise TypeError("Response is not of type ChatCompletion.")

        dataset.text = AkariDataSetType(main=text_main)
        dataset.allData = response
        return dataset
