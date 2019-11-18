from struct import unpack, pack
import numpy as np

__all__ = [
    'read_wkb_raster'
]

def read_wkb_raster(wkb):
    """Read a WKB raster to a Numpy array.

    Based off of the RFC here:

        http://trac.osgeo.org/postgis/browser/trunk/raster/doc/RFC2-WellKnownBinaryFormat

    Object is returned in this format:

    {
        'version': int,
        'scaleX': float,
        'scaleY': float,
        'ipX': float,
        'ipY': float,
        'skewX': float,
        'skewY': float,
        'srid': int,
        'width': int,
        'height': int,
        'bands': [{
            'nodata': bool|int|float,
            'isOffline': bool,
            'hasNodataValue': bool,
            'isNodataValue': bool,
            'ndarray': numpy.ndarray((width, height), bool|int|float)
        }, ...]
    }

    :wkb file-like object: Binary raster in WKB format
    :returns: obj
    """
    ret = {}

    # Determine the endiannes of the raster
    #
    # +---------------+-------------+------------------------------+
    # | endiannes     | byte        | 1:ndr/little endian          |
    # |               |             | 0:xdr/big endian             |
    # +---------------+-------------+------------------------------+
    (endian,) = unpack('<b', wkb.read(1))

    if endian == 0:
        endian = '>'
    elif endian == 1:
        endian = '<'

    # Read the raster header data.
    #
    # +---------------+-------------+------------------------------+
    # | version       | uint16      | format version (0 for this   |
    # |               |             | structure)                   |
    # +---------------+-------------+------------------------------+
    # | nBands        | uint16      | Number of bands              |
    # +---------------+-------------+------------------------------+
    # | scaleX        | float64     | pixel width                  |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | scaleY        | float64     | pixel height                 |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | ipX           | float64     | X ordinate of upper-left     |
    # |               |             | pixel's upper-left corner    |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | ipY           | float64     | Y ordinate of upper-left     |
    # |               |             | pixel's upper-left corner    |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | skewX         | float64     | rotation about Y-axis        |
    # +---------------+-------------+------------------------------+
    # | skewY         | float64     | rotation about X-axis        |
    # +---------------+-------------+------------------------------+
    # | srid          | int32       | Spatial reference id         |
    # +---------------+-------------+------------------------------+
    # | width         | uint16      | number of pixel columns      |
    # +---------------+-------------+------------------------------+
    # | height        | uint16      | number of pixel rows         |
    # +---------------+-------------+------------------------------+
    (version, bands, scaleX, scaleY, ipX, ipY, skewX, skewY,
     srid, width, height) = unpack(endian + 'HHddddddIHH', wkb.read(60))

    ret['version'] = version
    ret['scaleX'] = scaleX
    ret['scaleY'] = scaleY
    ret['ipX'] = ipX
    ret['ipY'] = ipY
    ret['skewX'] = skewX
    ret['skewY'] = skewY
    ret['srid'] = srid
    ret['width'] = width
    ret['height'] = height
    ret['bands'] = []

    for _ in range(bands):
        band = {}

        # Read band header data
        #
        # +---------------+--------------+-----------------------------------+
        # | isOffline     | 1bit         | If true, data is to be found      |
        # |               |              | on the filesystem, trought the    |
        # |               |              | path specified in RASTERDATA      |
        # +---------------+--------------+-----------------------------------+
        # | hasNodataValue| 1bit         | If true, stored nodata value is   |
        # |               |              | a true nodata value. Otherwise    |
        # |               |              | the value stored as a nodata      |
        # |               |              | value should be ignored.          |
        # +---------------+--------------+-----------------------------------+
        # | isNodataValue | 1bit         | If true, all the values of the    |
        # |               |              | band are expected to be nodata    |
        # |               |              | values. This is a dirty flag.     |
        # |               |              | To set the flag to its real value |
        # |               |              | the function st_bandisnodata must |
        # |               |              | must be called for the band with  |
        # |               |              | 'TRUE' as last argument.          |
        # +---------------+--------------+-----------------------------------+
        # | reserved      | 1bit         | unused in this version            |
        # +---------------+--------------+-----------------------------------+
        # | pixtype       | 4bits        | 0: 1-bit boolean                  |
        # |               |              | 1: 2-bit unsigned integer         |
        # |               |              | 2: 4-bit unsigned integer         |
        # |               |              | 3: 8-bit signed integer           |
        # |               |              | 4: 8-bit unsigned integer         |
        # |               |              | 5: 16-bit signed integer          |
        # |               |              | 6: 16-bit unsigned signed integer |
        # |               |              | 7: 32-bit signed integer          |
        # |               |              | 8: 32-bit unsigned signed integer |
        # |               |              | 9: 32-bit float                   |
        # |               |              | 10: 64-bit float                  |
        # +---------------+--------------+-----------------------------------+
        #
        # Requires reading a single byte, and splitting the bits into the
        # header attributes
        (bits,) = unpack(endian + 'b', wkb.read(1))

        band['isOffline'] = bool(bits & 128)  # first bit
        band['hasNodataValue'] = bool(bits & 64)  # second bit
        band['isNodataValue'] = bool(bits & 32)  # third bit

        pixtype = bits & int('00001111', 2) # bits 5-8
        band['pixtype'] = pixtype

        # Based on the pixel type, determine the struct format, byte size and
        # numpy dtype
        fmts = ['?', 'B', 'B', 'b', 'B', 'h',
                'H', 'i', 'I', 'f', 'd']
        dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2',
                  'u2', 'i4', 'u4', 'f4', 'f8']
        sizes = [1, 1, 1, 1, 1, 2, 2, 4, 4, 4, 8]

        dtype = dtypes[pixtype]
        size = sizes[pixtype]
        fmt = fmts[pixtype]

        # Read the nodata value
        (nodata,) = unpack(endian + fmt, wkb.read(size))

        band['nodata'] = nodata

        if band['isOffline']:

            # Read the out-db metadata
            #
            # +-------------+-------------+-----------------------------------+
            # | bandNumber  | uint8       | 0-based band number to use from   |
            # |             |             | the set available in the external |
            # |             |             | file                              |
            # +-------------+-------------+-----------------------------------+
            # | path        | string      | null-terminated path to data file |
            # +-------------+-------------+-----------------------------------+

            # offline bands are 0-based, make 1-based for user consumption
            (band_num,) = unpack(endian + 'B', wkb.read(1))
            band['bandNumber'] = band_num + 1

            data = b''
            while True:
                byte = wkb.read(1)
                if byte == b'\x00':
                    break

                data += byte

            band['path'] = data.decode()

        else:

            # Read the pixel values: width * height * size
            #
            # +------------+--------------+-----------------------------------+
            # | pix[w*h]   | 1 to 8 bytes | Pixels values, row after row,     |
            # |            | depending on | so pix[0] is upper-left, pix[w-1] |
            # |            | pixtype [1]  | is upper-right.                   |
            # |            |              |                                   |
            # |            |              | As for endiannes, it is specified |
            # |            |              | at the start of WKB, and implicit |
            # |            |              | up to 8bits (bit-order is most    |
            # |            |              | significant first)                |
            # |            |              |                                   |
            # +------------+--------------+-----------------------------------+
            band['ndarray'] = np.ndarray(
                (height, width),
                buffer=wkb.read(width * height * size),
                dtype=np.dtype(dtype)
            )

        ret['bands'].append(band)

    return ret


