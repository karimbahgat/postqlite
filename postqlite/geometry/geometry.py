
from sqlite3 import Binary

from shapely.wkb import loads as wkb_loads
from shapely.wkt import loads as wkt_loads
from shapely.geometry import asShape, Point, MultiPoint, Polygon, box
from shapely.ops import unary_union

from struct import unpack, unpack_from
from io import BytesIO
from itertools import islice
import json
import math
import sys


PY2 = sys.version_info[0] == 2


def _wkb_byteorder(wkb):
    byteorder = unpack_from('b', wkb)[0]
    byteorder = '>' if byteorder == 0 else '<'
    return byteorder


wkbtype_to_shptype = {1: 'Point',
                      2: 'LineString',
                      3: 'Polygon',
                      4: 'MultiPoint',
                      5: 'MultiLineString',
                      6: 'MultiPolygon',
                      7: 'GeometryCollection'}


def register_funcs(conn):
    # see: https://postgis.net/docs/reference.html

    # constructors
    # TODO: maybe make more effective by converting directly, without the shapely overhead
    conn.create_function('st_Point', 2, lambda x,y: Geometry(shp=Point(x,y)).dump_wkb() )
    conn.create_function('st_MakeEnvelope', 4, lambda xmin,ymin,xmax,ymax: Geometry(shp=box(xmin,ymin,xmax,ymax)).dump_wkb() )
    conn.create_function('st_GeomFromText', 1, lambda wkt: Geometry(shp=wkt_loads(wkt)).dump_wkb() )
    conn.create_function('st_GeomFromGeoJSON', 1, lambda geojstr: Geometry(shp=asShape(json.loads(geojstr))).dump_wkb() )

    # representation
    conn.create_function('st_AsText', 1, lambda wkb: Geometry(wkb).as_WKT() if wkb != None else None )
    conn.create_function('st_AsGeoJSON', 1, lambda wkb: json.dumps(Geometry(wkb).as_GeoJSON()) if wkb != None else None )
    conn.create_function('st_AsRaster', -1, lambda *args: Geometry(args[0]).as_raster(*args[1:]).dump_wkb() if args[0] else None )
    
    # brings back simple types
    conn.create_function('GeometryType', 1, lambda wkb: Geometry(wkb).type() if wkb != None else None )
    conn.create_function('st_Area', 1, lambda wkb: Geometry(wkb).area() if wkb != None else None )
    conn.create_function('st_Xmin', 1, lambda wkb: Geometry(wkb).bbox()[0] if wkb != None else None )
    conn.create_function('st_Xmax', 1, lambda wkb: Geometry(wkb).bbox()[2] if wkb != None else None )
    conn.create_function('st_Ymin', 1, lambda wkb: Geometry(wkb).bbox()[1] if wkb != None else None )
    conn.create_function('st_Ymax', 1, lambda wkb: Geometry(wkb).bbox()[3] if wkb != None else None )

    conn.create_function('st_Intersects', 2, lambda wkb,otherwkb: Geometry(wkb).intersects(Geometry(otherwkb)) if wkb != None and otherwkb != None else None )
    conn.create_function('st_Disjoint', 2, lambda wkb,otherwkb: Geometry(wkb).disjoint(Geometry(otherwkb)) if wkb != None and otherwkb != None else None )

    conn.create_function('st_Distance', 2, lambda wkb,otherwkb: Geometry(wkb).distance(Geometry(otherwkb)) if wkb != None else None )

    # brings back geom
    conn.create_function('Box2d', 1, lambda wkb: Geometry(wkb).box2d().dump_wkb() if wkb != None else None )
    conn.create_function('st_Envelope', 1, lambda wkb: Geometry(wkb).envelope().dump_wkb() if wkb != None else None )
    conn.create_function('st_Expand', 2, lambda wkb,dist: Geometry(wkb).expand(dist).dump_wkb() if wkb != None else None )
    
    conn.create_function('st_Centroid', 1, lambda wkb: Geometry(wkb).centroid().dump_wkb() if wkb != None else None )
    conn.create_function('st_Buffer', 2, lambda wkb,dist: Geometry(wkb).buffer(dist).dump_wkb() if wkb != None else None )
    
    conn.create_function('st_Intersection', 2, lambda wkb,otherwkb: Geometry(wkb).intersection(Geometry(otherwkb)).dump_wkb() if wkb != None and otherwkb != None else None )
    conn.create_function('st_Difference', 2, lambda wkb,otherwkb: Geometry(wkb).difference(Geometry(otherwkb)).dump_wkb() if wkb != None and otherwkb != None else None )
    conn.create_function('st_Union', 2, lambda wkb,otherwkb: Geometry(wkb).union(Geometry(otherwkb)).dump_wkb() if wkb != None and otherwkb != None else None )

    conn.create_function('st_Simplify', 2, lambda wkb,tol: Geometry(wkb).simplify(tol, preserve_topology=False).dump_wkb() if wkb != None else None )
    conn.create_function('st_SimplifyPreserveTopology', 2, lambda wkb,tol: Geometry(wkb).simplify(tol, preserve_topology=True).dump_wkb() if wkb != None else None )

