
import shapefile
import os


class Shapefile(object):
    def __init__(self, filepath, encoding='utf8', encoding_errors='strict', **kwargs):
        self.filepath = filepath
        self.encoding = encoding
        self.encoding_errors = encoding_errors
        self.kwargs = kwargs

        self.reader = self.load_reader()
        self.fieldnames, self.fieldtypes = self.load_fields()
        self.meta = self.load_meta()

    def __len__(self):
        return len(self.reader)
        
    def __iter__(self):
        return self.stream()

    def stream(self):
        def getgeoj(obj):
            geoj = obj.__geo_interface__
            return geoj
        rowgeoms = ((feat.record,getgeoj(feat.shape)) for feat in self.reader.iterShapeRecords())
        return rowgeoms

    def load_reader(self):
        reader = shapefile.Reader(self.filepath, encoding=self.encoding, encodingErrors=self.encoding_errors, **self.kwargs)
        return reader

    def load_fields(self):
        def fieldtype(name,typ,size,dec):
            if typ in ('C','D','L'): # text, dates, and logical
                return 'TEXT'
            elif typ in ('F','N'):
                if dec == 0:
                    return 'INT'
                else:
                    return 'REAL'
        fieldnames = [fieldinfo[0] for fieldinfo in self.reader.fields[1:]]
        fieldtypes = [fieldtype(*fieldinfo) for fieldinfo in self.reader.fields[1:]]
        return fieldnames, fieldtypes

    def load_meta(self):
        # load projection string from .prj file if exists
        if os.path.lexists(self.filepath[:-4] + ".prj"):
            crs = open(self.filepath[:-4] + ".prj", "r").read()
        else:
            crs = "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
        meta = dict(crs=crs)
        return meta
