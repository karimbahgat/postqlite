
import postqlite
import tk2
import os
from time import time

import traceback

#from . import ops
#from . import stats
from .geometry import geometry
from .raster import raster





class SQLiteApp(tk2.Tk):
    def __init__(self, *args, **kwargs):
        tk2.basics.Tk.__init__(self, *args, **kwargs)

        self.top = tk2.Frame(self)
        self.top.pack(side='top', fill='x', expand=1)
        #self.top.place(relx=0, rely=0, relwidth=1, relheight=0.6)

        self.query = QueryEditor(self.top)
        self.query.pack(side='left', fill='both', expand=1)
        self.query.app = self

        self.info = DataInfo(self.top)
        self.info.pack(side='right', fill='both', expand=1)
        self.info.app = self

        self.bottom = tk2.Frame(self)
        self.bottom.pack(side='bottom', fill='x', expand=1)

        self.browser = TableBrowser(self.bottom)
        self.browser.pack(side='left', fill="both", expand=1)
        #self.browser.place(relx=0, rely=0, relwidth=0.6, relheight=1)
        self.browser.app = self

        self.graphics = GraphicsViewer(self.bottom, width=100)
        self.graphics.pack(side='right', fill='both', expand=1)
        #self.browser.place(relx=0.6, rely=0, relwidth=0.4, relheight=1)

        self.connect(':memory:')

        # bindings
        def dndfunc(event):
            filepath = list(event.data)[0]
            self.connect(filepath)
        self.winfo_toplevel().bind_dnddrop(dndfunc, "Files", event='<Drop>')
        self.winfo_toplevel().bind('<Control-Return>', lambda e: self.query.run_query())

        self.state('zoomed')

    def connect(self, db):
        if isinstance(db, basestring):
            path = db
            if path == ':memory:':
                # in-memory
                name = '[in-memory]'
                root = '[in-memory]'
            else:
                # file path
                root,name = os.path.split(path)
            # load
            self.db = postqlite.connect(path)
        else:
            # already loaded db
            self.db = db
            path = '[unknown]'
            root = '[unknown]'
            name = '[unknown]'
            
        self.info.data.set( '{}'.format(name) )
        self.info.path.set( '{}'.format(root) )

        # get info
        tableinfo = []
        for table in self._tablenames():
            columns = self._column_info(table)
            tableinfo.append((table, columns))

        # populate
        self.info.populate(tableinfo)

        # log
        msg = 'Connected to database: {}'.format(path)
        self.query.log.log_new(msg, 'normal')

    def _tablenames(self):
        names = [row[0] for row in self.db.cursor().execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return names

    def _column_info(self, table):
        # cid,name,typ,notnull,default,pk
        if '.' in table:
            schema,name = table.split('.')
            query = 'PRAGMA {}.table_info({})'.format(schema, table)
        else:
            query = 'PRAGMA table_info({})'.format(table)
        columns = [(name,typ) for _,name,typ,_,_,_ in self.db.cursor().execute(query)]
        return columns

    def run_sql(self, sql):
        msg = 'Running query: \n' + sql
        self.query.log.log_new(msg, 'normal')
        
        try:
            # execute
            t = time()
            req = self.db.cursor().execute(sql)
            # reset
            tree = self.browser.table.tree
            tree.delete(*tree.get_children())
            # set fields
            fields = [item[0] for item in req.description]
            tree["columns"]=tuple(fields)
            for fl in fields:
                tree.heading(fl, text=fl)
            # populate table rows
            maxrows = 1000
            rows = self.browser.table.rows = []
            for i,row in enumerate(req):
                tid = tree.insert("", "end", i+1, text=i+1, values=row)
                rows.append(row)
                if i+1 >= maxrows:
                    break
            # finish rest of query
            itot = i+1
            for row in req:
                itot += 1
            elaps = time() - t
            
            msg = '\n' + 'Query completed in {} seconds'.format(round(elaps,6))
            msg += '\n' + 'Resulted in {} rows of data'.format(itot)
            if itot > (i+1):
                msg += '\n' + 'Showing only first {}'.format(i+1)
            self.query.log.log_append(msg, 'normal')
            
        except:
            # log error
            err = traceback.format_exc()
            self.query.log.log_append(err, 'error')
            
            # reset table
            fields = []
            rows = [[]]
            self.browser.table.populate(fields, rows)





class DataInfo(tk2.basics.Label):
    def __init__(self, master, *args, **kwargs):
        tk2.basics.Label.__init__(self, master, *args, **kwargs)

        self.data = tk2.Entry(self, label='Data:', default='None', width=300)
        self.data.pack(side='top', fill="x", expand=1)

        self.path = tk2.Entry(self, label='Path:', default='None', width=300)
        self.path.pack(side='top', fill="x", expand=1)

        self.content = tk2.Treeview(self)
        self.content.pack(side='top', fill="both", expand=1)

        tree = self.content.tree
        tree["columns"]=("column","type")
        tree.column("#0", width=100, minwidth=100, stretch='no')
        tree.column("column", width=200, minwidth=100, stretch='no')
        tree.column("type", width=100, minwidth=100, stretch='no')

        tree.heading("#0", text="Table",anchor='w')
        tree.heading("column", text="Column",anchor='w')
        tree.heading("type", text="Type",anchor='w')

        self.actions = tk2.Label(self)
        self.actions.pack(side='top', fill="x", expand=1)
        def tableview():
            item = tree.selection()[0]
            prn = tree.parent(item)
            if prn:
                table = tree.item(prn)['text']
            else:
                table = tree.item(item)['text']
            self.preview_table(table)
        tablebut = tk2.Button(self.actions, text='Preview Table', command=tableview)
        tablebut.pack(side='left')

    def populate(self, tables):
        tree = self.content.tree
        tree.delete(*tree.get_children())
        for table,columns in tables:
            tid = self.content.insert("", "end", text=table, values=("", "", ""), open=True)
            i = 1
            for col,typ in columns:
                self.content.insert(tid, "end", text=i, values=(col, typ))
                i += 1

    def preview_table(self, table):
        sql = '''
select *
from {}
limit 100
                '''.format(table)
        self.app.run_sql(sql)
        




class TableBrowser(tk2.basics.Label):
    def __init__(self, master, *args, **kwargs):
        tk2.basics.Label.__init__(self, master, *args, **kwargs)

        self.menu = tk2.Label(self, text='Results:')
        self.menu.pack(side='top', fill="x", expand=1)

        self.table = tk2.scrollwidgets.Table(self)
        self.table.pack(side='bottom', fill="both", expand=1)

        self.table.tree.bind('<Button-1>', self.click)

    def click(self, event):
        x,y = event.x, event.y
        #print x,y
        row = self.table.tree.identify_row(y)
        column = self.table.tree.identify_column(x)
        #print row,column
        if not column or column == '#0':
            return
        ci = int(float(column[1:])) - 1 # zero-index
        ri = int(float(row)) - 1 # zero-index
        #print ci,ri
        val = self.table.rows[ri][ci]
        #print ci,ri,val
        if val and isinstance(val, geometry.Geometry):
            self.show_geom(val)
        elif val and isinstance(val, raster.Raster):
            self.show_rast(val)

    def show_geom(self, geom):
        from PIL import Image
        xmin,ymin,xmax,ymax = geom.bbox()
        xw,yh = xmax-xmin, ymax-ymin
        aspect = xw / float(yh)
        h = int(300)
        w = int(h * aspect)
        rast = geom.as_raster(w, h, 'u1', 255, 0)
        img = Image.fromarray(rast.data(1))
        self.app.graphics.show(img)

    def show_rast(self, rast):
        from PIL import Image
        rast = rast.resize(300, 300)
        arr = rast.data(1) # just 1st band for now
        arr = (arr / float(arr.max())) * 255 # normalize
        img = Image.fromarray(arr) 
        self.app.graphics.show(img)





class QueryEditor(tk2.basics.Label):
    def __init__(self, master, *args, **kwargs):
        tk2.basics.Label.__init__(self, master, *args, **kwargs)

        self.title = tk2.Label(self, text='Query Editor:')
        self.title.pack(fill="x", expand=1)

        self.text = tk2.Text(self, height=12)
        self.text.pack(fill="both", expand=1)

        self.buttons = tk2.Label(self)
        self.buttons.pack(fill="x", expand=1)
        runbut = tk2.Button(self.buttons, text='Run', command=self.run_query)
        runbut.pack(side='left')

        self.log = LogViewer(self)
        self.log.pack(fill="both", expand=1)

    def run_query(self):
        sql = self.text.get('1.0', 'end')
        self.app.run_sql(sql)
            






class LogViewer(tk2.basics.Label):
    def __init__(self, master, *args, **kwargs):
        tk2.basics.Label.__init__(self, master, *args, **kwargs)

        self.title = tk2.Label(self, text='Run Log:')
        self.title.pack(fill="x", expand=1)

        self.text = tk2.Text(self, height=5)
        self.text.config(state='disabled')
        self.text.tag_config('normal')
        self.text.tag_config('error', foreground='red')
        self.text.pack(fill="both", expand=1)

    def log_new(self, text, *tags):
        self.text.config(state='normal')
        #prev = self.text.get('1.0', 'end')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', text, tags)
        self.text.yview_moveto(1)
        self.text.config(state='disabled')

    def log_append(self, text, *tags):
        self.text.config(state='normal')
        #prev = self.text.get('1.0', 'end')
        self.text.insert('end', text, tags)
        self.text.yview_moveto(1)
        self.text.config(state='disabled')







class GraphicsViewer(tk2.basics.Label):
    def __init__(self, master, *args, **kwargs):
        tk2.basics.Label.__init__(self, master, *args, **kwargs)

        self.title = tk2.Label(self, text='Graphics:')
        self.title.pack(fill="x", expand=0)

        self.output = tk2.Label(self, background='white')
        self.output['anchor'] = 'center'
        self.output.pack(fill="both", expand=1)

        self.actions = tk2.Label(self)
        self.actions.pack(fill="x", expand=0)

    def show(self, img):
        from PIL import Image,ImageTk,ImageOps
        w,h = self.output.winfo_width(), self.output.winfo_height()
        wratio = img.size[0] / float(w)
        hratio = img.size[1] / float(h)
        ratio = max(wratio, hratio)
        w,h = int(img.size[0]/ratio), int(img.size[1]/ratio)
        img = img.resize((w,h), Image.ANTIALIAS)
        self.tkim = ImageTk.PhotoImage(img)
        self.output['image'] = self.tkim
        




