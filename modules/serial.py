import dataclasses

from akari import (
    AkariData,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _SerialModuleParamModule:
    """SerialModule によって管理されるシーケンス内で実行するための単一の Akari モジュールの設定を指定します。

    このクラスの各インスタンスは、実行するモジュール、受信するパラメータ、
    およびシーケンス内の実行に関連付ける特定のコールバックモジュールがあるかどうかを詳細に示します。

    Attributes:
        moduleType (AkariModuleType): 実行する Akari モジュールのクラスタイプ。
        moduleParams (AkariModuleParams): `moduleType` の `call` または `stream_call` メソッドに
            渡される特定のパラメータインスタンス。
        moduleCallback (Optional[AkariModuleType]): 実行されたモジュールへのコールバックとして
            渡されるオプションの Akari モジュールタイプ。デフォルトは None で、
            このステップの特定のコールバックオーバーライドがないことを示します。
    """

    moduleType: AkariModuleType
    moduleParams: AkariModuleParams
    moduleCallback: AkariModuleType | None = None


@dataclasses.dataclass
class _SerialModuleParams:
    """SerialModule が実行するモジュール設定の順序付きリストが含まれています。

    プライマリアトリビュート `modules` はリストを保持し、各要素は
    `_SerialModuleParamModule` のインスタンスであり、シリアル実行チェーンの 1 ステップを定義します。

    Attributes:
        modules (list[_SerialModuleParamModule]): モジュール実行定義の順序付きリスト。
            SerialModule はこのリストを反復処理し、定義された各モジュールを
            指定された順序で実行します。
    """

    modules: list[_SerialModuleParamModule]


class _SerialModule(AkariModule):
    """事前定義された Akari モジュールのリストの実行を厳密なシーケンシャル順序で調整します。

    このモジュールは、モジュール設定（タイプ、パラメータ、およびオプションのコールバック）のリストを取得し、
    AkariRouter を使用してそれぞれを呼び出します。1 つのモジュールからの出力 `AkariData` は、
    次のモジュールの入力となり、効果的にそれらを連鎖させます。
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """SerialModule インスタンスを構築します。

        Args:
            router (AkariRouter): Akari ルーターインスタンス。定義されたシーケンス内の各モジュールを
                呼び出すために必要です。
            logger (AkariLogger): 操作の詳細とデバッグ情報を記録するためのロガーインスタンス。
        """
        super().__init__(router, logger)

    def call(self, data: AkariData, params: _SerialModuleParams, callback: AkariModuleType | None = None) -> AkariData:
        """設定された Akari モジュールのリストを介して AkariData オブジェクトを順番に渡すことによって処理します。

        `params.modules` で定義された各モジュールについて、このメソッドは AkariRouter を使用して
        モジュールを呼び出します。`AkariData` オブジェクトは各モジュール呼び出しの結果で更新され、
        その後、後続のモジュールへの入力として渡されます。この `call` メソッドに渡された
        `callback` 引数は、シーケンスの実行中に SerialModule 自体では使用されません。

        Args:
            data (AkariData): シーケンスの最初のモジュールによって処理される初期 AkariData オブジェクト。
            params (_SerialModuleParams): 実行するモジュールとそのそれぞれのパラメータおよび
                コールバックを定義する `_SerialModuleParamModule` インスタンスのリストを含むオブジェクト。
            callback (Optional[AkariModuleType]): オプションのコールバックモジュール。
                このパラメータは現在、SerialModule のオーケストレーションロジックでは利用されていません。

        Returns:
            AkariData: 設定されたシーケンスのすべてのモジュールによって処理された後の AkariData オブジェクト。
        """
        for module in params.modules:
            data = self._router.callModule(
                moduleType=module.moduleType,
                data=data,
                params=module.moduleParams,
                callback=module.moduleCallback,
                streaming=False,
            )

        return data

    def stream_call(
        self, data: AkariData, params: _SerialModuleParams, callback: AkariModuleType | None = None
    ) -> AkariData:
        """設定されたモジュールを介して AkariData オブジェクトを順番に処理し、非ストリーミング `call` の動作をミラーリングします。

        `stream_call` という名前ですが、この実装は現在、モジュールのシーケンスを反復処理し、
        それぞれを非ストリーミング方式で呼び出します（つまり、`streaming=False` がルーターに渡されます）。
        シーケンス全体の真のストリーミング動作はここでは実装されていません。
        シーケンス内の個々のモジュールは、ルーターによって `stream_call` が呼び出された場合
        （ここではそうではありません）、独自のストリーミングを実行する場合があります。

        Args:
            data (AkariData): 初期 AkariData オブジェクト。
            params (_SerialModuleParams): `call` メソッドと同じ、モジュールのシーケンスを定義するパラメータ。
            callback (Optional[AkariModuleType]): オプションのコールバックモジュール。
                渡されますが、このメソッドのシーケンシャルロジックでは直接使用されません。

        Returns:
            AkariData: シーケンスのすべてのモジュールによる処理後の AkariData オブジェクト。
        """
        for module in params.modules:
            data = self._router.callModule(
                moduleType=module.moduleType,
                data=data,
                params=module.moduleParams,
                callback=module.moduleCallback,
                streaming=False,
            )

        return data
