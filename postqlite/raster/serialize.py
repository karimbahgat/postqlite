
import sqlite3
from sqlite3 import Binary
from io import BytesIO

from .raster import Raster


def create_rast(blob):
    # from sqlite3 wkb blob to raster memoryview
    # py2: memview of buffer, py3: memview of bytes
    wkb_buf = memoryview(blob)
    rast = Raster(wkb_buf)
    return rast

##def dump_rast(rast):
##    # raster memoryview to sqlite3 db blob
##    # py2: db requires buffer, py3: db requires memview
##    wkb_mem = rast.dump_wkb()
##    return Binary(wkb_mem.tobytes())

sqlite3.register_converter('rast', create_rast)
sqlite3.register_adapter(Raster, lambda r: r.dump_wkb() )


