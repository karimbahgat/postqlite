
import numpy as np
import numpy.ma as ma
import math
import json
from struct import unpack_from, pack_into, pack, calcsize

from affine import Affine
from shapely.geometry import Point, MultiPoint, Polygon
from PIL import Image

from .load import file_reader
from ..vector.geometry import Geometry

from wkb_raster import write_wkb_raster

# TODOs:
# 1 (DONE): Honor nodata values throughout using np.ma arrays if rast has nodata ('hasNodataValue'), incl summarystats, mapalgebra, intersection, etc
# 2 (DONE): All vector and raster funcs and aggs must be moved to a separate 'register.py' module
# ... with separate functions for each that detects vector vs raster and calls the corresponding func/agg
# 3 (DONE): Add geometry burning function, asRaster() using basic PIL drawing
# 4: Figure out correct wkb handling (keep it as sqlite's read-write buffer? does that change the underlaying db data? how to create own read-write buffer?)
# 5: Make an interactive tk app for writing sql directly
# 6: Fix geometry asRaster() extent direction bug...
# ... 

def register_funcs(conn):
    # see: https://postgis.net/docs/reference.html

    # constructors
    conn.create_function('rt_MakeEmptyRaster', -1, lambda *args: make_empty_raster(*args).dump_wkb() ) 
    conn.create_function('rt_RastFromWKB', 1, lambda wkb: Raster(wkb).dump_wkb() ) # whats the point of this?
    conn.create_function('rt_Band', 2, lambda wkb,i: Raster(wkb).band(i).dump_wkb() ) 

    # metadata
    conn.create_function('rt_Width', 1, lambda wkb: Raster(wkb).width if wkb else None)
    conn.create_function('rt_Height', 1, lambda wkb: Raster(wkb).height if wkb else None)
    conn.create_function('rt_ScaleX', 1, lambda wkb: Raster(wkb).scaleX if wkb else None)
    conn.create_function('rt_ScaleY', 1, lambda wkb: Raster(wkb).scaleY if wkb else None)
    conn.create_function('rt_SkewX', 1, lambda wkb: Raster(wkb).skewX if wkb else None)
    conn.create_function('rt_SkewY', 1, lambda wkb: Raster(wkb).skewY if wkb else None)
    conn.create_function('rt_UpperLeftX', 1, lambda wkb: Raster(wkb).upperLeftX if wkb else None)
    conn.create_function('rt_UpperLeftY', 1, lambda wkb: Raster(wkb).upperLeftY if wkb else None)
    conn.create_function('rt_NumBands', 1, lambda wkb: Raster(wkb).numbands if wkb else None)
    conn.create_function('rt_GeoReference', 1, lambda wkb: json.dumps(Raster(wkb).georeference()) if wkb else None)
    conn.create_function('rt_MetaData', 1, lambda wkb: json.dumps(Raster(wkb).metadata()) if wkb else None)

    conn.create_function('rt_Box2D', 1, lambda wkb: Raster(wkb).box2d().dump_wkb() if wkb else None)

    #conn.create_function('rt_BandMetaData', 1, lambda wkb: Raster(wkb).numbands if wkb else None)
    conn.create_function('rt_BandNoDataValue', 2, lambda wkb,band: Raster(wkb).nodataval(band) if wkb else None)
    #conn.create_function('rt_BandIsNoData', 1, lambda wkb: Raster(wkb).numbands if wkb else None)
    conn.create_function('rt_BandPixelType', 2, lambda wkb,band: Raster(wkb).pixel_type(band) if wkb else None)
    #conn.create_function('rt_HasNoBand', 1, lambda wkb: Raster(wkb).numbands if wkb else None)

    # setting
    conn.create_function('rt_SetRotation', 2, lambda wkb,rad: Raster(wkb).set_rotation(rad).dump_wkb() if wkb else None)
    conn.create_function('rt_SetScale', 3, lambda wkb,x,y: Raster(wkb).set_scale(x,y).dump_wkb() if wkb else None)
    conn.create_function('rt_SetSkew', 3, lambda wkb,x,y: Raster(wkb).set_skew(x,y).dump_wkb() if wkb else None)
    conn.create_function('rt_SetUpperLeft', 3, lambda wkb,x,y: Raster(wkb).set_upperleft(x,y).dump_wkb() if wkb else None)

    # representations
    #conn.create_function('rt_Summary', 1, lambda wkb: Raster(wkb).summary() if wkb else None)
    conn.create_function('rt_Envelope', 1, lambda wkb: Raster(wkb).envelope().dump_wkb() if wkb else None)
    conn.create_function('rt_ConvexHull', 1, lambda wkb: Raster(wkb).convex_hull().dump_wkb() if wkb else None)
    #conn.create_function('rt_MinConvexHull', 1, lambda wkb: Raster(wkb).min_convex_hull().dump_wkb() if wkb else None)
    conn.create_function('rt_AsBinary', 1, lambda wkb: Raster(wkb).dump_wkb() if wkb else None)
    #PNG+JPEG? requires img type column

    # querying
    conn.create_function('rt_WorldToRasterCoord', 3, lambda wkb,x,y: Raster(wkb).world_to_raster_coord(x, y).dump_wkb() if wkb else None)
    conn.create_function('rt_RasterToWorldCoord', 3, lambda wkb,x,y: Raster(wkb).raster_to_world_coord(x, y).dump_wkb() if wkb else None)
    #conn.create_function('rt_Value', 3, lambda wkb,x,y: Raster(wkb).value(x, y) if wkb else None)
    #conn.create_function('rt_SetValue', 3, lambda wkb,x,y: Raster(wkb).value(x, y) if wkb else None)
    #conn.create_function('rt_PixelAsPolygon', 3, lambda wkb,x,y: Raster(wkb).value(x, y) if wkb else None)
    #conn.create_function('rt_PixelAsPoint', 3, lambda wkb,x,y: Raster(wkb).value(x, y) if wkb else None)
    #conn.create_function('rt_PixelAsCentroid', 3, lambda wkb,x,y: Raster(wkb).value(x, y) if wkb else None)

    # stats
    def summarystats(*args):
        if not args[0]:
            return None
        args = list(args)
        rast = Raster(args.pop(0))
        stats = rast.summarystats(*args)
        return json.dumps(stats)
    conn.create_function('rt_SummaryStats', -1, summarystats)

    # changing
    conn.create_function('rt_Resize', -1, lambda *args: Raster(args[0]).resize(*args[1:]).dump_wkb() if args[0] else None)
    #conn.create_function('rt_Rescale', -1, lambda *args: Raster(args[0]).rescale(*args[1:]).dump_wkb() if args[0] else None)
    #conn.create_function('rt_Resample', 2, lambda wkb,refwkb: Raster(wkb).resample(Raster(refwkb)).dump_wkb() if wkb else None)
    #conn.create_function('rt_Transform', 2, lambda wkb,crs: Raster(wkb).transform(crs).dump_wkb() if wkb else None)

    # interacting
    #conn.create_function('rt_Clip', 2, lambda wkb,geomwkb: Raster(wkb).clip(Geometry(geomwkb)).dump_wkb() if wkb and geomwkb else None)
    conn.create_function('rt_Intersection', -1, lambda *args: Raster(args[0]).intersection(Raster(*args[1:])).dump_wkb() if args[0] else None)
    conn.create_function('rt_MapAlgebra', -1, lambda *args: Raster(args[0]).mapalgebra(*args[1:]).dump_wkb() if args[0] else None)

    # relations
    conn.create_function('rt_SameAlignment', 2, lambda wkb,otherwkb: Raster(wkb).same_alignment(Raster(otherwkb)) if wkb and otherwkb else None)
    conn.create_function('rt_Intersects', 2, lambda wkb,otherwkb: Raster(wkb).intersects(Raster(otherwkb)) if wkb and otherwkb else None)
    #conn.create_function('rt_Disjoint', 2, lambda wkb,otherwkb: Raster(wkb).intersects(Raster(otherwkb)) if wkb and otherwkb else None)

