
import pygeoj


class GeoJSON(object):
    def __init__(self, filepath, **kwargs):
        self.filepath = filepath
        self.kwargs = kwargs

        self.reader = self.load_reader()
        self.fieldnames, self.fieldtypes = self.load_fields()
        self.meta = self.load_meta()

    def __len__(self):
        return len(self.reader)
        
    def __iter__(self):
        return self.stream()

    def stream(self):
        for feat in self.reader:
            props = feat.properties
            row = [props[field] for field in self.fieldnames]
            geom = feat.geometry.__geo_interface__
            yield row, geom

    def load_reader(self):
        reader = pygeoj.load(filepath=self.filepath, **self.kwargs)
        return reader

    def load_fields(self):
        fieldnames = self.reader.all_attributes
        fieldtypes = [None for _ in fieldnames]
        return fieldnames, fieldtypes

    def load_meta(self):
        meta = None
        return meta
