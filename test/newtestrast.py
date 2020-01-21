
import postqlite
import json
import pythongis as pg

from PIL import Image


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

# box2d
print 'box2d'
for row in cur.execute('select st_asText(st_box2d(rast)) from test'):
    print row
    break

# envelope
print 'envelope'
for row in cur.execute('select st_asText(st_envelope(rast)) from test'):
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


####################
# relations

# same alignment
print 'same alignment'
for rast1,rast2 in cur.execute("select t1.rast,t2.rast from test as t1, test as t2 limit 1 offset 1"):
    print rast1.bbox(), rast2.bbox()
    print rast1.same_alignment(rast2)
    break

# same alignment
print 'same alignment, aggregate'
for row in cur.execute("select st_sameAlignment(rast) from test"):
    print row
    break


####################
# extracting

# band selection
print 'band selection'
for row in cur.execute("select st_numBands(rast), st_numBands(st_Band(rast, 1)), st_numBands(st_Band(rast, '1,2')) from test"):
    print row
    break

# band nodata
print 'band nodata'
for row in cur.execute("select st_bandNoDataValue(rast,1) from test"):
    print row
    break

# band pixel type
print 'band pixel type'
for row in cur.execute("select st_bandPixelType(rast,1) from test"):
    print row
    break

# band numpy array
print 'band numpy array'
for row in cur.execute("select rast from test"):
    print row
    arr = row[0].data(1)
    print arr
    #from PIL import Image
    #Image.fromarray(arr).show()
    break

# band summary stats
print 'band summary stats'
for row in cur.execute("select st_summarystats(rast,1) from test"):
    print row
    break


#############
# changing

# resize
print 'resize'
for row in cur.execute('''select st_resize(rast,200,100) as "[rast]", st_width(st_resize(rast,200,100)),st_height(st_resize(rast,200,100)) from test'''):
    print row
    #arr = row[0].data(1)
    #print arr
    #from PIL import Image
    #Image.fromarray(arr).show()
    break

# map algebra, single
print 'map algebra, single'
for row in cur.execute('''select rast from test'''):
    print row
    rast = row[0]
    print rast.summarystats()
    print 'simple math'
    result = rast.mapalgebra(1, 'f4', '[rast] ** 2')
    print result.summarystats()
    
    #print 'dummy coding?'
    #result = rast.mapalgebra(1, 'f4', '[rast] = 255')
    #print result.summarystats()
    
    print 'conditional'
    result = rast.mapalgebra(1, 'f4', 'case when [rast] = 0 then 0 when [rast] <= 100 then 1 when [rast] <= 200 then 2 else 99 end')
    print result.summarystats()

    print 'between'
    result = rast.mapalgebra(1, 'f4', 'case when [rast] = 0 then 0 when [rast] between 1 and 100 then 1 when [rast] between 101 and 200 then 2 else 99 end')
    print result.summarystats()
    break

# map algebra, multi
print 'map algebra, multi'
for rast1,rast2 in cur.execute("select t1.rast,t2.rast from test as t1, test as t2 limit 1 offset 1"):
    print 1, rast1.summarystats()
    print 2, rast2.summarystats()
    
    print 'simple math'
    result = rast1.mapalgebra(rast2, '([rast1] + [rast2]) / 2.0',
                              None, 'union')
    print result.summarystats()
    
    #print 'dummy coding?'
    #result = rast.mapalgebra(1, 'f4', '[rast] = 255')
    #print result.summarystats()
    
    print 'conditional'
    result = rast.mapalgebra(rast2, 'case when [rast1] > [rast2] then 255 when [rast1] < [rast2] then 1 else 127 end',
                             None, 'union')
    print result.summarystats()
    #Image.fromarray(result.data()).show()

    #print 'between'
    #result = rast.mapalgebra(rast2 'case when [rast1] = 0 then 0 when [rast1] between 1 and 100 then 1 when [rast1] between 101 and 200 then 2 else 99 end')
    #print result.summarystats()
    
    break

# union aggregate
print 'union aggregate'

# in-db (unknown step error...?)
##for (rast,) in cur.execute("select st_union(rast) from test"):
##    print rast
##    break

# debug
agg = postqlite.raster.raster.ST_Union()
for (rast,) in cur.execute("select rast from test"):
    print rast
    agg.step(rast.dump_wkb(), 'max')
    #Image.fromarray(agg.result.data(1)).show()
rast = postqlite.raster.raster.Raster(agg.finalize())

# view
print rast.metadata()
print rast.summarystats()
Image.fromarray(rast.data(1)).show()











