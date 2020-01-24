
import postqlite
import json
import pythongis as pg
from PIL import Image

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
cur.execute('create table maps (file text, rast rast)')
cur.execute('create table countries (name text, geom geom)')

# populate with real data
print 'populate'
#fil = r"C:\Users\kimok\OneDrive\Documents\GitHub\AutoMap\tests\testmaps\zaire_map_georeferenced.tiftxu-oclc-6654394-nb-30-4th-ed.jpg"
fil = r"C:\Users\kimok\OneDrive\Documents\GitHub\AutoMap\tests\testmaps\burkina_georeferenced.tif"
d = postqlite.raster.data.Raster(fil)
for tile in d.tiled(tilesize=(500,500)):
    print tile
    wkb = tile.wkb
    wkbtile = postqlite.raster.raster.Raster(wkb)
    cur.execute('insert into maps values (?, ?)', (fil,wkbtile,) )

d = postqlite.vector.load.from_file("C:\Users\kimok\Desktop\BIGDATA\priocountries\priocountries.shp")
for row,geoj in d.stream():
    name = row['NAME']
    cur.execute('insert into countries values (?, st_simplify(st_geomfromgeojson(?),0.1))', (name, json.dumps(geoj),) )

# check full
print 'maps', cur.execute('select count(oid) from maps').fetchone()
print 'countries', cur.execute('select count(oid) from countries').fetchone()





# country previews
##for name,rast in cur.execute('''select name,st_asRaster(geom,0.1,-0.1,'u1',255) as "[rast]" from countries where geom is not null limit 1'''):
##    print name,rast
##    arr = rast.data(1)
##    Image.fromarray(arr).show()





# map tiles clipped to countries
print 'country map clipping'
##for row in cur.execute('''
##                        select name,rt_union("rast")
##                        from (
##                            select name, rt_Clip(rast, geom, 0.0, 1) as "rast [rast]"
##                            from maps,countries
##                            where geom is not null and st_intersects(geom, rt_envelope(rast))
##                            )
##                        group by name
##                        '''):
##    print row
##    name,clipunion = row
##    Image.fromarray(clipunion.data(1)).show()
##
##fdsafas

for row in cur.execute('''
                    select name, rt_Clip(rast, geom, 0.0, 1) as "[rast]", rt_Clip(rast, geom, 0.0, 0) as "[rast]", geom, rast
                    from maps,countries
                    where geom is not null and st_intersects(geom, rt_envelope(rast))
                    limit 3
                        '''):
    print row
    name,clip,clip_nocrop,geom,rast = row
    Image.fromarray(rast.data(1)).show()
    Image.fromarray(clip.data(1)).show()
    Image.fromarray(clip_nocrop.data(1)).show()


fdsafdsa


# play with map algebra...
##for row in cur.execute('''
##                    select name,st_rasterunion( rast ) as "[rast]"
##                    from (
##                        select name, st_intersection(rast,
##                                                    st_asRaster(geom, rast, 'u1', 255) ) as "rast [rast]"
##                        from maps,countries
##                        where st_distance(geom, st_envelope(rast)) = 0
##                        )
##                    group by name
##                        '''):
for row in cur.execute('''
                    select name, st_asRaster(geom, rt_scalex(rast), rt_scaley(rast), 'u1', 255, 0, rt_upperleftx(rast), rt_upperlefty(rast)) as "[rast]", geom, rast
                    from maps,countries
                    where geom is not null and st_intersects(geom, rt_envelope(rast))
                        '''):
##for row in cur.execute('''
##                    select name, st_asRaster(geom, st_scalex(rast), st_scaley(rast), 'u1', 255) as "[rast]"
##                    from maps,countries
##                    where geom is not null and st_intersects(geom, st_envelope(rast))
##                        '''):
    print row
    name,georast,geom,rast = row
    Image.fromarray(rast.data(1)).show()
    Image.fromarray(georast.data(1)).show()

    Image.fromarray(rast.intersection(georast, 'band1').data(1)).show()
    Image.fromarray(rast.mapalgebra(georast, '([rast1]+[rast2]/2.0)', None, 'intersection').data(1)).show()
    Image.fromarray(rast.mapalgebra(georast, '([rast1]+[rast2]/2.0)', None, 'union').data(1)).show()

    break






