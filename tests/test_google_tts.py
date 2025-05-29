import unittest
from unittest.mock import MagicMock, patch, call

from google.cloud import texttospeech as gcp_texttospeech

from akari import (
    AkariData,  # Though module expects AkariDataSet, AkariData might be used for stream_call test
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
    AkariRouter,
)
from modules.google.tts import (
    GoogleTextToSpeechModule,
    GoogleTextToSpeechParams,
)


class TestGoogleTextToSpeechModule(unittest.TestCase):
    def setUp(self):
        self.mock_router = MagicMock(spec=AkariRouter)
        self.mock_logger = MagicMock(spec=AkariLogger)

        # Patch the client during initialization of the module
        self.patcher = patch("modules.google.tts.gcp_texttospeech.TextToSpeechClient")
        self.MockTextToSpeechClient = self.patcher.start()
        self.mock_tts_client_instance = self.MockTextToSpeechClient.return_value

        self.module = GoogleTextToSpeechModule(self.mock_router, self.mock_logger)

    def tearDown(self):
        self.patcher.stop()

    def _prepare_input_dataset(self, text: str | None) -> AkariDataSet:
        """Helper to prepare AkariDataSet input as expected by the module's call method."""
        outer_dataset = AkariDataSet()
        if text is not None:
            inner_dataset = AkariDataSet()
            inner_dataset.text = AkariDataSetType(main=text)
            outer_dataset.add(inner_dataset)
        # If text is None, outer_dataset.datasets will be empty, simulating no text input
        return outer_dataset

    def test_call_successful_synthesis(self):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.audio_content = b"synthesized_audio_bytes"
        mock_response.audio_config = MagicMock()
        mock_response.audio_config.sample_rate_hertz = 24000
        self.mock_tts_client_instance.synthesize_speech.return_value = mock_response

        input_text = "Hello world"
        input_dataset = self._prepare_input_dataset(input_text)

        params = GoogleTextToSpeechParams(
            language_code="en-US",
            voice_name="en-US-Wavenet-A",
            sample_rate_hertz=24000, # Explicitly set for meta check
        )

        result_dataset = self.module.call(input_dataset, params)

        self.mock_tts_client_instance.synthesize_speech.assert_called_once()
        called_args, called_kwargs = (
            self.mock_tts_client_instance.synthesize_speech.call_args
        )

        self.assertEqual(called_kwargs["input"].text, input_text)
        self.assertEqual(called_kwargs["voice"].language_code, "en-US")
        self.assertEqual(called_kwargs["voice"].name, "en-US-Wavenet-A")
        self.assertEqual(
            called_kwargs["audio_config"].audio_encoding,
            gcp_texttospeech.AudioEncoding.LINEAR16,
        )
        self.assertEqual(called_kwargs["audio_config"].speaking_rate, 1.0) # Default
        self.assertEqual(called_kwargs["audio_config"].pitch, 0.0) # Default
        self.assertEqual(called_kwargs["audio_config"].sample_rate_hertz, 24000)


        self.assertIsNotNone(result_dataset.audio)
        self.assertEqual(result_dataset.audio.main, b"synthesized_audio_bytes")
        self.assertIsNotNone(result_dataset.meta)
        self.assertIn("sample_rate_hertz", result_dataset.meta.main)
        self.assertEqual(result_dataset.meta.main["sample_rate_hertz"], 24000)
        self.assertEqual(result_dataset.meta.main["language_code"], "en-US")
        self.assertEqual(result_dataset.meta.main["voice_name"], "en-US-Wavenet-A")
        self.assertIsNone(result_dataset.text) # No error text

    def test_call_no_input_text(self):
        # Prepare input data with no text
        input_dataset_empty = self._prepare_input_dataset(None) # No text in inner dataset
        
        # Also test with inner dataset present but no text.main
        input_dataset_no_main = AkariDataSet()
        inner_no_main = AkariDataSet()
        inner_no_main.text = AkariDataSetType() # main is None by default
        input_dataset_no_main.add(inner_no_main)

        test_cases = [input_dataset_empty, input_dataset_no_main]

        for input_dataset in test_cases:
            self.mock_logger.reset_mock() # Reset logger for each case
            self.mock_tts_client_instance.synthesize_speech.reset_mock()

            params = GoogleTextToSpeechParams() # Use defaults
            result_dataset = self.module.call(input_dataset, params)

            self.assertIsNotNone(result_dataset.text)
            self.assertTrue("Error: No text provided for synthesis." in result_dataset.text.main)
            self.mock_tts_client_instance.synthesize_speech.assert_not_called()
            self.mock_logger.error.assert_called_with(
                "No text provided in data.last().text.main for TTS synthesis."
            )

    def test_stream_call_raises_not_implemented_error(self):
        with self.assertRaisesRegex(NotImplementedError, "GoogleTextToSpeechModule does not support streaming."):
            # stream_call expects AkariData, not AkariDataSet
            self.module.stream_call(AkariData(), GoogleTextToSpeechParams())
        self.mock_logger.warning.assert_called_with(
            "stream_call is not implemented for GoogleTextToSpeechModule."
        )


    def test_close_method(self):
        self.module.close()
        self.mock_logger.info.assert_called_once_with(
            "GoogleTextToSpeechModule close called. Client cleanup is typically automatic for google-cloud-texttospeech."
        )

    def test_call_with_varied_parameters(self):
        mock_response = MagicMock()
        mock_response.audio_content = b"varied_audio"
        # Simulate no audio_config on response to test fallback for sample_rate_hertz in meta
        del mock_response.audio_config 
        self.mock_tts_client_instance.synthesize_speech.return_value = mock_response

        input_text = "Different params"
        input_dataset = self._prepare_input_dataset(input_text)

        params = GoogleTextToSpeechParams(
            language_code="fr-FR",
            voice_name="fr-FR-Wavenet-B",
            speaking_rate=1.5,
            pitch=-2.5,
            audio_encoding="MP3", # Non-default
            sample_rate_hertz=16000, # Non-default
            effects_profile_id=["small-room-speaker"]
        )

        result_dataset = self.module.call(input_dataset, params)

        self.mock_tts_client_instance.synthesize_speech.assert_called_once()
        called_args, called_kwargs = (
            self.mock_tts_client_instance.synthesize_speech.call_args
        )

        self.assertEqual(called_kwargs["input"].text, input_text)
        self.assertEqual(called_kwargs["voice"].language_code, "fr-FR")
        self.assertEqual(called_kwargs["voice"].name, "fr-FR-Wavenet-B")
        self.assertEqual(called_kwargs["audio_config"].speaking_rate, 1.5)
        self.assertEqual(called_kwargs["audio_config"].pitch, -2.5)
        self.assertEqual(
            called_kwargs["audio_config"].audio_encoding,
            gcp_texttospeech.AudioEncoding.MP3,
        )
        self.assertEqual(called_kwargs["audio_config"].sample_rate_hertz, 16000)
        self.assertEqual(called_kwargs["audio_config"].effects_profile_id, ["small-room-speaker"])


        self.assertIsNotNone(result_dataset.audio)
        self.assertEqual(result_dataset.audio.main, b"varied_audio")
        self.assertIsNotNone(result_dataset.meta)
        self.assertEqual(result_dataset.meta.main["language_code"], "fr-FR")
        self.assertEqual(result_dataset.meta.main["voice_name"], "fr-FR-Wavenet-B")
        self.assertEqual(result_dataset.meta.main["speaking_rate"], 1.5)
        self.assertEqual(result_dataset.meta.main["pitch"], -2.5)
        self.assertEqual(result_dataset.meta.main["audio_encoding"], "MP3")
        self.assertEqual(result_dataset.meta.main["sample_rate_hertz"], 16000) # Fallback from params
        self.assertIsNone(result_dataset.text)

    def test_call_api_exception(self):
        self.mock_tts_client_instance.synthesize_speech.side_effect = Exception("API Error")

        input_text = "Test API error"
        input_dataset = self._prepare_input_dataset(input_text)
        params = GoogleTextToSpeechParams()

        result_dataset = self.module.call(input_dataset, params)

        self.mock_tts_client_instance.synthesize_speech.assert_called_once()
        self.assertIsNotNone(result_dataset.text)
        self.assertTrue("Error: Google TTS synthesis failed: API Error" in result_dataset.text.main)
        self.mock_logger.error.assert_called_with("Error during Google TTS synthesis: API Error")
        self.assertIsNone(result_dataset.audio)
        self.assertIsNone(result_dataset.meta)


if __name__ == "__main__":
    unittest.main()
