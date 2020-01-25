
import postqlite
import os
import json



if __name__ == '__main__':

    print 'init'
    db = postqlite.connect('testdata/foresttest.db')

    if False:
        # init
        cur = db.cursor()
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
            break

        d = postqlite.vector.load.from_file("C:\Users\kimok\Desktop\BIGDATA\priocountries\priocountries.shp")
        for row,geoj in d.stream():
            name = row['NAME']
            cur.execute('insert into countries values (?, st_simplify(st_geomfromgeojson(?),0.1))', (name, json.dumps(geoj),) )

        db.commit()
        
    app = postqlite.app.SQLiteApp()
    app.connect(db)
    app.mainloop()




