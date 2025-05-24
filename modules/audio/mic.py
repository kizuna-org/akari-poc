import dataclasses
import threading
import time
from typing import Any

import pyaudio

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
class _MicModuleParams:
    """マイク音声キャプチャの設定を定義します。

    音声形式（サンプルレート、チャンネル、PyAudio 形式）、デバイス選択、
    処理のためのチャンク化動作、キャプチャされた音声データでコールバックモジュールを
    どのように呼び出すかなどの側面を制御します。

    Attributes:
        format (int): サンプルの PyAudio 形式定数（例: `pyaudio.paInt16`）。
            サンプルサイズとタイプを決定します。デフォルトは `pyaudio.paInt16` です。
        rate (int): ヘルツ単位の目的のサンプリングレート（サンプル/秒）。
            一般的な値には 16000、24000、44100、48000 が含まれます。デフォルトは 24000 です。
        channels (int): 録音するオーディオチャンネルの数（例: モノラルは 1、ステレオは 2）。
            デフォルトは 1 です。
        frames_per_buffer (int): PyAudio が単一の操作で読み取るオーディオフレームの数。
            これはレイテンシと処理の粒度に影響します。デフォルトは 1024 です。
        input_device_index (Optional[int]): 使用するオーディオ入力デバイスの数値インデックス。
            `None` の場合、PyAudio のデフォルト入力デバイスが選択されます。デフォルトは None です。
        streamDurationMilliseconds (int): コールバックモジュールにディスパッチされる前に
            収集される各オーディオセグメントの期間をミリ秒単位で指定します。
            デフォルトは 500 ミリ秒です。
        destructionMilliseconds (int): ミリ秒単位のスライディングウィンドウを定義します。
            この期間より古いオーディオフレーム（現在の処理セグメントの最新フレームからの相対的な期間）は
            内部バッファから破棄されます。これにより、連続録音のメモリ管理が容易になります。
            デフォルトは 500 ミリ秒です。
        callback_when_thread_is_alive (bool): 前のコールバックスレッドがまだ実行中の場合に、
            新しいコールバックを開始できるかどうかを制御します。False（デフォルト）の場合、
            前のコールバックが完了した場合にのみ新しいコールバックが開始されます。
            True の場合、新しいコールバックを同時に起動できます。デフォルトは False です。
        callbackParams (Any | None): 呼び出されたときにコールバックモジュールに渡される
            任意のパラメータ。これにより、コンテキスト情報を音声データとともに送信できます。
            デフォルトは None です。
        callback_callback (Optional[AkariModuleType]): オーディオセグメント
            （`streamDurationMilliseconds` の）の準備ができたときに呼び出される Akari モジュールの
            クラスタイプ。このモジュールは録音された音声データを受信します。
            デフォルトは None で、コールバックはトリガーされません。
    """

    format: int = pyaudio.paInt16
    rate: int = 24000
    channels: int = 1
    frames_per_buffer: int = 1024
    input_device_index: int | None = None
    streamDurationMilliseconds: int = 5 * 100
    destructionMilliseconds: int = 5 * 100
    callback_when_thread_is_alive: bool = False
    callbackParams: Any | None = None
    callback_callback: AkariModuleType | None = None


