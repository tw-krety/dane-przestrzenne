import pandas as pd
import os
from bs4 import BeautifulSoup
from tqdm import tqdm
import networkx as nx
from stops_utils import is_bus_line
from typing import Literal


class Stop:

    __slots__ = ['name', 'code', 'lat', 'lon']

    def __init__(self, name: str, code: int, latitude: float, longitude: float):
        self.name = name
        self.code = code
        self.lat = latitude
        self.lon = longitude
    
    def __repr__(self) -> str:
        return f'Stop: "{self.name}"'
    
    def __eq__(self, other) -> bool:
        return self.name == other.name
    
    def __hash__(self):
        return hash(self.name)

    def __lt__(self, other):
        return self.name <= other.name


def load_stops(path: str, strategy: Literal['first', 'mean']='mean') -> pd.DataFrame:
    """Function that returns DataFrame with names and geolocalisation for bus and tram stops.

    Args:
        path (str): path to the file with stops data.
        strategy (Optional[str]): strategy used when a stop has more than one pair
        of coordinates. Available options: 'first', 'mean'. Defaults to 'first'.
    
    Returns: (DataFrame)

    Columns description:
        stop_name: name of the stop
        stop_lat: latitude of the stop
        stop_lon: longitude of the stop
        stop_code: unique code of the stop
    """
    stops_df = pd.read_csv(path)
    stops_df = stops_df[['stop_name', 'stop_lat', 'stop_lon', 'stop_code']]
    stops_df['stop_name'] = stops_df['stop_name'].str.lower()
    coords = stops_df[['stop_name', 'stop_lat', 'stop_lon']]
    codes = stops_df[['stop_name', 'stop_code']]
    codes = codes.groupby(['stop_name'], as_index=False).first()
    if strategy == 'mean':
        coords = coords.groupby(['stop_name'], as_index=False).mean()
    else:
        coords = coords.groupby(['stop_name'], as_index=False).first()
    data = coords.join(codes.set_index('stop_name'), on='stop_name')
    return data


RouteData = dict[str, tuple[list[Stop], list[Stop]]]
TimeData = dict[str, tuple[list[int], list[int]]]


def load_routes(path: str, stops: pd.DataFrame) -> tuple[RouteData, TimeData]:
    """Function that loads all routes data. Returns a dict which keys (str) are the names of the lines,
    and the values are 2 element tuples where first element is the list of stops (list[Stop]) for the first variant of the
    route, and the second element is the list of stops for the second vartiant of the route.

    Args:
        path (str): path to the directory that stores all directories with xml files.
        stops (DataFrame): dataframe that contains information about stops names, ids, latitudes and longitudes.
    
    Returns: (dict[str, tuple[list[Stop], list[Stop]]])
    """
    ret = {}
    route_times = {}
    xml_paths = __get_xml_paths(path)
    for path in tqdm(xml_paths):
        line_name, var1, var2 = __load_line_variants_from_xml(path)
        stop_list_var1, route_times1 = __get_stop_list(var1, stops)
        stop_list_var2, route_times2 = __get_stop_list(var2, stops)
        ret[line_name] = (stop_list_var1, stop_list_var2)
        route_times[line_name] = (route_times1, route_times2)
    return ret, route_times


def __get_xml_paths(path: str) -> list:
    xmls = []
    for filename in os.listdir(path):
        full_path = os.path.join(path, filename, f'{filename}.xml')
        xmls.append(full_path)
    return xmls


def __load_line_variants_from_xml(xml_path: str) -> tuple:
    with open(xml_path, 'r', encoding='utf-8') as file:
        data = file.read()
    data = BeautifulSoup(data, 'xml')
    name = data.find('linie').find('linia').get('nazwa').lower()
    stops1_xml = data.find('linie').find('wariant', {'id': 1}).find('czasy').find_all('przystanek')
    stops2_xml = data.find('linie').find('wariant', {'id': 2}).find('czasy').find_all('przystanek')
    return name, stops1_xml, stops2_xml


def __get_stop_list(stops_xml: list, stops: pd.DataFrame) -> tuple[list[Stop], list[int]]:
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
            lat, lon = stops.loc[stops['stop_name'] == name, ['stop_lat', 'stop_lon']].values[0]
        except IndexError:
            lat, lon = None, None
            errs_count += 1
        s = Stop(name, code, lat, lon)
        ret.append(s)
        if i != 0:
            times.append(time)
    if errs_count != 0:
        print(f'WARNING: {errs_count} values without geolocalisation.')
    return ret, times


def load_to_graph(routes: RouteData, times: TimeData) -> nx.Graph:
    ret = nx.Graph()
    for name, (r1, r2) in routes.items():
        t1, t2 = times[name]
        ret = __add_stop_nodes(ret, r1)
        ret = __add_stop_nodes(ret, r2)
        ret = __add_edges(ret, r1, t1)
        ret = __add_edges(ret, r2, t2)
    ret.remove_edges_from(nx.selfloop_edges(ret))
    return ret


def get_all_stops(routes: dict) -> set:
    ret = set()
    for _, (r1, r2) in routes.items():
        for stop in r1:
            ret.add(stop)
        for stop in r2:
            ret.add(stop)
    return ret


def get_tram_graph(routes: RouteData, times: TimeData) -> nx.Graph:
    ret = nx.Graph()
    for name, (r1, r2) in routes.items():
        if not is_bus_line(name):
            ret = __add_stop_nodes(ret, r1)
            ret = __add_stop_nodes(ret, r2)
            ret = __add_edges(ret, r1)
            ret = __add_edges(ret, r2)
    ret.remove_edges_from(nx.selfloop_edges(ret))
    return ret


def get_bus_graph(routes: RouteData, times: TimeData) -> nx.Graph:
    ret = nx.Graph()
    for name, (r1, r2) in routes.items():
        if is_bus_line(name):
            ret = __add_stop_nodes(ret, r1)
            ret = __add_stop_nodes(ret, r2)
            ret = __add_edges(ret, r1)
            ret = __add_edges(ret, r2)
    ret.remove_edges_from(nx.selfloop_edges(ret))
    return ret


def __add_stop_nodes(graph: nx.Graph, route: list[Stop]) -> nx.Graph:
    ret = nx.Graph(graph)
    for stop in route:
        ret.add_node(stop.name, lat=stop.lat, lon=stop.lon)
    return ret


def __add_edges(graph: nx.Graph, route: list[Stop], times: list[int]) -> nx.Graph:
    ret = nx.Graph(graph)
    for i in range(len(route) - 1):
        u: Stop = route[i]
        v: Stop = route[i + 1]
        time = times[i]
        ret.add_edge(u.name, v.name, time=time)
    return ret



    


