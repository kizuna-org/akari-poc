"""Azure OpenAI Text-to-Speech (TTS) APIを使用してテキストを音声に変換するAkariモジュール."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from akari_core.logger import AkariLogger
    from openai import AzureOpenAI

from akari_core.module import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)

# from typing_extensions import Literal # ERA001 - removed commented-out code


@dataclasses.dataclass
class _TTSModuleParams(AkariModuleParams):
    """Azure OpenAI TTSモジュール用のパラメータ."""

    model: str
    voice: str
    instructions: str | None
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "pcm"
    speed: float = 1.0
    callback_params: AkariModuleParams | None = None
    """コールバックモジュール用のパラメータ."""


class _TTSModule(AkariModule):
    """Azure OpenAI Text-to-Speech (TTS) APIを使用してテキストを音声に変換するAkariモジュール."""

    def __init__(self, router: AkariRouter, logger: AkariLogger, client: AzureOpenAI) -> None:
        """Initialize the Azure OpenAI TTS module.

        Args:
            router: Akari router instance.
            logger: Akari logger instance.
            client: Initialized AzureOpenAI client instance.
        """
        super().__init__(router, logger)
        self.client = client

    def call(
        self,
        data: AkariData,
        params: _TTSModuleParams,
    ) -> AkariDataSet:
        """Send text to the Azure OpenAI TTS API and receive the synthesized audio data."""
        input_data = data.last().text
        if input_data is None:
            error_msg = "Input data is missing or empty."
            raise ValueError(error_msg)

        try:
            response = self.client.audio.speech.create(
                model=params.model,
                voice=params.voice,
                response_format=params.response_format,
                input=input_data.main,
                speed=params.speed,
            )

            result_dataset = AkariDataSet()
            result_dataset.audio = AkariDataSetType(main=response.content)
            result_dataset.bool = AkariDataSetType(main=True)
            self._logger.debug("TTS synthesis successful")

            return result_dataset

        except Exception as e:
            self._logger.exception("Error during TTS synthesis: %s", e)
            error_msg = f"Error during TTS synthesis: {e!s}"
            return AkariDataSet(text=AkariDataSetType(main=error_msg))

    def stream_call(
        self,
        _data: AkariData,
        _params: _TTSModuleParams,
        _callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """stream_call is not implemented for now."""
        not_implemented_msg = "stream_call is not implemented for Azure OpenAI TTS for now"
        raise NotImplementedError(not_implemented_msg)

    def close(self) -> None:
        """Perform cleanup operations if necessary."""
        self._logger.info("AzureOpenAI TTS module closed.")
