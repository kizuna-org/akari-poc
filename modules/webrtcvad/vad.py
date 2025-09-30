import dataclasses
import io
import time
from enum import Enum
from typing import Any, Literal

import pyaudio
import webrtcvad

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


class _WebRTCVadMode(Enum):
    """WebRTC 音声アクティビティ検出器（VAD）の感度レベルを指定します。

    VAD の積極性は、オーディオフレームを音声として分類する可能性を決定します。
    数値モードが高いほど、より積極的（感度が低い）な VAD に対応し、音声の識別に
    より制限的になります。

    Attributes:
        VERY_SENSITIVE (int): モード 0。最も積極的でなく、オーディオを音声として
            分類する可能性が最も高いです。バックグラウンドノイズの少ない環境に適しています。
        SENSITIVE (int): モード 1。バランスの取れた感度レベル。
        LOW_SENSITIVE (int): モード 2。SENSITIVE よりも積極的で、境界線のオーディオを
            音声として分類する可能性が低くなります。
        STRICT (int): モード 3。最も積極的で、音声の分類に最も制限的です。
            明確な音声検出が最重要である騒がしい環境に最適です。
    """

    VERY_SENSITIVE = 0
    SENSITIVE = 1
    LOW_SENSITIVE = 2
    STRICT = 3


@dataclasses.dataclass
class _WebRTCVadParams:
    """WebRTC VAD モジュールの動作を設定します。

    設定には、VAD 感度、期待されるオーディオプロパティ（サンプルレート、フレーム期間）、
    および音声イベントに基づくコールバックのトリガーロジックが含まれます。

    Attributes:
        mode (_WebRTCVadMode): VAD アルゴリズムの積極性を決定します。
            モードが高いほど、オーディオを音声として分類する際に制限が厳しくなります。
            デフォルトは `_WebRTCVadMode.VERY_SENSITIVE` です。
        sample_rate (Literal[8000, 16000, 32000, 48000]): 入力オーディオのサンプルレート（ヘルツ単位）。
            WebRTC VAD ライブラリは特定のレートをサポートしています。デフォルトは 16000 Hz です。
        frame_duration_ms (Literal[10, 20, 30]): VAD が処理する個々のオーディオフレームの
            期間（ミリ秒単位）。WebRTC VAD ライブラリは特定のフレーム期間をサポートしています。
            デフォルトは 30 ミリ秒です。
        speech_sleep_duration_ms (int): ヒステリシスメカニズム。VAD が非音声を検出したが、
            このミリ秒以内に音声が検出されていた場合、モジュールは機能的にそれを
            継続的な音声として扱うことができます。これにより、音声セグメントが途中で
            途切れるのを防ぐことができます。値 0 はこの機能を無効にします。デフォルトは 0 です。
        callback_when_speech_ended (bool): コールバックのタイミングを制御します。`True` の場合、
            設定されたコールバックモジュールは、音声セグメントが終了したときにのみ呼び出されます
            （つまり、`speech_sleep_duration_ms` を考慮して、音声から非音声への遷移）。
            `False` の場合、音声（または機能的な音声）として分類されたフレームでコールバックが
            呼び出されます。デフォルトは `False` です。
        callback_params (Optional[AkariModuleParams]): この VAD モジュールによって呼び出されたときに
            コールバックモジュールに渡される任意のパラメータ。これにより、コンテキストデータが
            パイプラインを通過できます。デフォルトは `None` です。
    """

    mode: _WebRTCVadMode = _WebRTCVadMode.VERY_SENSITIVE
    sample_rate: Literal[8000, 16000, 32000, 48000] = 16000
    frame_duration_ms: Literal[10, 20, 30] = 30
    speech_sleep_duration_ms: int = 0
    callback_when_speech_ended: bool = False
    callback_params: AkariModuleParams | None = None


