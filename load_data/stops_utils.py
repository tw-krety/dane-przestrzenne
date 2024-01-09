
def get_bus_lines(routes: dict) -> dict:
    return {name: trails for name, trails in routes.items() if is_bus_line(name)}


def get_tram_lines(routes: dict) -> dict:
    return {name: trails for name, trails in routes.items() if not is_bus_line(name)}


def is_bus_line(name: str) -> bool:
    if name.isalpha():
        return True
    try:
        number = int(name)
    except ValueError:
        return False
    if number >= 100:
        return True
    return False


def get_tram_stops(routes: dict) -> set:
    ret = set()
    for name, (r1, r2) in routes.items():
        if not is_bus_line(name):
            ret.update(r1)
            ret.update(r2)
    return ret


def get_bus_stops(routes: dict) -> set:
    ret = set()
    for name, (r1, r2) in routes.items():
        if is_bus_line(name):
            ret.update(r1)
            ret.update(r2)
    return ret


def get_double_stops(routes: dict) -> set:
    bus = get_bus_stops(routes)
    tram = get_tram_stops(routes)
    return bus.intersection(tram)