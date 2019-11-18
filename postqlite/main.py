
import sqlite3

#from . import ops
#from . import stats
from .vector import geometry


def connect(path, *args, **kwargs):

    kwargs['detect_types'] = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES # overrides...
    conn = sqlite3.connect(path, *args, **kwargs)

    # make faster (SOMEHOW ACTUALLY MUCH SLOWER FOR EXECUTEMANY...)
    #conn.isolation_level = None

    # register custom functions
    #stats.register_funcs(self.db)
    #ops.register_funcs(self.db)
    geometry.register_funcs(conn)

    return conn
