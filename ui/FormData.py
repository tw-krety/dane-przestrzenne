from dataclasses import dataclass
from typing import Optional


@dataclass
class FormData:
    stop_id: int
    stop_display_name: str
    transfer_time: Optional[int]
    stop_reach_max_time: int