from __future__ import annotations

from typing import List, Optional, Tuple

import netpbmfile
import numpy as np
import yaml

from litterbug.brensenham import define_line

OCCUPIED = 1
UNKNOWN = -1
FREE = 0

OCCUPIED_PGM = 0
UNKNOWN_PGM = 205
FREE_PGM = 254

OCCUPIED_RGB = [0, 0, 0]
UNKNOWN_RGB = [127, 127, 127]
FREE_RGB = [255, 255, 255]


class Map:
    def __init__(self, map: np.ndarray, resolution: float, origin: Tuple[float, float]):
        self.map = map
        self.resolution = resolution
        self.origin = origin

    @staticmethod
    def From_Map(
        path: str,
        robot_offset: Optional[Tuple[float, float]] = None,
        resolution: Optional[float] = None,
    ) -> Map:
        """
        From_Map loads a map from a pgm file and loads it into
        our Map class object.

        The robot_offset is needed as the map, when generated,
        will assume that the robot's position when it started
        mapping is (0.0, 0.0). If this is *not* true, then the
        map has a natural offset that needs to be adjusted.

        The resolution is the meters per pixel of the map.

        This function will attempt to read the resolution and
        offset from the accompany YAML file through the fields
        resolution and origin, respectively. If these fields
        set in the function above, it will override the values
        in the YAML file; if both are set, no YAML file is
        attempted to be read. If none are provided and the
        values are not found in the YAML file, then this
        function will throw a MissingMapConfigError
        """
        map_path = f"{path}.pgm"
        yaml_path = f"{path}.yaml"

        map = netpbmfile.imread(map_path)

        data = None
        if resolution is None or robot_offset is None:
            with open(yaml_path, "r") as file:
                data = yaml.safe_load(file)

        missing_fields: List[str] = []
        if resolution is None:
            try:
                resolution = data["resolution"]
            except KeyError:  # noqa
                missing_fields.append("resolution")

        if robot_offset is None:
            try:
                robot_offset = (data["origin"]["x"], data["origin"]["y"])
            except KeyError:
                missing_fields.append("origin")

        if len(missing_fields) > 0:
            raise MissingMapConfigError(missing_fields)

        # Now convert the map to a numpy array of expected type
        map = np.where(map == OCCUPIED_PGM, OCCUPIED, map)
        map = np.where(map == FREE_PGM, FREE, map)
        map = np.where(map == UNKNOWN_PGM, UNKNOWN, map)

        return Map(map, resolution=resolution, origin=robot_offset)

    def __meter_to_pixel_coordinates(
        self, point: Tuple[float, float]
    ) -> Tuple[int, int]:
        """
        __meter_to_pixel_coordinates converts a point in meters to
        pixel coordinates in the map.
        """
        return (
            int((point[0] - self.point[0]) / self.__resolution),
            self.map.shape[0] - int((point[1] - self.point[1]) / self.__resolution),
        )

    def line_of_sight(
        self, origin: Tuple[float, float], target: Tuple[float, float]
    ) -> bool:
        """
        line_of_sight returns true if there is a clear line of sight
        between the origin and target, where a line drawn between
        the two points via Brensenham's algorithm does not intersect
        with any occupied cells.
        """
        origin = self.__meter_to_pixel_coordinates(origin)
        target = self.__meter_to_pixel_coordinates(target)

        # Find all cells that a line between the two would pass
        # via Brensenham's algorithm
        cells = define_line(origin[0], origin[1], target[0], target[1])

        # Now determine if any of the cells in our map are
        # mark OCCUPIED; if so, return False
        for cell in cells:
            if self.map[cell[1], cell[0]] == OCCUPIED:
                return False

        return True


class MissingMapConfigError(Exception):
    """
    MissingMapConfigError is an exception that is raised when
    a map is attempted to be loaded, but the config is missing
    the required fields.
    """

    def __init__(self, missing_fields: List[str]):
        self.missing_fields = missing_fields

    def __str__(self):
        return f"Missing required fields in config: {self.missing_fields}"
