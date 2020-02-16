import postqlite
from postqlite.geometry.geometry import Geometry

from shapely.geometry import Point, LineString

# init
print 'init'
db = postqlite.connect(':memory:')
cur = db.cursor()
cur.execute('create table test (geom geom, geom2 geom)')

# populate
print 'inserting'
#shp = Point(1,1)
shp = LineString([(1,1) for _ in xrange(10000)])
geom = Geometry(shp.wkb)
geoms = ((geom,geom) for _ in xrange(100))
cur.executemany('insert into test values (?,?)', geoms)

#################
# constructors

# point
print 'construct point'
for row in cur.execute('select st_point(1,2) as "[geom]" from test'):
    print str(row)[:100]
    print row[0].bbox()
    break

# envelope
print 'construct envelope'
for row in cur.execute('select st_MakeEnvelope(0,0,10,10) as "[geom]" from test'):
    print str(row)[:100]
    print row[0].bbox()
    break

# wkt
print 'construct from wkt'
for row in cur.execute('''select st_GeomFromText('Point(1 2)') as "[geom]" from test'''):
    print str(row)[:100]
    print row[0].bbox()
    break

# geoj
print 'construct from geojson'
for row in cur.execute('''select st_GeomFromGeoJSON('{"type":"Point","coordinates":[-48.23456,20.12345]}') as "[geom]" from test'''):
    print str(row)[:100]
    print row[0].bbox()
    break


#################
# representation

# as wkt
print 'as wkt'
for row in cur.execute('select st_asText(st_MakeEnvelope(0,0,10,10)) from test'):
    print str(row)[:100]
    break

# as geojson
print 'as geojson'
for row in cur.execute('select st_asGeoJSON(st_MakeEnvelope(0,0,10,10)) from test'):
    print str(row)[:100]
    break

# as svg
# ...

# as raster
print 'as raster'
for geom,rast in cur.execute('select st_Buffer(st_Point(0,0), 50) as "[geom]",rt_MakeEmptyRaster(720,360,-180,90,0.5,-0.5,0,0) as "[rast]" from test'):
    print geom.bbox(),rast.metadata()
    grast = geom.as_raster(rast, 'u1', 255)
    print grast.summarystats()
    #arr = grast.data(1)
    #from PIL import Image
    #Image.fromarray(arr).show()
    break


#################
# basic info

# load just the wkb
print 'loading just the wkb'
for row in cur.execute('select * from test'):
    print str(row)[:100]
    break

# read just the types
print 'reading just the type'
for row in cur.execute('select geometrytype(geom) from test'):
    print row
    break

# read bounds
print 'reading the bounds'
for row in cur.execute('select st_xmin(geom),st_ymin(geom),st_xmax(geom),st_ymax(geom) from test'):
    print row
    break

# box2d
print 'box2d'
for row in cur.execute('select st_asText(box2d(geom)) from test'):
    print row
    break

# box2d expand
print 'expand'
for row in cur.execute('select st_asText(st_expand(geom, 0.666)) from test'):
    print row
    break

# area
print 'area'
for row in cur.execute('select st_area(st_buffer(geom, 1.0)) from test'):
    print row
    break

# intersects
print 'intersects'
for row in cur.execute('select st_intersects(geom,geom2) from test'):
    print row
    break

# disjoint
print 'disjoint'
for row in cur.execute('select st_disjoint(geom,geom2) from test'):
    print row
    break

# distance
print 'distance'
for row in cur.execute('select st_distance(geom,geom2) from test'):
    print row
    break


#######
# produces new geoms

# centroid
print 'centroid'
for row in cur.execute('select st_astext(st_centroid(st_makeenvelope(0,0,10,10))) from test'):
    print row
    break

# buffer
print 'buffering'
for row in cur.execute('select st_buffer(geom, 1.0) as "[geom]", geometrytype(st_buffer(geom, 1.0)) from test'):
    print row
    break

# intersection
print 'intersection'
for row in cur.execute('select st_intersection(geom,geom2) as "[geom]",geometrytype(st_intersection(geom,geom2)) from test'):
    print row
    break

# difference
print 'difference'
for row in cur.execute('select st_difference(geom,geom2) as "[geom]",geometrytype(st_difference(geom,geom2)) from test'):
    print row
    break

# union
print 'union'
for row in cur.execute('select geometrytype(st_union(geom,geom2)) from test'):
    print row
    break

# simplify
print 'simplify'
for row in cur.execute('select st_simplify(geom,0.01) as "[geom]",geometrytype(st_simplify(geom,0.01)) from test'):
    print row
    break

# simplify preserve topology
print 'simplify preserve topology'
for row in cur.execute('select st_astext(st_simplifyPreserveTopology(geom,0.01)) from test'):
    print row
    break

# transform (ie crs reproject)
# ...


##############
# aggregates

# agg union
print 'agg union'
for row in cur.execute('select geometrytype(st_union(geom)) from test'):
    print row
    break

# agg extent
print 'reading the aggregate bounds'
for row in cur.execute('select st_asText(st_extent(geom)) from test'):
    print row
    break





