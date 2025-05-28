# Akari モジュール作成ガイド

Akari モジュールは、Akari フレームワーク内の基本的な処理単位です。このガイドでは、独自のカスタムモジュールを作成する方法について概説します。

コアコンセプト
モジュールを作成する前に、これらの主要コンポーネントを理解することが重要です。

AkariModule: すべての Akari モジュールが継承する必要のある抽象基底クラスです。モジュールの基本的な構造（初期化、標準操作およびストリーミング操作のメソッドなど）を定義します。

AkariData: データセットのシーケンスを調整し、処理パイプラインを通るデータの状態とフローを表します。モジュールは AkariData インスタンスを受け取り、以前のデータセットを検査し、新しい AkariDataSet インスタンスを追加できます。

AkariDataSet: 単一のモジュール実行によって生成されたさまざまなデータ型（テキスト、音声、ブール値、メタデータ）を、モジュール実行に関するメタデータとともに集約します。

AkariRouter: Akari モジュールの実行を管理します。利用可能なモジュールのレジストリを保持し、データフロー、パラメータ渡し、ロギングを処理しながら、それらに呼び出しをディスパッチします。

AkariLogger: Akari フレームワーク内で使用するためのカスタマイズされたロガーインスタンスです。

カスタムモジュールの作成
カスタム Akari モジュールを作成するには、次の手順に従います。

1. モジュールクラスの定義
   akari.AkariModule を継承する新しい Python クラスを作成します。

from akari import (
AkariData,
AkariDataSet,
AkariDataSetType, # AkariDataSetType をインポート
AkariDataStreamType, # AkariDataStreamType をインポート (ストリームデータ用)
AkariLogger,
AkariModule,
AkariModuleParams, # またはパラメータ用のカスタムデータクラス
AkariModuleType,
AkariRouter,
)
import dataclasses # パラメータクラス用に dataclasses をインポート
from typing import Any # メタデータ用に Any をインポート

# モジュール固有のパラメータを定義（オプション）

@dataclasses.dataclass
class MyCustomModuleParams(AkariModuleParams): # AkariModuleParams を継承
my_setting_1: str
my_setting_2: int = 10
sample_rate: int = 16000 # 音声処理用のサンプルレートなど

class MyCustomModule(AkariModule): # ...

2.  モジュールの初期化
    **init**メソッドを実装します。これは router: AkariRouter と logger: AkariLogger を引数として受け入れ、super().**init**(router, logger)を使用して親クラスの**init**メソッドに渡す必要があります。モジュールが必要とする可能性のある他の属性も初期化できます。

        def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
            super().__init__(router, logger)
            # ここにカスタム初期化を記述
            self._logger.info("MyCustomModule initialized")

3.  call メソッドの実装
    call メソッドは、非ストリーミング操作のためのモジュールの主要なロジックが存在する場所です。これは AkariModule の抽象メソッドであるため、実装する必要があります。

パラメータ:

data: akari.AkariData: 入力データオブジェクト。以前のモジュールからの結果を含む可能性があります。

params: AkariModuleParams（またはカスタムデータクラス）: その動作を構成するモジュール固有のパラメータ。

callback: AkariModuleType | None = None: オプションのコールバックモジュールタイプ。

戻り値:

モジュールが単一の結果セットを生成する場合は akari.AkariDataSet インスタンス、または全体的なデータパイプラインを変更したり複数のデータセットを生成したりする場合は akari.AkariData インスタンスのいずれかを返す必要があります。

    def call(
        self,
        data: AkariData,
        params: MyCustomModuleParams, # 具体的なParamsデータクラスに置き換えます
        callback: AkariModuleType | None = None
    ) -> AkariDataSet | AkariData:
        self._logger.debug(f"MyCustomModule 'call' invoked with data: {data}, params: {params}")

        # --- ここにモジュールのロジックを記述 ---
        # 例: 最後のデータセットからテキストと音声データにアクセス
        input_text = "Default"
        input_audio_bytes: bytes | None = None
        audio_meta: dict[str, Any] | None = None

        if data.datasets: # data.datasetsが空でないことを確認
            last_dataset = data.last()
            if last_dataset.text: # last_dataset.textがNoneでないことを確認
                input_text = last_dataset.text.main
            if last_dataset.audio: # last_dataset.audioがNoneでないことを確認
                input_audio_bytes = last_dataset.audio.main
                # 音声ストリームがある場合は、最後の要素を取得することも可能
                # if last_dataset.audio.stream:
                #     input_audio_bytes = last_dataset.audio.stream.last()
            if last_dataset.meta: # last_dataset.metaがNoneでないことを確認
                audio_meta = last_dataset.meta.main
                self._logger.info(f"Input audio metadata: {audio_meta}")


        # 結果用の新しいデータセットを作成
        result_dataset = AkariDataSet()
        # AkariDataSetTypeを使用して型付けされたデータを設定
        result_dataset.text = AkariDataSetType(main=f"Processed: {input_text} with param1: {params.my_setting_1}, param2: {params.my_setting_2}")

        if input_audio_bytes:
            # 何らかの音声処理を行う (例: 音量を2倍にする - これはダミー処理です)
            processed_audio_bytes = input_audio_bytes # ここで実際の処理を行う
            result_dataset.audio = AkariDataSetType(main=processed_audio_bytes)
            # 新しい音声メタデータを設定
            result_dataset.meta = AkariDataSetType(main={
                "processed": True,
                "original_sample_rate": audio_meta.get("rate") if audio_meta else params.sample_rate,
                "new_sample_rate": params.sample_rate, # パラメータから取得
                "channels": audio_meta.get("channels") if audio_meta else 1,
            })
        else:
            # 音声データがない場合の処理
            result_dataset.meta = AkariDataSetType(main={"message": "No input audio data."})


        # モジュールが単に1つのデータセットを追加する場合:
        return result_dataset

        # または、AkariDataオブジェクトをより広範囲に変更する場合:
        # data.add(result_dataset)
        # return data

