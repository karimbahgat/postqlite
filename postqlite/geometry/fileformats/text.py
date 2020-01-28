
import csv
import sys
import io

csv.field_size_limit(sys.maxint)


class TextDelimited(object):
    def __init__(self, filepath, encoding='utf8', encoding_errors='strict', **kwargs):
        self.filepath = filepath
        self.encoding = encoding
        self.encoding_errors = encoding_errors
        self.kwargs = kwargs

        self.reader = self.load_reader()
        self.fieldnames = self.load_fields()
        self.fieldtypes = None
        self.meta = {}

    def __iter__(self):
        return self.stream()

    def stream(self):
        self.fileobj.seek(0)
        rows = (row for row in self.reader)

        if "skip" in self.kwargs:
            for _ in range(self.kwargs["skip"]):
                next(rows)

        _fields = next(rows)

        # TODO: This naive parsing is a bit slower than just pure iterating
        # Instead, do the parsing in import_table() after we have sniffed the data types
        # This way only tries to convert to the correct column type
        # Also open file with codec so less overhead from many decode calls
        def parsestring(string):
            try:
                val = float(string.replace(",","."))
                if val.is_integer():
                    val = int(val)
                return val
            except:
                if string.upper() == "NULL":
                    return None
                else:
                    return string.decode(self.encoding, errors=self.encoding_errors)
                
        rows = ([parsestring(cell) for cell in row] for row in rows)

        if "last" in self.kwargs:
            last = self.kwargs["last"]
            rows = (r for i,r in enumerate(rows) if i <= last)
        
        rowgeoms = ((row,None) for row in rows)
        return rowgeoms

    @staticmethod
    def dump(filepath, fields, data, encoding='utf8', **kwargs):
        # use excel dialect by default
        dialect = csv.excel
        
        # .tsv files are by definition tab-separated
        if filepath.endswith('.tsv'):
            dialect.delimiter = '\t'
        else:
            dialect.delimiter = ','
        
        # overwrite with user input
        for k,v in kwargs.items():
            setattr(dialect, k, v)

        # determine field conversions
        fieldnames,fieldtypes = zip(*fields)
        fieldtypes = [typ.lower() for typ in fieldtypes]
        def typfunc(typ):
            if typ == 'text':
                return lambda v: v.encode(encoding)
            else:
                return lambda v: v
        fieldfuncs = [typfunc(typ) for typ in fieldtypes]

        # write to file
        with open(filepath, "wb") as fobj:
            writer = csv.writer(fobj, dialect)
            print fieldnames
            writer.writerow([f.encode(encoding) for f in fieldnames])
            for row in data:
                row = [v if v is None else encode(v)
                       for v,encode in zip(row,fieldfuncs)]
                writer.writerow(row)

    def load_reader(self):
        self.fileobj = open(self.filepath, "rb")
        
        # auto detect delimiter
        # unless specified, only based on first 10 mb, otherwise gets really slow for large files
        sniffsize = self.kwargs.pop('sniffdialectsize', 10)
        dialect = csv.Sniffer().sniff(self.fileobj.read(1056*sniffsize)) 
        self.fileobj.seek(0)

        # .tsv files are by definition tab-separated
        if self.filepath.endswith('.tsv'):
            dialect.delimiter = '\t'
        
        # overwrite with user input
        for k,v in self.kwargs.items():
            setattr(dialect, k, v)

        # load reader
        reader = csv.reader(self.fileobj, dialect)
        return reader

    def load_fields(self):
        self.fileobj.seek(0)
        
        if "skip" in self.kwargs:
            for _ in range(self.kwargs["skip"]):
                next(self.reader)

        fields = next(self.reader)
        fields = [field.decode(self.encoding, errors=self.encoding_errors) for field in fields]
        return fields




        
