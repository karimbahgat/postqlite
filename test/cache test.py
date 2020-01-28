
import postqlite
import os
import json



if __name__ == '__main__':

    print 'init'
    db = postqlite.connect('testdata/foresttest.db')

    for r in db.cursor().execute('select st_intersects(geom,geom),st_intersects(geom,geom) from countries limit 1 offset 1'):
        print r

    asfdfa
        
    app = postqlite.app.SQLiteApp()
    app.connect(db)
    app.mainloop()