def register_aggs(conn):
    conn.create_aggregate('st_Extent', 1, ST_Extent)
    conn.create_aggregate('st_Union', 1, ST_Union)
    

# aggs

class ST_Extent(object):
    def __init__(self):
        self.chunksize = 10000
        self.boxes = []
        self.result = None

    def step(self, wkb):
        if wkb is None:
            return
        self.boxes.append(Geometry(wkb).bbox())
        if len(self.boxes) >= self.chunksize:
            if self.result:
                # include any previous result
                self.boxes.append(self.result) 
            xmins,ymins,xmaxs,ymaxs = zip(*self.boxes)
            self.result = min(xmins),min(ymins),max(xmaxs),max(ymaxs)
            self.boxes = []

    def finalize(self):
        if self.boxes:
            # any remaining boxes
            if self.result:
                # include any previous result
                self.boxes.append(self.result) 
            xmins,ymins,xmaxs,ymaxs = zip(*self.boxes)
            self.result = min(xmins),min(ymins),max(xmaxs),max(ymaxs)
            self.boxes = []
        # return result
        xmin,ymin,xmax,ymax = self.result
        pointbox = Geometry(shp=MultiPoint([(xmin,ymin),(xmax,ymax)]))
        return pointbox.dump_wkb()

class ST_Union(object):
    def __init__(self):
        self.chunksize = 10000
        self.shapes = []
        self.result = None

    def step(self, wkb):
        if wkb is None:
            return
        geom = Geometry(wkb)
        geom._load_shapely()
        self.shapes.append(geom._shp)
        if len(self.shapes) >= self.chunksize:
            chunk_result = unary_union(self.shapes)
            if self.result:
                # merge with previous
                self.result = self.result.union(chunk_result)
            else:
                # first
                self.result = chunk_result
            self.shapes = []

    def finalize(self):
        if self.shapes:
            # any outstanding unions
            chunk_result = unary_union(self.shapes)
            if self.result:
                # merge with previous
                self.result = self.result.union(chunk_result)
            else:
                # first
                self.result = chunk_result

        resultgeom = Geometry(shp=self.result)
        return resultgeom.dump_wkb()

# class

CACHE = dict()

class Geometry(object):

    def __init__(self, wkb=None, shp=None):
        if wkb:
            wkb = memoryview(wkb)
        self._wkb = wkb
        self._shp = shp

    def _load_shapely(self):
        '''wkb buffer to shapely'''
        # TODO: its possible that each reference to geom column in query creates a new geom instance from the db for each
        # in that case, storing ._shp doesnt help and shapely creation becomes very duplicative
        # explore accessing a dict of cached geometry instances based on the wkb bytes?
