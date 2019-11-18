
from . import fileformats

from wkb_raster import read_wkb_raster

file_extensions = {".tif": "GeoTIFF",
                   }

def detect_filetype(filepath):
    for ext in file_extensions.keys():
        if filepath.lower().endswith(ext):
            return file_extensions[ext]
    else:
        return None


def file_reader(filepath, **kwargs):
    filetype = detect_filetype(filepath)

    try:
        import gdal
        reader = fileformats.GDALRaster(filepath, **kwargs)
        
    except ImportError:
        if filetype in ('GeoTIFF'):
            reader = fileformats.GeoTIFF(filepath, **kwargs)

        else:
            raise Exception("Could not import data from the given filepath: the filetype extension is either missing or not supported")

    return reader

def from_wkb(wkb):
    from .data import Raster
    rast_dct = read_wkb_raster(wkb)
    width, height = rast_dct['width'], rast_dct['height']
    affine = [rast_dct[k] for k in 'scaleX skewX ipX skewY scaleY ipY'.split()]
    rast = Raster(None, width, height, affine)
    dtypes = ['bool', None, None, 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'float32', 'float64']
    for band_dct in rast_dct['bands']:
        data = band_dct['ndarray']
        dtype = dtypes[band_dct['pixtype']]
        width, height = rast_dct['width'], rast_dct['height']
        nodataval = band_dct['nodata']
        rast.add_band(data, dtype, width, height, nodataval)
    return rast



