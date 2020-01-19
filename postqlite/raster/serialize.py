
import sqlite3
from sqlite3 import Binary
from io import BytesIO

from .raster import Raster


def create_rast(wkb_buf):
    # wkb buffer to raster
    rast = Raster(bytes(wkb_buf))
    return rast

def dump_rast(rast):
    # raster to wkb buffer
    wkb = rast.dump_wkb()
    buf = Binary(wkb)
    return buf


sqlite3.register_converter('rast', create_rast)
sqlite3.register_adapter(Raster, dump_rast)


