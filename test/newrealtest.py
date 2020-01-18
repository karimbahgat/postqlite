
import postqlite
import json
import pythongis as pg

def viewresult(res):
    vz = pg.VectorData()
    for r in res:
        props = [] #r[:-1] if len(r) > 1 else []
        geoj = json.loads(r[-1]) # assumes last value of row is returned as geojson string
        vz.add_feature(props, geoj)
    vz.view()

# init
print 'init'
db = postqlite.connect(':memory:')
cur = db.cursor()
cur.execute('create table test (name text, geom geom)')

# populate with real country data
print 'populate'
d = postqlite.vector.load.from_file("C:\Users\kimok\Desktop\BIGDATA\priocountries\priocountries.shp")
for row,geoj in d.stream():
    name = row['NAME']
    cur.execute('insert into test values (?, st_simplify(st_geomfromgeojson(?),0.1))', (name, json.dumps(geoj),) )

# check full
print 'full', cur.execute('select count(oid) from test').fetchone()

# features that intersect eachother
##print 'self intersect'
##for row in cur.execute('select left.name, right.name from test as left, test as right where st_intersects(left.geom, right.geom)'):
##    print row

# view all types
print 'types'
for r in cur.execute('select distinct st_type(geom) from test'):
    print r

# view all as centroids
print 'centroids'
res = cur.execute('select name,st_asGeoJSON(st_centroid(geom)) from test')
viewresult(res)

# view all as bboxes
print 'bboxes'
for r in cur.execute('select name,st_xmin(geom),st_ymin(geom),st_xmax(geom),st_ymax(geom) from test limit 10'):
    print r
res = cur.execute('select name,st_asGeoJSON(st_makeEnvelope(st_xmin(geom),st_ymin(geom),st_xmax(geom),st_ymax(geom))) from test')
viewresult(res)

# check union
print 'union'
res = cur.execute('select st_asGeoJSON(st_union(geom)) from test')
viewresult(res)