def register_aggs(conn):
    conn.create_aggregate('rt_SameAlignment', 1, RT_SameAlignment)
    conn.create_aggregate('rt_Union', -1, RT_Union)
    conn.create_aggregate('rt_SummaryStatsAgg', -1, RT_SummaryStatsAgg)


# classes

class RT_SameAlignment(object):
    def __init__(self):
        self.ref = None
        self.failed = False

    def step(self, wkb):
        if wkb is None:
            return
        
        rast = Raster(wkb)
        if self.ref:
            # compare with the reference raster (first one)
            aligned = rast.same_alignment(self.ref)
            if not aligned:
                self.failed = True
        else:
            # first one
            self.ref = rast

    def finalize(self):
        success = not self.failed
        return success

class RT_SummaryStatsAgg(object):
    def __init__(self):
        self.result = None

    def step(self, *args):
        if args[0] is None:
            return

        rast = Raster(args[0])

        # parse args
        if len(args) >= 2:
            if isinstance(args[1], bool):
                # rast, boolean exclude_nodata_value
                exclude_nodata_value = args[1]
                nband = args[2] if len(args) >= 3 else 1
            elif isinstance(args[1], int):
                # rast, integer nband, boolean exclude_nodata_value
                nband = args[1]
                exclude_nodata_value = args[2] if len(args) >= 3 else True
            else:
                raise Exception('Invalid function args: {}'.format(args))
        else:
            nband = 1
            exclude_nodata_value = True

        # calc stats
        stats = rast.summarystats(nband, exclude_nodata_value)

        # update results
        if self.result:
            self.result['sum'] += stats['sum']
            self.result['count'] += stats['count']
            self.result['min'] = min(self.result['min'], stats['min'])
            self.result['max'] = max(self.result['max'], stats['max'])
            # what about stdev...? 
            # ... 

        else:
            self.result = stats

    def finalize(self):
        # make final calc
        self.result['mean'] = self.result['sum'] / float(self.result['count'])
        # what about stdev...?
        # ...
        self.result.pop('stddev')
        # dump to string (only used within the db)
        dictstr = json.dumps(self.result)
        return dictstr

class RT_Union(object):
    # NOTE: currently only unions one band, whereas postgis does all if not specified
    def __init__(self):
        self.result = None

    def step(self, *args):
        if args[0] is None:
            return

        # parse args
        args = list(args)
        args[0] = Raster(args[0])
        
        # setof raster rast
        if len(args) == 1 and isinstance(args[0], Raster):
            rast = args[0]
            nband = 1
            uniontype = 'last'
        # setof raster rast, integer nband
        elif len(args) == 2 and isinstance(args[0], Raster) and isinstance(args[1], int):
            rast,nband = args[:2]
            uniontype = 'last'
        # setof raster rast, text uniontype
        elif len(args) == 2 and isinstance(args[0], Raster) and isinstance(args[1], basestring):
            rast,uniontype = args[:2]
            nband = 1
        # setof raster rast, integer nband, text uniontype
        elif len(args) == 3 and isinstance(args[0], Raster) and isinstance(args[1], int) and isinstance(args[2], basestring):
            rast,nband,uniontype = args
        # else
        else:
            raise Exception('Invalid function args: {}'.format(args))
        
        if self.result:
            # update the cumulative union raster
            if uniontype == 'first':
                expr = '[rast1]'
            elif uniontype == 'last':
                expr = '[rast2]'
            elif uniontype == 'min':
                expr = 'min([rast1], [rast2])'
            elif uniontype == 'max':
                expr = 'max([rast1], [rast2])'
            elif uniontype == 'sum':
                expr = '[rast1] + [rast2]'
            # mean
            # count
            # range
            self.result = self.result.mapalgebra(nband, rast, nband, expr, None, 'union')
            
        else:
            # first one
            self.result = rast

    def finalize(self):
        wkb = self.result.dump_wkb()
        return wkb
    

def make_empty_raster(*args):
    # parse args
    if len(args) == 1 and isinstance(args[0], Raster):
        # raster rast
        rast = args[0]
        meta = rast.metadata()
        width,height,upperleftx,upperlefty,scalex,scaley,skewx,skewy,srid = [meta[k]
                                                                             for k in 'width,height,upperleftx,upperlefty,scalex,scaley,skewx,skewy,srid'.split(',')]
    elif len(args) >= 8 and isinstance(args[0], int):
        # integer width, integer height, float8 upperleftx, float8 upperlefty, float8 scalex, float8 scaley, float8 skewx, float8 skewy, integer srid=unknown
        width,height,upperleftx,upperlefty,scalex,scaley,skewx,skewy = args[:8]
        srid = args[8] if len(args) == 9 else 0
        
    elif len(args) == 5 and isinstance(args[0], int):
        # integer width, integer height, float8 upperleftx, float8 upperlefty, float8 pixelsize
        width,height,upperleftx,upperlefty,scale = args[:5]
        scalex = scaley = scale
        skewx,skewy = 0,0
        srid = 0

    else:
        raise Exception('Invalid function args: {}'.format(args))

    # create raster
    wkb = b''

    # write raster header from scratch
    header = dict(zip('width,height,ipX,ipY,scaleX,scaleY,skewX,skewY,srid'.split(','),
                      [width,height,upperleftx,upperlefty,scalex,scaley,skewx,skewy,srid]))
    header['version'] = 0 # think this is correct version? 
    header['numbands'] = 0
    endianFmt = '>' # arbitrary
    header['endian'] = 1 if endianFmt == '<' else 0
    headervals = [header[k] for k in 'version,numbands,scaleX,scaleY,ipX,ipY,skewX,skewY,srid,width,height'.split(',')]
    wkb += pack('<b', header['endian'])
    wkb += pack(endianFmt + 'HHddddddIHH', *headervals)

    rast = Raster(buffer(wkb))
    return rast


class Raster(object):
    def __init__(self, wkb):
        self._wkb = wkb
        self._header = None

