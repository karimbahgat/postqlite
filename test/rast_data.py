
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
for name,rast in cur.execute('''select name,st_asRaster(geom,0.1,-0.1,'u1',255) as "[rast]" from countries where geom is not null limit 1'''):
    print name,rast
    arr = rast.data(1)
    Image.fromarray(arr).show()





# preview maps
print 'preview maps'
for row in cur.execute('''
                    select file,rast
                    from maps
                        '''):
    print row
    rast = row[1]
    arr = rast.data(1)
    from PIL import Image
    Image.fromarray(arr).show()

    break




# map tiles intersected with countries
print 'country map intersections'
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
##for row in cur.execute('''
##                    select name, st_asRaster(geom, st_scalex(rast), st_scaley(rast), 'u1', 255, 0, st_upperleftx(rast), st_upperlefty(rast)) as "[rast]"
##                    from maps,countries
##                    where geom is not null and st_distance(geom, st_envelope(rast)) = 0
##                        '''):
for row in cur.execute('''
                    select name, st_asRaster(geom, st_scalex(rast), st_scaley(rast), 'u1', 255) as "[rast]"
                    from maps,countries
                    where geom is not null and st_distance(geom, st_envelope(rast)) = 0
                        '''):
    print row
    rast = row[1]
    arr = rast.data(1)
    from PIL import Image
    Image.fromarray(arr).show()

    break






