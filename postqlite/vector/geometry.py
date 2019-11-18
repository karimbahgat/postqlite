
from sqlite3 import Binary

from shapely.wkb import loads as wkb_loads
from shapely.geometry import shape

from struct import unpack, unpack_from
from io import BytesIO
from itertools import islice

def _wkb_byteorder(wkb):
    byteorder = unpack_from('b', wkb)[0]
    byteorder = '>' if byteorder == 0 else '<'
    return byteorder

def _wkb_type(wkb):
    byteorder = _wkb_byteorder(wkb)
    typ = unpack_from(byteorder+'xi', wkb)[0]
    return typ


wkbtype_to_shptype = {1: 'Point',
                      2: 'LineString',
                      3: 'Polygon',
                      4: 'MultiPoint',
                      5: 'MultiLineString',
                      6: 'MultiPolygon'}


def register_funcs(conn):
    conn.create_function('st_type', 1, st_type)
    conn.create_function('st_buffer', 2, st_buffer)
    
    conn.create_function('box2d', 1, box2d)
    conn.create_function('st_xmin', 1, st_xmin)
    conn.create_function('st_xmax', 1, st_xmax)
    conn.create_function('st_ymin', 1, st_ymin)
    conn.create_function('st_ymax', 1, st_ymax)

def register_aggs(conn):
    conn.create_function('st_extent', 1, ST_Extent)


# internal db functions
# expects and outputs wkb binary buffer
# only for use inside the db, will not auto load as Geometry objects in select-queries
# see: https://postgis.net/docs/reference.html

def st_type(wkb):
    g = Geometry(wkb)
    typ = g.type()
    return typ

def st_buffer(wkb, dist):
    g = Geometry(wkb)
    g2 = g.buffer(dist)
    return g2.dump_wkb()

def box2d(wkb):
    box = Box2D(wkb)
    return box

def st_xmin(wkb):
    box = Box2D(wkb)
    return box.xmin

def st_ymin(wkb):
    box = Box2D(wkb)
    return box.ymin

def st_xmax(wkb):
    box = Box2D(wkb)
    return box.xmax

def st_ymax(wkb):
    box = Box2D(wkb)
    return box.ymax

def st_expand(wkb):
    raise Exception

# aggs

class ST_Extent(object):
    def __init__(self):
        self.xmin = None
        self.ymin = None
        self.xmax = None
        self.ymax = None

    def step(self, wkb):
        box = Box2D(wkb)
        self.xmin = min(self.xmin, box.xmin)
        self.ymin = min(self.ymin, box.ymin)
        self.xmax = max(self.xmax, box.xmax)
        self.ymax = max(self.ymax, box.ymax)

    def finalize(self):
        box = Box2D()
        box.xmin = self.xmin
        box.ymin = self.ymin
        box.xmax = self.xmax
        box.ymax = self.ymax
        return box.wkb

# class

class Box2D(object):

    def __init__(self, wkb):
        # available funcs:
        # https://postgis.net/docs/PostGIS_Special_Functions_Index.html#PostGIS_BoxFunctions
        # wkb structure
        # https://www.gaia-gis.it/gaia-sins/BLOB-Geometry.html
        # NOTE: maybe its not worth it, loading to shapely might be faster
        # ...
        # NOTE: actually is ca 10% faster than shapely for complex polys, and 5x for points. 
        # TODO: switch to faster version, build fmt string and unpack all coords in one call
        # ...

        # funky testing of polygon type (faster)