##    def __repr__(self):
##        return "<Raster data: dtype={dtype} bands={bands} size={size} bbox={bbox}>".format(dtype=None, #self.dtype,
##                                                                                           bands=len(self.bands),
##                                                                                           size=(self.width,self.height),
##                                                                                           bbox=self.bbox)

    # metadata

    def _load_header(self):
        # TODO: its possible that each reference to rast column in query creates a new raster instance from the db for each
        # in that case, storing ._header doesnt help and loading entire header becomes very duplicative
        # explore only loading the bytes needed for each header param
        # OR access a cached version of the raster instance based on the wkb bytes?

        # NOTE: The WKB format restricts the width/height to max 65535
        # ...so will fail if unioning very large rasters, which I guess is okay
        # ...since the purpose is to work with tiles iteratively
    
        (endian,) = unpack_from('<b', self._wkb)

        if endian == 0:
            endian = '>'
        elif endian == 1:
            endian = '<'

        (version, bands, scaleX, scaleY, ipX, ipY, skewX, skewY,
         srid, width, height) = unpack_from(endian + 'xHHddddddIHH', self._wkb)

        self._header = dict()
        self._header['endian'] = endian
        self._header['version'] = version
        self._header['scaleX'] = scaleX
        self._header['scaleY'] = scaleY
        self._header['ipX'] = ipX
        self._header['ipY'] = ipY
        self._header['skewX'] = skewX
        self._header['skewY'] = skewY
        self._header['srid'] = srid
        self._header['width'] = width
        self._header['height'] = height
        self._header['numbands'] = bands

        self._affine = Affine(scaleX, skewX, ipX,
                              skewY, scaleY, ipY)

    @property
    def width(self):
        if not self._header:
            self._load_header()
        return self._header['width']

    @property
    def height(self):
        if not self._header:
            self._load_header()
        return self._header['height']

    @property
    def numbands(self):
        if not self._header:
            self._load_header()
        return self._header['numbands']

    @property
    def scaleX(self):
        if not self._header:
            self._load_header()
        return self._header['scaleX']

    @property
    def scaleY(self):
        if not self._header:
            self._load_header()
        return self._header['scaleY']

    @property
    def skewX(self):
        if not self._header:
            self._load_header()
        return self._header['skewX']

    @property
    def skewX(self):
        if not self._header:
            self._load_header()
        return self._header['skewX']

    @property
    def skewY(self):
        if not self._header:
            self._load_header()
        return self._header['skewY']

    @property
    def upperLeftX(self):
        if not self._header:
            self._load_header()
        return self._header['ipX']

    @property
    def upperLeftY(self):
        if not self._header:
            self._load_header()
        return self._header['ipY']

    def georeference(self):
        if not self._header:
            self._load_header()
        # gdal style default
        aff = [self._header[k] for k in 'scaleX skewY skewX scaleY ipX ipY'.split()]
        return aff

    def metadata(self):
        if not self._header:
            self._load_header()
        meta = {'upperleftx': self._header['ipX'],
                'upperlefty': self._header['ipY'],
                'width': self._header['width'],
                'height': self._header['height'],
                'scalex': self._header['scaleX'],
                'scaley': self._header['scaleY'],
                'skewx': self._header['skewX'],
                'skewy': self._header['skewY'],
                'srid': self._header['srid'],
                'numbands': self._header['numbands']}
        return meta

    def bbox(self):
        # get coords of all four corners
        w,h = self.width, self.height
        corners = [(0,0),(0,w-1),(w-1,h-1),(0,h-1)]
        coords = [self.raster_to_world_coord(px,py).as_GeoJSON()['coordinates']
                  for px,py in corners]
        xs,ys = zip(*coords)
        return min(xs),min(ys),max(xs),max(ys)

    def box2d(self):
        xmin,ymin,xmax,ymax = self.bbox()
        pointbox = Geometry(MultiPoint([(xmin,ymin),(xmax,ymax)]).wkb)
        return pointbox

    def envelope(self):
        xmin,ymin,xmax,ymax = self.bbox()
        polygon = Geometry(Polygon([(xmin,ymin),(xmin,ymax),(xmax,ymax),(xmax,ymin),(xmin,ymin)]).wkb)
        return polygon

    def convex_hull(self):
        w,h = self.width,self.height
        corners = [(0,0),(0,h-1),(w-1,h-1),(w-1,0)]
        coords = [self.raster_to_world_coord(px,py).as_GeoJSON()['coordinates'] for px,py in corners]
        coords.append(coords[-1])
        polygon = Geometry(Polygon(coords).wkb)
        return polygon

    # setting

    # TODO: not sure if these should write to the original buffer, or create separate copies...? 

    def set_rotation(self, rotation):
        if not self._header:
            self._load_header()

        # TODO: make sure this is the correct affine sequence...
        ang = math.degrees(rotation)
        self._affine = self._affine * Affine.rotation(ang)

        # update params
        xscale,xskew,xoff, yskew,yscale,yoff, _,_,_ = list(self._affine)
        self.set_scale(xscale, yscale)
        self.set_skew(xskew, yskew)

        return self

    def set_scale(self, scaleX, scaleY):
        if not self._header:
            self._load_header()
            
        self._header['scaleX'] = scaleX
        self._header['scaleY'] = scaleY

        # affines start after 'bHH' in the order of scaleX,scaleY,ipX,ipY,skewX,skewY
        endian = self._header['endian']
        pack_into(endian + 'dd', self._wkb, 1+2+2, scaleX, scaleY)

        return self

    def set_skew(self, skewX, skewY):
        if not self._header:
            self._load_header()
            
        self._header['skewX'] = skewX
        self._header['skewY'] = skewY

        # affines start after 'bHH' in the order of scaleX,scaleY,ipX,ipY,skewX,skewY
        endian = self._header['endian']
        pack_into(endian + 'dd', self._wkb, 1+2+2+8*4, skewX, skewY)

        return self

    def set_upperleft(self, upperLeftX, upperLeftY):
        if not self._header:
            self._load_header()
            
        self._header['ipX'] = upperLeftX
        self._header['ipY'] = upperLeftY

        # affines start after 'bHH' in the order of scaleX,scaleY,ipX,ipY,skewX,skewY
        endian = self._header['endian']
        pack_into(endian + 'dd', self._wkb, 1+2+2+8+8, upperLeftX, upperLeftY)

        return self

    # querying

    def raster_to_world_coord(self, px, py):
        if not self._header:
            self._load_header()
            
        x,y = self._affine * (px,py)

        shp = Point(x, y)
        geom = Geometry(shp.wkb)
        geom._shp = shp
        return geom

    def world_to_raster_coord(self, x, y):
        if not self._header:
            self._load_header()
            
        px,py = ~self._affine * (x,y)
            
        shp = Point(px, py)
        geom = Geometry(shp.wkb)
        geom._shp = shp
        return geom

    # bands

    def _band_start(self, i):
        if not self._header:
            self._load_header()

        skip = 1+60 #calcsize('bHHddddddIHH') # raster header

        _i = 1
        while _i < i:
        
            bandsize = self._band_size(skip)
            skip += bandsize

            _i += 1

        return skip

    def _band_header(self, i):
        if not self._header:
            self._load_header()

        header = dict()
        start = self._band_start(i)

        # Requires reading a single byte, and splitting the bits into the
        # header attributes
        endian = self._header['endian']
        (bits,) = unpack_from(endian + 'b', self._wkb, offset=start)

        header['isOffline'] = bool(bits & 128)  # first bit
        header['hasNodataValue'] = bool(bits & 64)  # second bit
        header['isNodataValue'] = bool(bits & 32)  # third bit

        pixtype = bits & int('00001111', 2) # bits 5-8
        header['pixtype'] = pixtype

        # Based on the pixel type, determine the data type byte size
        fmts = ['?', 'B', 'B', 'b', 'B', 'h',
                'H', 'i', 'I', 'f', 'd']
        fmt = fmts[pixtype]

        # Read the nodata value
        (nodata,) = unpack_from(endian + fmt, self._wkb, offset=start+1)
        header['nodata'] = nodata

        return header

    def _write_band_header(self, header):
        wkb = b''
        bits = 0

        endian = self._header['endian']

        if header['isOffline']:
            bits = (bits & int('01111111', 2)) | int('10000000', 2) # first bit
        if header['hasNodataValue']:
            bits = (bits & int('10111111', 2)) | int('01000000', 2) # second bit
        if header['isNodataValue']:
            bits = (bits & int('11011111', 2)) | int('00100000', 2) # third bit

        # Based on the pixel type, determine the struct format, byte size and
        # numpy dtype
        pixtype = header['pixtype']
        
        fmts = ['?', 'B', 'B', 'b', 'B', 'h',
                'H', 'i', 'I', 'f', 'd']
        dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2',
                  'u2', 'i4', 'u4', 'f4', 'f8']
        #dtypes = ['bool', 'uint8', 'uint8', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'float32', 'float64']
        sizes = [1, 1, 1, 1, 1, 2, 2, 4, 4, 4, 8]

        dtype = dtypes[pixtype]
        size = sizes[pixtype]
        fmt = fmts[pixtype]
        bits = (bits & int('11110000', 2)) | (pixtype & int('00001111', 2))

        # Write the bits to a byte
        wkb += pack(endian + 'b', bits)

        # Write the nodata value
        nodata = header['nodata']
        wkb += pack(endian + fmt, nodata)

        return wkb

    def _band_size(self, start):
        #print 'band start',start
        skip = 0
        
        # Requires reading a single byte, and splitting the bits into the
        # header attributes
        endian = self._header['endian']
        (bits,) = unpack_from(endian + 'b', self._wkb, offset=start)
        skip += 1

        # Based on the pixel type, determine the data type byte size
        pixtype = bits & int('00001111', 2) # bits 5-8
        sizes = [1, 1, 1, 1, 1, 2, 2, 4, 4, 4, 8]
        size = sizes[pixtype]

        # Skip nodataval
        skip += size

        # Skip data
        isOffline = bool(bits & 128)  # first bit
        if isOffline:
            raise Exception
        
        else:
            arraysize = self._header['width'] * self._header['height'] * size
            skip += arraysize

        #print 'band size',skip
        return skip

    def band(self, i):
        '''Returns a new raster containing only the specified bands'''
        if not self._header:
            self._load_header()
            
        if isinstance(i, int):
            bands = [i]
        else:
            bands = [int(_i.strip()) for _i in i.split(',')] # comma separated list of band nrs

        # init
        wkb = b''

        # copy raster header
        #rastheadersize = 1+60 #calcsize('bHHddddddIHH')
        #wkb += self._wkb[:rastheadersize]

        # OR edit and write raster header from scratch
        header = self._header.copy()
        endianFmt = header['endian']
        header['endian'] = 1 if header['endian'] == '<' else 0
        header['numbands'] = len(bands)
        headervals = [header[k] for k in 'version,numbands,scaleX,scaleY,ipX,ipY,skewX,skewY,srid,width,height'.split(',')]
        wkb += pack('<b', header['endian'])
        wkb += pack(endianFmt + 'HHddddddIHH', *headervals)

        # copy each specified band
        for bandnum in bands:
            #print 'band',repr(bandnum)
            start = self._band_start(bandnum)
            bandsize = self._band_size(start)
            wkb += self._wkb[start:start+bandsize]

        wkb_buf = buffer(wkb)
        rast = Raster(wkb_buf)
        return rast

    def nodataval(self, band=1):
        if not self._header:
            self._load_header()

        start = self._band_start(band)

        endian = self._header['endian']
        (bits,) = unpack_from(endian + 'b', self._wkb, offset=start)

        # Based on the pixel type, determine the data type
        pixtype = bits & int('00001111', 2) # bits 5-8

        fmts = ['?', 'B', 'B', 'b', 'B', 'h',
                'H', 'i', 'I', 'f', 'd']
        fmt = fmts[pixtype]

        # Read the nodata value
        (nodata,) = unpack_from(endian + fmt, self._wkb, offset=start+1)
        hasNodataValue = bool(bits & 64)  # second bit
        return nodata if hasNodataValue else None

    def pixel_type(self, band=1):
        '''Returns the numpy data type'''
        if not self._header:
            self._load_header()

        start = self._band_start(band)

        endian = self._header['endian']
        (bits,) = unpack_from(endian + 'b', self._wkb, offset=start)

        # Based on the pixel type, determine the data type
        pixtype = bits & int('00001111', 2) # bits 5-8

        dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2',
                  'u2', 'i4', 'u4', 'f4', 'f8']
        dtype = dtypes[pixtype]

        return dtype

    def data(self, band=1):
        '''Returns band data as numpy array'''
        if not self._header:
            self._load_header()

        start = self._band_start(band)
        skip = 0

        endian = self._header['endian']
        (bits,) = unpack_from(endian + 'b', self._wkb, offset=start)
        skip += 1

        # Based on the pixel type, determine the data type
        pixtype = bits & int('00001111', 2) # bits 5-8

        fmts = ['?', 'B', 'B', 'b', 'B', 'h',
                'H', 'i', 'I', 'f', 'd']
        dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2',
                  'u2', 'i4', 'u4', 'f4', 'f8']
        sizes = [1, 1, 1, 1, 1, 2, 2, 4, 4, 4, 8]
        fmt = fmts[pixtype]
        dtype = dtypes[pixtype]
        size = sizes[pixtype]

        # Read nodataval
        hasNodataValue = bool(bits & 64)  # second bit
        if hasNodataValue:
            (nodata,) = unpack_from(endian + fmt, self._wkb, offset=start+1)
        skip += size

        # Read data
        isOffline = bool(bits & 128)  # first bit
        if isOffline:
            raise Exception
        
        else:
            width,height = self._header['width'], self._header['height']
            data = np.ndarray((height, width),
                              buffer=self._wkb, offset=start+skip,
                              dtype=np.dtype(dtype)
                              )
            if hasNodataValue:
                mask = data == nodata
            else:
                mask = False
            data = ma.array(data, mask=mask)

        return data

    def summarystats(self, *args):
        # should return: count | sum  |    mean    |  stddev   | min | max

        # parse args
        if len(args) >= 0:
            if isinstance(args[0], bool):
                # boolean exclude_nodata_value
                exclude_nodata_value = args[0]
                nband = 1
            elif isinstance(args[0], int):
                # integer nband, boolean exclude_nodata_value
                nband = args[0]
                exclude_nodata_value = args[1] if len(args) == 2 else True
        else:
            nband = 1
            exclude_nodata_value = True

        # get stats
        arr = self.data(nband)
        if exclude_nodata_value is False:
            arr = np.array(arr) # full array without mask
        stats = {'count': int(arr.count()),
                 'sum': float(arr.sum()),
                 'mean': float(arr.mean()),
                 'stddev': float(np.std(arr)),
                 'min': float(arr.min()),
                 'max': float(arr.max()),
                 }
        return stats


    # changing

    def resize(self, *args):
        '''
        width, height, [algorithm='NearestNeighbour']
        '''
        if not self._header:
            self._load_header()

        # parse args
        assert len(args) >= 2
        if isinstance(args[0], int) and isinstance(args[1], int):
            width, height = args[:2]
            algorithm = args[2] if len(args) >= 3 else 'nearestneighbour'
        else:
            raise Exception('Invalid function args: {}'.format(args))

        # MAYBE just outsource entire writing here?
        # ...

        # init
        wkb = b''

        # copy raster header
        #rastheadersize = 1+60 #calcsize('bHHddddddIHH')
        #wkb += self._wkb[:rastheadersize]

        # OR edit and write raster header from scratch
        header = self._header.copy()
        endianFmt = header['endian']
        header['endian'] = 1 if header['endian'] == '<' else 0
        header['width'] = width
        header['height'] = height
        headervals = [header[k] for k in 'version,numbands,scaleX,scaleY,ipX,ipY,skewX,skewY,srid,width,height'.split(',')]
        wkb += pack('<b', header['endian'])
        wkb += pack(endianFmt + 'HHddddddIHH', *headervals)

        # write each band
        for bandnum in range(1, self._header['numbands']+1):
            #print 'band',repr(bandnum)
            # get and update band headers
            bandhead = self._band_header(bandnum)
            bandhead['isOffline'] = False
            
            # write band headers
            wkb += self._write_band_header(bandhead)

            # resize the data
            arr = self.data(bandnum)
            im = Image.fromarray(arr)
            method = {'nearestneighbor': Image.NEAREST,
                      'nearestneighbour': Image.NEAREST,
                      'bilinear': Image.BILINEAR,
                      'cubicspline': Image.BICUBIC,
                      'lanczos': Image.LANCZOS}[algorithm.lower()]
            im_result = im.resize((width,height), method)
            arr_result = np.array(im_result)

            if bandhead['hasNodataValue']:
                # also resize mask and write nodatavals into resulting array
                mask_im = Image.fromarray(arr.mask)
                mask_result = mask_im.resize((width,height), Image.NEAREST)
                arr_result[mask_result] = bandhead['nodata']
                
            # byteswap
            #if endianFmt != arr_result.dtype.byteorder:
            #    # TODO: HANDLE NATIVE BYTEORDER, IE '='
            #    arr_result = arr_result.byteswap()

            # write arr result
            databytes = arr_result.tostring()
            wkb += databytes

        wkb_buf = buffer(wkb)
        rast = Raster(wkb_buf)
        return rast

