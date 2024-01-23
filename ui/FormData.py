from dataclasses import dataclass


@dataclass
class FormData:
    stop_id: int
    stop_display_name: str
    transfer_time: int