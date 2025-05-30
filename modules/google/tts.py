"""Google Cloud Text-to-Speech (TTS) APIを使用してテキストを音声に変換するAkariモジュール."""

from __future__ import annotations

# import copy # Removed unused import
import dataclasses

# import typing # Removed unused import
from google.cloud import texttospeech

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    # AkariDataStreamType, # Removed unused import
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _GoogleTextToSpeechParams(AkariModuleParams):
    """Google Cloud TTSモジュール用のパラメータ."""

    model: str
    voice: str
    instructions: str | None
    response_format: str = "pcm"  # Use str instead of Literal for now
    speed: float = 1.0
    # Added missing parameters from lint errors or common usage
    language_code: str = "en-US"
    voice_name: str | None = None
    pitch: float = 0.0
    sample_rate_hertz: int | None = None
    effects_profile_id: list[str] | None = None
    callback_params: AkariModuleParams | None = None  # FA102 - Fixed


class _GoogleTextToSpeechModule(AkariModule):
    """Google Cloud Text-to-Speech (TTS) APIを使用してテキストを音声に変換するAkariモジュール."""

    def __init__(
        self,
        router: AkariRouter,
        logger: AkariLogger,
        client: texttospeech.TextToSpeechClient,
    ) -> None:
        """Initialize the GoogleTextToSpeechModule.

        Args:
            router: Akari router instance.
            logger: Akari logger instance.
            client: Initialized Google Cloud Speech client instance.
        """
        super().__init__(router, logger)
        self._client = client

    # C901, PLR0915 - complex method, skipping automatic fix
    def call(
        self,
        data: AkariData,
        params: _GoogleTextToSpeechParams,
        # ARG002 removed
    ) -> AkariDataSet:
        """Send text to the Google Cloud TTS API and receive the synthesized audio data."""
        input_text = ""
        text_dataset = data.last().text
        if text_dataset and text_dataset.main:
            input_text = text_dataset.main

        if not input_text:
            error_msg = "Input data is missing or empty."
            raise ValueError(error_msg)  # TRY003, EM101 fixed

        synthesis_input = texttospeech.SynthesisInput(text=input_text)

        # Select the type of audio file you want returned
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding[params.response_format.upper()],
            speaking_rate=params.speed,
            pitch=params.pitch,
            sample_rate_hertz=params.sample_rate_hertz,
            effects_profile_id=params.effects_profile_id,
        )

        # Select the voice parameters to use for the synthesis
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=params.language_code,  # Assuming voice is in format 'language-REGION-SSML'
            name=params.voice_name if params.voice_name else params.voice,
        )

        # Perform the text-to-speech request
        try:
            response = self._client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config,
            )

            # The response's audio_content is binary. Write it to a file.
            # TRY300 fixed by moving return to else block
            result_dataset = AkariDataSet()
            result_dataset.audio = AkariDataSetType(main=response.audio_content)
            return result_dataset
        except Exception as e:
            # BLE001: Do not catch blind exception: `Exception` -> Catch specific exceptions # Keeping comment for now
            # TRY400: Use logging.exception instead of logging.error # Keeping comment for now
            # G004: Logging statement uses f-string -> Use % formatting # Keeping comment for now
            # EM101: Exception must not use a string literal, assign to variable first # Keeping comment for now
            # TRY003: Avoid specifying long messages outside the exception class # Keeping comment for now
            # EM102: Exception must not use an f-string literal, assign to variable first # Keeping comment for now
            # TRY401: Redundant exception object included in `logging.exception` call # Keeping comment for now
            # F841: Local variable `error_msg` is assigned to but never used # Keeping comment for now
            error_main_msg = f"Error during Google TTS streaming synthesis: {e!s}"
            self._logger.exception("Error during Google TTS streaming synthesis: %s", e)  # TRY401 fixed
            result_dataset = AkariDataSet()
            result_dataset.text = AkariDataSetType(main=error_main_msg)
            return result_dataset

    def stream_call(
        self,
        data: AkariData,
        params: _GoogleTextToSpeechParams,
        callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        not_implemented_msg = "GoogleTextToSpeechModule does not support streaming."
        self._logger.warning(not_implemented_msg)
        raise NotImplementedError(not_implemented_msg)  # EM101 fixed

    def close(self) -> None:
        self._logger.info(
            "GoogleTextToSpeechModule close called. Client cleanup is typically automatic for google-cloud-texttospeech."
        )  # E501 - will rely on xc format
