
import sys

try:
    import gdal
    gdal.UseExceptions()
except:
    pass


class GDALRaster(object):
    def __init__(self, filepath, **kwargs):
        self.filepath = filepath
        self.kwargs = kwargs

        self.reader = self.load_reader()
        #self.dtype = self.load_dtype()
        self.width, self.height = self.load_size()
        self.bandcount = self.load_bandcount()
        self.affine = self.load_affine()
        self.pixeltype = self.load_pixeltype()
        self.crs = self.load_crs()
        self.meta = self.load_meta()

    def data(self, band, bbox=None):
        band += 1 # gdal band is 1-based
        band = self.reader.GetRasterBand(band) 
        if bbox:
            x1,y1,x2,y2 = bbox
            w,h = x2-x1, y2-y1
            if (x1 + w) > self.width:
                w = self.width - x1
            if (y1 + h) > self.height:
                h = self.height - y1
            arrdata = band.ReadAsArray(x1, y1, w, h)
        else:
            arrdata = band.ReadAsArray(0, 0, self.width, self.height)
        return arrdata

    def nodata(self, band):
        band += 1 # gdal band is 1-based
        band = self.reader.GetRasterBand(band)
        return band.GetNoDataValue()

    def load_reader(self):
        reader = gdal.Open(self.filepath)
        return reader

    def load_size(self):
        return self.reader.RasterXSize, self.reader.RasterYSize

    def load_bandcount(self):
        return self.reader.RasterCount

    def load_affine(self):
        # gdal uses a slightly different affine sequence so we switch here
        xoff,xscale,xskew,yoff,yskew,yscale = self.reader.GetGeoTransform()
        affine = xscale,xskew,xoff,yskew,yscale,yoff
        return affine
        
    def load_pixeltype(self):
        return None

    def load_crs(self):
        crs = self.reader.GetProjectionRef()
        return crs

    def load_meta(self):
        return None


