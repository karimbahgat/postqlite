
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

        self.browser = TableBrowser(self)
        self.browser.pack(side='bottom', fill="both", expand=1)
        #self.browser.place(relx=0, rely=0.6, relwidth=1, relheight=0.5)

        self.connect(':memory:')

        # bindings
        def dndfunc(event):
            filepath = list(event.data)[0]
            self.connect(filepath)
        self.winfo_toplevel().bind_dnddrop(dndfunc, "Files", event='<Drop>')
        self.winfo_toplevel().bind('<Control-d>', lambda e: self.query.run())

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
        self.query.log.log(msg, 'normal')

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





class DataInfo(tk2.basics.Label):
    def __init__(self, master, *args, **kwargs):
        tk2.basics.Label.__init__(self, master, *args, **kwargs)

        self.data = tk2.Entry(self, label='Data:', default='None', width=300)
        self.data.pack(side='top', fill="x", expand=1)

        self.path = tk2.Entry(self, label='Path:', default='None', width=300)
        self.path.pack(side='top', fill="x", expand=1)

        self.content = tk2.Treeview(self)
        self.content.pack(side='bottom', fill="both", expand=1)

        tree = self.content.tree
        tree["columns"]=("column","type")
        tree.column("#0", width=100, minwidth=100, stretch='no')
        tree.column("column", width=200, minwidth=100, stretch='no')
        tree.column("type", width=100, minwidth=100, stretch='no')

        tree.heading("#0", text="Table",anchor='w')
        tree.heading("column", text="Column",anchor='w')
        tree.heading("type", text="Type",anchor='w')

    def populate(self, tables):
        for table,columns in tables:
            tid = self.content.insert("", "end", text=table, values=("", "", ""), open=True)
            i = 1
            for col,typ in columns:
                self.content.insert(tid, "end", text=i, values=(col, typ))
                i += 1




class TableBrowser(tk2.basics.Label):
    def __init__(self, master, *args, **kwargs):
        tk2.basics.Label.__init__(self, master, *args, **kwargs)

        self.menu = tk2.Label(self, text='Results:')
        self.menu.pack(side='top', fill="x", expand=1)

        self.table = tk2.scrollwidgets.Table(self)
        self.table.pack(side='bottom', fill="both", expand=1)





class QueryEditor(tk2.basics.Label):
    def __init__(self, master, *args, **kwargs):
        tk2.basics.Label.__init__(self, master, *args, **kwargs)

        self.title = tk2.Label(self, text='Query Editor:')
        self.title.pack(fill="x", expand=1)

        self.text = tk2.Text(self, height=12)
        self.text.pack(fill="both", expand=1)

        self.buttons = tk2.Label(self)
        self.buttons.pack(fill="x", expand=1)
        runbut = tk2.Button(self.buttons, text='Run', command=self.run)
        runbut.pack(side='left')

        self.log = LogViewer(self)
        self.log.pack(fill="both", expand=1)

    def run(self):
        sql = self.text.get('1.0', 'end')
        try:
            # execute
            t = time()
            req = self.app.db.cursor().execute(sql)
            # reset
            tree = self.app.browser.table.tree
            tree.delete(*tree.get_children())
            # set fields
            fields = [item[0] for item in req.description]
            tree["columns"]=tuple(fields)
            # populate table rows
            maxrows = 1000
            for i,row in enumerate(req):
                tid = tree.insert("", "end", text=i+1, values=row)
                if i+1 >= maxrows:
                    break
            # finish rest of query
            itot = i+1
            for row in req:
                itot += 1
            elaps = time() - t
            msg = 'Query completed in {} seconds'.format(round(elaps,6))
            msg += '\n' + 'Resulted in {} rows of data'.format(itot)
            if itot > (i+1):
                msg += '\n' + 'Showing only first {}'.format(i+1)
            self.log.log(msg, 'normal')
            
##            # execute
##            t = time()
##            req = self.app.db.cursor().execute(sql)
##            maxrows = 1000
##            rows = []
##            for i,r in enumerate(req):
##                if len(rows) < maxrows:
##                    rows.append(r)
##            elaps = time() - t
##            msg = 'Query completed in {} seconds'.format(round(elaps,6))
##            msg += '\n' + 'Resulted in {} rows of data'.format(i+1)
##            if i+1 > len(rows):
##                msg += '\n' + 'Showing only first {}'.format(len(rows))
##            self.log.log(msg, 'normal')
##            
##            # populate table
##            fields = [item[0] for item in req.description]
##            self.app.browser.table.populate(fields, rows)
            
        except:
            # log error
            err = traceback.format_exc()
            self.log.log(err, 'error')
            
            # reset table
            fields = []
            rows = [[]]
            self.app.browser.table.populate(fields, rows)
            






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

    def log(self, text, *tags):
        self.text.config(state='normal')
        #prev = self.text.get('1.0', 'end')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', text, tags)
        self.text.config(state='disabled')







