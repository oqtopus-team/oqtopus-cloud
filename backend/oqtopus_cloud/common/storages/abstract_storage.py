from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any, Callable, Iterator, List, TypeVar

R = TypeVar("R")


class AbstractStorage(ABC):
    @abstractmethod
    def get(self, key: str) -> bytes | None: ...

    @abstractmethod
    def put(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def prefix(self, prefix: str) -> Iterator[str]: ...

    @abstractmethod
    def is_file(self, key: str) -> bool: ...

    @abstractmethod
    def is_directory(self, key: str) -> bool: ...

    @abstractmethod
    def does_exist(self, key: str) -> bool: ...

    def traverse_prefix(self, prefix: str, action: Callable[[str], R]) -> List[R]:
        results: List[R] = []
        for path in self.prefix(prefix):
            result = action(path)
            results.append(result)
        return results

    @abstractmethod
    def get_upload_presigned_url_data(
        self, key: str, expires: timedelta = timedelta(hours=1)
    ) -> dict[str, Any]: ...

    @abstractmethod
    def get_download_presigned_url(
        self, key: str, expires: timedelta = timedelta(hours=1)
    ) -> str: ...
