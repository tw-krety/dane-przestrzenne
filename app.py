import dataclasses
from functools import lru_cache
from typing import Literal

import folium
from flask import Flask, render_template, request, jsonify
from flask_caching import Cache

import ui_config as cfg
from load_data.load_data import MPKGraphLoader, Stop
from ui.FormData import FormData
from ui.StopRepository import StopRepository, StopDTO

from map_utils import get_izochrone_map, TransferConfig, _load_stops, get_map


LOADERS = {
    "all_2023": MPKGraphLoader.from_pickle('./data/mpk_graph_loader_2023.pkl'),
    "all_2024": MPKGraphLoader.from_pickle('./data/mpk_graph_loader_2024.pkl'),
    "tram_2023": MPKGraphLoader.from_pickle('./data/tram_graph_loader_2023.pkl'),
    "tram_2024": MPKGraphLoader.from_pickle('./data/tram_graph_loader_2024.pkl'),
    "bus_2023": MPKGraphLoader.from_pickle('./data/bus_graph_loader_2023.pkl'),
    "bus_2024": MPKGraphLoader.from_pickle('./data/bus_graph_loader_2024.pkl')
}

STOP_REPOS: dict[Literal['all', 'tram', 'bus'], StopRepository] = {
    "all": StopRepository.from_loaders([LOADERS['all_2023'], LOADERS['all_2024']]),
    "tram": StopRepository.from_loaders([LOADERS['tram_2023'], LOADERS['tram_2024']]),
    "bus": StopRepository.from_loaders([LOADERS['bus_2023'], LOADERS['bus_2024']])
}

app_config = {
    "DEBUG": True,  # some Flask specific configs
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 300
}

app = Flask(__name__, template_folder='templates')
app.config.from_mapping(app_config)

cache = Cache(app)


@app.route('/')
def map_view():
    starting_stop_id: int = request.args.get('starting_stop', default=cfg.DEFAULT_STARTING_STOP_ID, type=int)
    transfer_time = request.args.get('transfer_time', default=cfg.DEFAULT_TRANSFER_TIME, type=int)
    stop_reach_max_time = int(request.args.get('stop_reach_max_time', default=cfg.DEFAULT_STOP_REACH_MAX_TIME))
    network_kind = request.args.get("network_kind", default="all", type=str)

    stop: StopDTO = STOP_REPOS['all'].get_by_id(starting_stop_id)
    form_data = FormData(stop.id, stop.display_name, transfer_time, stop_reach_max_time)

    # default maps
    map1 = compute_default_map(stop.name, stop_reach_max_time, transfer_time, f"{network_kind}_2023")
    map2 = compute_default_map(stop.name, stop_reach_max_time, transfer_time, f"{network_kind}_2024")

    # isochrone maps
    iso_map1 = compute_isochrone_map(stop.name, transfer_time, f"{network_kind}_2023")
    iso_map2 = compute_isochrone_map(stop.name, transfer_time, f"{network_kind}_2024")

    return render_template(
        'page.html',
        iso_map1=iso_map1._repr_html_(), iso_map2=iso_map2._repr_html_(),
        default_map1=map1._repr_html_(), default_map2=map2._repr_html_(),
        form_data=form_data
    )


@app.route("/search_stops", methods=["GET"])
def search_stops():
    search_term = request.args.get('q', '').strip()
    network_kind = request.args.get('network_kind', default='all', type=str)

    assert network_kind in ['all', 'tram', 'bus'], "Invalid network kind"
    matching_stops: list[StopDTO] = STOP_REPOS[network_kind].query(search_term)

    search_response = [
        {
            "id": stop.id,
            "text": stop.display_name
        }
        for stop in matching_stops
    ]

    return jsonify(results=search_response)


@app.route("/update_map", methods=["GET"])
def update_map():
    starting_stop_id = request.args.get('starting_stop', type=int)
    transfer_time = request.args.get('transfer_time', type=int)
    stop_reach_max_time = request.args.get('stop_reach_max_time', type=int)
    year = request.args.get('year', type=str)
    network_kind = request.args.get('network_kind', type=str)
    map_type = request.args.get('map_type', type=str)

    loader_name = f"{network_kind}_{year}"  # e.g bus_2023
    assert loader_name in LOADERS.keys()

    stop = STOP_REPOS[network_kind].get_by_id(starting_stop_id)

    if map_type == 'iso':
        mpk_map = compute_isochrone_map(stop.name, transfer_time, loader_name)
    elif map_type == 'default':
        mpk_map = compute_default_map(stop.name, stop_reach_max_time, transfer_time, loader_name)
    else:
        raise ValueError(f"Invalid map type: {map_type}")

    return jsonify({
        'map_html': mpk_map._repr_html_(),
    })


@lru_cache(maxsize=16)
def compute_isochrone_map(stop_name: str, transfer_time_minutes: int, loader_name: str):
    loader = LOADERS[loader_name]
    return get_izochrone_map(
        cfg.DEFAULT_REGIONS_RESOLUTION, loader,
        TransferConfig(stop_name, 5, transfer_time_minutes),
        [5, 15, 30, 45, 60, 75]
    )


@lru_cache(maxsize=16)
def compute_default_map(stop_name: str, stop_reach_max_time: int, transfer_time_minutes: int, loader_name: str):
    loader = LOADERS[loader_name]
    return get_map(
        cfg.DEFAULT_REGIONS_RESOLUTION, loader,
        TransferConfig(stop_name, stop_reach_max_time, transfer_time_minutes)
    )


if __name__ == '__main__':
    app.run(debug=True)
