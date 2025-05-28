# modules/google/stt.py
import dataclasses
import queue
import threading
import time
from typing import Any, Generator, Iterable, cast  # Iterable をインポート

from google.cloud import speech
from google.cloud.speech_v1.types import StreamingRecognizeResponse

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
    AkariModule,
    AkariModuleParams,  # AkariModuleParams自体は型ヒントとして利用
    AkariModuleType,
    AkariRouter,
    AkariDataStreamType,  # AkariDataStreamTypeをインポート
)


# AkariModuleParamsを直接継承しないように変更
@dataclasses.dataclass
class GoogleSpeechToTextStreamParams:  # AkariModuleParams を継承しない
    """
    Google Cloud Speech-to-Textストリーミングモジュール用のパラメータ。

    Attributes:
        language_code (str): 音声認識に使用する言語コード (例: "ja-JP", "en-US")。
        sample_rate_hertz (int): 入力音声のサンプルレート (Hz)。
                                AkariDataのメタデータから取得することを推奨。
        interim_results (bool): 中間結果を返すかどうか。デフォルトはTrue。
        enable_automatic_punctuation (bool): 自動句読点を有効にするか。デフォルトはTrue。
        model (str | None): 使用する音声モデル (例: "telephony", "latest_long")。
                            Noneの場合はAPIのデフォルトを使用。デフォルトはNone。
        downstream_callback_params (AkariModuleParams | None):
            文字起こし結果を渡すコールバックモジュール用のパラメータ。デフォルトはNone。
        end_stream_flag (bool): (stream_callのparamsとして動的に渡される想定)
                                このフラグがTrueの場合、STTストリームを終了する。デフォルトはFalse。
                                モジュール呼び出し時に params.end_stream_flag = True のように設定。
    """

    language_code: str = "ja-JP"
    sample_rate_hertz: int = 16000  # MicModuleなどから渡されるメタデータで上書き推奨
    interim_results: bool = True
    enable_automatic_punctuation: bool = True
    model: str | None = None
    downstream_callback_params: AkariModuleParams | None = None  # 型はAkariModuleParams (Any) のまま
    end_stream_flag: bool = False  # モジュール呼び出し時に動的に設定


