import os
import random

import pandas as pd
import networkx as nx

from bs4 import BeautifulSoup, ResultSet
from tqdm import tqdm
from typing import Union, Optional


def __random_color() -> str:
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    return f'#{r:02X}{g:02X}{b:02X}'


def get_line_colors(graph: nx.DiGraph) -> list[str]:
    lines = set(map(lambda stop: stop.line, graph.nodes))
    color_map = {line: __random_color() for line in lines}
    return [color_map[stop.line] for stop in graph.nodes]


class Stop:

    __slots__ = ['name', 'code', 'lat', 'lon', 'line']

    def __init__(self, name: str, code: int, latitude: float, longitude: float, line: str):
        self.name = name
        self.code = code
        self.lat = latitude
        self.lon = longitude
        self.line = line
    
    def __repr__(self) -> str:
        return f'line {self.line}: "{self.name}"'
    
    def __eq__(self, other: Union[str, "Stop"]) -> bool:
        if isinstance(other, str):
            return self.name == other
        if isinstance(other, Stop):
            return self.name == other.name and self.line == other.line
        return False
    
    def __hash__(self):
        return hash(self.name + self.line)

    def __lt__(self, other):
        return self.name <= other.name


class MPKGraphLoader:
    def __init__(self, data_path: str, transfer_time: float = 5.0) -> None:
        self.__data_path = data_path
        self.__stops_data = self.__load_stops_df()
        routes = self.__load_routes()
        self.__line_graphs: dict[str, nx.DiGraph] = {}
        for line_name, routes_data in routes.items():
            line_graph = self.__get_line_graph(*routes_data)
            self.__line_graphs[line_name] = line_graph
        
        self.__total_graph = self.__get_total_graph(transfer_time)
    
    @property
    def multigraph(self) -> nx.DiGraph:
        return self.__total_graph
    
    @property
    def line_names(self) -> list[str]:
        return list(self.__line_graphs.keys())
    
    @property
    def tram_line_names(self) -> list[str]:
        return list(filter(lambda x: not self.__is_bus_line(x), self.__line_graphs.keys()))
    
    @property
    def bus_line_names(self) -> list[str]:
        return list(filter(self.__is_bus_line, self.__line_graphs.keys()))
    
    @property
    def stop_names(self) -> list[str]:
        return list(set(map(lambda stop: stop.name, self.multigraph.nodes)))
    
    def __getitem__(self, line_name: str) -> nx.DiGraph:
        return self.__line_graphs[line_name]

    def get_stop(self, name: str) -> list[Stop]:
        return list(filter(lambda stop: stop == name, self.multigraph.nodes))

    def to_pickle(self, path: str):
        import pickle
        with open(path, 'wb') as file:
            pickle.dump(self, file)
    
    @staticmethod
    def from_pickle(path: str) -> "MPKGraphLoader":
        import pickle
        with open(path, 'rb') as file:
            return pickle.load(file)
    
    def __is_bus_line(self, name: str):
        if name.isalpha():
            return True
        try:
            number = int(name)
        except ValueError:
            return False
        if number >= 100:
            return True
        return False
    
    def get_tram_liens(self) -> dict[str, nx.DiGraph]:
        ret = {}
        for name, graph in self.__line_graphs.items():
            if not self.__is_bus_line(name):
                ret[name] = graph
        return ret
    
    def get_bus_lines(self) -> dict[str, nx.DiGraph]:
        ret = {}
        for name, graph in self.__line_graphs.items():
            if self.__is_bus_line(name):
                ret[name] = graph
        return ret
    
    def get_sugraph(self, lines: list[str]) -> nx.DiGraph:
        ret = nx.DiGraph()
        for u, v in self.multigraph.edges:
            if u.line in lines and v.line in lines:
                ret.add_edge(u, v, time=self.multigraph[u][v])
        return ret
    
    def get_stops_in_range(self, start_name: str, max_time: float, transfer_time: Optional[float] = None) -> list[Stop]:
        stops = list(filter(lambda stop: stop == start_name, self.multigraph.nodes))
        ret = set()
        for stop in stops:
            accessible_stops = self.__find_accessible_stops(stop, max_time, transfer_time=transfer_time)
            ret.update(accessible_stops)
        return ret
    
    def __find_accessible_stops(self, start: Stop, max_time: float, transfer_time: Optional[float] = None) -> set[Stop]:
        queue = [
            (neighbour, edge_data['time']) if transfer_time is None or neighbour.line == start.line else (neighbour, transfer_time)
            for neighbour, edge_data
            in self.multigraph[start].items()
        ]
        visited_stops = set()
        accessible_stops = []

        while queue:
            current_stop, current_time = queue.pop(0)
            if current_stop not in visited_stops:
                visited_stops.add(current_stop)
                if current_time <= max_time:
                    accessible_stops.append(current_stop)
                    for neighbour, edge_data in self.multigraph[current_stop].items():
                        travel_time = edge_data['time'] if transfer_time is None or neighbour.line == current_stop.line else transfer_time
                        queue.append((neighbour, current_time + travel_time))
        return accessible_stops

    
    def __load_stops_df(self) -> pd.DataFrame:
        df_path = os.path.join(self.__data_path, 'stops.txt')
        stops_df = pd.read_csv(df_path)
        stops_df = stops_df[['stop_name', 'stop_lat', 'stop_lon', 'stop_code']]
        stops_df['stop_name'] = stops_df['stop_name'].str.lower()
        coords = stops_df[['stop_name', 'stop_lat', 'stop_lon']]
        codes = stops_df[['stop_name', 'stop_code']]
        codes = codes.groupby(['stop_name'], as_index=False).first()
        coords = coords.groupby(['stop_name'], as_index=False).mean()
        data = coords.join(codes.set_index('stop_name'), on='stop_name')
        return data
    
    def __load_routes(self) -> dict[str, tuple[list[Stop], list[Stop], list[int], list[int]]]:
        ret = {}
        xml_paths = self.__get_xml_paths()
        for path in tqdm(xml_paths):
            line_name, var1, var2 = self.__load_line_variants_from_xml(path)
            stop_list_var1, route_times1 = self.__get_stop_list(line_name, var1)
            stop_list_var2, route_times2 = self.__get_stop_list(line_name, var2)
            ret[line_name] = (stop_list_var1, stop_list_var2, route_times1, route_times2)
        return ret
    
    def __get_xml_paths(self) -> list[str]:
        path = os.path.join(self.__data_path, 'lines')
        xmls = []
        for filename in os.listdir(path):
            full_path = os.path.join(path, filename, f'{filename}.xml')
            xmls.append(full_path)
        return xmls
    
    def __load_line_variants_from_xml(self, xml_path: str) -> tuple[str, ResultSet, ResultSet]:
        with open(xml_path, 'r', encoding='utf-8') as file:
            data = file.read()
        data = BeautifulSoup(data, 'xml')
        name = data.find('linie').find('linia').get('nazwa').lower()
        stops1_xml = data.find('linie').find('wariant', {'id': 1}).find('czasy').find_all('przystanek')
        stops2_xml = data.find('linie').find('wariant', {'id': 2}).find('czasy').find_all('przystanek')
        return name, stops1_xml, stops2_xml
    
    def __get_stop_list(self, line_name: str, stops_xml: list) -> tuple[list[Stop], list[int]]:
        ret = []
        times = []
        errs_count = 0
        delta_time = 0
        for i, stop in enumerate(stops_xml):
            name = stop.get('nazwa').lower()
            code = int(stop.get('id'))
            time = 0
            if i != 0:
                time = int(stop.get('czas')) - delta_time
                delta_time += time
            try:
                lat, lon = self.__stops_data.loc[self.__stops_data['stop_name'] == name, ['stop_lat', 'stop_lon']].values[0]
            except IndexError:
                lat, lon = None, None
                errs_count += 1
            s = Stop(name, code, lat, lon, line_name)
            ret.append(s)
            if i != 0:
                times.append(time)
        if errs_count != 0:
            print(f'WARNING: {errs_count} values without geolocalisation.')
        return ret, times
    
    def __get_line_graph(self, variant1: list[Stop], variant2: list[Stop], times1: list[int], times2: list[int]) -> nx.DiGraph:
        ret = nx.DiGraph()
        ret = self.__get_one_variant(ret, variant1, times1)
        ret = self.__get_one_variant(ret, variant2, times2)
        return ret
        
    def __get_one_variant(self, graph: nx.DiGraph, variant: list[Stop], times: list[int]) -> nx.DiGraph:
        for i in range(len(variant) - 1):
            u: Stop = variant[i]
            v: Stop = variant[i+1]
            t: int = times[i]
            graph.add_node(u)
            graph.add_node(v)
            graph.add_edge(u, v, time=t)
        return graph
    
    def __get_total_graph(self, transfer_time: float) -> nx.DiGraph:
        ret = nx.DiGraph()
        for line1, line_1_graph in self.__line_graphs.items():
            for line2, line_2_graph in self.__line_graphs.items():
                if line1 != line2:
                    for u, v in line_1_graph.edges:
                        ret.add_edge(u, v, time=line_1_graph[u][v]['time'])
                    for u, v in line_2_graph.edges:
                        ret.add_edge(u, v, time=line_2_graph[u][v]['time'])

                    line1_stop_names = set(map(lambda stop: stop.name, line_1_graph.nodes))
                    line2_stop_names = set(map(lambda stop: stop.name, line_2_graph.nodes))
                    common_names = line1_stop_names & line2_stop_names
                    for name in common_names:
                        line1_stop = list(filter(lambda stop: stop == name, line_1_graph.nodes))[0]
                        line2_stop = list(filter(lambda stop: stop == name, line_2_graph.nodes))[0]
                        ret.add_edge(line1_stop, line2_stop, time=transfer_time)
                        ret.add_edge(line2_stop, line1_stop, time=transfer_time)
        ret.remove_edges_from(nx.selfloop_edges(ret))
        return ret
