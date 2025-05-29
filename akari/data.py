import dataclasses
from typing import Any, Dict, Generic, TypeVar

from akari.module import _AkariModuleParams, _AkariModuleType

T = TypeVar("T")


class _AkariDataStreamType(Generic[T]):
    """Manages a sequence of data points, typically representing deltas or chunks within a stream.

    Allows for typed data streams, ensuring that all elements within a stream
    are of a consistent type. Provides basic operations like accessing the last
    element, getting the length, and retrieving elements by index.

    Attributes:
        _delta (list[T]): Stores the sequence of data points. The name `_delta`
            suggests that these points might represent changes or increments,
            but it can hold any sequence of data.
    """

    def __init__(self, delta: list[T]) -> None:
        """Constructs a new data stream instance.

        Args:
            delta (list[T]): The initial list of data points to populate the stream.
        """
        self._delta = delta

    def last(self) -> T:
        """Fetches the most recently added data point in the stream.

        Returns:
            T: The last data point.

        Raises:
            IndexError: If the stream contains no elements.
        """
        if not self._delta:
            raise IndexError("No history available")
        return self._delta[-1]

    def __len__(self) -> int:
        """Computes the total number of data points currently in the stream.

        Returns:
            int: The count of data points.
        """
        return len(self._delta)

    def __getitem__(self, index: int) -> T:
        """Accesses a data point at a specific position (index) in the stream.

        Args:
            index (int): The zero-based index of the desired data point.

        Returns:
            T: The data point located at the specified index.

        Raises:
            IndexError: If the provided index is outside the valid range of the stream.
        """
        if index < 0 or index >= len(self._delta):
            raise IndexError("Index out of range")
        return self._delta[index]

    def __repr__(self) -> str:
        """Generates a developer-friendly string representation of the data stream.

        Returns:
            str: A string showing the class name and the internal delta list.
        """
        return f"AkariDataStreamType(delta={self._delta})"

    def __eq__(self, value: object) -> bool:
        """Determines if this data stream is equivalent to another object.

        Equality is based on whether the other object is also an `_AkariDataStreamType`
        and if their internal `_delta` lists are identical.

        Args:
            value (object): The object to compare against this stream.

        Returns:
            bool: True if the objects are considered equal, False otherwise.
        """
        if not isinstance(value, _AkariDataStreamType):
            return NotImplemented
        return self._delta == value._delta


@dataclasses.dataclass
class _AkariDataModuleType:
    """Encapsulates metadata detailing the execution context of an Akari module that generated a specific dataset.

    Provides crucial information for tracing data provenance and understanding
    the pipeline's behavior.

    Attributes:
        moduleType: The specific type (class) of the Akari module that was executed.
        params: The parameters instance passed to the module during its execution.
        streaming (bool): Indicates if the module was invoked in a streaming context.
        callback (Optional[_AkariModuleType]): The type of the callback module, if one was
            configured for the executed module.
        startTime (float): The timestamp (from `time.process_time()`) marking the
            beginning of the module's execution.
        endTime (float): The timestamp (from `time.process_time()`) marking the
            completion of the module's execution.
    """

    moduleType: _AkariModuleType
    params: _AkariModuleParams
    streaming: bool
    callback: _AkariModuleType | None
    startTime: float
    endTime: float


class _AkariDataSetType(Generic[T]):
    """Provides a structured container for a specific type of data within an AkariDataSet.

    It holds a primary data payload (`main`), an optional associated stream
    (`stream`), and a dictionary for any other related data points (`others`).
    This generic class allows for type safety for these components.

    Attributes:
        main (T): The primary data artifact (e.g., a string of text, a block of audio bytes).
        stream (Optional[_AkariDataStreamType[T]]): An optional stream of data related
            to `main`. For instance, if `main` is a complete audio transcription,
            `stream` might contain incremental speech segments.
        others (Dict[str, T]): A dictionary for storing additional, named data points
            of the same type `T` that are contextually related to `main`.
    """

    def __init__(
        self,
        main: T,
        stream: _AkariDataStreamType[T] | None = None,
        others: Dict[str, T] | None = None,
    ) -> None:
        """Constructs a new typed data set.

        Args:
            main (T): The primary data point for this set.
            stream (Optional[_AkariDataStreamType[T]]): An optional stream of related
                data points. Defaults to None if not provided.
            others (Optional[Dict[str, T]]): A dictionary of other named data points
                of the same type `T`. Defaults to an empty dictionary if not provided.
        """
        self.main = main
        self.stream = stream
        self.others = others if others is not None else {}

    def __repr__(self) -> str:
        """Generates a developer-friendly string representation of the typed data set.

        Returns:
            str: A string showing the class name and its `main`, `stream`, and `others` attributes.
        """
        return f"AkariDataSetType(main={self.main}, stream={self.stream}, others={self.others})"

    def __eq__(self, value: object) -> bool:
        """Determines if this typed data set is equivalent to another object.

        Equality requires the other object to be an `_AkariDataSetType` and for
        their `main`, `stream`, and `others` attributes to be respectively equal.

        Args:
            value (object): The object to compare against this typed data set.

        Returns:
            bool: True if the objects are considered equal, False otherwise.
        """
        if not isinstance(value, _AkariDataSetType):
            return NotImplemented
        return self.main == value.main and self.stream == value.stream and self.others == value.others


