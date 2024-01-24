import hashlib
from dataclasses import dataclass

from load_data.load_data import MPKGraphLoader


@dataclass
class StopDTO:
    id: str
    name: str
    display_name: str

    def __init__(self, name: str):
        self.id = hashlib.md5(name.encode('utf-8')).hexdigest()
        self.name = name
        self.display_name = " ".join([word.capitalize() for word in name.split(" ")])\
            .strip()


class StopRepository:

    def __init__(self, stops: list[StopDTO]):
        self.stops: dict[str, StopDTO] = {
            stop.id: stop for stop in stops
        }

    def get_by_id(self, ident: str):
        return self.stops[ident]

    def query(self, stop_name: str) -> list[StopDTO]:
        normalized_query = stop_name.lower()
        matching_stops = [stop for stop in self.stops.values() if normalized_query in stop.name.lower()]
        return matching_stops

    @staticmethod
    def from_loaders(loaders: list[MPKGraphLoader]):
        stops: list[set] = [
            set(loader.stop_names)
            for loader in loaders
        ]
        common_stops = set.intersection(*stops)

        common_stops = list(sorted(common_stops))
        stop_entities: list[StopDTO] = [
            StopDTO(name=stop_name)
            for stop_name in common_stops
        ]

        return StopRepository(stop_entities)
