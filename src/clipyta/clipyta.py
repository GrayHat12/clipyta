from collections import defaultdict
from typing import Any, Callable, Generic, TypeVar
from .utils import Transformation, flatten, BorderConfig, SortConfig, Alignment
from functools import lru_cache

DK = TypeVar('DK')
DV = TypeVar('DV')


def default_border_config() -> BorderConfig:
    """
    Generates the default border configuration dictionary for the table renderer.

    Returns:
        BorderConfig: A dictionary mapping layout components to their default 
            ASCII characters ('vertical', 'horizontal', 'horizontal_bold', and 'vertical_bold').

    Example:
        >>> config = default_border_config()
        >>> print(config['vertical'])
        '|'
    """
    return {
        "vertical": '|',
        "horizontal": '-',
        "horizontal_bold": '|',
        'vertical_bold': '='
    }


def generate_renderer[K, V](
    border_config: BorderConfig | None = default_border_config(),
    row_sorting: SortConfig[str] | Callable[[str], int] | None = None,
    col_sorting: SortConfig[dict[K, V]] | Callable[[
        dict[K, V]], int] | None = None,
    transformations: dict[str, Transformation] = {},
    align: Alignment = Alignment.center
) -> Renderer[K, V]:
    """
    Factory function to instantiate and configure a Renderer object.

    Allows for deep customization of borders, row/column sorting, data transformations, 
    and text alignment. Handles the automatic conversion of standard callable sorting 
    functions into typed SortConfig wrappers.

    Args:
        border_config (BorderConfig | None, optional): Custom dictionary mapping layout 
            components to border characters. Defaults to default_border_config().
        row_sorting (SortConfig[str] | Callable[[str], int] | None, optional): 
            Configuration or callable function to sort the rows of the table. Defaults to None.
        col_sorting (SortConfig[dict[K, V]] | Callable[[dict[K, V]], int] | None, optional): 
            Configuration or callable function to sort the table columns. Defaults to None.
        transformations (dict[str, Transformation], optional): A mapping of column names to 
            Transformation dictionaries for modifying keys and values dynamically. Defaults to {}.
        align (Alignment, optional): Enum specifying alignment strategy (center, left, right) 
            for text within cells. Defaults to Alignment.center.

    Returns:
        Renderer[K, V]: A fully configured Renderer instance ready to process and display data.

    Examples:

        Scenario 1: Basic Custom Formatting
        Applying left-alignment and a custom sorting logic to automatically order 
        rows based on a specific dictionary key (e.g., 'age').
        >>> renderer = generate_renderer(
        ...     align=Alignment.left,
        ...     row_sorting=lambda row: row.get('age', 0)
        ... )

        Scenario 2: Applying Data Transformations
        Renaming a messy database key ('usr_dob') to a clean header ('Date of Birth') 
        and formatting the values within that column, while ignoring others.
        >>> transformations = {
        ...     'usr_dob': {
        ...         'name': 'Date of Birth',
        ...         'value': lambda date_str: date_str.replace('-', '/')
        ...     },
        ...     'price': {
        ...         'name': 'Price (USD)',
        ...         'value': lambda p: f"${float(p):.2f}"
        ...     }
        ... }
        >>> renderer = generate_renderer(transformations=transformations)

        Scenario 3: Custom Layouts and Complex Sorting
        Creating a "markdown-style" table without outer bold borders, while simultaneously 
        applying a SortConfig to render rows in reverse-alphabetical order by 'username'.
        >>> custom_borders = {
        ...     "vertical": "|",
        ...     "horizontal": "-",
        ...     "horizontal_bold": "-",
        ...     "vertical_bold": "|"
        ... }
        >>> row_sorter = SortConfig(
        ...     sort=lambda row: row.get('username', ''),
        ...     reverse=True
        ... )
        >>> renderer = generate_renderer(
        ...     border_config=custom_borders,
        ...     row_sorting=row_sorter
        ... )
    """
    if row_sorting is not None and not isinstance(row_sorting, SortConfig) and callable(row_sorting):
        row_sorting = SortConfig[str](sort=row_sorting)
    if col_sorting is not None and not isinstance(col_sorting, SortConfig) and callable(col_sorting):
        col_sorting = SortConfig[dict[K, V]](sort=col_sorting)
    return Renderer[K, V](border_config, row_sorting, col_sorting, transformations, align)


