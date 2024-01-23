from dataclasses import dataclass

from load_data.load_data import MPKGraphLoader


@dataclass
class StopEntity:
    id: int
    name: str


class StopRepository:

    def __init__(self, stops: list[StopEntity]):
        self.stops = stops

    def get_by_id(self, ident: int):
        return self.stops[ident]

    def query(self, stop_name: str) -> list[StopEntity]:
        normalized_query = stop_name.lower()
        matching_stops = [stop for stop in self.stops if normalized_query in stop.name.lower()]
        return matching_stops

    @staticmethod
    def from_loaders(loaders: list[MPKGraphLoader]):
        stops: list[set] = [
            set(loader.stop_names)
            for loader in loaders
        ]
        common_stops = set.union(*stops)

        common_stops = list(sorted(common_stops))
        stop_entities: list[StopEntity] = [
            StopEntity(id=i, name=stop_name)
            for i, stop_name in enumerate(common_stops)
        ]

        return StopRepository(stop_entities)
