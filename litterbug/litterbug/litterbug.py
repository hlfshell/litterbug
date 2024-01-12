import math
from threading import Lock
from typing import Optional

from nav_msgs.msg import Odometry
from rclpy.node import Node

from litterbug.config import LitterbugConfig
from litterbug.gazebo import Gazebo
from litterbug.litterbug.items import Item
from litterbug.map import Map

from typing import Callable, Dict, List, Tuple
from random import random, choice, uniform


class Litterbug(Node):
    """
    TODO
    """

    def __init__(
        self,
        config: LitterbugConfig,
        map: Optional[Map] = None,
        gazebo: Optional[Gazebo] = None,
        on_item_detected: Callable[[Item], None] = None,
    ):
        self.__config = config

        if map is not None:
            self.__map = map
        else:
            self.__map = Map.From_Map(
                config["map.file"],
                config["map.resolution"],
                config["map.offset"],
            )

        if gazebo is not None:
            self.__gazebo = gazebo
        else:
            self.__gazebo = Gazebo(config["gazebo.models_directories"])

        super().__init__(config["core.service_name"])

        # Initialize topic subscriptions
        self.__robot_pose_lock = Lock()
        self.__robot_location: Tuple[float, float] = (0.0, 0.0)
        self.__robot_orientation: float = 0.0
        self.__odometry_subscription = self.create_subscription(
            msg_type=Odometry,
            topic=config["core.topics.odometry"],
            callback=self.__odometry_callback,
            qos_profile=10,
        )

        # World items and inventory state
        self.__items_lock = Lock()
        self.__items: Dict[str, Item] = {}
        self.__inventory: Dict[str, Item] = {}
        self.__item_types: List[str] = {}

        # If we are simulating the vision, prepare it
        if config["vision.enable_simulation"]:
            self.__on_item_detected = on_item_detected
            self.__initiate_vision()

    def __initiate_vision(self):
        """
        __initiate_vision prepares the vision simulation features
        including ROS2 topics and timers
        """
        fps = self.__config["vision.fps"]

        self.__fov: int = self.__config["vision.fov"]
        self.__vision_range: float = self.__config["vision.range"]
        self.__vision_minimum_range: float = self.__config["vision.minimum_range"]
        self.__enable_false_negatives: bool = self.__config[
            "vision.enable_false_negatives"
        ]
        self.__vision_location_error: Dict[str, float] = self.__config["vision.error"]

        self.__false_negative_probability = self.__config[
            "vision.false_negative_probability"
        ]

        self.__enable_false_positives = self.__config["vision.enable_false_positives"]
        self.__ghost_positive_probability = (
            1 / self.__config["vision.ghost_positive_rate"]
        ) * (1 / fps)
        self.__mislabel_probability = self.__config["vision.mislabel_probability"]

        self.create_timer(1.0 / fps, self.vision_scan)

    def populate(self):
        """
        populate will, for each item it knows about, create it if
        it does not already exist in the simulation or in the robot's
        inventory. When it does this, it will attempt to create the
        item within the simulation as well.
        """
        pass

    def get_robot_pose(self) -> Tuple[Tuple[float, float], float]:
        """
        get_robot_pose thread safely returns the latest robot
        position ((x, y) in meters) and orientation (psi, in
        radians)
        """
        with self.__robot_pose_lock:
            return self.__robot_location, self.__robot_orientation

    def get_world_items(self) -> Dict[str, Item]:
        """
        get_world_items returns a dictionary of all items in the
        world, keyed by their name
        """
        with self.__items_lock:
            return self.__items

    def get_robot_inventory(self) -> Dict[str, Item]:
        """
        get_robot_inventory returns a dictionary of all items in
        the robot's inventory, keyed by their name
        """
        with self.__items_lock:
            return self.__inventory

    def get_item_types(self) -> List[str]:
        """
        get_item_types returns a list of all item types that are
        known to the robot
        """
        with self.__items_lock:
            return self.__item_types

    def vision_scan(self):
        """
        vision_scan will, at a set FPS, perform simulated vision.
        It will also handle false negative and positive emulation
        if configured to do so. Once items are identified, an
        ObjectSpotted ROS msg will be spawn to broadcast the item
        or call it out to the custom function passed to litterbug
        via the on_item_detected parameter.
        """

        location, orientation = self.get_robot_pose()

        items = self.get_world_items()

        to_broadcast: List[Item] = []

        # First, determine if we did see anything
        for item in items:
            seen = self.__map.line_of_sight(location, item.origin)

            # If we saw it, figure out the probability that we will
            # false negative it if enabled
            if seen and self.__enable_false_negatives:
                if random() < self.__false_negative_probability:
                    continue
                if (
                    self.__enable_false_positives
                    and random() < self.__ghost_positive_probability
                ):
                    # We are doing a false positive, so let's figure out
                    # what we're going to mislabel this item as
                    # Pick a random item to represent
                    item_type = choice(self.get_item_types())
                    # Create a new item with the same location and orientation
                    # but with the new item type
                    item = Item(
                        name=item.name,
                        label=item_type,
                        model="",
                        origin=item.origin,
                        orientation=item.orientation,
                    )
                    to_broadcast.append(item)
                else:
                    to_broadcast.append(item)
            elif seen:
                to_broadcast.append(item)

        # Now, if we are going to send false positives, we will
        # see if we generate some now
        if self.__enable_false_positives and self.__ghost_positive_probability > 0.0:
            ghost_positives = self.__ghost_positives()
            to_broadcast += ghost_positives

        # We now have a list of items we wish to broadcast. If we
        # have a function assigned to __on_item_detected, we will
        # call that; otherwise it's just broadcasted to our ROS2
        # topic
        for item in to_broadcast:
            if self.__on_item_detected is not None:
                self.__on_item_detected(item)
            else:
                self.__broadcast_item_spotted(item)
    
    def __ghost_positives(self) -> List[Item]:
        """
        Given the current robot's position and the configuration
        of false negative probabilities (vision.ghost_positive_rate)
        possibly generate a set of false positives.
        """
        location, orientation = self.get_robot_pose()
        
        to_broadcast : List[Item] = []

        # We do a while loop this way to possibly create multiple
        # false positives if the math/die rolls call for it.
        while True:
            if self.__mislabel_probability > random():
                break

            # We are going to send a false positive of an item
            # that is not there at all.
            # Pick a random item to represent
            item_type = choice(self.get_item_types())

            # Determine a realistic location for this item to
            # exist by generating a random point and ensuring
            # via the Map it's viewable. We limit generation
            # to 25 possible tries before abandoning the process
            # in case we're in a position where we're close to
            # a wall and can't really detect much
            attempts = 0
            while attempts < 25:
                # Determine the orientation of the robot and add
                # some random ±fov (convert it to radians!) to it
                fov = math.radians(self.__fov)
                angle = uniform(-fov, fov)

                # Generate some distance away from the robot to trigger
                # our false positive on
                distance = uniform(self.__vision_minimum_range, self.__vision_range)

                # Now find the coordinates of a line at the set distance
                # at the angle we generated
                spot = (
                    location[0] + distance * math.cos(orientation + angle),
                    location[1] + distance * math.sin(orientation + angle),
                )

                if not self.__map.line_of_sight(location, spot):
                    continue
                else:
                    # Create a fake Item for our false positive
                    item = Item(
                        name="",
                        label=item_type,
                        model="",
                        origin=spot,
                        orientation=orientation,
                    )
                    to_broadcast.append(item)
                    break

            # If we've reached this point, we failed to generate
            # a false positive and will abort
            break

    def __broadcast_item_spotted(self, item: Item):
        """
        __broadcast_item_spotted will broadcast a ObjectSpotted ROS message
        to the ROS2 topic to all possible subscribers.
        """
        self.__???
        TODO - get the message generated and created here for
        broadcast also create the broadcast topic

    def __quaternion_to_euler(self, x, y, z, w) -> Tuple[float, float, float]:
        """
        __quaternion_to_euler converts a quaternion to euler angles
        (in radians) - our return value is a Tuple of (phi, theta,
        psi)
        """
        phi = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))

        theta = 2.0 * (w * y - z * x)
        theta = 1.0 if theta > 1.0 else theta
        theta = -1.0 if theta < -1.0 else theta
        theta = math.asin(theta)

        psi = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))

        return phi, theta, psi

    def __odom_callback(self, msg: Odometry):
        """
        __odom_callback receives the incoming Odometry message
        and saves it to memory in a thread safe manner. We
        convert the quaternion rotation to Euler angles before
        isolating psi (z-axis rotation) for the robot's resulting
        orientation.
        """
        pose = msg.pose.pose
        position = pose.position
        quaternion = pose.orientation

        _, _, psi = self.__quaternion_to_euler(
            quaternion.x, quaternion.y, quaternion.z, quaternion.w
        )

        with self.__robot_pose_lock:
            self.__robot_location = (position.x, position.y)
            self.__robot_orientation = psi
