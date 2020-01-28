
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
#d = postqlite.raster.data.Raster(r"C:\Users\kimok\Desktop\BIGDATA\NORAD data\deforestation\Hansen_GFC-2018-v1.6_gain_00N_040W.tif")
print d
for tile in d.tiled(tilesize=(1000,1000)):
    wkb = tile.wkb
    wkbtile = postqlite.raster.raster.Raster(wkb)
    cur.execute('insert into test values (?)', (wkbtile,) )

# check full
print 'full', cur.execute('select count(oid) from test').fetchone()



#############
# construction

# create empty
print 'create empty'
for row in cur.execute('select rt_metadata(rt_MakeEmptyRaster(500,250,-180,90,0.5)) from test'):
    print row
    break


#############
# get basic metadata

# width/height
print 'width/height'
for row in cur.execute('select rt_width(rast),rt_height(rast) from test'):
    print row
    break

# numbands
print 'numbands'
for row in cur.execute('select rt_numbands(rast) from test'):
    print row
    break

# georef params
print 'georeref params'
for row in cur.execute('select rt_ScaleX(rast),rt_ScaleY(rast),rt_SkewX(rast),rt_SkewY(rast),rt_UpperLeftX(rast),rt_UpperLeftY(rast) from test'):
    print row
    break

# georeference
print 'georereference'
for row in cur.execute('select rt_georeference(rast) from test'):
    print row
    break

# metadata
print 'metadata'
for row in cur.execute('select rt_metadata(rast) from test'):
    print row
    break

# box2d
print 'box2d'
for row in cur.execute('select st_asText(rt_box2d(rast)) from test'):
    print row
    break

# box2d agg
print 'box2d agg'
for row in cur.execute('select st_asText(st_Extent(rt_box2d(rast))) from test'):
    print row
    break

# envelope
print 'envelope'
for row in cur.execute('select st_asText(rt_envelope(rast)) from test'):
    print row
    break

# convex hull
print 'convex hull'
for row in cur.execute('select st_asText(rt_ConvexHull(rast)) from test'):
    print row
    break


####################
# setting

# scale
print 'scale'
for row in cur.execute('select rt_MetaData(rt_SetScale(rast,-99,-99)) from test'):
    print row
    break

# skew
print 'skew'
for row in cur.execute('select rt_MetaData(rt_SetSkew(rast,-99,-99)) from test'):
    print row
    break

# offset
print 'offset'
for row in cur.execute('select rt_MetaData(rt_SetUpperLeft(rast,-99,-99)) from test'):
    print row
    break

# rotate
print 'rotate'
for row in cur.execute('select st_asText(rt_ConvexHull(rt_SetRotation(rast,0.78))),rt_ConvexHull(rt_SetRotation(rast,0.78)) as "[geom]" from test'):
    print row
##    geoj = row[1].as_GeoJSON()
##    import pythongis as pg
##    v = pg.VectorData()
##    v.add_feature([], geoj)
##    v.view()
    break


####################
# querying

# raster to world
print 'raster to world'
for row in cur.execute('select st_asText(rt_rasterToWorldCoord(rast, 0, 0)) from test'):
    print row
    break

# world to raster
print 'world to raster'
for row in cur.execute('select st_asText(rt_worldToRasterCoord(rast, 0, 0)) from test'):
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

# same alignment, aggregate
print 'same alignment, aggregate'
for row in cur.execute("select rt_sameAlignment(rast) from test"):
    print row
    break

# intersects
print 'intersects'
for (r1,r2) in cur.execute("select t1.rast,t2.rast from test as t1,test as t2 where rt_Intersects(t1.rast, t2.rast) limit 10 offset 1"):
    print r1.bbox(),r2.bbox()


####################
# extracting

# band selection
print 'band selection'
for row in cur.execute("select rt_numBands(rast), rt_numBands(rt_Band(rast, 1)), rt_numBands(rt_Band(rast, '1')) from test"):
    print row
    break

# band nodata
print 'band nodata'
for row in cur.execute("select rt_bandNoDataValue(rast,1) from test"):
    print row
    break

# band pixel type
print 'band pixel type'
for row in cur.execute("select rt_bandPixelType(rast,1) from test"):
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
for row in cur.execute("select rt_summarystats(rast,1) from test"):
    print row
    break


#############
# changing

