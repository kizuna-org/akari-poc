import ast
from typing import Iterator


class NoPrintChecker:
    error_code = "N800"
    message_template = "{} print文が見つかりました。ログを使用することを検討してください。"

    def __init__(self, tree: ast.AST, filename: str) -> None:
        self.tree: ast.AST = tree
        self.filename: str = filename

    @property
    def message(self) -> str:
        return self.message_template.format(self.error_code)

    def run(self) -> Iterator[tuple[int, int, str, type]]:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                yield node.lineno, node.col_offset, self.message, type(self)
