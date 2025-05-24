from akari import (
    AkariData,
    AkariDataSet,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


class _RootModule(AkariModule):
    """Akari データ処理パイプラインのエントリポイントまたは開始トリガーとして機能します。

    主な責務は、一連のモジュール実行を開始することです。
    これは、モジュールタイプをパラメータとして受け取り、AkariRouter を使用して
    その初期モジュールを呼び出すことによって行われます。通常、それ自体はデータ処理を実行せず、
    他のモジュールに委任します。
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """RootModule インスタンスを構築します。

        Args:
            router (AkariRouter): Akari ルーターインスタンス。パイプラインの最初のモジュールを
                呼び出すために不可欠です。
            logger (AkariLogger): モジュールのアクティビティとデバッグ情報を記録するための
                ロガーインスタンス。
        """
        super().__init__(router, logger)

    def call(self, data: AkariData, params: AkariModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        """最初の処理モジュールを呼び出すことによって Akari パイプラインを開始します。

        この RootModule の `call` メソッドの `params` 引数は、最初に実行する必要がある
        Akari モジュールのタイプ（クラス）として一意に解釈されます。ルーターはその後、
        このターゲットモジュールを呼び出すように指示され、初期 `data` と任意の `callback` を渡します。
        RootModule 自体は、その役割が純粋にオーケストレーションであるため、空の `AkariDataSet` を返します。

        Args:
            data (AkariData): パイプラインの初期 AkariData インスタンス。
                新しいシーケンスを開始する場合、通常は空です。
            params (AkariModuleParams): パイプラインで最初に実行される AkariModuleType（クラス）
                であることが期待されます。これは `router.callModule` の `moduleType` 引数として
                使用されます。
            callback (Optional[AkariModuleType]): 最初のモジュールの実行に渡される
                オプションのコールバックモジュールタイプ。

        Returns:
            AkariDataSet: 空の `AkariDataSet`。パイプラインの実際の結果は、
            後続のモジュール呼び出しを通じて渡される `AkariData` オブジェクト内に
            蓄積されることが期待されます。
        """
        self._logger.debug("RootModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)
        self._router.callModule(moduleType=params, data=data, params=None, streaming=False, callback=callback)

        return AkariDataSet()