# resize
print 'resize'
for row in cur.execute('''select rt_resize(rast,200,100) as "[rast]", rt_width(rt_resize(rast,200,100)),rt_height(rt_resize(rast,200,100)) from test'''):
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
for rast1,rast2 in cur.execute('''with cross as (select t1.rast as rast, rt_setUpperLeft(t2.rast,rt_upperleftx(t2.rast)*0.75,rt_upperlefty(t2.rast)*0.75) as shift
                                                    from test as t1, test as t2
                                                    where t1.rast != t2.rast)
                                  select rast as "[rast]", shift as "[rast]"
                                  from cross
                                  where rt_intersects(rast,shift)
                                  limit 2'''):
    print 1, rast1.summarystats()
    print 2, rast2.summarystats()
    
    print 'simple math'
    result = rast1.mapalgebra(rast2, '([rast1] + [rast2]) / 2.0',
                              None, 'union')
    print result.summarystats()
    Image.fromarray(result.data()).show()
    
    #print 'dummy coding?'
    #result = rast.mapalgebra(1, 'f4', '[rast] = 255')
    #print result.summarystats()
    
    print 'conditional'
    result = rast.mapalgebra(rast2, 'case when [rast1] > [rast2] then 255 when [rast1] < [rast2] then 1 else 127 end',
                             None, 'union')
    print result.summarystats()
    Image.fromarray(result.data()).show()

    #print 'between'
    #result = rast.mapalgebra(rast2 'case when [rast1] = 0 then 0 when [rast1] between 1 and 100 then 1 when [rast1] between 101 and 200 then 2 else 99 end')
    #print result.summarystats()

# intersection
print 'intersection'
for rast1,rast2 in cur.execute("""with cross as (select t1.rast as rast, rt_setUpperLeft(t2.rast,rt_upperleftx(t2.rast)*0.75,rt_upperlefty(t2.rast)*0.75) as shift
                                                    from test as t1, test as t2
                                                    where t1.rast != t2.rast)
                                  select rast as "[rast]", shift as "[rast]"
                                  from cross
                                  where rt_intersects(rast,shift)
                                  limit 2
                                    """):
    print rast1.bbox(),rast2.bbox(),rast1.intersects(rast2)
    isec = rast1.intersection(rast2, 'band1')
    print isec.bbox()
    #Image.fromarray(isec.data(1)).show()

print 'clip'
##for rasterized,intersected in cur.execute('''
##                                            select st_asRaster(st_Buffer(st_Point(2000,2000), 500), rast, 'u1', 255) as "[rast]",
##                                                    rt_Intersection(st_asRaster(st_Buffer(st_Point(2000,2000), 500), rast, 'u1', 255), rast) as "[rast]"
##                                            from test
##                                            where st_intersects(st_Buffer(st_Point(2000,2000), 500), rt_envelope(rast))
##                                            '''):
for buff,rast in cur.execute('''
                                select st_Buffer(st_Point(2000,2000), 500) as "[geom]",
                                        rast
                                from test
                                where st_intersects(st_Buffer(st_Point(2000,2000), 500), rt_Envelope(rast))
                                limit 1
                                '''):
    print buff.bbox(),rast.bbox()
    rasterized = buff.as_raster(rast, 'u1', 255)
    intersected = rasterized.intersection(rast, 'band2') #mapalgebra(rast,'max([rast1],[rast2])') #intersection(rast, 'band2')
    
##    arr = rasterized.data(1)
##    from PIL import Image
##    Image.fromarray(arr).show()
    
##    arr = intersected.data(1)
##    from PIL import Image
##    Image.fromarray(arr).show()

    rastclip = rast.clip(buff, 0.0, True) # crop
    Image.fromarray(rastclip.data(1)).show()

    rastclip = rast.clip(buff, 0.0, False) # crop
    Image.fromarray(rastclip.data(1)).show()




# union aggregate
print 'union aggregate'

# in-db (unknown step error...?)
##for (rast,) in cur.execute("select st_metadata(st_rasterunion(rast)) from test"):
##    print rast
##    break

# debug
import cProfile
p=cProfile.Profile()
p.enable()
agg = postqlite.raster.raster.RT_Union()
for (rast,) in cur.execute('select rt_setUpperLeft(rast,rt_upperleftx(rast)*0.75,rt_upperlefty(rast)*0.75) as "[rast]" from test'):
    print rast
    agg.step(rast.dump_wkb(), 'sum')
    #Image.fromarray(agg.result.data(1)).show()
rast = postqlite.raster.raster.Raster(agg.finalize())
p.create_stats()
p.print_stats('tottime')

# view
print rast.metadata()
print rast.summarystats()
Image.fromarray(rast.data(1)).show()

rastclip = rast.clip(buff, False) # no crop
Image.fromarray(rastclip.data(1)).show()

rastclip = rast.clip(buff) # crop
Image.fromarray(rastclip.data(1)).show()