class _WebRTCVadModule(AkariModule):
    """WebRTC 音声アクティビティ検出エンジンを使用して、リアルタイムオーディオストリームの音声セグメントを検出します。

    このモジュールは、ストリーミングオーディオデータ用に設計されています。受信オーディオチャンクを
    フレームごとに分析し、各フレームに音声が含まれているかどうかを判断し、音声として識別された
    オーディオセグメントの内部バッファを管理します。設定されたパラメータに基づいて、
    音声の開始時または終了時にコールバック Akari モジュールをトリガーし、蓄積された音声オーディオを渡します。

    Attributes:
        _vad (webrtcvad.Vad): WebRTC VAD アルゴリズムのインスタンス。
        _last_speech_time (float): 音声として検出された最後のフレームのタイムスタンプ。
            `speech_sleep_duration_ms` の実装に使用されます。
        _callbacked (bool): 現在の音声セグメントに対してコールバックが行われたかどうかを示すフラグ。
            冗長なコールバックを回避するために使用されます。
        _audio_buffer (bytes): 現在の音声セグメントの一部であるオーディオフレームを蓄積します。
            このバッファはコールバックモジュールに送信されます。
    """

    def __init__(
        self,
        router: AkariRouter,
        logger: AkariLogger,
    ) -> None:
        """_WebRTCVadModule インスタンスを構築します。

        WebRTC VAD オブジェクトと、音声タイミング、コールバックステータス、
        およびオーディオバッファリングを追跡するための内部状態変数を初期化します。

        Args:
            router (AkariRouter): Akari ルーターインスタンス。設定されたコールバックモジュールの
                呼び出しに使用されます。
            logger (AkariLogger): VAD アクティビティ、音声検出イベント、およびエラーを記録するための
                ロガーインスタンス。
        """
        super().__init__(router, logger)
        self._vad = webrtcvad.Vad()
        self._last_speech_time = time.mktime(time.gmtime(0))
        self._callbacked = True
        self._audio_buffer: bytes = b""

    def call(self, data: AkariData, params: _WebRTCVadParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        """標準の非ストリーミング呼び出し（このモジュールではサポートされていません）。

        WebRTC VAD モジュールは、音声セグメントを検出するために時間とともにオーディオチャンクを
        処理するため、本質的にストリーム指向です。したがって、従来のブロッキング `call` メソッドは
        実装していません。

        Args:
            data (AkariData): 入力データ（未使用）。
            params (_WebRTCVadParams): VAD パラメータ（未使用）。
            callback (Optional[AkariModuleType]): コールバックモジュール（未使用）。

        Raises:
            NotImplementedError: このモジュールは `stream_call` を必要とするため、常に発生します。
        """
        raise NotImplementedError("WebRTCVadModule does not support call method. Use stream_call instead.")

    def stream_call(
        self, data: AkariData, params: _WebRTCVadParams, callback: AkariModuleType | None = None
    ) -> AkariData:
        """WebRTC VAD アルゴリズムを使用して、受信オーディオチャンクの音声アクティビティを分析します。

        このメソッドは、`data.last().audio.main` にオーディオチャンクがあることを期待します。
        設定された `params`（モード、サンプルレート、フレーム期間）に従ってこのチャンクを処理します。
        音声が検出された場合、オーディオチャンク（利用可能な場合は `data.last().audio.stream.last()` から、
        そうでない場合は `data.last().audio.main` から）が内部 `_audio_buffer` に追加されます。

        コールバックメカニズムは、`params.callback_when_speech_ended` と
        `params.speech_sleep_duration_ms` に基づいて実装されます。
        - `callback_when_speech_ended` が False の場合、音声（または `speech_sleep_duration_ms` を
          考慮した機能的な音声）が検出されるとすぐにコールバックがトリガーされます。
        - `callback_when_speech_ended` が True の場合、音声セグメントが終了したときにのみ
          コールバックがトリガーされます（つまり、VAD が一定期間の音声の後に非音声を報告し、
          `speech_sleep_duration_ms` ヒステリシスが経過した場合）。

        コールバックがトリガーされると、蓄積された `_audio_buffer` が AkariRouter を介して
        指定された `callback` モジュールに送信されます。その後、バッファはクリアされます。
        このメソッドは、現在のチャンクのブール VAD 結果とオーディオバッファの状態を含む
        新しい `AkariDataSet` で入力 `AkariData` オブジェクトを更新します。

        Args:
            data (AkariData): 最新のオーディオチャンクを含む `AkariData` オブジェクト。
                期待されるオーディオの場所: VAD フレームの場合は `data.last().audio.main`、
                バッファリングの場合は `data.last().audio.stream.last()`（または `.main`）。
            params (_WebRTCVadParams): VAD 感度、オーディオプロパティ、およびコールバックロジックの
                設定パラメータ。
            callback (Optional[AkariModuleType]): 音声イベント（設定ごとの開始または終了）が
                発生したときに呼び出される Akari モジュールタイプ。

        Returns:
            AkariData: 変更された `AkariData` オブジェクト。処理されたフレームの VAD の
            ブール出力と現在のオーディオバッファの詳細を含む新しい `AkariDataSet` が含まれます。

        Raises:
            ValueError: `data.last().audio` がないか空の場合、オーディオチャンクが
                設定されたフレームサイズに対して短すぎる場合、または `self._vad.is_speech()` 中に
                エラーが発生した場合。
        """
        audio = data.last().audio
        if audio is None:
            raise ValueError("Audio data is missing or empty.")

        self._vad.set_mode(params.mode.value)

        buffer = io.BytesIO(audio.main)
        frame_size_bytes = int(params.sample_rate * params.frame_duration_ms / 1000 * 2)

        if len(audio.main) < frame_size_bytes:
            raise ValueError(
                f"Audio data is too short. Expected at least {frame_size_bytes} bytes, but got {len(audio.main)} bytes."
            )

        buffer.seek(-frame_size_bytes, io.SEEK_END)
        audio_data = buffer.read(frame_size_bytes)

        try:
            is_speech = self._vad.is_speech(audio_data, params.sample_rate)
            self._logger.debug("WebRTC VAD detected speech: %s", is_speech)
        except Exception as e:
            raise ValueError(f"Error processing audio data with WebRTC VAD: {e}") from e

        dataset = AkariDataSet()
        dataset.bool = AkariDataSetType(is_speech)
        dataset.audio = AkariDataSetType(main=self._audio_buffer, others={"all": audio_data})
        dataset.meta = data.last().meta
        data.add(dataset)

        if is_speech:
            self._last_speech_time = time.time()
            self._callbacked = False
            if audio.stream is not None:
                self._audio_buffer += audio.stream.last()
        else:
            if time.time() - self._last_speech_time < params.speech_sleep_duration_ms / 1000:
                is_speech = True

        self._logger.debug("WebRTC VAD functional detected speech: %s", is_speech)

        if callback:
            if (not params.callback_when_speech_ended and is_speech) or (
                params.callback_when_speech_ended and not is_speech and not self._callbacked
            ):
                data = self._router.callModule(callback, data, params.callback_params, True, None)
                self._callbacked = True
                self._audio_buffer = b""

        return data