##        wkb_bytes = self._wkb.tobytes()
##        cached = CACHE.get(wkb_bytes, None)
##        if cached:
##            #print 'getting cached'
##            shp = cached
##        else:
##            #print 'loading new'
##            shp = wkb_loads(wkb_bytes)
##            CACHE[wkb_bytes] = shp
##        self._shp = shp

        # non-cache approach
        self._shp = wkb_loads(self._wkb.tobytes())

    # dont require shapely (ie reading binary directly)

    def type(self):
        if self._shp:
            return self._shp.geom_type
        else:
            byteorder = _wkb_byteorder(self._wkb)
            typ = unpack_from(byteorder+'xi', self._wkb)[0]
            typ = wkbtype_to_shptype[typ]
            return typ

    def bbox(self):
        if self._shp:
            # shapely already loaded, fastest to let shapely do it
            xmin,ymin,xmax,ymax = self._shp.bounds
            return xmin,ymin,xmax,ymax
        else:
            # create directly from wkb, avoid overhead of converting to shapely
            # OR MAYBE PYTHON BBOX IS TOO SLOW? TEST!
            
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

            stream = BytesIO(self._wkb)
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
            else:
                raise NotImplementedError('Geometry bbox calculation of type {}'.format(typ))

            return xmin,ymin,xmax,ymax

    def box2d(self):
        xmin,ymin,xmax,ymax = self.bbox()
        pointbox = Geometry(shp=MultiPoint([(xmin,ymin),(xmax,ymax)]))
        return pointbox

    def envelope(self):
        xmin,ymin,xmax,ymax = self.bbox()
        polygon = Geometry(shp=Polygon([(xmin,ymin),(xmin,ymax),(xmax,ymax),(xmax,ymin),(xmin,ymin)]))
        return polygon

    def expand(self, units):
        xmin,ymin,xmax,ymax = self.bbox()
        w = xmax-xmin
        h = ymax-ymin
        xmin -= units
        xmax += units
        ymin -= units
        ymax += units
        pointbox = Geometry(shp=MultiPoint([(xmin,ymin),(xmax,ymax)]))
        return pointbox

    def area(self):
        # temp
        if not self._shp:
            self._load_shapely()
        return self._shp.area
        
##        if self._shp:
##            # shapely already loaded, fastest to let shapely do it
##            return self._shp.area
##        else:
##            # create directly from wkb, avoid overhead of converting to shapely
##            # OR MAYBE PYTHON AREA IS TOO SLOW? TEST! 
##            raise NotImplemented

    # representation

    def as_WKT(self):
        # temp solution
        if not self._shp:
            self._load_shapely()
        return self._shp.wkt
    
##        if self._shp:
##            # shapely already loaded, fastest to let shapely do it
##            return self._shp.__geo_interface__
##        else:
##            # create directly from wkb, avoid overhead of converting to shapely
##            raise NotImplemented

    def as_GeoJSON(self):
        # temp solution
        if not self._shp:
            self._load_shapely()
        return self._shp.__geo_interface__
    
##        if self._shp:
##            # shapely already loaded, fastest to let shapely do it
##            return self._shp.__geo_interface__
##        else:
##            # create directly from wkb, avoid overhead of converting to shapely
##            raise NotImplemented

    def as_SVG(self):
        # create directly from wkb
        pass

    def as_raster(self, *args):
        '''
        Group 1:
            Variant 1:
                refraster, pixeltype, [value=1, nodataval=0]
        Group 2:
            Variant 2:
                ...
            Variant 3:
                scalex, scaley, pixeltype, [value=1, nodataval=0, upperleftx=NULL, upperlefty=NULL, skewx=0, skewy=0]
        Group 3:
            Variant 4:
                ...
            Variant 5:
                width, height, pixeltype, [value=1, nodataval=0, upperleftx=NULL, upperlefty=NULL, skewx=0, skewy=0
        '''
        from ..raster.raster import Raster, make_empty_raster

        # parse args
        def getarg(args, pos, default):
            if len(args) >= (pos+1):
                val = args[pos]
                if val is None:
                    val = default
            else:
                val = default
            return val
            
        # GROUP 1: existing raster
        if not isinstance(args[0], (float,int)):
            # raster ref, text pixeltype, double precision value=1, double precision nodataval=0, boolean touched=false
            if isinstance(args[0], Raster):
                ref = args[0]
            else:
                ref = Raster(args[0])
            pixeltype = args[1]
            value = getarg(args, 2, 1) 
            nodataval = getarg(args, 3, 0)
            
        # GROUP 2: set params, autocalc width/height
        elif isinstance(args[0], float) and isinstance(args[2], float):
