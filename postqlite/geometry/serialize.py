
import sqlite3
from sqlite3 import Binary

from .geometry import Geometry



def create_geom(blob):
    # from sqlite3 wkb blob to geometry memoryview
    # py2: memview of buffer, py3: memview of bytes
    wkb_mem = memoryview(blob)
    geom = Geometry(wkb_mem)
    return geom

##def dump_geom(geom):
##    # geometry memoryview to sqlite3 db blob
##    # py2: db requires buffer, py3: db requires memview
##    wkb_mem = geom.dump_wkb()
##    return Binary(wkb_mem.tobytes())

##def geoj_to_wkb(geoj):
##    # geojson to wkb buffer
##    wkb = shape(geoj).wkb
##    buf = Binary(wkb)
##    return buf


sqlite3.register_converter('geom', create_geom)
sqlite3.register_adapter(Geometry, lambda g: g.dump_wkb() )
#sqlite3.register_adapter(dict, geoj_to_wkb)
