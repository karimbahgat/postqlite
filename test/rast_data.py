
import postqlite
import json
import pythongis as pg

# TODO: DOUBLE CHECK THAT NULL VALUES ARE HANDLED THROUGHOUT

def viewresult(res):
    from PIL import Image
    vz = pg.renderer.Map()
    for r in res:
        props = [] #r[:-1] if len(r) > 1 else []
        if r[-1]:
            rast = r[-1] # assumes last value of row is returned as geojson string
            aff = list(rast.affine)[:6]
            #aff[4] *= -1 # invert for normal images
            ims = [Image.fromarray(b.data()) for b in rast.bands]
            im = Image.merge('RGB', ims)
            d = pg.RasterData(image=im,
                              #mode=rast.band(0).dtype, width=rast.width, height=rast.height,
                              affine=aff)
            d.bands[0].nodataval = 0
            vz.add_layer(d)
    vz.render_all()
    vz.view()

# init
print 'init'
db = postqlite.connect(':memory:')
cur = db.cursor()
cur.execute('create table test (rast rast)')

# populate with real country data
print 'populate'
d = postqlite.raster.data.Raster(r"C:\Users\kimok\OneDrive\Documents\GitHub\AutoMap\tests\testmaps\txu-oclc-6654394-nb-30-4th-ed.jpg")
for tile in d.tiled(tilesize=(1000,1000)):
    print tile
    wkb = tile.wkb
    wkbtile = postqlite.raster.raster.Raster(wkb)
    cur.execute('insert into test values (?)', (wkbtile,) )

# check full
print 'full', cur.execute('select count(oid) from test').fetchone()
res = cur.execute('select rast from test')
viewresult(res)

dfsdfs



### features that intersect eachother
##print 'self intersect'
##for row in cur.execute('select left.name, right.name from test as left, test as right where st_intersects(left.geom, right.geom)'):
##    print row
##
### view all types
##print 'types'
##for r in cur.execute('select distinct st_type(geom) from test'):
##    print r
##
### view all as centroids
##print 'centroids'
##res = cur.execute('select name,st_asGeoJSON(st_centroid(geom)) from test')
##viewresult(res)
##
### view all as bboxes
##print 'bboxes'
##for r in cur.execute('select name,st_xmin(geom),st_ymin(geom),st_xmax(geom),st_ymax(geom) from test where geom is not null limit 10'):
##    print r
##res = cur.execute('select name,st_asGeoJSON(st_makeEnvelope(st_xmin(geom),st_ymin(geom),st_xmax(geom),st_ymax(geom))) from test where geom is not null')
##viewresult(res)
##
### check union
##print 'union'
##res = cur.execute('select st_asGeoJSON(st_union(geom)) from test')
##viewresult(res)




