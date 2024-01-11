from abc import ABC, abstractmethod
from uuid import uuid4

from typing import Optional, Tuple


class Item(ABC):
    """
    An item is a generic tracker of position, state,
    model, and anything else that litterbug may need
    for its simulation. It will also manage the host
    of interactions or resulting attributes that an
    item might have as a result.
    """

    def __init__(
        self,
        id: Optional[str],
        origin: Tuple[float, float],
        orientation: Tuple[float, float, float],
        label: str,
        model_path: str,
    ):
        super().__init__()

        if id is None or id == "":
            id = str(uuid4())
        self.id = id
        self.origin = origin
        self.orientation = orientation
        self.label = label
        self.model_path = model_path
