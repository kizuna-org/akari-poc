from typing import Dict, Generic, TypeVar

T = TypeVar("T")


class AkariDataSetType(Generic[T]):
    def __init__(self, main: T, others: Dict[str, T]) -> None:
        self.main = main
        self.others = others


class AkariDataSet:
    def __init__(self) -> None:
        self.text: AkariDataSetType[str] | None = None


class AkariData:
    def __init__(self, last: AkariDataSet) -> None:
        self.last = last