class GoogleSpeechToTextStreamModule(AkariModule):
    """
    Google Cloud Speech-to-Text APIを使用して音声ストリームを文字起こしするAkariモジュール。
    MicModuleなどから音声チャンクを継続的に受け取り、リアルタイムで文字起こし結果を
    指定されたコールバックモジュールに送信します。
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger, client: speech.SpeechClient) -> None:
        super().__init__(router, logger)
        self._client: speech.SpeechClient = client
        self._streaming_config: speech.StreamingRecognitionConfig | None = None
        self._audio_queue: queue.Queue[bytes | None] = queue.Queue()
        self._processing_thread: threading.Thread | None = None
        self._is_streaming_active: bool = False
        self._lock: threading.Lock = threading.Lock()  # 状態変更の同期用

        self._downstream_callback_module_type: AkariModuleType | None = None
        self._downstream_callback_params_for_router: AkariModuleParams | None = None  # 型はAnyのまま

        # client はコンストラクタで受け取るので、ここでの初期化は不要
        # try:
        #     self._logger.info("Google SpeechClient initialized successfully.")
        # except Exception as e:
        #     self._logger.error(f"Failed to initialize Google SpeechClient: {e}")
        self._logger.info("GoogleSpeechToTextStreamModule initialized with provided SpeechClient.")

    def _audio_chunk_provider(self) -> Generator[speech.StreamingRecognizeRequest, None, None]:
        """
        内部キューから音声チャンクを取得し、Google STT APIリクエストを生成するジェネレータ。
        """
        self._logger.debug("Audio chunk provider thread started.")
        while self._is_streaming_active or not self._audio_queue.empty():
            try:
                chunk = self._audio_queue.get(block=True, timeout=0.1)  # タイムアウトで定期的に状態確認
                if chunk is None:  # ストリーム終了のシグナル
                    self._logger.debug("Audio chunk provider received None, signaling end.")
                    return
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
            except queue.Empty:
                # self._logger.debug("Audio queue empty, continuing...")
                continue
            except Exception as e:
                self._logger.error(f"Error in audio chunk provider: {e}")
                return  # ジェネレータを終了させる
        self._logger.debug("Audio chunk provider loop finished.")

    def _google_stt_processor_thread_target(self) -> None:
        """
        Google STT APIとのストリーミング通信を処理し、結果をコールバックするスレッド関数。
        """
        if not self._streaming_config:  # self._client は __init__ で必須なのでチェック済みとみなす
            self._logger.error("Streaming_config not initialized in thread.")
            self._is_streaming_active = False  # 安全のためストリーミングを停止
            return

        self._logger.info("Google STT processing thread starting.")
        try:
            requests = self._audio_chunk_provider()
            # 修正: streaming_recognize のキーワード引数を 'config' に変更
            responses: Iterable[StreamingRecognizeResponse] = self._client.streaming_recognize(
                config=self._streaming_config, requests=requests
            )

            for response in responses:
                if not self._is_streaming_active and self._audio_queue.empty():  # 早期終了のチェック
                    self._logger.info("Streaming deactivated and queue empty, exiting STT processor loop.")
                    break

                if not response.results:
                    continue

                result = response.results[0]
                if not result.alternatives:
                    continue

                transcript = result.alternatives[0].transcript
                is_final = result.is_final

                self._logger.debug(f"STT Result: '{transcript}' (Final: {is_final})")

                if self._downstream_callback_module_type:
                    transcript_dataset = AkariDataSet()
                    transcript_dataset.text = AkariDataSetType(main=transcript)
                    transcript_dataset.meta = AkariDataSetType(
                        main={
                            "is_final": is_final,
                            "language_code": result.language_code if result.language_code else "",
                            "stability": result.stability if hasattr(result, "stability") else 0.0,
                        }
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
                        self._logger.error(f"Error calling downstream callback module: {e_router}")

        except Exception as e:
            self._logger.error(
                f"Exception in Google STT processing thread: {e}", exc_info=True
            )  # exc_info=Trueでスタックトレースも表示
        finally:
            self._logger.info("Google STT processing thread finished.")
            with self._lock:
                self._is_streaming_active = False
                # スレッドが終了したことを示すためにNoneをキューに入れる（もしジェネレータがまだ待機している場合）
                # ただし、通常はジェネレータ内の_is_streaming_activeで終了するはず
                if (
                    self._processing_thread and self._processing_thread.is_alive()
                ):  # このチェックは理論上不要だが念のため
                    self._audio_queue.put(None)  # 安全策

    def _start_streaming_session(
        self, params: GoogleSpeechToTextStreamParams, callback: AkariModuleType | None
    ) -> None:
        """新しいSTTストリーミングセッションを開始し、処理スレッドを起動する。"""
        self._logger.info("Starting new Google STT stream session.")
        self._is_streaming_active = True
        self._downstream_callback_module_type = callback
        self._downstream_callback_params_for_router = params.downstream_callback_params

        recognition_config_proto = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=params.sample_rate_hertz,
            language_code=params.language_code,
            enable_automatic_punctuation=params.enable_automatic_punctuation,
            model=params.model if params.model else None,
        )
        self._streaming_config = speech.StreamingRecognitionConfig(
            config=recognition_config_proto, interim_results=params.interim_results
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
        """STTストリーミングセッションを停止する。"""
        self._logger.info("Stopping Google STT stream session.")
        self._is_streaming_active = False  # まずフラグをFalseに
        self._audio_queue.put(None)  # ジェネレータに終了を通知

        if self._processing_thread and self._processing_thread.is_alive():
            self._logger.debug("Waiting for STT processing thread to join...")
            self._processing_thread.join(timeout=2.0)  # タイムアウト付きで待機
            if self._processing_thread.is_alive():
                self._logger.warning("STT processing thread did not join in time.")
        self._processing_thread = None
        self._logger.info("STT stream session stopped.")

    def call(
        self, data: AkariData, params: GoogleSpeechToTextStreamParams, callback: AkariModuleType | None = None
    ) -> AkariDataSet:  # paramsの型をGoogleSpeechToTextStreamParamsに変更
        self._logger.warning(
            "call() is not implemented for GoogleSpeechToTextStreamModule. Use stream_call() for streaming STT."
        )
        raise NotImplementedError("Use stream_call for Google Speech-to-Text streaming.")

    def stream_call(
        self, data: AkariData, params: AkariModuleParams, callback: AkariModuleType | None = None
    ) -> AkariDataSet:
        if not isinstance(params, GoogleSpeechToTextStreamParams):
            self._logger.error(f"Invalid params type: {type(params)}. Expected GoogleSpeechToTextStreamParams.")
            error_dataset = AkariDataSet()
            error_dataset.text = AkariDataSetType(main="Error: Invalid parameters type for STT module.")
            return error_dataset
        current_params: GoogleSpeechToTextStreamParams = params

        with self._lock:
            if current_params.end_stream_flag:
                if self._is_streaming_active:
                    self._stop_streaming_session()
                else:
                    self._logger.info("Received end_stream_flag but STT session was not active.")
                return AkariDataSet()  # 終了時は空のデータセットを返す

            # メタデータからサンプルレートを取得して上書き
            if data.datasets:  # datasetsリストが空でないことを確認
                last_dataset = data.last()
                if last_dataset.meta and last_dataset.meta.main and "rate" in last_dataset.meta.main:
                    actual_sample_rate = last_dataset.meta.main["rate"]
                    if current_params.sample_rate_hertz != actual_sample_rate:
                        self._logger.warning(
                            f"Overriding params.sample_rate_hertz ({current_params.sample_rate_hertz}) "
                            f"with actual sample rate from metadata ({actual_sample_rate})."
                        )
                        current_params.sample_rate_hertz = actual_sample_rate

            if not self._is_streaming_active:
                # stream_call に渡された callback (下流モジュール) を使用
                self._start_streaming_session(current_params, callback)

            audio_chunk: bytes | None = None
            if data.datasets:  # datasetsリストが空でないことを確認
                last_dataset = data.last()
                if last_dataset.audio:  # audio属性がNoneでないことを確認
                    if last_dataset.audio.stream and len(last_dataset.audio.stream) > 0:
                        audio_chunk = last_dataset.audio.stream.last()
                    elif last_dataset.audio.main:
                        audio_chunk = last_dataset.audio.main

            if audio_chunk:
                if self._is_streaming_active:
                    self._audio_queue.put(audio_chunk)
                    self._logger.debug(f"Added audio chunk of size {len(audio_chunk)} to queue.")
                else:
                    self._logger.warning("Received audio chunk, but STT session is not active. Chunk ignored.")
            else:
                self._logger.debug("No audio chunk found in AkariData.")

        status_dataset = AkariDataSet()
        status_dataset.meta = AkariDataSetType(
            main={"status": "Audio chunk received." if audio_chunk else "No audio chunk."}
        )
        return status_dataset

    def close(self) -> None:
        """Deterministically stop the streaming session and clean up resources."""
        if hasattr(self, "_is_streaming_active") and self._is_streaming_active:
            self._logger.info("Closing GoogleSpeechToTextStreamModule. Stopping active stream.")
            self._stop_streaming_session()

    def __del__(self) -> None:
        """Attempt cleanup when the object is deleted."""
        self.close()
