from dataclasses import dataclass


@dataclass
class FormData:
    stop_id: int
    stop_display_name: str
    transfer_time: int
    stop_reach_max_time: int