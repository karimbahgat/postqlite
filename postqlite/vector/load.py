
from . import fileformats


file_extensions = {".shp": "Shapefile",
                   ".json": "GeoJSON",
                   ".geojson": "GeoJSON",
                   ".xls": "Excel 97",
                   ".xlsx": "Excel",
                   ".dta": "Stata",
                   ".csv": "CSV",
                   ".tsv": "TSV",
                   ".txt": "Text-Delimited",
                   }

def detect_filetype(filepath):
    for ext in file_extensions.keys():
        if filepath.lower().endswith(ext):
            return file_extensions[ext]
    else:
        return None


def from_file(filepath, **kwargs):
    filetype = detect_filetype(filepath)
    
    if filetype in ('CSV','TSV','Text-Delimited'):
        reader = fileformats.TextDelimited(filepath, **kwargs)

    elif filetype == 'Shapefile':
        reader = fileformats.Shapefile(filepath, **kwargs)

    elif filetype == 'GeoJSON':
        reader = fileformats.GeoJSON(filepath, **kwargs)

    elif filetype == 'Excel 97':
        reader = fileformats.Excel97(filepath, **kwargs)

    elif filetype == 'Excel':
        reader = fileformats.Excel(filepath, **kwargs)

    else:
        raise Exception("Could not import data from the given filepath: the filetype extension is either missing or not supported")

    return reader
