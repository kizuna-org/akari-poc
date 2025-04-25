from typing import Any, Dict, Generic, TypeVar

T = TypeVar("T")


class AkariDataStreamType(Generic[T]):
    def __init__(self, delta: list[T]) -> None:
        self._delta = delta

    def last(self) -> T:
        if not self._delta:
            raise IndexError("No history available")
        return self._delta[-1]

    def __len__(self) -> int:
        return len(self._delta)

    def __getitem__(self, index: int) -> T:
        if index < 0 or index >= len(self._delta):
            raise IndexError("Index out of range")
        return self._delta[index]

    def __repr__(self) -> str:
        return f"AkariDataStreamType(delta={self._delta})"


class AkariDataSetType(Generic[T]):
    def __init__(
        self, main: T, stream: AkariDataStreamType[T] | None = None, others: Dict[str, T] | None = None
    ) -> None:
        self.main = main
        self.stream = stream
        self.others = others if others is not None else {}

    def __repr__(self) -> str:
        return f"AkariDataSetType(main={self.main}, stream={self.stream}, others={self.others})"


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