class Renderer(Generic[DK, DV]):
    """
    The core engine for parsing, formatting, and drawing structured dataset as an ASCII table.

    This generic class manages the state and logic required to calculate dynamic column widths, 
    apply sorting configurations, execute data transformations, and render a visually aligned 
    table to standard output. It is generally recommended to instantiate this class using 
    the `generate_renderer` factory function rather than initializing it directly.

    Type Variables:
        DK: The expected type of the data dictionary keys.
        DV: The expected type of the data dictionary values.

    Example:
        >>> # While direct instantiation is possible, the factory function is preferred:
        >>> renderer = Renderer(
        ...     border_config=default_border_config(),
        ...     col_sorting=None,
        ...     row_sorting=None,
        ...     transformations={},
        ...     align=Alignment.center
        ... )
    """

    def __init__(
        self,
        border_config: BorderConfig | None,
        col_sorting: SortConfig[str] | None,
        row_sorting: SortConfig[dict[Any, Any]] | None,
        transformations: dict[Any, Transformation],
        align: Alignment
    ):
        """
        Initializes the Renderer instance with layout, parsing, and formatting configurations.

        Args:
            border_config (BorderConfig | None): Dictionary of border string configurations. 
                If None, all borders gracefully fallback to empty strings (no visible borders).
            col_sorting (SortConfig[str] | None): Configuration object managing column ordering.
            row_sorting (SortConfig[dict[Any, Any]] | None): Configuration object managing row ordering.
            transformations (dict[Any, Transformation]): Mapping that dictates how specific keys 
                and their payload values are mutated during the rendering pass.
            align (Alignment): Enum instance governing horizontal text alignment within individual cells.

        Example:
            >>> renderer = Renderer(None, None, None, {}, Alignment.center)
        """
        self.__lines = 0
        if border_config is None:
            border_config = {
                'vertical': '',
                'horizontal': '',
                'horizontal_bold': '',
                'vertical_bold': ''
            }
        self.__border_config = border_config
        self.__longest_cell_lengths: defaultdict[str, int] = defaultdict(
            lambda: 0)
        self.__row_sorting = row_sorting
        self.__col_sorting = col_sorting
        self.__transformations = transformations
        self.__all_keys: set[str] = set()
        self.__align = align

    def _formatter(self, key: Any, text: Any = ...) -> str:
        """
        Calculates padding and formats a given cell's text based on column width and alignment strategy.

        Relies on pre-calculated maximum cell widths (`__longest_cell_lengths`) to ensure uniform 
        column dimensions across the rendered table.

        Args:
            key (Any): The column key or header, used to look up the maximum required width for this specific column.
            text (Any, optional): The actual text payload to display inside the cell. If set to Ellipsis (...), 
                the method defaults to using the `key` value as the display text. Defaults to Ellipsis.

        Returns:
            str: The fully padded, aligned string bounded by an extra margin spacing, ready for standard output.

        Example:
            >>> # Assuming the maximum recorded width for the 'Status' column is 6
            >>> renderer._formatter('Status', 'OK')
            '   OK   '
        """
        if text is Ellipsis:
            text = key
        if not isinstance(key, str):
            key = str(key)
        if not isinstance(text, str):
            text = str(text)

        return self.__align.align(text)(self.__longest_cell_lengths[key] + 2)

    @lru_cache(maxsize=1)
    def __sort_keys(self, all_keys_lst: tuple[str]):
        """
        Sorts the provided tuple of dictionary keys based on the initialized column sorting configuration.

        Applies memoization (`@lru_cache`) to prevent redundant sorting calculations on identical sets of keys 
        during rapid rendering cycles.

        Args:
            all_keys_lst (tuple[str]): A tuple containing all unique, flattened keys extracted from the dataset.

        Returns:
            list[str]: A sorted list of strings representing the final left-to-right order of columns.

        Example:
            >>> # Assuming a SortConfig that sorts strings alphabetically
            >>> renderer._Renderer__sort_keys(('id', 'username', 'age'))
            ['age', 'id', 'username']
        """
        if isinstance(self.__col_sorting, SortConfig):
            return sorted(list(all_keys_lst),
                          key=self.__col_sorting.sort, reverse=self.__col_sorting.reverse)
        return list(all_keys_lst)

    def render(self, data: list[dict[Any, Any]]) -> None:
        """
        Processes, flattens, formats, and outputs a list of dictionaries as an ASCII table.

        This method handles the entire execution pipeline: it flattens nested dictionaries/lists, applies 
        key/value transformations, computes maximum necessary column dimensions, and dynamically draws the 
        table layout. If called consecutively, it utilizes ANSI escape sequences to overwrite the previously 
        drawn table output, creating an in-place updating effect.

        Args:
            data (list[dict[Any, Any]]): The raw dataset to be rendered. Elements can contain nested 
                iterables or dictionaries.

        Returns:
            None: The final formatted table is printed directly to the standard output.

        Example:
            >>> renderer = generate_renderer()
            >>> data = [{'user': {'name': 'Alice', 'role': 'Admin'}}]
            >>> renderer.render(data)
            # Output is visually drawn to the console, featuring 'user.name' and 'user.role' columns.
        """
        if isinstance(self.__row_sorting, SortConfig):
            data = sorted(data, key=self.__row_sorting.sort,
                          reverse=self.__row_sorting.reverse)
        for idx in range(len(data)):
            data[idx] = flatten(data[idx])
            for key in list(data[idx].keys()):
                transformation = self.__transformations.get(key)
                if transformation:
                    value = data[idx].pop(key)
                    if transformation['value'] is not None:
                        value = transformation['value'](value)
                    if transformation['name'] is not None:
                        key = transformation['name']
                    data[idx][key] = value
                self.__all_keys.add(key if isinstance(key, str) else str(key))

        for key in self.__all_keys:
            self.__longest_cell_lengths[key] = max(
                len(str(key)), self.__longest_cell_lengths[key])
        for item in data:
            for key, value in item.items():
                self.__longest_cell_lengths[key] = max(
                    len(str(value)), self.__longest_cell_lengths[key])

        all_keys_lst = self.__sort_keys(tuple(self.__all_keys))

        header = self.__border_config['vertical_bold'] + self.__border_config['vertical_bold'].join(
            map(self._formatter, all_keys_lst)) + self.__border_config['vertical_bold']

        total_width = len(header)

        horizontal_column_prim = self.__border_config['horizontal_bold'] * total_width
        horizontal_column_seco = self.__border_config['horizontal'] * total_width

        if self.__lines > 0:
            print('\033[F'*self.__lines + '\033[K', end='')
            self.__lines = 0

        print(horizontal_column_prim)
        print(header)
        print(horizontal_column_prim)

        self.__lines += 3

        for item in data:
            out = self.__border_config['vertical']
            for key in all_keys_lst:
                value = item.get(key, '-')
                out += self._formatter(key, value)
                out += self.__border_config['vertical']
            print(out)
            print(horizontal_column_seco)
            self.__lines += 2