##    def rescale(self, *args):
##        if not self._header:
##            self._load_header()
##
##        # parse args
##        assert len(args) >= 2
##        if isinstance(args[0], (float,int)) and isinstance(args[1], (float,int)):
##            scalex,scaley = args[:2]
##            algorithm = args[2] if len(args) >= 3 else 'nearestneighbour'
##        else:
##            raise Exception('Invalid function args: {}'.format(args))
##
##        resample_args = []
##        # ...
##
##        rast = self.resample(*resample_args)
##        return rast

    def mapalgebra(self, *args):
        '''
        Single mode:
            Variant 1:
                nband, pixeltype, expression, [nodataval=NULL]
            Variant 2:
                pixeltype, expression, [nodataval=NULL]
        Multi mode:
            Variant 3:
                nband1, rast2, nband2, expression, [text pixeltype=NULL, text extenttype=INTERSECTION, text nodata1expr=NULL, text nodata2expr=NULL, double precision nodatanodataval=NULL]
            Variant 4:
                rast2, expression, [text pixeltype=NULL, text extenttype=INTERSECTION, text nodata1expr=NULL, text nodata2expr=NULL, double precision nodatanodataval=NULL]
        '''
        if not self._header:
            self._load_header()

        # parse args
        assert len(args) >= 2
        
        # single mode
        if isinstance(args[0], int) and isinstance(args[1], basestring):
            # nband, pixeltype, expression, nodataval=NULL
            nband, pixeltype, expression = args[:3]
            nodataval = args[3] if len(args) >= 4 else None
            mode = 'single'
            
        elif isinstance(args[0], basestring) and isinstance(args[1], basestring):
            # pixeltype, expression, nodataval=NULL
            pixeltype, expression = args[:2]
            nband = 1
            nodataval = args[2] if len(args) >= 3 else None
            mode = 'single'
            
        # multi mode
        elif isinstance(args[0], int) and isinstance(args[1], Raster):
            # integer nband1, raster rast2, integer nband2, text expression, text pixeltype=NULL, text extenttype=INTERSECTION, text nodata1expr=NULL, text nodata2expr=NULL, double precision nodatanodataval=NULL
            nband1,rast2,nband2,expression = args[:4]
            pixeltype = args[4] if len(args) >= 5 else None
            extenttype = args[5] if len(args) >= 6 else 'intersection'
            nodata1expr = args[6] if len(args) >= 7 else None
            nodata2expr = args[7] if len(args) >= 8 else None
            nodatanodataval = args[8] if len(args) >= 9 else 0 # default to 0? 
            mode = 'multi'
            
        elif isinstance(args[0], Raster) and isinstance(args[1], basestring):
            # raster rast2, text expression, text pixeltype=NULL, text extenttype=INTERSECTION, text nodata1expr=NULL, text nodata2expr=NULL, double precision nodatanodataval=NULL
            rast2,expression = args[:2]
            nband1,nband2 = 1,1 # assume first bands
            pixeltype = args[2] if len(args) >= 3 else None
            extenttype = args[3] if len(args) >= 4 else 'intersection'
            nodata1expr = args[4] if len(args) >= 5 else None
            nodata2expr = args[5] if len(args) >= 6 else None
            nodatanodataval = args[6] if len(args) >= 7 else 0 # default to 0? 
            mode = 'multi'
            
        else:
            raise Exception('Invalid function args: {}'.format(args))

        # MAYBE just outsource entire writing here?
        # ...

        # init
        wkb = b''

        if mode == 'single':
            # edit and write raster header from scratch
            header = self._header.copy()
            endianFmt = header['endian']
            header['endian'] = 1 if header['endian'] == '<' else 0
            header['numbands'] = 1
            if nodataval != None:
                header['hasNodataValue'] = True
                header['nodataval'] = nodataval
            headervals = [header[k] for k in 'version,numbands,scaleX,scaleY,ipX,ipY,skewX,skewY,srid,width,height'.split(',')]
            wkb += pack('<b', header['endian'])
            wkb += pack(endianFmt + 'HHddddddIHH', *headervals)
            
            # get and update band headers
            bandhead = self._band_header(nband)
            bandhead['isOffline'] = False
            dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2',
                      'u2', 'i4', 'u4', 'f4', 'f8']
            bandhead['pixtype'] = dtypes.index(pixeltype)
            
            # write band headers
            wkb += self._write_band_header(bandhead)

            # set environment
            arr = self.data(nband)
            arr = arr.astype(np.dtype(pixeltype))
            locenv = {'rast': arr, 'np': np}

            # parse expression
            expression = expression.lower()

            def sql2py(sql):
                # TODO: support multiple and/or statements
                # ... 

                # convert rast references
                sql = sql.replace('[rast]', 'rast')

                # equal condition
                # TODO: Need fix if = without spaces
                sql = sql.replace(' = ', ' == ')

                # max min
                sql = sql.replace('max(', 'np.maximum(')
                sql = sql.replace('min(', 'np.minimum(')
                
                # between clause, ie "col BETWEEN v1 AND v2"
                if 'between' in sql:
                    col,bw = sql.split(' between ')
                    vmin,vmax = bw.split(' and ')
                    sql = '({vmin} <= {col}) & ({col} <= {vmax})'.format(vmin=vmin, col=col, vmax=vmax)
                    
                return sql

            # calculate
            if expression.startswith('case'):
                # conditional expression
                # ie: case when then ... when then ... else
                expression = expression.replace('case when ', '')
                whenpart,elsepart = expression.split(' else ')
                
                whens = whenpart.split(' when ')
                when_cumul = np.zeros(arr.shape, dtype=bool)
                arr_result = arr.copy()
                for when in whens:
                    when,then = when.split(' then ')

                    # perform the math
                    pyexpr = sql2py(when)
                    #print 'when', pyexpr
                    when_result = eval(pyexpr, {}, locenv)
                    if np.any(when_result):
                        when_result = when_result & (when_result ^ when_cumul) # exclude previous when-pixels
                        when_cumul = when_cumul | when_result # update cumulative when-pixels

                        pyexpr = sql2py(then)
                        #print 'then', pyexpr
                        then_result = eval(pyexpr, {}, locenv)

                        # set values in results
                        arr_result[when_result] = then_result

                # final else clause
                remain = ~when_cumul
                if np.any(remain):
                    elsepart = elsepart.replace(' end', '')
                    pyexpr = sql2py(elsepart)
                    #print 'else', pyexpr
                    else_result = eval(pyexpr, {}, locenv)

                    # set values in results
                    arr_result[remain] = else_result

            else: 
                # simple expression
                pyexpr = sql2py(expression)
                arr_result = eval(pyexpr, {}, locenv)
                
            # byteswap
            #if endianFmt != arr_result.dtype.byteorder:
            #    # TODO: HANDLE NATIVE BYTEORDER, IE '='
            #    arr_result = arr_result.byteswap()

            # write arr result
            databytes = arr_result.tostring()
            wkb += databytes

        elif mode == 'multi':

            assert self.same_alignment(rast2)

            # determine output extent
            extenttype = extenttype.lower()
            
