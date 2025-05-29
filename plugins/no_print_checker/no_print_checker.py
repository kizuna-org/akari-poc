"""Plugin to check for print statements."""

import ast
from collections.abc import Iterator


class NoPrintChecker:
    """Checks for the presence of print statements."""

    error_code = "N800"
    message_template = "{} print文が見つかりました。ログを使用することを検討してください。"

    def __init__(self, tree: ast.AST, filename: str) -> None:
        """Initialize the checker with the AST tree and filename."""
        self.tree: ast.AST = tree
        self.filename: str = filename

    @property
    def message(self) -> str:
        """Return the formatted error message."""
        return self.message_template.format(self.error_code)

    def run(self) -> Iterator[tuple[int, int, str, type]]:
        """Run the checker and yield errors found."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                yield node.lineno, node.col_offset, self.message, type(self)
