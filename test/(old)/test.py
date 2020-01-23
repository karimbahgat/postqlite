
import postqlite
from postqlite.vector.geometry import Geometry

from shapely.geometry import Point, LineString

from time import time

# init
db = postqlite.connect(':memory:')
cur = db.cursor()
cur.execute('create table test (geom geom)')

# populate
#shp = Point(1,1)
shp = LineString([(1,1) for _ in xrange(10000)])
geom = Geometry(None)
geom._shp = shp
print 'inserting', geom
t=time()
#for _ in range(1000):
#    cur.execute('insert into test values (?)', (geom,))
geoms = ((geom,) for _ in xrange(10000))
cur.executemany('insert into test values (?)', geoms)
print time()-t

# load just the wkb
print 'loading just the wkb'
t=time()
for row in cur.execute('select * from test'):
    pass
print time()-t
print row

# load full shapely
print 'loading full shapely'
t=time()
for row in cur.execute('select * from test'):
    row[0].load_shapely()
print time()-t
print row

# read just the types
print 'reading just the type'
t=time()
for row in cur.execute('select st_type(geom) from test'):
    pass
print time()-t
print row

# buffer
print 'buffering'
t=time()
for row in cur.execute('select st_buffer(geom, 1.0) as "[geom]" from test'):
    pass
print time()-t
print row[0], row[0].type()
#print row, Geometry(row[0]).type()




