from srai.regionalizers import geocode_to_region_gdf, H3Regionalizer
from load_data import MPKGraphLoader
from shapely.geometry import Point
import geopandas as gpd
import pandas as pd

CITY = "Wroclaw"
COUNTRY = "Poland"

class TransferConfig:
    def __init__(self, start_name, max_time, transfer_time):
        self.start_name = start_name
        self.max_time = max_time
        self.transfer_time = transfer_time

def get_map(regions_resolution: int, graph_loader: MPKGraphLoader, transfer_cfg: TransferConfig = None):

    if regions_resolution <= 1:
        raise ValueError(f"Regions resolution must be greater than 1. Currently {regions_resolution}")

    stops = _load_stops(graph_loader)
    regions = _get_regions(regions_resolution, graph_loader, transfer_cfg)
    map_ = regions.explore(tooltip = False, highlight = False, column = "count", cmap="Blues", style_kwds = dict(opacity=0.05))
    map_ = stops.explore(color = "#ff7daf", m = map_, style_kwds = dict(opacity=0.8))

    if transfer_cfg:
        stops_in_range = _find_stops_in_range(graph_loader, transfer_cfg)
        map_ = stops_in_range.explore(color = "#1eff00", m = map_)
        starting_stop = _get_starting_stop(graph_loader, transfer_cfg)
        map_ = starting_stop.explore(color = "#ff0000", m = map_)
        

    return map_

def _get_regions(regions_resolution: int, graph_loader: MPKGraphLoader, transfer_cfg: TransferConfig) -> gpd.GeoDataFrame:
    area_name = f"{CITY}, {COUNTRY}"
    area = geocode_to_region_gdf(area_name)
    regions = H3Regionalizer(regions_resolution).transform(area)

    all_stops = _load_stops(graph_loader)
    all_stops_region = gpd.sjoin(all_stops, regions, how='left', op='within')

    no_stops_per_region = all_stops_region.index_right.value_counts().astype(int)

    if transfer_cfg:
        stops = _find_stops_in_range(graph_loader, transfer_cfg)
        stops_region = pd.merge(stops, all_stops_region, how='left', on='region_id')
        visited_stops_per_region = stops_region.index_right.value_counts().astype(int)
        no_stops_per_region = (visited_stops_per_region / no_stops_per_region).fillna(0)

    regions = pd.concat([
        regions,
        no_stops_per_region
    ], axis = 1).fillna(0)

    return regions


def _load_stops(graph_loader: MPKGraphLoader) -> gpd.GeoDataFrame:
    stops = []
    for name in graph_loader.stop_names:
        stop = graph_loader.get_stop(name)[0]
        d = {
            'region_id': name,
            'geometry': Point(stop.lon, stop.lat)
        }
        stops.append(d)

    stops = gpd.GeoDataFrame.from_dict(stops)
    stops = stops.set_index("region_id")
    
    return stops

def _find_stops_in_range(graph_loader: MPKGraphLoader, transfer_cfg: TransferConfig) -> gpd.GeoDataFrame:
    stops = graph_loader.get_stops_in_range(transfer_cfg.start_name,
                                            max_time = transfer_cfg.max_time, 
                                            transfer_time = transfer_cfg.transfer_time)
    stops = list(stops)
    stops_arr = []
    for stop in stops:
        d = {
            'region_id': stop.name,
            'geometry': Point(stop.lon, stop.lat)
        }
        stops_arr.append(d)
    
    stops = gpd.GeoDataFrame.from_dict(stops_arr)
    stops = stops.set_index("region_id")
    
    return stops.drop_duplicates()

def _get_starting_stop(graph_loader: MPKGraphLoader, transfer_cfg: TransferConfig) -> gpd.GeoDataFrame:
    staring_stop = graph_loader.get_stop(transfer_cfg.start_name)[0]
    stop = gpd.GeoDataFrame.from_dict([{
        'region_id': staring_stop.name,
        'geometry': Point(staring_stop.lon, staring_stop.lat)
    }])
    stop = stop.set_index("region_id")
    
    return stop



