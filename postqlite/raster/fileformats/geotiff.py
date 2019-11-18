
import sys

import PIL, PIL.Image


PIL.Image.MAX_IMAGE_PIXELS = sys.maxsize


def pilmode_to_dtype(mode):
    dtyp = {"1":"int8",
            
            "L":"int8",
            "P":"int8",
            
            "I;16":"int16",
            "I":"int32",
            
            "F;16":"float16",
            "F":"float32"}[mode]
    
    return dtyp


class GeoTIFF(object):
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
        if bbox:
            tiletype, extent, fileoffset, args = self.reader.tile[0]
            if 1: #tiletype == 'raw':
                x1,y1,x2,y2 = bbox
                w,h = x2-x1, y2-y1
                newreader = self.load_reader()
                newreader.size = (w,h)
                lineoffset = len(self.reader.mode)*w*y1
                newreader.tile = [(tiletype, extent, fileoffset + lineoffset + x1, args)]
                newreader.load()
                imgdata = self.reader.crop(bbox).split()[band]
            else:
                imgdata = self.reader.crop(bbox).split()[band]

        else:
            imgdata - self.reader.split()[band]

        import numpy as np
        arrdata = np.array(imgdata)
        return arrdata

    def nodata(self, band):
        # same nodata for all bands
        nodataval = self.reader.tag.get(42113)
        if nodataval:
            try:
                float(nodataval) # make sure is possible to make into nr
                nodataval = eval(nodataval) # eval from string to nr
                return nodataval
            except:
                pass

    def load_reader(self):
        img = PIL.Image.open(self.filepath)
        return img

    def load_dtype(self):
        return pilmode_to_dtype(self.reader.mode)

    def load_size(self):
        return self.reader.size

    def load_bandcount(self):
        return len(self.reader.mode)

    def load_affine(self):
        if 1:
            # check tag definitions here
            tags = self.reader.tag
            if tags.has_key(34264):
                # ModelTransformationTag, aka 4x4 transform coeffs...
                [a,b,c,d,
                 e,f,g,h,
                 i,j,k,l,
                 m,n,o,p] = tags.get(34264)
                # But we don't want to meddle with 3-D transforms,
                # ...so for now only get the 2-D affine parameters
                xscale,xskew,xoff = a,b,d
                yskew,yscale,yoff = e,f,h
            else:
                if tags.has_key(33922):
                    # ModelTiepointTag
                    pix_x, pix_y, pix_z, geo_x, geo_y, geo_z = tags.get(33922)
                    xoff = geo_x - pix_x
                    yoff = geo_y - pix_y
                if tags.has_key(33550):
                    # ModelPixelScaleTag
                    xscale,yscale,zscale = tags.get(33550)
                    yscale = -yscale # note: cellheight must be inversed because geotiff has a reversed y-axis (ie 0,0 is in upperleft corner)
                xskew = 0
                yskew = 0

            return xscale, xskew, xoff, yskew, yscale, yoff

        if 0:
            # if no geotiff tag info look for world file transform coefficients
            affine = check_world_file(filepath)
            if affine:
                return affine
            
            else:
                raise Exception("Couldn't find any georef options, geotiff tags, or world file needed to position the image in space")

    def load_pixeltype(self):
        # check tag definitions here
        if self.reader.tag.has_key(1025):
            # GTRasterTypeGeoKey, aka midpoint pixels vs topleft area pixels
            if self.reader.tag.get(1025) == (1,):
                # is area
                return "area"
            elif self.reader.tag.get(1025) == (2,):
                # is point
                return "point"
        else:
            return 'area'

    def load_crs(self):
        crs = dict()
        if self.reader.tag.get(34735):
            # GeoKeyDirectoryTag
            crs["proj_params"] = self.reader.tag.get(34735)
        if self.reader.tag.get(34737):
            # GeoAsciiParamsTag
            crs["proj_name"] = self.reader.tag.get(34737)
        return crs

    def load_meta(self):
        return None


