import dataclasses
from functools import lru_cache

import folium
from flask import Flask, render_template, request, jsonify
from flask_caching import Cache

import ui_config as cfg
from load_data.load_data import MPKGraphLoader, Stop
from ui.FormData import FormData
from ui.StopRepository import StopRepository, StopDTO

from map_utils import get_izochrone_map, TransferConfig, _load_stops

LOADERS = {
    "2023": MPKGraphLoader.from_pickle('./data/mpk_graph_loader_2023.pkl'),
    "2024": MPKGraphLoader.from_pickle('./data/mpk_graph_loader_2024.pkl')
}

### DEPS
all_stops_repo = StopRepository.from_loaders([LOADERS['2023'], LOADERS['2024']])


app_config = {
    "DEBUG": True,          # some Flask specific configs
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

    stop: StopDTO = all_stops_repo.get_by_id(starting_stop_id)
    form_data = FormData(stop.id, stop.display_name, transfer_time)

    map1 = compute_isochrone_map(stop.name, transfer_time, "2023")
    map2 = compute_isochrone_map(stop.name, transfer_time, "2024")

    return render_template(
        'page.html',
        map_html_1=map1._repr_html_(), map_html_2=map2._repr_html_(),
        form_data=form_data
    )


@app.route("/search_stops", methods=["GET"])
def search_stops():
    search_term = request.args.get('q', '').strip()
    matching_stops: list[StopDTO] = all_stops_repo.query(search_term)

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
    loader_name = request.args.get('loader', type=str)

    stop = all_stops_repo.get_by_id(starting_stop_id)
    mpk_map = compute_isochrone_map(stop.name, transfer_time, loader_name)

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

if __name__ == '__main__':
    app.run(debug=True)