4. (オプション) stream_call メソッドの実装
   モジュールがストリーミング操作（データのチャンク処理やリアルタイムイベントの処理など）をサポートする必要がある場合は、stream_call メソッドをオーバーライドします。実装されていない場合、デフォルトで NotImplementedError が発生します。

パラメータと戻り値は call メソッドに似ていますが、ロジックは通常、より小さなデータ片を処理し、中間結果で callback モジュールを呼び出すことを含みます。音声ストリームを扱う場合、AkariDataStreamType が役立ちます。

    def stream_call(
        self,
        data: AkariData,
        params: MyCustomModuleParams, # 具体的なParamsデータクラスに置き換えます
        callback: AkariModuleType | None = None
    ) -> AkariDataSet | AkariData:
        self._logger.debug(f"MyCustomModule 'stream_call' invoked with data: {data}, params: {params}")

        if not callback:
            raise ValueError("Callback must be provided for stream_call in MyCustomModule")

        # --- ここにモジュールのストリーミングロジックを記述 ---
        # 例: 音声ストリームのチャンクを処理し、コールバックを呼び出す
        if data.datasets and data.last().audio and data.last().audio.stream:
            audio_chunk = data.last().audio.stream.last() # 最新の音声チャンク
            # 何らかの処理 (例: VADなど)
            processed_info = f"Processed audio chunk of length {len(audio_chunk)}"

            intermediate_dataset = AkariDataSet()
            intermediate_dataset.text = AkariDataSetType(main=processed_info)
            # 必要に応じて、処理済み音声チャンクをコールバックに渡す
            # intermediate_dataset.audio = AkariDataSetType(main=processed_audio_chunk)

            data_for_callback = AkariData()
            data_for_callback.add(intermediate_dataset)

            self._router.callModule(
                moduleType=callback,
                data=data_for_callback,
                params=params, # またはコールバック固有のパラメータ
                streaming=True
            )

        # 最終結果または累積結果を返す
        final_dataset = AkariDataSet()
        final_dataset.text = AkariDataSetType(main="Stream processing ongoing or complete.")
        return final_dataset

ストリーミング用に設計されたモジュールの例については、modules.audio.mic.\_MicModule や modules.webrtcvad.vad.\_WebRTCVadModule を参照してください。これらは AkariDataStreamType を使用して音声チャンクを扱います。

5. (オプション) パラメータデータクラスの定義
   複雑なパラメータの場合、専用のデータクラスを定義することをお勧めします。これにより、型ヒントと構成管理が向上します。多くの既存モジュールがこのパターンを使用しています（例: azure_openai.llm.\_LLMModuleParams、audio.mic.\_MicModuleParams）。
   ステップ 1 で既に MyCustomModuleParams として例を示しました。AkariModuleParams を継承することが推奨されます。

6. AkariData および AkariDataSet との対話
   データの読み取り:

通常、モジュールは data.last()を使用して AkariData に追加された最後のデータセットにアクセスします。

data.datasets が空でないことを常に確認してください（例: if data.datasets:）。

テキスト: data.last().text.main (存在すれば)

音声:

バイトデータ: data.last().audio.main (存在すれば)

ストリームデータ: data.last().audio.stream (存在すれば)。AkariDataStreamType[bytes]のインスタンスで、last()メソッドで最新のチャンクを取得したり、イテレートしたりできます。

modules.audio.mic.\_MicModule は、dataset.audio = AkariDataSetType(main=b"".join(frames), stream=AkariDataStreamType(frames))のように、完全な音声とストリームの両方を提供します。

メタデータ: data.last().meta.main (存在すれば)。これは通常、辞書型 (dict[str, Any]) です。

音声メタデータの読み取り例:

if data.datasets and data.last().meta:
meta_content = data.last().meta.main
sample_rate = meta_content.get("rate")
channels = meta_content.get("channels")
sample_width = meta_content.get("sample_width")
self.\_logger.info(f"Audio Info - Rate: {sample_rate}, Channels: {channels}, Width: {sample_width}")

データの書き込み:

新しい AkariDataSet インスタンスを作成します。

そのフィールド（例: dataset.text = AkariDataSetType(main="...")）を設定します。

音声:

バイトデータ: dataset.audio = AkariDataSetType(main=audio_bytes)

