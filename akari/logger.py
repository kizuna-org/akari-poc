import logging
import sys

_AkariLogger = logging.Logger


def _getLogger(name: str, level: int = logging.DEBUG) -> _AkariLogger:
    """Akari フレームワーク内で使用するためのカスタマイズされたロガーインスタンスを設定して提供します。

    指定された名前と重要度レベルでロガーを作成します。Akari を使用するアプリケーションが
    ロギングを設定しない場合に「ハンドラーが見つかりませんでした」という警告を防ぐために、
    デフォルトで `NullHandler` が追加されます。さらに、`StreamHandler` が
    `sys.stdout` にログメッセージを出力するように設定され、同じ指定された
    ロギングレベルを使用します。

    Args:
        name (str): ロガーの希望の名前（例: "Akari.Router"）。
        level (int): ロガーが処理する最小ロギングレベル（例:
            `logging.DEBUG`、`logging.INFO`）。デフォルトは `logging.DEBUG` です。

    Returns:
        _AkariLogger: 完全に設定されたロガーインスタンス。
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(logging.NullHandler())

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    logger.addHandler(handler)
    return logger