##            # double precision scalex, double precision scaley, double precision gridx, double precision gridy, text pixeltype, double precision value=1, double precision nodataval=0, double precision skewx=0, double precision skewy=0, boolean touched=false
##            # aligns upperleft to gridx/y
            scaleX,scaleY,gridX,gridY = args[:4]
            pixeltype = args[4]
            value = getarg(args, 5, 1) 
            nodataval = getarg(args, 6, 0) 
            skewX = getarg(args, 7, 0.0) 
            skewY = getarg(args, 8, 0.0)

            xmin,ymin,xmax,ymax = self.bbox()
            width = abs(xmax-xmin) / float(scaleX)
            height = abs(ymax-ymin) / float(scaleY)
            width = int(round(abs(width)))
            height = int(round(abs(height)))

            from affine import Affine
            upperLeftX = xmin if scaleX > 0 else xmax
            upperLeftY = ymin if scaleY > 0 else ymax
            aff = Affine(scaleX,skewX,upperLeftX, skewY,scaleY,upperLeftY)
            gridCol,gridRow = (~aff) * (gridX,gridY) # predict pixel of gridx,gridy
            gridX2,gridY2 = aff * (math.floor(gridCol), math.floor(gridRow)) # use whole pixel to predict gridx,gridy
            upperLeftX,upperLeftY = upperLeftX - (gridX2-gridX), upperLeftY - (gridY2-gridY) # use actual and predicted gridx,gridy to adjust upperleft geom extent

            #print 'bbox',xmin,ymin,xmax,ymax
            #print 'grid align',gridX,gridY,gridCol,gridRow,gridX2,gridY2
            #print 'asrast params',width, height, upperLeftX, upperLeftY, scaleX, scaleY, skewX, skewY
            
            ref = make_empty_raster(width, height, upperLeftX, upperLeftY, scaleX, scaleY, skewX, skewY)
            
        elif isinstance(args[0], float) and isinstance(args[2], basestring):
            # double precision scalex, double precision scaley, text pixeltype, double precision value=1, double precision nodataval=0, double precision upperleftx=NULL, double precision upperlefty=NULL, double precision skewx=0, double precision skewy=0, boolean touched=false
            # uses upperleft
            scaleX,scaleY,pixeltype = args[:3]
            value = getarg(args, 3, 1) 
            nodataval = getarg(args, 4, 0) 
            xmin,ymin,xmax,ymax = self.bbox()
            upperLeftX = getarg(args, 5, xmin) 
            upperLeftY = getarg(args, 6, ymax) # flipped y by default
            skewX = getarg(args, 7, 0.0) 
            skewY = getarg(args, 8, 0.0) 
            width = abs(xmax-xmin) / float(scaleX)
            height = abs(ymax-ymin) / float(scaleY)
            width = int(round(abs(width)))
            height = int(round(abs(height)))
            
            ref = make_empty_raster(width, height, upperLeftX, upperLeftY, scaleX, scaleY, skewX, skewY)
            
        # GROUP 3: set width/height, autocalc params
        elif isinstance(args[0], int) and isinstance(args[2], float):
            # integer width, integer height, double precision gridx, double precision gridy, text pixeltype, double precision value=1, double precision nodataval=0, double precision skewx=0, double precision skewy=0, boolean touched=false
            # aligns upperleft to gridx/y            
            width,height,gridX,gridY = args[:4]
            pixeltype = args[4]
            value = getarg(args, 5, 1) 
            nodataval = getarg(args, 6, 0) 
            skewX = getarg(args, 7, 0.0) 
            skewY = getarg(args, 8, 0.0)

            xmin,ymin,xmax,ymax = self.bbox()
            scaleX = abs(xmax-xmin) / float(width)
            scaleY = abs(ymax-ymin) / float(height) * -1 # flipped y by default (since we only width,height,upperleft, no way to know what direction crs goes)

            from affine import Affine
            upperLeftX = xmin if scaleX > 0 else xmax
            upperLeftY = ymin if scaleY > 0 else ymax
            aff = Affine(scaleX,skewX,upperLeftX, skewY,scaleY,upperLeftY)
            gridCol,gridRow = (~aff) * (gridX,gridY) # predict pixel of gridx,gridy
            gridX2,gridY2 = aff * (math.floor(gridCol), math.floor(gridRow)) # use whole pixel to predict gridx,gridy
            upperLeftX,upperLeftY = upperLeftX - (gridX2-gridX), upperLeftY - (gridY2-gridY) # use actual and predicted gridx,gridy to adjust upperleft geom extent

            ref = make_empty_raster(width, height, upperLeftX, upperLeftY, scaleX, scaleY, skewX, skewY)

        elif isinstance(args[0], int) and isinstance(args[2], basestring):
            # integer width, integer height, text pixeltype, double precision value=1, double precision nodataval=0, double precision upperleftx=NULL, double precision upperlefty=NULL, double precision skewx=0, double precision skewy=0, boolean touched=false
            # uses upperleft
            width,height,pixeltype = args[:3]
            value = getarg(args, 3, 1) 
            nodataval = getarg(args, 4, 0) 
            xmin,ymin,xmax,ymax = self.bbox()
            upperLeftX = getarg(args, 5, xmin) 
            upperLeftY = getarg(args, 6, ymax) # flipped y by default
            skewX = getarg(args, 7, 0.0) 
            skewY = getarg(args, 8, 0.0) 
            scaleX = abs(xmax-xmin) / float(width)
            scaleY = abs(ymax-ymin) / float(height) * -1 # flipped y by default
            
            ref = make_empty_raster(width, height, upperLeftX, upperLeftY, scaleX, scaleY, skewX, skewY)
            
        else:
            raise Exception('Invalid function args: {}'.format(args))

        # create drawer
        import numpy as np
        from PIL import Image,ImageDraw,ImagePath
        mode = {'b1':'1', 'u1':'L', 'i4':'I', 'f8':'F'}[pixeltype]
        img = Image.new(mode, (ref.width, ref.height), nodataval)
        drawer = ImageDraw.Draw(img)

        # get the raster's inverse affine to use for drawing
        a,b,c,d,e,f,_,_,_ = list(~ref._affine) 

        # set burn values
        fill = value
        outline = None
        holefill = nodataval
        holeoutline = None
        #print ["burnmain",fill,outline,"burnhole",holefill,holeoutline]

        # make all multis so can treat all same
        geoj = self.as_GeoJSON()
        geotype = geoj['type']
        coords = geoj["coordinates"]
        if not "Multi" in geotype:
            coords = [coords]

        # polygon, basic black fill, no outline
        if "Polygon" in geotype:
            for poly in coords:
                # exterior
                exterior = [tuple(p) for p in poly[0]]
                path = ImagePath.Path(exterior)
                #print list(path)[:10]
                path.transform((a,b,c,d,e,f))
                #print list(path)[:10]
                drawer.polygon(path, fill=fill, outline=outline)
                # holes
                if len(poly) > 1:
                    for hole in poly[1:]:
                        hole = [tuple(p) for p in hole]
                        path = ImagePath.Path(hole)
                        path.transform((a,b,c,d,e,f))
                        drawer.polygon(path, fill=holefill, outline=holeoutline)
                        
        # line, 1 pixel line thickness
        elif "LineString" in geotype:
            for line in coords:
                path = ImagePath.Path(line)
                path.transform((a,b,c,d,e,f))
                drawer.line(path, fill=fill)
            
        # point, 1 pixel square size
        elif "Point" in geotype:
            path = ImagePath.Path(coords)
            path.transform((a,b,c,d,e,f))
            drawer.point(path, fill=fill)

        # make raster from drawn img
        out = make_empty_raster(ref)
        out._load_header()
        arr = np.array(img)
        # TODO: prob outsource to builtin add_band() method
        wkb = out._wkb.tobytes()
        dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2',
                  'u2', 'i4', 'u4', 'f4', 'f8']
        pixeltypenum = dtypes.index(pixeltype)
        bandheader = {'isOffline': False,
                      'hasNodataValue': True,
                      'isNodataValue': False, # maybe check?
                      'pixtype': pixeltypenum,
                      'nodata': nodataval,
                      }
        wkb += out._write_band_header(bandheader)
        wkb += arr.tostring()

        wkb_mem = memoryview(wkb)
        rast = Raster(wkb_mem)
        return rast
            

    # require shapely

    def intersects(self, othergeom):
        if not self._shp:
            self._load_shapely()
        if not othergeom._shp:
            othergeom._load_shapely()
        res = self._shp.intersects(othergeom._shp)
        return res

    def disjoint(self, othergeom):
        if not self._shp:
            self._load_shapely()
        if not othergeom._shp:
            othergeom._load_shapely()
        res = self._shp.disjoint(othergeom._shp)
        return res

    def distance(self, othergeom):
        if not self._shp:
            self._load_shapely()
        if not othergeom._shp:
            othergeom._load_shapely()
        res = self._shp.distance(othergeom._shp)
        return res

    def centroid(self):
        if not self._shp:
            self._load_shapely()
        shp = self._shp.centroid
        geom = Geometry(shp=shp)
        return geom

    def buffer(self, dist):
        if not self._shp:
            self._load_shapely()
        shp = self._shp.buffer(dist)
        geom = Geometry(shp=shp)
        return geom

    def intersection(self, othergeom):
        if not self._shp:
            self._load_shapely()
        if not othergeom._shp:
            othergeom._load_shapely()
        shp = self._shp.intersection(othergeom._shp)
        geom = Geometry(shp=shp)
        return geom

    def difference(self, othergeom):
        if not self._shp:
            self._load_shapely()
        if not othergeom._shp:
            othergeom._load_shapely()
        shp = self._shp.difference(othergeom._shp)
        geom = Geometry(shp=shp)
        return geom

    def union(self, othergeom):
        if not self._shp:
            self._load_shapely()
        if not othergeom._shp:
            othergeom._load_shapely()
        shp = self._shp.union(othergeom._shp)
        geom = Geometry(shp=shp)
        return geom

    def simplify(self, tolerance, preserve_topology=True):
        if not self._shp:
            self._load_shapely()
        shp = self._shp.simplify(tolerance, preserve_topology=preserve_topology)
        geom = Geometry(shp=shp)
        return geom
    
    # serializing

    def dump_wkb(self):
        # geometry memoryview to sqlite3 db blob
        # py2: db requires buffer, py3: db requires memview
        if self._wkb:
            # use existing wkb
            wkb_mem = self._wkb
        elif self._shp != None:
            # if no wkb, then dump from shp
            if self._shp.is_empty:
                return None
            wkb_mem = memoryview(self._shp.wkb)
        else:
            raise Exception('Geometry must have _wkb or _shp, but has neither')
            
        if PY2:
            wkb_mem = buffer(wkb_mem.tobytes())
        return Binary(wkb_mem)




    
