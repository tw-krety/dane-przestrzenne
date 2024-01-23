import dataclasses

import folium
from flask import Flask, render_template, request, jsonify

import ui_config as cfg
from load_data.load_data import MPKGraphLoader, Stop
from ui.FormData import FormData
from ui.StopRepository import StopRepository, StopDTO

app = Flask(__name__, template_folder='templates')

from map_utils import get_izochrone_map, TransferConfig, _load_stops

STOP_NAME = 'maślice małe (brodnicka)'

loader_2023 = MPKGraphLoader.from_pickle('./data/mpk_graph_loader_2023.pkl')
loader_2024 = MPKGraphLoader.from_pickle('./data/mpk_graph_loader_2024.pkl')

### DEPS
stop_repository = StopRepository.from_loaders([loader_2023, loader_2024])


@app.route('/')
def map_view():
    starting_stop_id: int = request.args.get('starting_stop', default=cfg.DEFAULT_STARTING_STOP_ID, type=int)
    transfer_time = request.args.get('transfer_time', default=cfg.DEFAULT_TRANSFER_TIME, type=int)

    stop: StopDTO = stop_repository.get_by_id(starting_stop_id)
    form_data = FormData(stop.id, stop.display_name, transfer_time)

    map1 = compute_isochrone_map(stop.name, transfer_time, loader_2023)
    map2 = compute_isochrone_map(stop.name, transfer_time, loader_2024)

    return render_template(
        'page.html',
        map_html_1=map1._repr_html_(), map_html_2=map2._repr_html_(),
        form_data=form_data
    )


@app.route("/search_stops", methods=["GET"])
def search_stops():
    search_term = request.args.get('q', '').strip()
    matching_stops: list[StopDTO] = stop_repository.query(search_term)

    search_response = [
        {
            "id": stop.id,
            "text": stop.display_name
        }
        for stop in matching_stops
    ]

    return jsonify(results=search_response)


@app.route("/update_map", methods=["GET"])
def update_maps():
    starting_stop_id = request.args.get('starting_stop', type=int)
    transfer_time = request.args.get('transfer_time', type=int)
    loader = request.args.get('loader', type=str)

    loader = resolve_loader_by_name(loader)

    stop = stop_repository.get_by_id(starting_stop_id)
    mpk_map = compute_isochrone_map(stop.name, transfer_time, loader)

    return jsonify({
        'map_html': mpk_map._repr_html_(),
    })


def compute_isochrone_map(stop_name: str, transfer_time_minutes: int, loader: MPKGraphLoader):
    return get_izochrone_map(
        cfg.DEFAULT_REGIONS_RESOLUTION, loader,
        TransferConfig(stop_name, 5, transfer_time_minutes),
        [5, 15, 30, 45, 60, 75]
    )


def resolve_loader_by_name(loader_name: str):
    if loader_name == "2023":
        return loader_2023
    elif loader_name == "2024":
        return loader_2024
    else:
        raise ValueError(f"Invalid loader name: {loader_name}")


if __name__ == '__main__':
    app.run(debug=True)
