from gazebo_msgs.srv import DeleteEntity, GetEntityState, GetModelList, SpawnEntity
from litterbug.config import LitterbugConfig


class Gazebo(Node):
    """
    Gazebo controls our interface to Gazebo and its various
    plugins for interacting and controlling items within
    the simulation.
    """

    def __init__(
        self,
        config: LitterbugConfig,
    ):
        service_name = config["gazebo.service_name"]
        super().__init__(service_name)
        self.__models_directories = config["gazebo.models_directories"]

        self.__spawn_entity_client = self.create_client(
            SpawnEntity, config["gazebo.topics.spawn_entity"]
        )
        self.__delete_entity_client = self.create_client(
            DeleteEntity, config["gazebo.topics.delete_entity"]
        )
        self.__get_model_list_client = self.create_client(
            GetModelList, config["gazebo.topics.get_model_list"]
        )
        self.__get_entity_state_client = self.create_client(
            GetEntityState, config["gazebo.topics.get_entity_state"]
        )
        # Test
        self.__get_entity_exists_client = self.create_client(
            GetEntityState, config["gazebo.topics.get_entity_state"]
        )
