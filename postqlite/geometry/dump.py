
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


def to_file(filepath, fields, data, **kwargs):
    filetype = detect_filetype(filepath)
    
    if filetype in ('CSV','TSV','Text-Delimited'):
        fileformats.TextDelimited.dump(filepath, fields, data, **kwargs)

    elif filetype == 'Shapefile':
        fileformats.Shapefile.dump(filepath, fields, data, **kwargs)

    elif filetype == 'GeoJSON':
        fileformats.GeoJSON.dump(filepath, fields, data, **kwargs)

    elif filetype == 'Excel 97':
        fileformats.Excel97.dump(filepath, fields, data, **kwargs)

    else:
        raise Exception("Could not export data to the given filepath: the filetype extension is either missing or not supported")

