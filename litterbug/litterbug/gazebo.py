from gazebo_msgs.srv import DeleteEntity, GetEntityState, GetModelList, SpawnEntity


class Gazebo(Node):
    """
    Gazebo controls our interface to Gazebo and its various
    plugins for interacting and controlling items within
    the simulation.
    """

    def __init__(
        self,
        service_name: str,
        models_dir: str,
    ):
        super().__init__(service_name)
        self.__models_dir = models_dir
        self.__service_name = service_name

        self.__spawn_entity_client = self.create_client(SpawnEntity, "/spawn_entity")
        self.__delete_entity_client = self.create_client(DeleteEntity, "/delete_entity")
        self.__get_model_list_client = self.create_client(
            GetModelList, "/get_model_list"
        )
        self.__get_entity_state_client = self.create_client(
            GetEntityState, "/gazebo/get_entity_state"
        )
        # Test
        self.__get_entity_exists_client = self.create_client(
            GetEntityState, "/gazebo/get_entity_state"
        )
