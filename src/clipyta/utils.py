from typing import Any, Callable, TypedDict, TypeVar, Generic, SupportsIndex
from dataclasses import dataclass, field
from enum import IntEnum, auto

T = TypeVar('T')


class Alignment(IntEnum):
    """
    An enumeration representing horizontal text alignment strategies for rendering table cells.

    Provides predefined alignment states and a helper method to map these states 
    to their corresponding Python string alignment functions (`str.center`, `str.ljust`, `str.rjust`).

    Members:
        center: Aligns text to the middle of the cell.
        left: Aligns text to the left side of the cell.
        right: Aligns text to the right side of the cell.

    Example:
        >>> align_strategy = Alignment.left
        >>> print(align_strategy.name)
        'left'
    """
    center = auto()
    left = auto()
    right = auto()

    def align(self, value: str):
        """
        Resolves and returns the correct string alignment method corresponding to the active enum state.

        Args:
            value (str): The string value that will serve as the target for the alignment function.

        Returns:
            Callable[[int], str]: A bound Python string method (`str.center`, `str.ljust`, or `str.rjust`) 
                that accepts an integer width argument and returns the aligned string.

        Example:
            >>> align_func = Alignment.left.align("Test")
            >>> align_func(10)
            'Test      '
        """
        match self:
            case Alignment.center:
                return value.center
            case Alignment.left:
                return value.ljust
            case Alignment.right:
                return value.rjust


@dataclass
class SortConfig(Generic[T]):
    """
    A generic configuration wrapper for sorting operations.

    Bundles a sorting callable (the key function) with a boolean flag indicating 
    whether the sort order should be reversed. This allows the renderer to easily 
    store and apply complex, user-defined sorting rules for both rows and columns.

    Type Variables:
        T: The type of the elements being sorted (e.g., `str` for columns, `dict` for rows).

    Attributes:
        sort (Callable[[T], int]): The function used to extract a comparison key from each element.
        reverse (bool): If True, the sorted list is reversed (descending order). Defaults to False.

    Example:
        >>> # Configuring a reverse-alphabetical sort for strings
        >>> config = SortConfig[str](sort=lambda x: x, reverse=True)
    """
    sort: Callable[[T], int]
    reverse: bool = field(default_factory=lambda: False)


class BorderConfig(TypedDict):
    """
    A typed dictionary defining the structural characters used to draw the ASCII table borders.

    Attributes:
        vertical (str): The character used for standard vertical column separators.
        vertical_bold (str): The character used for the outer vertical edges of the table.
        horizontal (str): The character used for standard horizontal row separators.
        horizontal_bold (str): The character used for the primary horizontal borders (e.g., framing the header).

    Example:
        >>> minimal_borders: BorderConfig = {
        ...     "vertical": " ",
        ...     "vertical_bold": "",
        ...     "horizontal": "",
        ...     "horizontal_bold": "-"
        ... }
    """
    vertical: str
    vertical_bold: str
    horizontal: str
    horizontal_bold: str


class Transformation(TypedDict):
    """
    A configuration dictionary defining how a specific column's key (header) and value 
    should be mutated during the rendering phase.

    This is highly useful for cleaning up database keys into human-readable headers, 
    formatting timestamps, or rounding numerical values just before they are printed.

    Attributes:
        name (str | None): The new string to use as the column header. If None, the original key is kept.
        value (Callable[[Any], Any] | None): A function that takes the original cell value and returns 
            the formatted value. If None, the original value is kept.

    Example:
        >>> status_transform: Transformation = {
        ...     "name": "Current Status",
        ...     "value": lambda v: str(v).upper()
        ... }
    """
    name: str | None
    value: Callable[[Any], Any] | None


def flatten[K, V, T](data: dict[K, V] | list[T] | tuple[T] | set[T], root: str = '', join: str = '.'):
    """
    Recursively unpackages nested data structures into a single-level, flat dictionary mapping.

    Handles dictionaries, lists, tuples, and sets. Nested hierarchical relationships and index positions 
    are preserved by concatenating their keys/indices into a single string path, separated by a defined 
    join character.

    Args:
        data (dict[K, V] | list[T] | tuple[T] | set[T]): The complex, nested data structure to flatten.
        root (str, optional): The base prefix string to prepend to all flattened keys. Defaults to ''.
        join (str, optional): The delimiter character used to separate levels of hierarchy. Defaults to '.'.

    Returns:
        dict[str, Any]: A one-dimensional dictionary mapping dot-notation string paths to their deepest values.

    Example:
        >>> nested_payload = {"server": {"ports": [80, 443]}}
        >>> flatten(nested_payload)
        {'server.ports.0': 80, 'server.ports.1': 443}
    """
    flattened_dict: dict[str, Any] = {}
    if isinstance(data, (list, set, tuple)):
        for idx, item in enumerate(data):  # type: ignore
            idxkey = f'{root}{join}{idx}'.lstrip(join)
            if isinstance(item, (dict, list, tuple, set)):
                flattened_dict.update(
                    flatten(item, idxkey, join))  # type: ignore
            else:
                flattened_dict[idxkey] = item
    else:
        for key, value in data.items():
            new_key = f'{root}{join}{key}'.lstrip(join)
            if isinstance(value, (list, tuple, set, dict)):
                flattened_dict.update(
                    flatten(value, new_key, join))  # type: ignore
            # elif isinstance(value, dict):
            #     flattened_dict.update(
            #         flatten(value, new_key, join))  # type: ignore
            else:
                flattened_dict[f'{root}{join}{key}'.lstrip(join)] = value
    return flattened_dict