##        fmt = ''
##        byteorder = _wkb_byteorder(wkb)
##        fmt += 'x'
##        off = 1
##        wkbtyp = unpack_from(byteorder+'i', wkb, off)[0]
##        fmt += '4x'
##        off += 4
##        num = unpack_from(byteorder+'i', wkb, off)[0]
##        fmt += '4x'
##        off += 4
##        
##        for i in range(num):
##            pnum = unpack_from(byteorder+'i', wkb, off)[0]
##            #fmt += '4x' + 'dd'*pnum
##            if i == 0:
##                # exterior
##                fmt += '4x' + '{}d'.format(pnum*2)
##            else:
##                # ignore hole
##                fmt += '4x' + '{}x'.format(pnum*2*8)
##            off += 4 + 16*pnum
##        #print num,fmt
##        flat = unpack_from(byteorder+fmt, wkb)
##        #xs,ys = flat[0::2],flat[1::2]
##
##        self.xmin = min(islice(flat,0,None,2))
##        self.ymin = min(islice(flat,1,None,2))
##        self.xmax = max(islice(flat,0,None,2))
##        self.ymax = max(islice(flat,1,None,2))
##
##        return

        # real is below...

        def ringbox(stream):
            pnum = unpack(byteorder+'i', stream.read(4))[0]
            flat = unpack(byteorder+'{}d'.format(pnum*2), stream.read(16*pnum))
            #xs,ys = flat[0::2],flat[1::2]
            #return min(xs),min(ys),max(xs),max(ys)
            return (min(islice(flat,0,None,2)),
                    min(islice(flat,1,None,2)),
                    max(islice(flat,0,None,2)),
                    max(islice(flat,1,None,2)) )
        def polybox(stream):
            # only check exterior, ie the first ring
            #print 'poly tell',stream.tell()
            num = unpack(byteorder+'i', stream.read(4))[0]
            xmin,ymin,xmax,ymax = ringbox(stream)
            # skip holes, ie remaining rings
            if num > 1:
                for _ in range(num-1):
                    pnum = unpack(byteorder+'i', stream.read(4))[0]
                    unpack(byteorder+'{}x'.format(pnum*2*8), stream.read(16*pnum))
            return xmin,ymin,xmax,ymax
        def multi(stream):
            # 1 byte and one 4bit int class type of 1,2,3: point line or poly
            stream.read(5)
            return stream

        stream = BytesIO(wkb)
        byteorder = _wkb_byteorder(stream.read(1))
        wkbtyp = unpack(byteorder+'i', stream.read(4))[0]
        typ = wkbtype_to_shptype[wkbtyp]
        if typ == 'Point':
            x,y = unpack(byteorder+'dd', stream.read(8*2))
            xmin = xmax = x
            ymin = ymax = y
        elif typ == 'LineString':
            xmin,ymin,xmax,ymax = ringbox(stream)
        elif typ == 'Polygon':
            xmin,ymin,xmax,ymax = polybox(stream)
        elif typ == 'MultiPoint':
            num = unpack(byteorder+'i', stream.read(4))[0]
            flat = unpack(byteorder+'5xdd'*(num), stream.read((5+16)*num))
            xmin,ymin,xmax,ymax = (min(islice(flat,0,None,2)),
                                    min(islice(flat,1,None,2)),
                                    max(islice(flat,0,None,2)),
                                    max(islice(flat,1,None,2)) )
        elif typ == 'MultiLineString':
            num = unpack(byteorder+'i', stream.read(4))[0]
            xmins,ymins,xmaxs,ymaxs = zip(*(ringbox(multi(stream)) for _ in range(num)))
            xmin,ymin,xmax,ymax = min(xmins),min(ymins),max(xmaxs),max(ymaxs)
        elif typ == 'MultiPolygon':
            num = unpack(byteorder+'i', stream.read(4))[0]
            xmins,ymins,xmaxs,ymaxs = zip(*(polybox(multi(stream)) for _ in range(num)))
            xmin,ymin,xmax,ymax = min(xmins),min(ymins),max(xmaxs),max(ymaxs)
            
        self.xmin = xmin
        self.ymin = ymin
        self.xmax = xmax
        self.ymax = ymax

    def expand(self, units):
        pass

class Geometry(object):

    def __init__(self, wkb):
        self._wkb = wkb
        self._shp = None

    # dont require shapely (ie reading binary directly)

    def type(self):
        if self._shp:
            return self._shp.geom_type
        else:
            typ = _wkb_type(self._wkb)
            typ = wkbtype_to_shptype[typ]
            return typ

    def bbox(self):
        if self._shp:
            # shapely already loaded, fastest to let shapely do it
            return self._shp.bounds
        else:
            # create directly from wkb, avoid overhead of converting to shapely
            # OR MAYBE PYTHON BBOX IS TOO SLOW? TEST! 
            box = Box2D(self._wkb)
            return (box.xmin,box.ymin,box.xmax,box.ymax)

    def area(self):
        if self._shp:
            # shapely already loaded, fastest to let shapely do it
            return self._shp.area
        else:
            # create directly from wkb, avoid overhead of converting to shapely
            # OR MAYBE PYTHON AREA IS TOO SLOW? TEST! 
            pass

    def as_GeoJSON(self):
        if self._shp:
            # shapely already loaded, fastest to let shapely do it
            return self._shp.__geo_interface__
        else:
            # create directly from wkb, avoid overhead of converting to shapely
            pass

    def as_SVG(self):
        # create directly from wkb
        pass

    # require shapely

    def buffer(self, dist):
        if not self._shp:
            self.load_shapely()
        geom = Geometry(None)
        shp = self._shp.buffer(dist)
        geom._shp = shp
        return geom

    # serializing

    def load_shapely(self):
        # wkb buffer to shapely
        self._shp = wkb_loads(bytes(self._wkb))
        self._wkb = None # avoid storing both shp and wkb at same time

    def dump_wkb(self):
        # shapely to wkb buffer
        if self._shp:
            wkb = self._shp.wkb
        else:
            wkb = self._wkb
        buf = Binary(wkb)
        return buf




    
