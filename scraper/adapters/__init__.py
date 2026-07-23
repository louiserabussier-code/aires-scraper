from .aprr import AprrAdapter
from .area import AreaAdapter
from .sanef import SanefAdapter
from .vinci import VinciAdapter

ADAPTERS = {
    "vinci": VinciAdapter(),
    "sanef": SanefAdapter(),
    "aprr": AprrAdapter(),
    "area": AreaAdapter(),
}
