from typing import Any, Dict, Generic, TypeVar

T = TypeVar("T")


class AkariDataSetType(Generic[T]):
    def __init__(self, main: T, others: Dict[str, T] | None = None) -> None:
        self.main = main
        self.others = others if others is not None else {}


class AkariDataSet:
    def __init__(self) -> None:
        self.text: AkariDataSetType[str] | None = None
        self.audio: AkariDataSetType[bytes] | None = None
        self.allData: Any | None = None


class AkariData:
    def __init__(self) -> None:
        self.datasets: list[AkariDataSet] = []

    def add(self, dataset: AkariDataSet) -> None:
        self.datasets.append(dataset)

    def get(self, index: int) -> AkariDataSet:
        if index < 0 or index >= len(self.datasets):
            raise IndexError("Index out of range")
        return self.datasets[index]

    def last(self) -> AkariDataSet:
        if not self.datasets:
            raise IndexError("No datasets available")
        return self.datasets[-1]

    def __getitem__(self, index: int) -> AkariDataSet:
        return self.get(index)

    def __len__(self) -> int:
        return len(self.datasets)
