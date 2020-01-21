
import numpy as np
import math
import json
from struct import unpack_from, pack, calcsize

from affine import Affine
from shapely.geometry import Point, MultiPoint, Polygon
from PIL import Image

from .load import file_reader
from ..vector.geometry import Geometry

from wkb_raster import write_wkb_raster


def register_funcs(conn):
    # see: https://postgis.net/docs/reference.html

    # constructors
    #conn.create_function('ST_MakeEmptyRaster', 1, lambda wkb: Raster(wkb).dump_wkb() ) 
    conn.create_function('st_RastFromWKB', 1, lambda wkb: Raster(wkb).dump_wkb() ) # whats the point of this?
    conn.create_function('st_Band', 2, lambda wkb,i: Raster(wkb).band(i).dump_wkb() ) 

    # metadata
    conn.create_function('st_Width', 1, lambda wkb: Raster(wkb).width if wkb else None)
    conn.create_function('st_Height', 1, lambda wkb: Raster(wkb).height if wkb else None)
    conn.create_function('st_ScaleX', 1, lambda wkb: Raster(wkb).scaleX if wkb else None)
    conn.create_function('st_ScaleY', 1, lambda wkb: Raster(wkb).scaleY if wkb else None)
    conn.create_function('st_SkewX', 1, lambda wkb: Raster(wkb).skewX if wkb else None)
    conn.create_function('st_SkewY', 1, lambda wkb: Raster(wkb).skewY if wkb else None)
    conn.create_function('st_UpperLeftX', 1, lambda wkb: Raster(wkb).upperLeftX if wkb else None)
    conn.create_function('st_UpperLeftY', 1, lambda wkb: Raster(wkb).upperLeftY if wkb else None)
    conn.create_function('st_NumBands', 1, lambda wkb: Raster(wkb).numbands if wkb else None)
    conn.create_function('st_GeoReference', 1, lambda wkb: json.dumps(Raster(wkb).georeference()) if wkb else None)
    conn.create_function('st_MetaData', 1, lambda wkb: json.dumps(Raster(wkb).metadata()) if wkb else None)

    conn.create_function('st_Box2D', 1, lambda wkb: Raster(wkb).box2d().dump_wkb() if wkb else None)

    #conn.create_function('st_BandMetaData', 1, lambda wkb: Raster(wkb).numbands if wkb else None)
    conn.create_function('st_BandNoDataValue', 2, lambda wkb,band: Raster(wkb).no_data_value(band) if wkb else None)
    #conn.create_function('st_BandIsNoData', 1, lambda wkb: Raster(wkb).numbands if wkb else None)
    conn.create_function('st_BandPixelType', 2, lambda wkb,band: Raster(wkb).pixel_type(band) if wkb else None)
    #conn.create_function('st_HasNoBand', 1, lambda wkb: Raster(wkb).numbands if wkb else None)

    # representations
    conn.create_function('st_Envelope', 1, lambda wkb: Raster(wkb).envelope().dump_wkb() if wkb else None)
    #PNG+JPEG? requires img type column

    # querying
    conn.create_function('st_WorldToRasterCoord', 3, lambda wkb,x,y: Raster(wkb).world_to_raster_coord(x, y).dump_wkb() if wkb else None)
    conn.create_function('st_RasterToWorldCoord', 3, lambda wkb,x,y: Raster(wkb).raster_to_world_coord(x, y).dump_wkb() if wkb else None)
    #conn.create_function('st_Value', 3, lambda wkb,x,y: Raster(wkb).value(x, y) if wkb else None)
    #conn.create_function('st_SetValue', 3, lambda wkb,x,y: Raster(wkb).value(x, y) if wkb else None)
    #conn.create_function('st_PixelAsPolygon', 3, lambda wkb,x,y: Raster(wkb).value(x, y) if wkb else None)
    #conn.create_function('st_PixelAsPoint', 3, lambda wkb,x,y: Raster(wkb).value(x, y) if wkb else None)
    #conn.create_function('st_PixelAsCentroid', 3, lambda wkb,x,y: Raster(wkb).value(x, y) if wkb else None)

    # stats
    conn.create_function('st_SummaryStats', 2, lambda wkb,band: json.dumps(Raster(wkb).summarystats(band)) if wkb else None)

    # changing
    conn.create_function('st_Resize', 3, lambda wkb,width,height: Raster(wkb).resize(width, height).dump_wkb() if wkb else None)
    #conn.create_function('st_Resample', 2, lambda wkb,refwkb: Raster(wkb).resample(Raster(refwkb)).dump_wkb() if wkb else None)
    #conn.create_function('st_Transform', 2, lambda wkb,crs: Raster(wkb).transform(crs).dump_wkb() if wkb else None)

    # interacting
    #conn.create_function('st_Clip', 2, lambda wkb,geomwkb: Raster(wkb).clip(Geometry(geomwkb)).dump_wkb() if wkb and geomwkb else None)
    #conn.create_function('st_Intersection', 2, lambda wkb,otherwkb: Raster(wkb).intersection(Raster(otherwkb)).dump_wkb() if wkb and otherwkb else None)
    #conn.create_function('st_Union', 2, lambda wkb,otherwkb: Raster(wkb).union(Raster(otherwkb)).dump_wkb() if wkb and otherwkb else None)
    #conn.create_function('st_MapAlgebraExpr', 3, lambda wkb,otherwkb,opts: Raster(wkb).mapAlgebraExpr(Raster(otherwkb), **opts).dump_wkb() if wkb and otherwkb else None)

    # relations
    #conn.create_function('st_Intersects', 2, lambda wkb,otherwkb: Raster(wkb).intersects(Raster(otherwkb)) if wkb and otherwkb else None)
    #conn.create_function('st_Disjoint', 2, lambda wkb,otherwkb: Raster(wkb).intersects(Raster(otherwkb)) if wkb and otherwkb else None)

