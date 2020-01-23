
import postqlite
from geomet import wkb as geomet_wkb



# misc low level stuff from geomet, to circumvent slow wkb dumps code
# --> if len(list(flatten_multi_dim(coords_or_geoms))) == 0:
from itertools import chain
import struct
BIG_ENDIAN = b'\x00'
LITTLE_ENDIAN = b'\x01'
SRID_FLAG = b'\x20'
WKB_2D = {
    'Point': b'\x00\x00\x00\x01',
    'LineString': b'\x00\x00\x00\x02',
    'Polygon': b'\x00\x00\x00\x03',
    'MultiPoint': b'\x00\x00\x00\x04',
    'MultiLineString': b'\x00\x00\x00\x05',
    'MultiPolygon': b'\x00\x00\x00\x06',
    'GeometryCollection': b'\x00\x00\x00\x07',
}
WKB_Z = {
    'Point': b'\x00\x00\x03\xe9',
    'LineString': b'\x00\x00\x03\xea',
    'Polygon': b'\x00\x00\x03\xeb',
    'MultiPoint': b'\x00\x00\x03\xec',
    'MultiLineString': b'\x00\x00\x03\xed',
    'MultiPolygon': b'\x00\x00\x03\xee',
    'GeometryCollection': b'\x00\x00\x03\xef',
}
WKB_M = {
    'Point': b'\x00\x00\x07\xd1',
    'LineString': b'\x00\x00\x07\xd2',
    'Polygon': b'\x00\x00\x07\xd3',
    'MultiPoint': b'\x00\x00\x07\xd4',
    'MultiLineString': b'\x00\x00\x07\xd5',
    'MultiPolygon': b'\x00\x00\x07\xd6',
    'GeometryCollection': b'\x00\x00\x07\xd7',
}
WKB_ZM = {
    'Point': b'\x00\x00\x0b\xb9',
    'LineString': b'\x00\x00\x0b\xba',
    'Polygon': b'\x00\x00\x0b\xbb',
    'MultiPoint': b'\x00\x00\x0b\xbc',
    'MultiLineString': b'\x00\x00\x0b\xbd',
    'MultiPolygon': b'\x00\x00\x0b\xbe',
    'GeometryCollection': b'\x00\x00\x0b\xbf',
}
_WKB = {
    '2D': WKB_2D,
    'Z': WKB_Z,
    'M': WKB_M,
    'ZM': WKB_ZM,
}
_BINARY_TO_GEOM_TYPE = dict(
    chain(*((reversed(x) for x in wkb_map.items())
            for wkb_map in _WKB.values()))
)
_INT_TO_DIM_LABEL = {2: '2D', 3: 'Z', 4: 'ZM'}
def _header_bytefmt_byteorder(geom_type, num_dims, big_endian, meta=None):
    """
    Utility function to get the WKB header (endian byte + type header), byte
    format string, and byte order string.
    """
    dim = _INT_TO_DIM_LABEL.get(num_dims)
    if dim is None:
        pass  # TODO: raise

    type_byte_str = _WKB[dim][geom_type]
    srid = meta.get('srid')
    if srid is not None:
        # Add the srid flag
        type_byte_str = SRID_FLAG + type_byte_str[1:]

    if big_endian:
        header = BIG_ENDIAN
        byte_fmt = b'>'
        byte_order = '>'
    else:
        header = LITTLE_ENDIAN
        byte_fmt = b'<'
        byte_order = '<'
        # reverse the byte ordering for little endian
        type_byte_str = type_byte_str[::-1]

    header += type_byte_str
    if srid is not None:
        srid = int(srid)

        if big_endian:
            srid_header = struct.pack('>i', srid)
        else:
            srid_header = struct.pack('<i', srid)
        header += srid_header
    byte_fmt += b'd' * num_dims

    return header, byte_fmt, byte_order

def _dump_polygon(obj, big_endian, meta):
    """
    Dump a GeoJSON-like `dict` to a polygon WKB string.
    Input parameters and output are similar to :funct:`_dump_point`.
    """
    coords = obj['coordinates']
    vertex = coords[0][0]
    # Infer the number of dimensions from the first vertex
    num_dims = len(vertex)

    wkb_string, byte_fmt, byte_order = _header_bytefmt_byteorder(
        'Polygon', num_dims, big_endian, meta
    )

    # number of rings:
    wkb_string += struct.pack('%sl' % byte_order, len(coords))
    for ring in coords:
        # number of verts in this ring:
        wkb_string += struct.pack('%sl' % byte_order, len(ring))
        for vertex in ring:
            wkb_string += struct.pack(byte_fmt, *vertex)

    return wkb_string

def _dump_multipolygon(obj, big_endian, meta):
    """
    Dump a GeoJSON-like `dict` to a multipolygon WKB string.
    Input parameters and output are similar to :funct:`_dump_point`.
    """
    coords = obj['coordinates']
    vertex = coords[0][0][0]
    num_dims = len(vertex)

    wkb_string, byte_fmt, byte_order = _header_bytefmt_byteorder(
        'MultiPolygon', num_dims, big_endian, meta
    )

    poly_type = _WKB[_INT_TO_DIM_LABEL.get(num_dims)]['Polygon']
    if big_endian:
        poly_type = BIG_ENDIAN + poly_type
    else:
        poly_type = LITTLE_ENDIAN + poly_type[::-1]

    # apped the number of polygons
    wkb_string += struct.pack('%sl' % byte_order, len(coords))

    for polygon in coords:
        # append polygon header
        wkb_string += poly_type
        # append the number of rings in this polygon
        wkb_string += struct.pack('%sl' % byte_order, len(polygon))
        for ring in polygon:
            # append the number of vertices in this ring
            wkb_string += struct.pack('%sl' % byte_order, len(ring))
            for vertex in ring:
                wkb_string += struct.pack(byte_fmt, *vertex)

    return wkb_string





#shp = postqlite.vector.load.from_file(r"C:\Users\kimok\Desktop\BIGDATA\testup\WDPA\WDPA_Jul2019-shapefile-points.shp")
shp = postqlite.vector.load.from_file(r"C:\Users\kimok\Desktop\BIGDATA\testup\WDPA\WDPA_Jul2019-shapefile-polygons.shp")
print shp, len(shp)
names = shp.fieldnames + ['geom']
types = shp.fieldtypes + ['geom']

db = postqlite.connect('testfile.db')
coldef = ', '.join(('{} {}'.format(n,t) for n,t in zip(names,types)))
insertdef = ','.join('?'*len(names))
print coldef
cur = db.cursor()
cur.execute('create table if not exists test ({})'.format(coldef))

#wkbs = ((geomet_wkb.dumps(g),) for r,g in shp)
def rows():
    for r,g in shp:
        wkb = _dump_multipolygon(g,True,{}) if 'Multi' in g['type'] else _dump_polygon(g,True,{})
        row = list(r) + [buffer(wkb)]
        yield tuple(row)

print 'begin insert'

#cur.executemany('insert into test values (?)', wkbs)

db.isolation_level = None
cur.execute('begin')
for i,row in enumerate(rows()):
    if i>100000: break
    cur.execute('insert into test values ({})'.format(insertdef), row)
cur.execute('commit')

for r in cur.execute('select wdpaid,name,status,st_type(geom) from test limit 100'):
    print r


fdsfdfs
