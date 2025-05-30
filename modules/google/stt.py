"""Google Cloud Speech-to-Text (STT) APIを使用して音声ストリームを文字起こしするAkariモジュール."""

from __future__ import annotations  # Added for FA102 if any, and good practice

import dataclasses
import queue
import threading  # TC004: Moved out of TYPE_CHECKING
from collections.abc import Generator, Iterable
from typing import TYPE_CHECKING

from google.cloud import speech

# StreamingRecognizeResponse is already imported below, so no change needed here
# from google.cloud.speech_v1.types import StreamingRecognizeResponse
from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariDataStreamType,  # AkariDataStreamTypeをインポート
    AkariLogger,
    AkariModule,
    AkariModuleParams,  # AkariModuleParams自体は型ヒントとして利用
    AkariModuleType,
    AkariRouter,
)

# Ensure imports inside TYPE_CHECKING are only for type hinting
if TYPE_CHECKING:
    # Iterable and Generator already imported above
    # threading already imported above
    from google.cloud.speech_v1.types import StreamingRecognizeResponse  # This is fine here


# AkariModuleParamsを直接継承しないように変更
@dataclasses.dataclass
class _GoogleSpeechToTextStreamParams:  # AkariModuleParams を継承しない
    """Google Cloud Speech-to-Textストリーミングモジュール用のパラメータ."""

    language_code: str = "ja-JP"
    """音声認識に使用する言語コード (例: "ja-JP", "en-US")."""
    sample_rate_hertz: int = 16000
    """入力音声のサンプルレート (Hz). AkariDataのメタデータから取得することを推奨."""
    interim_results: bool = True
    """中間結果を返すかどうか. デフォルトはTrue."""
    enable_automatic_punctuation: bool = True
    """自動句読点を有効にするか. デフォルトはTrue."""
    model: str | None = None
    """使用する音声モデル (例: "telephony", "latest_long"). Noneの場合はAPIのデフォルトを使用. デフォルトはNone."""
    downstream_callback_params: AkariModuleParams | None = None
    """文字起こし結果を渡すコールバックモジュール用のパラメータ. デフォルトはNone."""
    end_stream_flag: bool = False
    """(stream_callのparamsとして動的に渡される想定) このフラグがTrueの場合、STTストリームを終了する. デフォルトはFalse."""
    callback_when_final: bool = True
    """最終結果をコールバックするかどうか. デフォルトはTrue.(Falseで常にコールバックする)"""


