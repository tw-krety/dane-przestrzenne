import dataclasses

import folium
from flask import Flask, render_template, request, jsonify

import ui_config as cfg
from load_data.load_data import MPKGraphLoader, Stop
from repository.StopRepository import StopRepository, StopEntity

app = Flask(__name__, template_folder='templates')

from map_utils import get_izochrone_map, TransferConfig, _load_stops

STOP_NAME = 'maślice małe (brodnicka)'

loader_2023 = MPKGraphLoader.from_pickle('./data/mpk_graph_loader_2023.pkl')
loader_2024 = MPKGraphLoader.from_pickle('./data/mpk_graph_loader_2024.pkl')


### DEPS
stop_repository = StopRepository.from_loaders([loader_2023, loader_2024])


@app.route('/')
def map_view():
    starting_stop_id: int = request.args.get('starting_stop', default=0, type=int)
    transfer_time = request.args.get('transfer_time', default=5, type=int)

    stop_name = stop_repository.get_by_id(starting_stop_id).name
    map1, map2 = compute_isochrone_maps(stop_name, transfer_time)

    return render_template(
        'page.html',
        map_html_1=map1._repr_html_(), map_html_2=map2._repr_html_()
    )


def compute_isochrone_maps(stop_name: str, transfer_time_minutes: int):
    map1: folium.Map = get_izochrone_map(
        cfg.DEFAULT_REGIONS_RESOLUTION, loader_2023,
        TransferConfig(stop_name, 5, transfer_time_minutes),
        [5, 15, 30, 45, 60, 75]
    )
    map2: folium.Map = get_izochrone_map(
        cfg.DEFAULT_REGIONS_RESOLUTION, loader_2024,
        TransferConfig(stop_name, 5, transfer_time_minutes),
        [5, 15, 30, 45, 60, 75]
    )

    # TODO doesnt work
    map1.options["zoom_start"] = cfg.DEFAULT_MAP_START_ZOOM
    map2.options["zoom_start"] = cfg.DEFAULT_MAP_START_ZOOM

    return map1, map2


@app.route("/search_stops", methods=["GET"])
def search_stops():
    search_term = request.args.get('q', '').strip()
    matching_stops: list[StopEntity] = stop_repository.query(search_term)

    search_response = [
        {
            "id": stop.id,
            "text": stop.name
        }
        for stop in matching_stops
    ]

    return jsonify(results=search_response)


if __name__ == '__main__':
    app.run(debug=True)
