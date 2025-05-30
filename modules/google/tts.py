"""Google Cloud Text-to-Speech (TTS) APIを使用してテキストを音声に変換するAkariモジュール."""

from __future__ import annotations

import dataclasses

# ERA001: Removed commented out imports for copy and typing
from google.cloud import texttospeech

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    # ERA001: AkariDataStreamType removed
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
    def call( # C901 - Will add noqa if still present after other fixes
        self,
        data: AkariData,
        params: _GoogleTextToSpeechParams,
        # callback: AkariModuleType | None = None, # ARG002 was here, removing callback
    ) -> AkariDataSet:
        """Send text to the Google Cloud TTS API and receive the synthesized audio data."""
        input_text = ""
        text_dataset = data.last().text
        if text_dataset and text_dataset.main:
            input_text = text_dataset.main

        if not input_text:
            # EM101, TRY003
            msg = "Input data is missing or empty."
            raise ValueError(msg)

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
            result_dataset = AkariDataSet()
            result_dataset.audio = AkariDataSetType(main=response.audio_content)
        except Exception as e:
            # BLE001, TRY400, G004, EM101, TRY003, EM102, F841 - Kept comments for context
            self._logger.exception("Error during Google TTS streaming synthesis: %s", e)  # TRY401 fixed (e is fine)
            # EM102, TRY003
            error_text = f"Error during Google TTS streaming synthesis: {e!s}"
            result_dataset = AkariDataSet() # Ensure dataset is initialized in except block too
            result_dataset.text = AkariDataSetType(main=error_text)
            return result_dataset # Return early on exception
        return result_dataset # TRY300: Moved return here

    def stream_call( # ARG002 for data, params, callback
        self,
        _data: AkariData, # Prefix with _ if unused
        _params: _GoogleTextToSpeechParams, # Prefix with _ if unused
        _callback: AkariModuleType | None = None, # Prefix with _ if unused
    ) -> AkariDataSet:
        # EM101, TRY003
        msg = "GoogleTextToSpeechModule does not support streaming."
        self._logger.warning(msg)
        raise NotImplementedError(msg)

    def close(self) -> None:
        self._logger.info(
            "GoogleTextToSpeechModule close called. Client cleanup is typically automatic for google-cloud-texttospeech." # noqa: E501
        )
