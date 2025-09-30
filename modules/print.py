import json
from typing import Any

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
    AkariModule,
    AkariModuleType,
    AkariRouter,
)


class _PrintModule(AkariModule):
    """AkariData シーケンスの最新のデータセットの内容をログに記録するデバッグユーティリティを提供します。

    その主な機能は、Akari パイプラインの特定のポイントでのデータ構造と内容に関する
    開発者の洞察を提供することです。可能な場合は JSON 表現を含む最後のデータセットの
    さまざまな側面と個々のフィールドをログに記録します。
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """PrintModule インスタンスを構築します。

        Args:
            router (AkariRouter): Akari ルーターインスタンス。潜在的なモジュール間通信に使用されます
                （ただし、このモジュールの現在の実装では基本クラスを超えて直接使用されません）。
            logger (AkariLogger): データセット情報が書き込まれるロガーインスタンス。
        """
        super().__init__(router, logger)

    def call(self, data: AkariData, params: Any, callback: AkariModuleType | None = None) -> AkariDataSet:
        """提供された AkariData オブジェクト内の最後の AkariDataSet の内容を検査してログに記録します。

        このメソッドはまず、包括的な概要のために最後のデータセット全体を JSON 文字列に
        シリアル化しようとします。シリアル化が失敗した場合（たとえば、バイトなどの
        シリアル化不可能なデータのため）、データセットの生の文字列表現のログ記録にフォールバックします。

        その後、最後のデータセットのすべての属性を反復処理します。`AkariDataSetType` の
        インスタンスであり、None でない `main` 値を持つ属性の場合、フィールド名とこの `main` 値を
        ログに記録します。他の None でない属性の場合、フィールド名と値を直接ログに記録します。

        Args:
            data (AkariData): データセットのシーケンスを含む AkariData オブジェクト。
                このシーケンスの最後のデータセットが検査対象です。
            params (Any): このモジュールのパラメータ。現在、これらのパラメータはログに記録されますが、
                モジュールのロジックではそれ以外には使用されません。
            callback (Optional[AkariModuleType]): オプションのコールバックモジュール。
                現在、このパラメータはログに記録されますが、使用されません。

        Returns:
            AkariDataSet: 検査されたものと同じ最後のデータセット。このモジュールはデータを変更しません。
        """
        self._logger.debug("PrintModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        last = data.last()
        try:
            self._logger.info("Last Data: %s", json.dumps(last, indent=4))
        except:
            self._logger.info("Last Data: %s", last)

        for field in last.__dict__:
            if hasattr(last, field) and field != "module":
                value = getattr(last, field)
                if isinstance(value, AkariDataSetType):
                    if value.main is not None:
                        self._logger.info("%s: %s", field, value.main)
                else:
                    if value is not None:
                        self._logger.info("%s: %s", field, value)

        return data.last()

    def stream_call(self, data: AkariData, params: Any, callback: AkariModuleType | None = None) -> AkariDataSet:
        """非ストリーミング `call` メソッドと同じロギングロジックを適用してストリーミングデータを処理します。

        このモジュールは、ストリーミングコールと非ストリーミングコールを同じように扱い、
        受信した最後のデータセットの内容をログに記録します。

        Args:
            data (AkariData): AkariData オブジェクト。通常、ストリームの最新のチャンクまたは
                セグメントを最後のデータセットとして含みます。
            params (Any): このモジュールのパラメータ（ログに記録されますが、使用されません）。
            callback (Optional[AkariModuleType]): オプションのコールバックモジュール
                （ログに記録されますが、使用されません）。

        Returns:
            AkariDataSet: 入力 AkariData オブジェクトの最後のデータセット。
        """
        return self.call(data, params, callback)
