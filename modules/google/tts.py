import copy
import dataclasses
import typing

from google.cloud import texttospeech  # Corrected import alias

from akari import (  # Corrected base import
    AkariData,
    AkariDataSet,
    AkariDataSetType,  # Ensured import
    AkariDataStreamType,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _GoogleTextToSpeechParams:
    language_code: str = "ja-JP"
    voice_name: str = "ja-JP-Standard-A"
    speaking_rate: float = 1.0
    pitch: float = 0.0
    audio_encoding: str = "LINEAR16"
    sample_rate_hertz: int | None = 24000
    effects_profile_id: list[str] | None = None
    callback_params: AkariModuleParams | None = None


class _GoogleTextToSpeechModule(AkariModule):
    def __init__(
        self,
        router: AkariRouter,
        logger: AkariLogger,
        client: texttospeech.TextToSpeechClient,
    ):
        super().__init__(router, logger)
        self._client = client

    def call(
        self,
        data: AkariData,  # Corrected type hint
        params: _GoogleTextToSpeechParams,
        callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        input_text = ""
        # Corrected input text retrieval as per instructions
        text_dataset = data.last().text
        if text_dataset and text_dataset.main:
            input_text = text_dataset.main
        else:
            self._logger.error("No text provided in data.last().text.main for TTS synthesis.")
            result_dataset = AkariDataSet()
            result_dataset.text = AkariDataSetType(main="Error: No text provided for synthesis.")
            return result_dataset

        try:
            synthesis_input = texttospeech.SynthesisInput(text=input_text)

            voice_params = texttospeech.VoiceSelectionParams(language_code=params.language_code, name=params.voice_name)
            audio_config_args = {
                "audio_encoding": getattr(texttospeech.AudioEncoding, params.audio_encoding),
                "speaking_rate": params.speaking_rate,
                "pitch": params.pitch,
            }
            if params.sample_rate_hertz is not None:
                audio_config_args["sample_rate_hertz"] = params.sample_rate_hertz
            if params.effects_profile_id is not None:
                audio_config_args["effects_profile_id"] = params.effects_profile_id

            if callback is None:
                audio_config = texttospeech.AudioConfig(**audio_config_args)

                response = self._client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice_params,
                    audio_config=audio_config,
                )

                # Successful return structure as per instructions
                result_dataset = AkariDataSet()
                result_dataset.audio = AkariDataSetType(main=response.audio_content)
                meta_info = {
                    "language_code": params.language_code,
                    "voice_name": params.voice_name,
                    "speaking_rate": params.speaking_rate,
                    "pitch": params.pitch,
                    "audio_encoding": params.audio_encoding,
                }
                if (
                    hasattr(response, "audio_config")
                    and response.audio_config
                    and hasattr(response.audio_config, "sample_rate_hertz")
                ):
                    meta_info["rate"] = response.audio_config.sample_rate_hertz
                elif params.sample_rate_hertz:
                    meta_info["rate"] = params.sample_rate_hertz
                meta_info["channels"] = 1
                result_dataset.meta = AkariDataSetType(main=meta_info)
                return result_dataset
            # Streaming implementation using Google Cloud TTS streaming API
            streaming_config = texttospeech.StreamingSynthesizeConfig(
                voice=voice_params,
            )
            config_request = texttospeech.StreamingSynthesizeRequest(streaming_config=streaming_config)
            text_iterator = [input_text]

            def request_generator() -> typing.Generator[texttospeech.StreamingSynthesizeRequest, None, None]:
                yield config_request
                for text in text_iterator:
                    yield texttospeech.StreamingSynthesizeRequest(
                        input=texttospeech.StreamingSynthesisInput(text=text),
                    )

            delta_bytes = []
            try:
                streaming_responses = self._client.streaming_synthesize(request_generator())
                for response in streaming_responses:
                    if hasattr(response, "audio_content") and response.audio_content:
                        b = response.audio_content
                        delta_bytes.append(b)
                        result_dataset = AkariDataSet()
                        stream = AkariDataStreamType(delta=delta_bytes.copy())
                        result_dataset.audio = AkariDataSetType(
                            main=b"".join(delta_bytes),
                            stream=stream,
                        )
                        meta_info = {
                            "language_code": params.language_code,
                            "voice_name": params.voice_name,
                            "speaking_rate": params.speaking_rate,
                            "pitch": params.pitch,
                            "audio_encoding": params.audio_encoding,
                        }
                        if params.sample_rate_hertz:
                            meta_info["rate"] = params.sample_rate_hertz
                        meta_info["channels"] = 1
                        result_dataset.meta = AkariDataSetType(main=meta_info)

                        callback_data = copy.deepcopy(data)
                        callback_data.add(result_dataset)

                        self._router.callModule(
                            moduleType=callback,
                            data=callback_data,
                            params=params.callback_params,
                            callback=callback,
                            streaming=True,
                        )

                return result_dataset
            except Exception as e:
                self._logger.error(f"Error during Google TTS streaming synthesis: {e}")
                result_dataset = AkariDataSet()
                result_dataset.text = AkariDataSetType(
                    main=f"Error: Google TTS streaming synthesis failed: {e!s}",
                )
                return result_dataset

        except Exception as e:
            # Error handling as per instructions
            self._logger.error(f"Error during Google TTS synthesis: {e}")
            result_dataset = AkariDataSet()
            result_dataset.text = AkariDataSetType(main=f"Error: Google TTS synthesis failed: {e!s}")
            return result_dataset

    def stream_call(
        self,
        data: AkariData,  # Signature as per instructions
        params: _GoogleTextToSpeechParams,
        callback: AkariModuleType | None = None,
    ) -> AkariDataSet:  # Return type as per instructions
        # Implementation as per instructions
        self._logger.warning("stream_call is not implemented for GoogleTextToSpeechModule.")
        raise NotImplementedError("GoogleTextToSpeechModule does not support streaming.")

    def close(self) -> None:
        # Implementation as per instructions
        self._logger.info(
            "GoogleTextToSpeechModule close called. Client cleanup is typically automatic for google-cloud-texttospeech.",
        )