class _AkariDataSet:
    """Aggregates various types of data (text, audio, boolean, metadata) produced by a single module execution.

    It also stores metadata about the module execution itself. This class acts as a
    standardized container for data passed between modules in an Akari pipeline.

    Attributes:
        module (_AkariDataModuleType): Metadata about the module that generated this dataset.
            This is typically set by the AkariRouter after a module executes.
        text (Optional[_AkariDataSetType[str]]): Holds string-based data.
        audio (Optional[_AkariDataSetType[bytes]]): Holds byte-based audio data.
        bool (Optional[_AkariDataSetType[bool]]): Holds boolean data.
        meta (Optional[_AkariDataSetType[dict[str, Any]]]): Holds dictionary-based
            metadata, often used for details like audio sampling rates or content types.
        allData (Any | None): A flexible field for storing any other type of data
            that doesn't fit the predefined categories, such as raw API responses.
    """

    module: _AkariDataModuleType | None = None

    def __init__(self) -> None:
        """Constructs an empty AkariDataSet, ready to be populated by a module."""
        self.text: _AkariDataSetType[str] | None = None
        self.audio: _AkariDataSetType[bytes] | None = None
        self.bool: _AkariDataSetType[bool] | None = None
        self.meta: _AkariDataSetType[dict[str, Any]] | None = None
        self.allData: Any | None = None

    def setModule(self, module: _AkariDataModuleType) -> None:
        """Attaches module execution metadata to this dataset.

        Allows the AkariRouter to associate a dataset with the module that
        created it and the parameters under which it ran. This association is crucial
        for data lineage and debugging.

        Args:
            module (_AkariDataModuleType): The metadata object describing the
                module's execution context.
        """
        self.module = module


class _AkariData:
    """Orchestrates a sequence of datasets, representing the state and flow of data through an Akari processing pipeline.

    Modules in a pipeline typically receive an `_AkariData` instance, can inspect
    previous datasets (especially the last one), and append new `_AkariDataSet`
    instances to it as they produce results.

    Attributes:
        datasets (list[_AkariDataSet]): An ordered list of datasets. New datasets
            are appended to the end of this list.
    """

    def __init__(self) -> None:
        """Constructs an AkariData instance with an initially empty list of datasets."""
        self.datasets: list[_AkariDataSet] = []

    def add(self, dataset: _AkariDataSet) -> None:
        """Appends a new dataset to the end of the current sequence.

        Args:
            dataset (_AkariDataSet): The dataset to be added.
        """
        self.datasets.append(dataset)

    def get(self, index: int) -> _AkariDataSet:
        """Fetches a dataset from the sequence by its zero-based index.

        Args:
            index (int): The index of the dataset to retrieve.

        Returns:
            _AkariDataSet: The dataset located at the specified index.

        Raises:
            IndexError: If the index is outside the valid range of the dataset list.
        """
        if index < 0 or index >= len(self.datasets):
            raise IndexError("Index out of range")
        return self.datasets[index]

    def last(self) -> _AkariDataSet:
        """Accesses the most recently added dataset in the sequence.

        Returns:
            _AkariDataSet: The last dataset in the list.

        Raises:
            IndexError: If the list of datasets is empty.
        """
        if not self.datasets:
            raise IndexError("No datasets available")
        return self.datasets[-1]

    def __getitem__(self, index: int) -> _AkariDataSet:
        """Enables dataset retrieval using subscript notation (e.g., `akari_data[i]`).

        Args:
            index (int): The index of the dataset to retrieve.

        Returns:
            _AkariDataSet: The dataset at the specified index.
        """
        return self.get(index)

    def __len__(self) -> int:
        """Calculates the total number of datasets currently in the sequence.

        Returns:
            int: The count of datasets.
        """
        return len(self.datasets)