ストリームデータ: dataset.audio = AkariDataSetType(main=full_audio_bytes, stream=AkariDataStreamType(list_of_audio_chunks))

メタデータ: dataset.meta = AkariDataSetType(main={"key": "value"})

音声メタデータの書き込み例:

result_dataset.meta = AkariDataSetType(main={
"rate": 16000,
"channels": 1,
"sample_width": 2, # PyAudio の pyaudio.paInt16 の場合など
"format": "wav", # 任意
})
```modules.io.save._SaveModule` は、WAV ファイルを保存する際にこのメタデータ（特に "channels", "sample_width", "rate"）を参照します。

モジュールの call または stream_call メソッドが AkariDataSet を返す場合、AkariRouter はこのデータセットで自動的に setModule を呼び出し（実行メタデータを記録するため）、それをメインの AkariData オブジェクトに追加します。

メソッドが AkariData オブジェクトを返す場合、モジュールがすでにデータセットの追加を管理していると見なされ、ルーターは result.last()で setModule を呼び出します。

7. ロガーとルーターの使用
   ロガー: self.\_logger を使用して、情報、デバッグメッセージ、またはエラーをログに記録します（例: self.\_logger.info("Processing started")、self.\_logger.error("An error occurred")）。

ルーター: モジュールが他の Akari モジュールを直接呼び出す必要がある場合（ストリーミングシナリオでのコールバックやサブタスクなど）、self.\_router.callModule(...)を使用します。

例: sample.module.\_SampleModule
提供されている sample.module.\_SampleModule は最小限の例です。

from akari import (
AkariData,
AkariDataSet,
AkariLogger,
AkariModule,
AkariModuleParams,
AkariModuleType,
AkariRouter,
)

class \_SampleModule(AkariModule):
def **init**(self, router: AkariRouter, logger: AkariLogger) -> None:
super().**init**(router, logger)

    def call(self, data: AkariData, params: AkariModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        self._logger.debug("SampleModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)
        self._logger.debug("Callback: %s", callback)
        return AkariDataSet()

このモジュールは重要な処理を実行しませんが、基本的な構造を示しています。受信したデータとパラメータをログに記録し、空の AkariDataSet を返します。

モジュールの登録
モジュールを作成した後、メインアプリケーションスクリプト（例: main.py）で AkariRouter に登録して呼び出せるようにする必要があります。

モジュールをインポートします:

# main.py 内

# from my_module_directory import MyCustomModule # モジュールが別のディレクトリにある場合

# from modules.my_custom_module import MyCustomModule # modules/my_custom_module.py にあると仮定

# 例:

# from modules.custom import MyCustomModule

# from modules.custom import MyCustomModuleParams # パラメータクラスもインポート

ルーターの初期化時にモジュールを追加します:
main.py の akariRouter.addModules(...)呼び出しを見つけ、新しいモジュールとそのインスタンスを辞書に追加します。

# main.py 内

# ... (他のインポートと初期化) ...

# akariRouter = akari.AkariRouter(logger=akariLogger) # 既存の行

# akariRouter.addModules(

# {

# modules.RootModule: modules.RootModule(akariRouter, akariLogger),

# modules.PrintModule: modules.PrintModule(akariRouter, akariLogger),

# # ... 他の既存モジュール ...

# MyCustomModule: MyCustomModule(akariRouter, akariLogger), # 新しいモジュールを追加

# }

# )

main.py の既存の構造に従って、MyCustomModule を適切な場所（例: modules ディレクトリ内）に配置し、modules/**init**.py で公開することを検討してください。

例えば、modules/custom/**init**.py を作成し、以下を記述します:

from .my_custom_module import MyCustomModule
from .my_custom_module import MyCustomModuleParams

**all** = ["MyCustomModule", "MyCustomModuleParams"]

そして modules/**init**.py で custom モジュールをエクスポートします:

# modules/**init**.py

# ...

from . import custom

# ...

# **all**に custom.MyCustomModule などを追加するか、main.py で直接 custom.MyCustomModule を使用

その後 main.py で以下のようにインポートして登録します:

# main.py

import modules # または from modules import custom

# ...

akariRouter.addModules(
{ # ...
modules.custom.MyCustomModule: modules.custom.MyCustomModule(akariRouter, akariLogger), # ...
}
)

モジュールの呼び出し
登録後、AkariRouter の callModule メソッドを使用して、他のモジュールから、またはパイプラインの開始点として、カスタムモジュールを呼び出すことができます。

# main.py または他のモジュール内

# initial_data = akari.AkariData()

# # 必要に応じて初期データセットを initial_data に追加

#

# module_params = MyCustomModuleParams(my_setting_1="hello", my_setting_2=123, sample_rate=24000)

#

# resulting_data = akariRouter.callModule(

# moduleType=MyCustomModule, # または modules.custom.MyCustomModule

# data=initial_data,

# params=module_params,

# streaming=False, # または True (stream_call を実装した場合)

# callback=None # または適切なコールバックモジュール

# )

これで、Akari フレームワーク内で独自のカスタムモジュールを作成して使用する準備が整いました。