class _MicModule(AkariModule):
    """指定されたマイクデバイスから音声入力をキャプチャします。

    連続録音ループを管理し、受信オーディオを設定可能なチャンクに処理します。
    完全なチャンクごとに、オーディオデータ（関連するメタデータとともに）を
    指定されたコールバック Akari モジュールにディスパッチして、
    さらなる処理（音声認識、VAD など）を行うことができます。
    コールバックは、メインの録音ループをブロックしないように別のスレッドで実行されます。

    Attributes:
        _thread (threading.Thread): 現在アクティブなコールバックスレッドを格納します（存在する場合）。
            これは、モジュールパラメータに基づいて同時コールバック実行を管理するのに役立ちます。
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """MicModule インスタンスを構築します。

        ベース AkariModule を初期化し、コールバックスレッドを管理するための
        プレースホルダーを準備します。

        Args:
            router (AkariRouter): Akari ルーターインスタンス。コールバックモジュールの呼び出しに使用されます。
            logger (AkariLogger): 操作の詳細とデバッグ情報を記録するためのロガーインスタンス。
        """
        super().__init__(router, logger)
        self._thread: threading.Thread = threading.Thread()

    def call(self, data: AkariData, params: _MicModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        """マイクからの連続音声録音ループを開始および管理します。

        `params` で設定された PyAudio ストリームを開きます。その後、無限ループに入り、
        チャンク単位で音声データを読み取ります。これらのチャンクは、
        `params.streamDurationMilliseconds` の音声が収集されるまで蓄積されます。
        この時点で、蓄積された音声（`main` として、およびストリーム内）と
        関連するメタデータ（チャンネル、サンプル幅、レート）を含む `AkariDataSet` が作成されます。

        （`params.callback_callback` で指定された）`callback` モジュールが設定されている場合、
        AkariRouter を介してこのコールバックモジュールを呼び出すために新しいスレッドが生成され、
        新しく作成された `AkariData`（オーディオデータセットを含む）と
        `params.callbackParams` が渡されます。1つのスレッドが既にアクティブな場合に
        新しいスレッドを起動する動作は、`params.callback_when_thread_is_alive` によって制御されます。

        このメソッドは、メモリを管理するために `params.destructionMilliseconds` に基づいて
        オーディオフレームのスライディングウィンドウを維持します。

        Note:
            このメソッドは無限ループを実行し、外部イベント
            （例えば、典型的なスクリプトでの `KeyboardInterrupt`、または Akari パイプラインを
            管理するアプリケーションによる）によって終了されることが期待されます。
            `data` 引数は、コールバック用の新しい `AkariData` インスタンスを作成するための
            テンプレートとして使用されますが、入力 `data` 自体は直接変更されたり、
            入力オーディオとして使用されたりすることはありません。主要な出力は、
            コールバックメカニズムを介して行われます。

        Args:
            data (AkariData): 初期（通常は空の）AkariData オブジェクト。
            params (_MicModuleParams): マイクの録音、チャンク化、およびコールバック動作の
                設定パラメータ。
            callback (Optional[AkariModuleType]): `params.callback_callback` で指定された
                Akari モジュールタイプが、スレッド化されたコールバックに実際に使用されるものです。
                このトップレベルの `callback` 引数は、スレッド化されたコールバックの現在の
                実装ロジックでは事実上無視されます。

        Returns:
            AkariDataSet: 空の `AkariDataSet`。実際のオーディオデータは、
            スレッド化されたコールバックメカニズムを介してディスパッチされます。

        Raises:
            PyAudioException: オーディオストリームのオープンまたは読み取りに問題がある場合
                （例: デバイスが見つからない、無効なパラメータ）。
            Exception: PyAudio およびシステムのオーディオ設定によっては、他の例外が発生する可能性があります。
        """
        dataset = AkariDataSet()

        audio = pyaudio.PyAudio()

        streamer = audio.open(
            format=params.format,
            channels=params.channels,
            rate=params.rate,
            input=True,
            frames_per_buffer=params.frames_per_buffer,
            input_device_index=params.input_device_index,
        )

        self._logger.info("Recording started...")
        try:
            frames = []
            frame = b""
            frame_time = time.time()
            streamer.start_stream()

            while True:
                data_chunk = streamer.read(params.frames_per_buffer, exception_on_overflow=False)
                frame += data_chunk

                current_time = time.time()
                if current_time - frame_time >= params.streamDurationMilliseconds / 1000:
                    frames.append(frame)

                    data = AkariData()
                    dataset = AkariDataSet()
                    stream = AkariDataStreamType(frames)
                    dataset.audio = AkariDataSetType(main=b"".join(frames), stream=stream)
                    dataset.meta = AkariDataSetType(
                        main={
                            "channels": params.channels,
                            "sample_width": audio.get_sample_size(params.format),
                            "rate": params.rate,
                        }
                    )
                    data.add(dataset)
                    if callback is not None:

                        def call_module_in_thread() -> None:
                            self._router.callModule(
                                moduleType=callback,
                                data=data,
                                params=params.callbackParams,
                                streaming=True,
                                callback=params.callback_callback,
                            )

                        if not self._thread.is_alive() or params.callback_when_thread_is_alive:
                            self._thread = threading.Thread(target=call_module_in_thread)
                            self._thread.start()

                    frame_time = current_time
                    frame = b""

                if len(frames) >= params.destructionMilliseconds / params.streamDurationMilliseconds:
                    frames = frames[1:]

        finally:
            streamer.stop_stream()
            streamer.close()
            audio.terminate()
