
import postqlite
import json
import os
import pythongis as pg
from PIL import Image

print 'init'
db = postqlite.connect('testdata/foresttest.db')
cur = db.cursor()

if False:
    # init
    cur.execute('create table forest (file text, rast rast)')
    cur.execute('create table countries (name text, geom geom)')

    # populate with real data
    print 'populate'
    root = r"C:\Users\kimok\Desktop\BIGDATA\NORAD data\deforestation"
    for fil in os.listdir(root):
        if not 'lossyear' in fil:
            continue
        d = postqlite.raster.data.Raster(root+'/'+fil)
        print fil, d
        for tile in d.tiled(tilesize=(2000,2000)):
            #print tile
            wkb = tile.wkb
            wkbtile = postqlite.raster.raster.Raster(wkb)
            cur.execute('insert into forest values (?, ?)', (fil,wkbtile,) )

    d = postqlite.vector.load.from_file("C:\Users\kimok\Desktop\BIGDATA\priocountries\priocountries.shp")
    for row,geoj in d.stream():
        name = row['NAME']
        cur.execute('insert into countries values (?, st_simplify(st_geomfromgeojson(?),0.1))', (name, json.dumps(geoj),) )

    db.commit()

################

# check full
print 'forest', cur.execute('select count(oid) from forest').fetchone()
print 'countries', cur.execute('select count(oid) from countries').fetchone()

for row in cur.execute('''select name from forest,countries
                            where st_intersects(st_envelope(geom), rt_envelope(rast))
                            limit 10
                            '''):
    print row

for row in cur.execute('''select countries.name, rt_summarystatsAgg(forest.rast, 1)
                            from forest,countries
                            where countries.name = 'Brazil'
                            and st_intersects(st_envelope(countries.geom), rt_envelope(forest.rast))
                            '''):
    print row







