"""Azure OpenAI STT module."""

from __future__ import annotations

import dataclasses
import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from akari_core.logger import AkariLogger
    from openai import AzureOpenAI
    from openai.types.audio import Transcription

from akari_core.module import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariModule,
    AkariModuleParams,
    AkariRouter,
)


@dataclasses.dataclass
class _STTModuleParams(AkariModuleParams):
    """Azure OpenAI STTモジュール用のパラメータ."""

    model: str
    language: str | None
    prompt: str | None
    temperature: float
    channels: int = 1
    rate: int = 16000
    callback_params: AkariModuleParams | None = None
    """文字起こし結果を渡すコールバックモジュール用のパラメータ. デフォルトはNone."""
    end_stream_flag: bool = False
    """このフラグがTrueの場合、STTストリームを終了する. デフォルトはFalse."""
    callback_when_final: bool = True
    """最終結果をコールバックするかどうか. デフォルトはTrue.(Falseで常にコールバックする)"""


class _STTModule(AkariModule):
    """Azure OpenAI Speech-to-Text APIを使用して音声を文字起こしするAkariモジュール."""

    def __init__(self, router: AkariRouter, logger: AkariLogger, client: AzureOpenAI) -> None:
        """Initialize the GoogleSpeechToTextStreamModule.

        Args:
            router: Akari router instance.
            logger: Akari logger instance.
            client: Initialized Google Cloud Speech client instance.
        """
        super().__init__(router, logger)
        self.client = client

    def call(
        self,
        data: AkariData,
        params: _STTModuleParams,
    ) -> AkariDataSet:
        """Convert spoken audio into text using the configured Azure OpenAI STT model.

        The method expects audio data to be present in `data.last().audio.main`.
        This data is then wrapped into a WAV audio format in an in-memory buffer.
        This WAV data is subsequently sent to the Azure OpenAI audio transcriptions API.
        The transcription result (as plain text) is then stored in a new
        `AkariDataSet`.

        Args:
            data (AkariData): The `AkariData` object containing the input audio.
                The audio bytes are expected in `data.last().audio.main`.
            params (_STTModuleParams): Configuration parameters for the transcription,
                such as the STT model name, language, prompt, temperature, and
                audio properties (channels, sample width, rate).

        Returns:
            AkariDataSet: An `AkariDataSet` where:
                - `text.main` contains the transcribed text as a string.
                - `allData` holds the raw response object from the Azure OpenAI API.

        Raises:
            ValueError: If `data.last().audio` is None or does not contain
                audio data.
            OpenAIError: If the Azure OpenAI API call fails for any reason
                (e.g., authentication, network issues, invalid parameters).
        """
        audio = data.last().audio
        if audio is None:
            error_msg = "Audio data is missing or empty."
            raise ValueError(error_msg)

        pcm_buffer = io.BytesIO(audio.main)

        try:
            transcript: Transcription = self.client.audio.transcriptions.create(
                model=params.model,
                file=pcm_buffer,
                language=params.language,
                prompt=params.prompt,
                temperature=params.temperature,
            )

            result_dataset = AkariDataSet()
            result_dataset.text = AkariDataSetType(main=transcript.text)
            result_dataset.bool = AkariDataSetType(main=True)
            # Add more metadata if available and relevant
            # For now, just include the basic text result.
            self._logger.debug("STT transcription successful: %s", transcript.text)
            # TRY300: No direct else block needed if we return directly after success.
            # If an exception occurs, it jumps to except.
        except Exception as e:
            self._logger.exception("Error during STT transcription: %s", e) # TRY401 - e is fine here
            # EM102, TRY003
            error_text = f"Error during STT transcription: {e!s}"
            return AkariDataSet(text=AkariDataSetType(main=error_text))
        return result_dataset # Moved return here for TRY300

    # stream_call is not implemented for Azure OpenAI STT for now
    # async_call is not implemented for Azure OpenAI STT for now

    def close(self) -> None:
        """Perform cleanup operations if necessary."""
        self._logger.info("AzureOpenAI STT module closed.")