class _GoogleSpeechToTextStreamModule(AkariModule):
    """Google Cloud Speech-to-Text APIを使用して音声ストリームを文字起こしするAkariモジュール.

    MicModuleなどから音声チャンクを継続的に受け取り、リアルタイムで文字起こし結果を
    指定されたコールバックモジュールに送信します。
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger, client: speech.SpeechClient) -> None:
        """GoogleSpeechToTextStreamModuleを初期化します.

        Args:
            router: Akariルーターインスタンス.
            logger: Akariロガーインスタンス.
            client: 初期化済みのGoogle Cloud Speechクライアントインスタンス.
        """
        super().__init__(router, logger)
        self._client: speech.SpeechClient = client
        self._streaming_config: speech.StreamingRecognitionConfig | None = None
        self._audio_queue: queue.Queue[bytes | None] = queue.Queue()
        self._processing_thread: threading.Thread | None = None
        self._is_streaming_active: bool = False
        self._lock: threading.Lock = threading.Lock()  # 状態変更の同期用

        self._downstream_callback_module_type: AkariModuleType | None = None
        self._downstream_callback_params_for_router: AkariModuleParams | None = None

        self._callback_when_final: bool = True
        self._result_delta: list[str] = []  # 逐次レスポンス保存用
        self._result_final: bool = False  # finalフラグ

    def _audio_chunk_provider(
        self,
    ) -> Generator[speech.StreamingRecognizeRequest, None, None]:
        """内部キューから音声チャンクを取得し、Google STT APIリクエストを生成するジェネレータ."""
        self._logger.debug("Audio chunk provider thread started.")
        while self._is_streaming_active or not self._audio_queue.empty():
            try:
                chunk = self._audio_queue.get(block=True, timeout=0.1)
                if chunk is None:
                    self._logger.debug("Audio chunk provider received None, signaling end.")
                    return
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
            except queue.Empty:
                continue
            except Exception as e:
                self._logger.exception("Error in audio chunk provider: %s", e)
                return
        self._logger.debug("Audio chunk provider loop finished.")

    def _google_stt_processor_thread_target(self) -> None:
        """Google STT APIとのストリーミング通信を処理し、結果をコールバックするスレッド関数."""
        if not self._streaming_config:
            self._logger.error("Streaming_config not initialized in thread.")
            self._is_streaming_active = False
            return

        self._logger.info("Google STT processing thread starting.")
        try:
            requests = self._audio_chunk_provider()
            responses: Iterable[StreamingRecognizeResponse] = self._client.streaming_recognize(
                config=self._streaming_config,
                requests=requests,
            )  # type: ignore

            for response in responses:
                if not self._is_streaming_active and self._audio_queue.empty():
                    self._logger.info("Streaming deactivated and queue empty, exiting STT processor loop.")
                    break

                if not response.results:
                    continue

                result = response.results[0]
                if not result.alternatives:
                    continue

                transcript = result.alternatives[0].transcript
                is_final = result.is_final

                self._logger.debug("STT Result: '%s' (Final: %s)", transcript, is_final)

                # 逐次レスポンス保存
                if transcript:
                    if not is_final:
                        self._result_delta.append(transcript)
                    else:
                        self._result_delta.append(transcript)
                        self._result_final = True

                if self._downstream_callback_module_type and (is_final or not self._callback_when_final):
                    transcript_dataset = AkariDataSet()
                    transcript_dataset.text = AkariDataSetType(main=transcript)
                    transcript_dataset.meta = AkariDataSetType(
                        main={
                            "is_final": is_final,
                            "language_code": (result.language_code if result.language_code else ""),
                            "stability": (result.stability if hasattr(result, "stability") else 0.0),
                        },
                    )

                    callback_data = AkariData()
                    callback_data.add(transcript_dataset)

                    try:
                        self._router.callModule(
                            moduleType=self._downstream_callback_module_type,
                            data=callback_data,
                            params=self._downstream_callback_params_for_router,
                            streaming=True,
                        )
                    except Exception as e_router:
                        self._logger.exception("Error calling downstream callback module: %s", e_router)

        except Exception as e:
            self._logger.exception("Exception in Google STT processing thread: %s", e)
        finally:
            self._logger.info("Google STT processing thread finished.")
            with self._lock:
                self._is_streaming_active = False
                if self._processing_thread and self._processing_thread.is_alive():
                    self._audio_queue.put(None)

    def _start_streaming_session(
        self,
        params: _GoogleSpeechToTextStreamParams,
        callback: AkariModuleType | None,
    ) -> None:
        """新しいSTTストリーミングセッションを開始し、処理スレッドを起動します."""
        self._logger.info("Starting new Google STT stream session.")
        self._is_streaming_active = True
        self._downstream_callback_module_type = callback
        self._downstream_callback_params_for_router = params.downstream_callback_params
        self._callback_when_final = params.callback_when_final

        recognition_config_proto = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=params.sample_rate_hertz,
            language_code=params.language_code,
            enable_automatic_punctuation=params.enable_automatic_punctuation,
            model=params.model if params.model else None,
        )
        self._streaming_config = speech.StreamingRecognitionConfig(
            config=recognition_config_proto,
            interim_results=params.interim_results,
        )

        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        self._processing_thread = threading.Thread(target=self._google_stt_processor_thread_target)
        self._processing_thread.daemon = True
        self._processing_thread.start()

    def _stop_streaming_session(self) -> None:
        """STTストリーミングセッションを停止します."""
        self._logger.info("Stopping Google STT stream session.")
        self._is_streaming_active = False
        self._audio_queue.put(None)

        if self._processing_thread and self._processing_thread.is_alive():
            self._logger.debug("Waiting for STT processing thread to join...")
            self._processing_thread.join(timeout=2.0)
            if self._processing_thread.is_alive():
                self._logger.warning("STT processing thread did not join in time.")
        self._processing_thread = None
        self._logger.info("STT stream session stopped.")

    def call(
        self,
        data: AkariData,
        params: _GoogleSpeechToTextStreamParams,
        callback: AkariModuleType | None = None, # No ARG002 for this, it's an abstract method override
    ) -> AkariDataSet:
        """ストリーミング専用モジュールのため、このメソッドはNotImplementedErrorを発生させます.

        代わりに `stream_call` を使用してください。

        Args:
            data: AkariDataインスタンス.
            params: モジュールパラメータ.
            callback: コールバックモジュールタイプ.

        Raises:
            NotImplementedError: このメソッドは実装されていません.
        """
        # EM101, TRY003
        msg = "call() is not implemented for GoogleSpeechToTextStreamModule. Use stream_call() for streaming STT."
        raise NotImplementedError(msg)

    def stream_call(  # noqa: C901, PLR0912
        self,
        data: AkariData,
        params: _GoogleSpeechToTextStreamParams,
        callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """音声チャンクを受け取り、Google STTストリームに追加します.

        文字起こし結果は、初期化時に設定されたコールバックモジュールに非同期で送信されます。

        Args:
            data: 入力データ。`data.last().audio.main` に音声チャンクを期待します。
                  `data.last().meta.main` から "rate" を読み取り、`params.sample_rate_hertz` を上書きします。
            params: モジュールの動作を制御するパラメータ。
                    `GoogleSpeechToTextStreamParams` 型である必要があります。
                    `end_stream_flag=True` でストリームを終了します。
            callback: 文字起こし結果を処理するコールバックモジュールタイプ。

        Returns:
            処理受付状況を示す `AkariDataSet`。実際の文字起こし結果はコールバック経由です。

        Raises:
            TypeError: `params` が `GoogleSpeechToTextStreamParams` 型でない場合。
        """
        if not isinstance(params, _GoogleSpeechToTextStreamParams):
            self._logger.error(
                "Invalid params type: %s. Expected GoogleSpeechToTextStreamParams.",
                type(params),
            )
            error_dataset = AkariDataSet()
            error_dataset.text = AkariDataSetType(main="Error: Invalid parameters type for STT module.")
            return error_dataset
        current_params: _GoogleSpeechToTextStreamParams = params

        with self._lock:
            if current_params.end_stream_flag:
                if self._is_streaming_active:
                    self._stop_streaming_session()
                else:
                    self._logger.info("Received end_stream_flag but STT session was not active.")
                return AkariDataSet()

            if data.datasets:
                last_dataset = data.last()
                if last_dataset.meta and last_dataset.meta.main and "rate" in last_dataset.meta.main:
                    actual_sample_rate = last_dataset.meta.main["rate"]
                    if current_params.sample_rate_hertz != actual_sample_rate:
                        self._logger.warning(
                            "Overriding params.sample_rate_hertz (%s) with actual sample rate from metadata (%s).",
                            current_params.sample_rate_hertz,
                            actual_sample_rate,
                        )
                        current_params.sample_rate_hertz = actual_sample_rate

            if not self._is_streaming_active:
                self._start_streaming_session(current_params, callback)

            audio_chunk: bytes | None = None
            if data.datasets:
                last_dataset = data.last()
                if last_dataset.audio:
                    if last_dataset.audio.stream and len(last_dataset.audio.stream) > 0:
                        audio_chunk = last_dataset.audio.stream.last()
                    elif last_dataset.audio.main:
                        audio_chunk = last_dataset.audio.main

            if audio_chunk:
                if self._is_streaming_active:
                    self._audio_queue.put(audio_chunk)
                    self._logger.debug("Added audio chunk of size %s to queue.", len(audio_chunk))
                else:
                    self._logger.warning("Received audio chunk, but STT session is not active. Chunk ignored.")
            else:
                self._logger.debug("No audio chunk found in AkariData.")

        dataset = AkariDataSet()
        stream = AkariDataStreamType(delta=self._result_delta.copy())
        dataset.text = AkariDataSetType(
            main=self._result_delta[-1] if len(self._result_delta) > 0 else "",
            stream=stream,
        )
        dataset.bool = AkariDataSetType(main=self._result_final)

        if self._result_final:
            self._result_delta.clear()
            self._result_final = False
        return dataset

    def close(self) -> None:
        """STTストリーミングセッションを確定的に停止し、リソースをクリーンアップします."""
        if hasattr(self, "_is_streaming_active") and self._is_streaming_active:
            self._logger.info("Closing GoogleSpeechToTextStreamModule. Stopping active stream.")
            self._stop_streaming_session()

    def __del__(self) -> None:
        """オブジェクトが削除される際にクリーンアップを試みます."""
        self.close()
