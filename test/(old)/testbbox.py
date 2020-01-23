
import postqlite
from time import time
import cProfile

from shapely.geometry import Point, LineString

# init
##db = postqlite.connect('testfile.db')
##cur = db.cursor()

# init and populate
db = postqlite.connect(':memory:')
cur = db.cursor()
cur.execute('create table test (geom geom)')
shp = Point(1,1)
#shp = LineString([(1,1) for _ in xrange(10000)])
geom = shp.wkb
print 'inserting'#, geom
t=time()
#for _ in range(1000):
#    cur.execute('insert into test values (?)', (geom,))
geoms = ((geom,) for _ in xrange(10000))
cur.executemany('insert into test values (?)', geoms)
print time()-t

# calc wkb bbox
print 'wkb bbox'
#pr = cProfile.Profile()
#pr.enable()
t=time()
for row in cur.execute('select geom from test limit 10000'):
    row[-1].bbox()
    pass
print time()-t
print row, row[-1].bbox()
#print pr.print_stats('tottime')

#fsdfs

# calc shapely bbox
print 'shapely bbox'
t=time()
for row in cur.execute('select geom from test limit 10000'):
    row[-1].load_shapely()
    row[-1]._shp.bounds
    pass
print time()-t
print row, row[-1].bbox()