##            # get coords for each pixel corner in rast2...
##            w2,h2 = rast2.width, rast2.height
##            corners2 = [(0,0),(0,w2-1),(w2-1,h2-1),(0,h2-1)]
##            cornercoords2 = [rast2.raster_to_world_coord(px,py).as_GeoJSON()['coordinates'] for px,py in corners2]
##            # get bounding box of rast2's pixel corner coords expressed in rast1 pixel positions
##            cornerpixels2 = [self.world_to_raster_coord(x,y).as_GeoJSON()['coordinates'] for x,y in cornercoords2]
##            pxs2,pys2 = zip(*cornerpixels2)
##            pxmin2,pymin2,pxmax2,pymax2 = min(pxs2),min(pys2),max(pxs2),max(pys2)
##            # get the combined pixel bounding box for these two bounding boxes (rast1 and rast2)
##            w1,h1 = self.width, self.height
##            pxmin1,pymin1,pxmax1,pymax1 = 0,0,w1-1,h1-1
##            pxmin = min(pxmin1,pxmin2)
##            pymin = min(pymin1,pymin2)
##            pxmax = max(pxmax1,pxmax2)
##            pymax = max(pymax1,pymax2)
##            # determine width and height based on the extent of this pixel bounding box
##            width = pxmax - pxmin
##            height = pymax - pymin
##            print pxmin1,pymin1,pxmax1,pymax1
##            print pxmin2,pymin2,pxmax2,pymax2
##            print pxmin,pymin,pxmax,pymax
##            print width,height

            if extenttype == 'first':
                ipX,ipY = self.upperLeftX,self.upperLeftY
                width,height = self.width,self.height
                # unless specified, first will only include pixels where rast1 is valid
                if not nodata1expr:
                    nodata1expr = str(nodatanodataval)
                if not nodata2expr:
                    nodata2expr = '[rast1]'
                
            elif extenttype == 'second':
                ipX,ipY = rast2.upperLeftX,rast2.upperLeftY
                width,height = rast2.width,rast2.height
                # unless specified, second will only include pixels where rast2 is valid
                if not nodata1expr:
                    nodata1expr = '[rast2]'
                if not nodata2expr:
                    nodata2expr = str(nodatanodataval)
                
            elif extenttype == 'intersection':
                # get intersection of coord bboxes
                box1 = self.envelope()
                box2 = rast2.envelope()
                if box1.intersects(box2):
                    box = box1.intersection(box2)
                else:
                    # if empty result, ie no intersection
                    # return None?
                    # or return zero width/height raster? 
                    return None
                # calculate rast1 pixel positions for the intersected bbox
                xmin,ymin,xmax,ymax = box.bbox()
                corners = [(xmin,ymin),(xmin,ymax),(xmax,ymax),(xmax,ymin)]
                pixelcorners = [self.world_to_raster_coord(x,y).as_GeoJSON()['coordinates'] for x,y in corners]
                pxs,pys = zip(*pixelcorners)
                pxmin,pymin,pxmax,pymax = min(pxs),min(pys),max(pxs),max(pys)
                upperLeftX = xmin if self.scaleX > 0 else xmax
                upperLeftY = ymin if self.scaleY > 0 else ymax
                # calculate new georef from these pixel positions
                ipX,ipY = upperLeftX,upperLeftY 
                width = pxmax-pxmin
                height = pymax-pymin
                # unless specified, intersection will not include pixels where only one raster is valid
                if not nodata1expr:
                    nodata1expr = str(nodatanodataval)
                if not nodata2expr:
                    nodata2expr = str(nodatanodataval)
                
            elif extenttype == 'union':
                # get union of coord bboxes
                box1 = self.box2d()
                box2 = rast2.box2d()
                box = box1.union(box2)
                # calculate rast1 pixel positions for the intersected bbox
                xmin,ymin,xmax,ymax = box.bbox()
                corners = [(xmin,ymin),(xmin,ymax),(xmax,ymax),(xmax,ymin)]
                pixelcorners = [self.world_to_raster_coord(x,y).as_GeoJSON()['coordinates'] for x,y in corners]
                pxs,pys = zip(*pixelcorners)
                pxmin,pymin,pxmax,pymax = min(pxs),min(pys),max(pxs),max(pys)
                upperLeftX = xmin if self.scaleX > 0 else xmax
                upperLeftY = ymin if self.scaleY > 0 else ymax
                # calculate new georef from these pixel positions
                ipX,ipY = upperLeftX,upperLeftY 
                width = pxmax-pxmin
                height = pymax-pymin
                # unless specified, union will include pixels where any of the rasters are valid
                if not nodata1expr:
                    nodata1expr = '[rast2]'
                if not nodata2expr:
                    nodata2expr = '[rast1]'

            width,height = int(width),int(height)
            
            # edit and write raster header from scratch
            header = self._header.copy()
            endianFmt = header['endian']
            header['endian'] = 1 if header['endian'] == '<' else 0
            header['numbands'] = 1
            header['width'] = width
            header['height'] = height
            header['ipX'] = ipX
            header['ipY'] = ipY
            #header['nodataval'] = None # output will not have nodataval, how to disable? 
            headervals = [header[k] for k in 'version,numbands,scaleX,scaleY,ipX,ipY,skewX,skewY,srid,width,height'.split(',')]
            wkb += pack('<b', header['endian'])
            wkb += pack(endianFmt + 'HHddddddIHH', *headervals)
            
            # get and update band headers
            bandhead = self._band_header(nband1)
            bandhead['isOffline'] = False
            bandhead['hasNodataValue'] = True
            bandhead['nodata'] = nodatanodataval
            dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2',
                      'u2', 'i4', 'u4', 'f4', 'f8']
            if pixeltype:
                bandhead['pixtype'] = dtypes.index(pixeltype)
            else:
                # keep same as rast1
                pixeltype = dtypes[bandhead['pixtype']]
            
            # write band headers
            wkb += self._write_band_header(bandhead)

            # create raster for new extent
            frame = make_empty_raster(width, height, ipX, ipY, self.scaleX, self.scaleY, self.skewX, self.skewY)
            frame_result = np.ones((height,width), dtype=pixeltype) * nodatanodataval # prefilled with nodatanodataval
            frame_result = Image.fromarray(frame_result)

            # reframe array 1
            arr1 = self.data(nband1)
            arr1 = arr1.astype(np.dtype(pixeltype))
            ulX,ulY = self.raster_to_world_coord(0, 0).as_GeoJSON()['coordinates']
            startX1,startY1 = frame.world_to_raster_coord(ulX, ulY).as_GeoJSON()['coordinates']
            # calc nodata2 value
            #print 'arr1 pixel bounds',startX1,startY1, startX1+self.width, startY1+self.height
            pyexpr = nodata2expr.lower()
            pyexpr = pyexpr.replace('[rast1]','rast1')
            locenv = {'rast1': arr1}
            nodata2_result = eval(pyexpr, {}, locenv)
            if isinstance(nodata2_result, (float,int)):
                # constant
                arr1_paste = np.ones(arr1.shape, dtype=arr1.dtype) * nodata2_result
            else:
                # array
                arr1_paste = nodata2_result
            # im paste
            if arr1.mask is False:
                frame_result.paste(Image.fromarray(arr1_paste), (int(startX1),int(startY1)))
            else:
                maskim1 = Image.fromarray((~arr1.mask).astype('u1')*255, mode='L')
                frame_result.paste(Image.fromarray(arr1_paste), (int(startX1),int(startY1)), mask=maskim1)
            # array paste
            #arr1dum = np.zeros((height,width), dtype=bool)
            #arr1dum[int(startY1):int(startY1+self.height), int(startX1):int(startX1+self.width)] = True
            # im crop
            #offx1,offy1 = self.world_to_raster_coord(ipX, ipY).as_GeoJSON()['coordinates']
            #im1 = Image.fromarray(arr1).crop((offx1,offy1,offx1+width,offy1+height))
            #arr1 = np.array(im1)

            # reframe array 2
            arr2 = rast2.data(nband2)
            arr2 = arr2.astype(np.dtype(pixeltype))
            ulX,ulY = rast2.raster_to_world_coord(0, 0).as_GeoJSON()['coordinates']
            startX2,startY2 = frame.world_to_raster_coord(ulX, ulY).as_GeoJSON()['coordinates']
            # calc nodata1 value
            #print 'arr2 pixel bounds',startX2,startY2, startX2+rast2.width, startY2+rast2.height
            pyexpr = nodata1expr.lower()
            pyexpr = pyexpr.replace('[rast2]','rast2')
            locenv = {'rast2': arr2}
            nodata1_result = eval(pyexpr, {}, locenv)
            if isinstance(nodata1_result, (float,int)):
                # constant
                arr2_paste = np.ones(arr2.shape, dtype=arr2.dtype) * nodata1_result
            else:
                # array
                arr2_paste = nodata1_result
            # im paste
            if arr2.mask is False:
                frame_result.paste(Image.fromarray(arr2_paste), (int(startX2),int(startY2)))
            else:
                maskim2 = Image.fromarray((~arr2.mask).astype('u1')*255, mode='L') # invert mask for PIL
                frame_result.paste(Image.fromarray(arr2_paste), (int(startX2),int(startY2)), mask=maskim2)
            # array paste
            #arr2dum = np.zeros((height,width), dtype=bool)
            #arr2dum[int(startY2):int(startY2+rast2.height), int(startX2):int(startX2+rast2.width)] = True
            # im crop
            #offx2,offy2 = rast2.world_to_raster_coord(ipX, ipY).as_GeoJSON()['coordinates']
            #im2 = Image.fromarray(arr2).crop((offx2,offy2,offx2+width,offy2+height))
            #arr2 = np.array(im2)

            # first paste each array onto frame
            #frame_result[int(startY1):int(startY1+self.height), int(startX1):int(startX1+self.width)] = arr1
            #frame_result[int(startY2):int(startY2+rast2.height), int(startX2):int(startX2+rast2.width)] = arr2

            #frame_result.show()

            # get coords of the intersecting parts (this is where the expression will be applied)
            startX,endX = max(startX1,startX2),min(startX1+self.width,startX2+rast2.width)
            startY,endY = max(startY1,startY2),min(startY1+self.height,startY2+rast2.height)
            xmin,ymin = frame.raster_to_world_coord(startX,startY).as_GeoJSON()['coordinates']
            xmax,ymax = frame.raster_to_world_coord(endX,endY).as_GeoJSON()['coordinates']

            # expression is only for the pixels that intersect
            # threefore only run expression if the two rasters overlap in the common grid
            #frameisec = arr1dum & arr2dum
            if (endX-startX) > 0 and (endY-startY) > 0:
                #print 'isec pixel bounds', startX, startY, endX, endY

                # clip arr1 to intersecting region
                pxmin1,pymin1 = self.world_to_raster_coord(xmin,ymin).as_GeoJSON()['coordinates']
                pxmax1,pymax1 = self.world_to_raster_coord(xmax,ymax).as_GeoJSON()['coordinates']
                pxmin1,pymin1,pxmax1,pymax1 = max(pxmin1,0),max(pymin1,0),min(pxmax1,self.width),min(pymax1,self.height)
                pxmin1,pymin1,pxmax1,pymax1 = map(int, [pxmin1,pymin1,pxmax1,pymax1])
                #print 'arr1 subset',pxmin1,pymin1,pxmax1,pymax1
                arr1clip = arr1[pymin1:pymax1, pxmin1:pxmax1]

                # clip arr2 to intersecting region
                pxmin2,pymin2 = rast2.world_to_raster_coord(xmin,ymin).as_GeoJSON()['coordinates']
                pxmax2,pymax2 = rast2.world_to_raster_coord(xmax,ymax).as_GeoJSON()['coordinates']
                pxmin2,pymin2,pxmax2,pymax2 = max(pxmin2,0),max(pymin2,0),min(pxmax2,self.width),min(pymax2,self.height)
                pxmin2,pymin2,pxmax2,pymax2 = map(int, [pxmin2,pymin2,pxmax2,pymax2])
                #print 'arr2 subset',pxmin2,pymin2,pxmax2,pymax2
                arr2clip = arr2[pymin2:pymax2, pxmin2:pxmax2]

                # determine intersecting pixels mask
                isec_mask = np.zeros(arr1clip.shape, dtype=bool)
                if arr1clip.mask is not False:
                    isec_mask = isec_mask | arr1clip.mask
                if arr2clip.mask is not False:
                    isec_mask = isec_mask | arr2clip.mask

                # set environment
                #print 'isec dims',arr1clip.shape,arr2clip.shape
                locenv = {'rast1': arr1clip, 'rast2': arr2clip, 'np': np}

                # parse expression
                expression = expression.lower()

                def sql2py(sql):
                    # TODO: support multiple and/or statements
                    # ... 

                    # convert rast references
                    sql = sql.replace('[rast1]', 'rast1').replace('[rast2]', 'rast2')

                    # equal condition
                    # TODO: Need fix if = without spaces
                    sql = sql.replace(' = ', ' == ')

                    # max min
                    sql = sql.replace('max(', 'np.maximum(')
                    sql = sql.replace('min(', 'np.minimum(')
                    
                    # between clause, ie "col BETWEEN v1 AND v2"
                    if 'between' in sql:
                        col,bw = sql.split(' between ')
                        vmin,vmax = bw.split(' and ')
                        sql = '({vmin} <= {col}) & ({col} <= {vmax})'.format(vmin=vmin, col=col, vmax=vmax)
                        
                    return sql

                # compute expression for the clipped grids
                if expression.startswith('case'):
                    # conditional expression
                    # ie: case when then ... when then ... else
                    expression = expression.replace('case when ', '')
                    whenpart,elsepart = expression.split(' else ')
                    
                    whens = whenpart.split(' when ')
                    when_cumul = np.zeros(arr1clip.shape, dtype=bool)

                    # isect result starts out as fully masked array of nodatanodataval
                    isec_result = ma.array(np.ones(arr1clip.shape, dtype=pixeltype) * nodatanodataval, mask=isec_mask)
                    
                    #when_cumul = np.zeros((height,width), dtype=bool)
                    #arr_result = np.zeros((height,width), dtype=pixeltype)
                    
                    for when in whens:
                        when,then = when.split(' then ')

                        # perform the math
                        pyexpr = sql2py(when)
                        #print 'when', pyexpr
                        when_result = eval(pyexpr, {}, locenv)
                        if np.any(when_result):
                            when_result = when_result & (when_result ^ when_cumul) # exclude previous when-pixels
                            when_cumul = when_cumul | when_result # update cumulative when-pixels

                            pyexpr = sql2py(then)
                            #print 'then', pyexpr
                            then_result = eval(pyexpr, {}, locenv)

                            # set values in results
                            isec_result[when_result] = then_result

                    # final else clause
                    remain = ~when_cumul
                    if np.any(remain):
                        elsepart = elsepart.replace(' end', '')
                        pyexpr = sql2py(elsepart)
                        #print 'else', pyexpr
                        else_result = eval(pyexpr, {}, locenv)

                        # set values in results
                        isec_result[remain] = else_result

                else:
                    # simple expression
                    pyexpr = sql2py(expression)
                    isec_calc = eval(pyexpr, {}, locenv)
                    if isinstance(isec_calc, (float,int)):
                        # constant
                        isec_arr = np.ones(arr1clip.shape, dtype=arr1.dtype) * isec_calc
                    else:
                        # array
                        isec_arr = isec_calc
                    isec_result = ma.array(isec_arr, mask=isec_mask)

                # paste final expression results onto the intersecting region
                #frame_result[frameisec] = isec_result
                maskim = Image.fromarray((~isec_mask).astype('u1')*255, mode='L') # invert mask for PIL
                frame_result.paste(Image.fromarray(isec_result), (int(startX),int(startY)), mask=maskim)


            # TODO: special handling if nodata1expr or nodata2expr specified
            # ...

            frame_result = np.array(frame_result) # nodata is already encoded in the image/array
                    
            # byteswap
            #if endianFmt != arr_result.dtype.byteorder:
            #    # TODO: HANDLE NATIVE BYTEORDER, IE '='
            #    arr_result = arr_result.byteswap()

            # write arr result
            databytes = frame_result.tostring()
            wkb += databytes


        wkb_buf = buffer(wkb)
        rast = Raster(wkb_buf)
        return rast

    def intersection(self, *args):
        '''
        Variant 1:
            rast2, text returnband, [nodataval=NULL]
        Variant 2:
            rast2, [nodataval=NULL]
        Variant 3:
            band1, rast2, band2, text returnband, [nodataval=NULL]
        Variant 4:
            band1, rast2, band2, [nodataval=NULL]
        '''
        if not self._header:
            self._load_header()
            
        # parse args
        assert len(args) >= 1
        if isinstance(args[0], Raster):
            if len(args) >= 2 and isinstance(args[1], basestring):
                # raster rast2, text returnband, double precision[] nodataval
                rast2,returnband = args[:2]
                nodataval = args[2] if len(args) >= 3 else None
                band1 = band2 = 1
            else:
                # raster rast2, double precision[] nodataval
                rast2 = args[0]
                returnband = 'band1' # correct default? 
                nodataval = args[1] if len(args) >= 2 else None
                band1 = band2 = 1
        elif isinstance(args[0], int):
            if len(args) >= 4 and isinstance(args[3], basestring):
                # integer band1, raster rast2, integer band2, text returnband, double precision[] nodataval
                band1,rast2,band2,returnband = args[:4]
                nodataval = args[4] if len(args) >= 5 else None
            else:
                # integer band1, raster rast2, integer band2, double precision[] nodataval
                band1,rast2,band2 = args[:3]
                returnband = 'band1' # correct default? 
                nodataval = args[3] if len(args) >= 4 else None
        else:
            raise Exception('Invalid function args: {}'.format(args))

        # prep args for mapalgebra
        # integer nband1, raster rast2, integer nband2, text expression, text pixeltype=NULL, text extenttype=INTERSECTION, text nodata1expr=NULL, text nodata2expr=NULL, double precision nodatanodataval=NULL
        returnband = returnband.lower()
        expr = {'band1':'[rast1]', 'band2':'[rast2]'}[returnband] # TODO: 'both' not yet supported 
        pixeltype = None
        # nodata1expr=NULL, text nodata2expr=NULL, double precision nodatanodataval=NULL
        result = self.mapalgebra(band1, rast2, band2, expr, pixeltype, 'intersection')
        return result



    ############
    # relations

    def same_alignment(self, rastB):
        if not self._header:
            self._load_header()
        if not rastB._header:
            rastB._load_header()

        # Goal: both rasters must have the same scale, skew, srid and
        # at least one of any of the four corners of any pixel of one raster
        # falls on any corner of the grid of the other raster

        # check that have the same params
        for param in 'scaleX scaleY skewX skewY'.split(' '): # TODO: also same srid?
            if self._header[param] != rastB._header[param]:
                return False

        # test that corner coordinates match up
        # TODO: probably only need to do it for one corner, eg (0,0)
        w,h = self.width, self.height
        corners = [(0,0),(0,w-1),(w-1,h-1),(0,h-1)]
        for x_pixelA,y_pixelA in corners:
            x, y = self.raster_to_world_coord(x_pixelA,y_pixelA).as_GeoJSON()['coordinates']
            x_pixelB,y_pixelB = rastB.world_to_raster_coord(x, y).as_GeoJSON()['coordinates']
            if x_pixelB.is_integer() and y_pixelB.is_integer():
                # one of the corner coordinates of rastA
                # falls exactly on a corner pixel in rastB (integers)
                # meaning they have same alignment
                return True

        # coorner coordinates do not match up
        return False

    def intersects(self, *args):
        '''
        Variant 1:
            nbandA, rastB, nbandB, [nodata=NULL]
        Variant 2:
            rastB
        '''
        # for now only allow the simple raster-to-raster intersects

        # parse args
        if len(args) == 3:
            nbandA,rastB,nbandB = args
            mode = 'nodata'
        elif len(args) == 1:
            rastB = args[0]
            mode = 'convex'
        else:
            raise Exception('Invalid function args: {}'.format(args))

        # load headers
        if not self._header:
            self._load_header()
        if not rastB._header:
            rastB._load_header()

        # test
        if mode == 'convex':
            hullA = self.convex_hull()
            hullB = rastB.convex_hull()
            intersects = hullA.intersects(hullB)

        elif mode == 'nodata':
            hullA = self.convex_hull()
            hullB = rastB.convex_hull()
            maybe = hullA.intersects(hullB)
            if maybe:
                expr = '1'
                pixeltype = None
                # nodata1expr=NULL, text nodata2expr=NULL, double precision nodatanodataval=NULL
                overlay = self.mapalgebra(nbandA, rastB, nbandB, expr, pixeltype, 'intersection')
                intersects = overlay # TODO: how check result? 
            else:
                intersects = False

        return intersects


