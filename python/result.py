from typing import Tuple, Union, Any

# Coqtop Response Types #
class Ok:
    """A response representing success."""

    def __init__(self, val: Any, msg: str = "") -> None:
        """Initialize values."""
        self.val = val
        self.msg = msg

class Err:
    """A response representing failure."""

    def __init__(self, msg: str, loc: Tuple[int, int] = (-1, -1)) -> None:
        """Initialize values."""
        self.msg = msg
        self.loc = loc

Result = Union[Ok, Err]

