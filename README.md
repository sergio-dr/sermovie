<a id="sermovie"></a>

# sermovie

SER Decoder (see https://www.grischa-hahn.homepage.t-online.de/astro/ser/  ).

Copyright (C) 2023 Sergio Díaz, sergiodiaz.eu

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
more details.

You should have received a copy of the GNU General Public License along with
this program.  If not, see <http://www.gnu.org/licenses/>.

<a id="sermovie.SERMovie"></a>

## SERMovie Objects

```python
class SERMovie()
```

Simple class for reading SER movie files, with timestamp support.

Based on:
- [Grischa Hahn's SER Specs](https://www.grischa-hahn.homepage.t-online.de/astro/ser/)
- [PyMovie](https://github.com/bob-anderson-ok/pymovie/blob/master/src/pymovie/SER.py)
- [pySER-Reader](https://github.com/Copper280z/pySER-Reader/blob/master/ser_reader.py)

Usage example:

    from sermovie import SERMovie
    import matplotlib.pyplot as plt

    m = SERMovie("file.ser")
    print(m)  # Header info

    # For reading frames, some options:
    # 1) Directly, outside context: open, read data then close the file
    im = m.getFrame(0)
    print(im.shape)
    plt.imshow(im)

    # 2) Within context: the file is only opened at the beginning and
    # closed at the end (better if getting multiple frames)
    with m:
        im = m.getFrame(0)
        print(im.shape)
        plt.imshow(im)

    # 3) Access frames via memmap, so you can access all the stream
    # as a big array where frames can be indexed by the first axis
    # (slices and advanced indexing are supported)
    im = m.as_memmap()
    print(im.shape)
    plt.imshow(im[0, ...])


Attributes
----------
color_modes : dict
    dictionary with supported color modes

color : str
    color mode of the current file (see color_modes)

planes : int
    number of planes of each frame

endian : str
    'little' or 'big'

width : int
    width of each frame, in pixels

height : int
    height of each frame, in pixels

bpp : int
    bits per plane, 8 or 16

shape : tuple
    tuple (height, width, planes), or (height, width) if planes==1

frame_pixels : int
    total number of pixel in each frame

frame_bytes : int
    frame size in bytes

observer : str
    observer field (40 bytes max)

instrument : str
    instrument field (40 bytes max)

telescope : str
    telescope field (40 bytes max)

datetime : datetime
    start date/time of image stream, in local time

datetime_utc : datetime
    start date/time of image stream, in UTC

timestamps_utc : np.array[datetime64]
    numpy array including timestamps for all frames, if present

Parameters
----------
fname : str
    filename

Raises
------
NotImplementedError
    Raises if unexpected values are found in the file header