##    def add_band(self, *args, **kwargs):
##        if args and isinstance(args[0], Band):
##            band = args[0]
##        else:
##            band = Band(self, *args, **kwargs)
##        self.bands.append(band)

##    def tiled(self, tilesize=None, tiles=None):
##        # create iterable tiler class, to allow also checking length
##        
##        class Tiler:
##            def __init__(self, rast, tilesize=None, tiles=None):
##                self.rast = rast
##                
##                # determine tile sizes
##                if not (tilesize or tiles):
##                    tilesize = (200,200)
##                if tiles:
##                    xtiles,ytiles = list(map(float, (xtiles,ytiles)))
##                    tilesize = int(self.rast.width/xtiles)+1, int(self.rast.height/ytiles)+1
##
##                self.tilesize = tilesize
##                
##            def __iter__(self):
##                tw,th = self.tilesize
##                for y in range(0, self.rast.height, th):
##                    for x in range(0, self.rast.width, tw):
##                        tile = self.rast.crop([x, y, x+tw, y+th], worldcoords=False)
##                        yield tile
##                        
##            def __len__(self):
##                return self.tilenum()
##
##            def tilenum(self):
##                tw,th = list(map(float, self.tilesize))
##                tiles = (int(self.rast.width/tw)+1, int(self.rast.height/th))
##                tilenum = tiles[0] * tiles[1]
##                return tilenum
##
##        return Tiler(self, tilesize=tilesize, tiles=tiles)
##
##    def crop(self, bbox, worldcoords=True):
##        if worldcoords:
##            x1,y1,x2,y2 = bbox
##            px1,py1 = self.geo_to_cell(x1, y1)
##            px2,py2 = self.geo_to_cell(x2, y2)
##        else:
##            px1,py1,px2,py2 = bbox
##
##        print bbox, '-->', [px1,py1,px2,py2]
##
##        # do bounds check
##        pxmin = min(px1,px2)
##        pymin = min(py1,py2)
##        pxmax = max(px1,px2)
##        pymax = max(py1,py2)
##        
##        pxmin = max(0, pxmin)
##        pymin = max(0, pymin)
##        pxmax = min(self.width, pxmax)
##        pymax = min(self.height, pymax)
##
##        #print pxmin,pymin,pxmax,pymax
##
##        if pxmax < 0 or pxmin > self.width or pymax < 0 or pymin > self.height:
##            raise Exception("The cropping bbox is entirely outside the raster extent")
##
##        pw,ph = pxmax-pxmin, pymax-pymin
##        if pw <= 0 or ph <= 0:
##            raise Exception("Cropping bbox was too small, resulting in 0 pixels")
##
##        xscale,xskew,xoff,yskew,yscale,yoff,_,_,_ = list(self.affine)
##        xoff += px1 * xscale
##        yoff += py1 * yscale
##
##        px2, py2 = min(px1+pw, self.width), min(py1+ph, self.height)
##        pw, ph = px2-px1, py2-py1
##        
##        rast = Raster(None, pw, ph, [xscale,xskew,xoff,yskew,yscale,yoff])
##        for band in self.bands:
##            cropped_band = band.crop([px1, py1, px2, py2])
##            rast.add_band(cropped_band)
##        return rast 
    
    def dump_wkb(self):
        wkb = self._wkb
        return wkb


    