def register_aggs(conn):
    pass


# classes

##class Band(object):
##    def __init__(self, rast, data=None, dtype=None, width=None, height=None, initialvalue=0, nodataval=None):
##        self.rast = rast
##        # data is either None or np.array
##        self._data = data
##        self.dtype = dtype
##        self.width = width
##        self.height = height
##        self.initialvalue = initialvalue
##        self.nodataval = nodataval
##
##    def __repr__(self):
##        return "<Band object: dtype={dtype} size={size} nodataval={nodataval}>".format(dtype=self.dtype,
##                                                                                       size=(self.width,self.height),
##                                                                                       nodataval=self.nodataval)
##    
##
##    def data(self, bbox=None):        
##        # if file source, use the reader to return the data, but do not store the data in memory
##        if self.rast and self.rast.filepath:
##            bandnum = self.rast.bands.index(self)
##            data = self.rast.reader.data(bandnum, bbox)
##
##        else:
##            # create empty data if not exists
##            data = self._data
##            if data is None:
##                data = np.full((self.width,self.height), initialvalue, dtype=dtype)
##                self._data = data
##
##            # crop to bbox
##            if bbox:
##                x1,y1,x2,y2 = bbox
##                x2, y2 = min(x12, self.width), min(y2, self.height)
##                w,h = x2-x1, y2-y1
##                data = data[y1:y2, x1:x2]
##
##        return data
##
##    def crop(self, bbox):
##        data = self.data(bbox)
##        w, h = data.shape[1], data.shape[0]
##        band = Band(None, data, data.dtype, w, h, self.nodataval)
##        return band
##
##    def wkb_dict(self):
##        data = self.data() # force loading the data
##        dtypes = ['bool', None, None, 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'float32', 'float64']
##        pixtype = dtypes.index(str(self.dtype))
##                               
##        dct = {'isOffline': self.rast and bool(self.rast.filepath),
##               'hasNodataValue': self.nodataval is not None,
##               'isNodataValue': np.all(self.data == self.nodataval),
##               'ndarray': data,
##               'pixtype': pixtype,
##               }
##
##        dct['nodata'] = self.nodataval if dct['hasNodataValue'] else 0
##        
##        if dct['isOffline']:
##            bandnum = self.rast.bands.index(self)
##            dct['bandNumber'] = bandnum
##            dct['path'] = self.rast.filepath
##            
##        return dct

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

    def no_data_value(self, band=1):
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
        return nodata

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

        dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2',
                  'u2', 'i4', 'u4', 'f4', 'f8']
        dtype = dtypes[pixtype]

        # Skip nodataval
        sizes = [1, 1, 1, 1, 1, 2, 2, 4, 4, 4, 8]
        size = sizes[pixtype]
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

        return data

    def summarystats(self, band=1):
        # should return: count | sum  |    mean    |  stddev   | min | max
        arr = self.data(band)
        stats = {'count': arr.shape[0]*arr.shape[1],
                 'sum': float(arr.sum()),
                 'mean': float(arr.mean()),
                 'stddev': float(np.std(arr)),
                 'min': float(arr.min()),
                 'max': float(arr.max()),
                 }
        return stats


    # changing

    def resize(self, width, height, algorithm='nearest'):
        if not self._header:
            self._load_header()

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
            method = {'nearest': Image.NEAREST}[algorithm]
            im2 = im.resize((width,height), method)
            arr2 = np.array(im2)
                
            # write arr2
            if endianFmt != arr2.dtype.byteorder:
                arr2 = arr2.byteswap()
            databytes = arr2.tostring()
            wkb += databytes

        wkb_buf = buffer(wkb)
        rast = Raster(wkb_buf)
        return rast

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


    
