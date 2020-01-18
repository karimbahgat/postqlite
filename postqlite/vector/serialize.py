
import sqlite3
from sqlite3 import Binary

from .geometry import Geometry



def create_geom(wkb_buf):
    # wkb buffer to shapely
    # TODO: MAYBE HANDLE NONE?
    geom = Geometry(wkb_buf)
    return geom

def dump_geom(geom):
    # geometry class to wkb buffer
    # TODO: MAYBE HANDLE NONE?
    wkb_buf = geom.dump_wkb()
    return wkb_buf

##def geoj_to_wkb(geoj):
##    # geojson to wkb buffer
##    wkb = shape(geoj).wkb
##    buf = Binary(wkb)
##    return buf


sqlite3.register_converter('geom', create_geom)
sqlite3.register_adapter(Geometry, dump_geom)
#sqlite3.register_adapter(dict, geoj_to_wkb)