# NOT SURE IF ANY OF THESE RESPECT ENDIANESS        

def write_wkb_raster(bands, width, height, affine, srid=4326):
    """Write Numpy arrays to WKB raster.
    """

    wkb = b''

    # Set the endiannes of the raster
    #
    # +---------------+-------------+------------------------------+
    # | endiannes     | byte        | 1:ndr/little endian          |
    # |               |             | 0:xdr/big endian             |
    # +---------------+-------------+------------------------------+
    endian = '>'
    if endian == '>':
        endiannes = 0
    elif endian == '<':
        endiannes = 1
    wkb += pack('<b', endiannes)

    # Write the raster header data.
    #
    # +---------------+-------------+------------------------------+
    # | version       | uint16      | format version (0 for this   |
    # |               |             | structure)                   |
    # +---------------+-------------+------------------------------+
    # | nBands        | uint16      | Number of bands              |
    # +---------------+-------------+------------------------------+
    # | scaleX        | float64     | pixel width                  |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | scaleY        | float64     | pixel height                 |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | ipX           | float64     | X ordinate of upper-left     |
    # |               |             | pixel's upper-left corner    |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | ipY           | float64     | Y ordinate of upper-left     |
    # |               |             | pixel's upper-left corner    |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | skewX         | float64     | rotation about Y-axis        |
    # +---------------+-------------+------------------------------+
    # | skewY         | float64     | rotation about X-axis        |
    # +---------------+-------------+------------------------------+
    # | srid          | int32       | Spatial reference id         |
    # +---------------+-------------+------------------------------+
    # | width         | uint16      | number of pixel columns      |
    # +---------------+-------------+------------------------------+
    # | height        | uint16      | number of pixel rows         |
    # +---------------+-------------+------------------------------+
    version = 0
    scaleX, skewX, ipX, skewY, scaleY, ipY = affine
    wkb += pack(endian + 'HHddddddIHH', version, len(bands), scaleX, scaleY, ipX, ipY, skewX, skewY, srid, width, height)

    for band in bands:

        # Write band header data
        #
        # +---------------+--------------+-----------------------------------+
        # | isOffline     | 1bit         | If true, data is to be found      |
        # |               |              | on the filesystem, trought the    |
        # |               |              | path specified in RASTERDATA      |
        # +---------------+--------------+-----------------------------------+
        # | hasNodataValue| 1bit         | If true, stored nodata value is   |
        # |               |              | a true nodata value. Otherwise    |
        # |               |              | the value stored as a nodata      |
        # |               |              | value should be ignored.          |
        # +---------------+--------------+-----------------------------------+
        # | isNodataValue | 1bit         | If true, all the values of the    |
        # |               |              | band are expected to be nodata    |
        # |               |              | values. This is a dirty flag.     |
        # |               |              | To set the flag to its real value |
        # |               |              | the function st_bandisnodata must |
        # |               |              | must be called for the band with  |
        # |               |              | 'TRUE' as last argument.          |
        # +---------------+--------------+-----------------------------------+
        # | reserved      | 1bit         | unused in this version            |
        # +---------------+--------------+-----------------------------------+
        # | pixtype       | 4bits        | 0: 1-bit boolean                  |
        # |               |              | 1: 2-bit unsigned integer         |
        # |               |              | 2: 4-bit unsigned integer         |
        # |               |              | 3: 8-bit signed integer           |
        # |               |              | 4: 8-bit unsigned integer         |
        # |               |              | 5: 16-bit signed integer          |
        # |               |              | 6: 16-bit unsigned signed integer |
        # |               |              | 7: 32-bit signed integer          |
        # |               |              | 8: 32-bit unsigned signed integer |
        # |               |              | 9: 32-bit float                   |
        # |               |              | 10: 64-bit float                  |
        # +---------------+--------------+-----------------------------------+
        #
        # Requires writing a single byte, and splitting the bits into the
        # header attributes

        bits = 0

        if band['isOffline']:
            bits = (bits & int('01111111', 2)) | int('10000000', 2) # first bit
        if band['hasNodataValue']:
            bits = (bits & int('10111111', 2)) | int('01000000', 2) # second bit
        if band['isNodataValue']:
            bits = (bits & int('11011111', 2)) | int('00100000', 2) # third bit

        # Based on the pixel type, determine the struct format, byte size and
        # numpy dtype
        pixtype = band['pixtype']
        
        fmts = ['?', 'B', 'B', 'b', 'B', 'h',
                'H', 'i', 'I', 'f', 'd']
        dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2',
                  'u2', 'i4', 'u4', 'f4', 'f8']
        #dtypes = ['bool', 'uint8', 'uint8', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'float32', 'float64']
        sizes = [1, 1, 1, 1, 1, 2, 2, 4, 4, 4, 8]

        dtype = dtypes[pixtype]
        size = sizes[pixtype]
        fmt = fmts[pixtype]
        bits = (bits & int('11110000', 2)) | (pixtype & int('00001111', 2))

        # Write the bits to a byte
        wkb += pack(endian + 'b', bits)

        # Write the nodata value
        nodata = band['nodata']
        wkb += pack(endian + fmt, nodata)

        if band['isOffline']:

            # Wr9te the out-db metadata
            #
            # +-------------+-------------+-----------------------------------+
            # | bandNumber  | uint8       | 0-based band number to use from   |
            # |             |             | the set available in the external |
            # |             |             | file                              |
            # +-------------+-------------+-----------------------------------+
            # | path        | string      | null-terminated path to data file |
            # +-------------+-------------+-----------------------------------+

            # offline bands are 1-based for user consumption, should be 0-based
            band_num = band['bandNumber'] - 1
            wkb += pack(endian + 'B', band_num)
            
            path = band['path'].encode()
            path += b'\x00' # null terminated
            wkb += pack(endian + '{}s'.format(len(path)), path)

        else:

            # Write the pixel values: width * height * size
            #
            # +------------+--------------+-----------------------------------+
            # | pix[w*h]   | 1 to 8 bytes | Pixels values, row after row,     |
            # |            | depending on | so pix[0] is upper-left, pix[w-1] |
            # |            | pixtype [1]  | is upper-right.                   |
            # |            |              |                                   |
            # |            |              | As for endiannes, it is specified |
            # |            |              | at the start of WKB, and implicit |
            # |            |              | up to 8bits (bit-order is most    |
            # |            |              | significant first)                |
            # |            |              |                                   |
            # +------------+--------------+-----------------------------------+
            
            arr = band['ndarray']
            if endian != arr.dtype.byteorder:
                arr = arr.byteswap()
            databytes = arr.tostring()
            wkb += databytes

    return wkb





