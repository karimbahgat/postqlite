


class Fileformat(object):
    def __init__(self, filepath, **kwargs):
        self.filepath = filepath
        self.kwargs = kwargs

        self.reader = self.load_reader()
        self.fieldnames = self.load_fields()
        self.meta = self.load_meta()

    def __len__(self):
        return len(self.reader)
        
    def __iter__(self):
        return self.stream()

    def stream(self):
        
        return rowgeoms

    def load_reader(self):

        return reader

    def load_fields(self):

        return fieldnames, fieldtypes

    def load_meta(self):

        return meta
