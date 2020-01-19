
import postqlite
import json
import pythongis as pg


# TODO: DOUBLE CHECK THAT NULL VALUES ARE HANDLED THROUGHOUT


# init
print 'init'
db = postqlite.connect(':memory:')
cur = db.cursor()
cur.execute('create table test (rast rast)')

# populate with real image data
print 'populate'
d = postqlite.raster.data.Raster(r"C:\Users\kimok\OneDrive\Documents\GitHub\AutoMap\tests\testmaps\txu-oclc-6654394-nb-30-4th-ed.jpg")
for tile in d.tiled(tilesize=(1000,1000)):
    wkb = tile.wkb
    wkbtile = postqlite.raster.raster.Raster(wkb)
    cur.execute('insert into test values (?)', (wkbtile,) )

# check full
print 'full', cur.execute('select count(oid) from test').fetchone()



#############
# get basic metadata

# width/height
print 'width/height'
for row in cur.execute('select st_width(rast),st_height(rast) from test'):
    print row
    break

# numbands
print 'numbands'
for row in cur.execute('select st_numbands(rast) from test'):
    print row
    break

# georef params
print 'georeref params'
for row in cur.execute('select st_ScaleX(rast),st_ScaleY(rast),st_SkewX(rast),st_SkewY(rast),st_UpperLeftX(rast),st_UpperLeftY(rast) from test'):
    print row
    break

# georeference
print 'georereference'
for row in cur.execute('select st_georeference(rast) from test'):
    print row
    break

# metadata
print 'metadata'
for row in cur.execute('select st_metadata(rast) from test'):
    print row
    break


####################
# querying

# raster to world
print 'raster to world'
for row in cur.execute('select st_asText(st_rasterToWorldCoord(rast, 0, 0)) from test'):
    print row
    break

# world to raster
print 'world to raster'
for row in cur.execute('select st_asText(st_worldToRasterCoord(rast, 0, 0)) from test'):
    print row
    break




