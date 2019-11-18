
import sqlite3
from sqlite3 import Binary
from io import BytesIO

from .data import Raster
from .load import from_wkb


def rast_to_wkb(rast):
    # raster to wkb buffer
    wkb = rast.wkb
    buf = Binary(wkb)
    return buf

def from_wkb_buffer(wkb_buf):
    # wkb buffer to raster
    rast = from_wkb(BytesIO(bytes(wkb_buf)))
    return rast


sqlite3.register_adapter(Raster, rast_to_wkb)
sqlite3.register_converter('rast', from_wkb_buffer)
