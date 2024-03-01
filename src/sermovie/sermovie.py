# coding: utf-8

"""
SER Decoder (see https://www.grischa-hahn.homepage.t-online.de/astro/ser/  ).

Copyright (C) 2023 Sergio Diaz, sergiodiaz.eu

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
more details.

You should have received a copy of the GNU General Public License along with
this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import numpy as np
from datetime import datetime
import warnings


class SERMovie:
    """
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
        # 1) Directly, outside context: get_frame() opens the file, reads
        # one frame and automatically closes the file
        im = m.get_frame(0)
        print(im.shape)
        plt.imshow(im)

        # 2) Within context: the file is only opened at the beginning and
        # closed at the end of the context. This is better than the
        # previous option when accessing to multiple frames.
        with m:
            im0 = m.get_frame(0)
            im1 = m.get_frame(1)
            plt.imshow(im1-im0)

        # 3) Access frames via memmap, so you can access all the stream
        # as a big array where frames can be indexed by the first axis
        # (slices and advanced indexing are supported)
        ims = m.as_memmap()
        print(ims.shape)
        plt.imshow(ims[0, ...])


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

    datetime : numpy.datetime64
        start date/time of image stream, in local time
        Use .item() to convert to datetime

    datetime_utc : numpy.datetime64
        start date/time of image stream, in UTC
        Use .item() to convert to datetime

    timestamps_utc : np.array[numpy.datetime64]
        numpy array including timestamps for all frames, if present

    Parameters
    ----------
    fname : str
        filename

    Raises
    ------
    NotImplementedError
        Raises if unexpected values are found in the file header
    """

    file_id = "LUCAM-RECORDER"
    header_size = 178
    color_modes = {
        0: "MONO",
        8: "BAYER_RGGB",
        9: "BAYER_GRBG",
        10: "BAYER_GBRG",
        11: "BAYER_BGGR",
        16: "BAYER_CYYM",
        17: "BAYER_YCMY",
        18: "BAYER_YMCY",
        19: "BAYER_MYYC",
        100: "RGB",
        101: "BGR",
    }

    def __init__(self, fname):
        self.fname = fname

        read_int32 = lambda f: int.from_bytes(f.read(4), byteorder="little")
        read_int64 = lambda f: int.from_bytes(f.read(8), byteorder="little")
        read_str = lambda f, length: f.read(length).decode().strip()

        with open(fname, "rb") as f:
            file_id = read_str(f, 14)
            if file_id != self.file_id:
                raise NotImplementedError(f"Unexpected FileID {file_id}")
            self.lu_id = read_int32(f)  # unused, 0

            self.color_id = read_int32(f)
            self.color = self.color_modes[self.color_id]
            self.planes = 3 if self.color in ("RGB", "BGR") else 1

            self.endian = "little" if read_int32(f) else "big"

            self.width = read_int32(f)
            self.height = read_int32(f)
            self.bpp = read_int32(f)
            dtypes = {
                8: "uint8",
                16: ">u2" if self.endian == "little" else "<u2",
            }
            try:
                self.dtype = dtypes[self.bpp]
            except KeyError:
                raise NotImplementedError(f"Unexpected PixelDepthPerPlane {self.bpp}")
            self.shape = (
                (self.height, self.width)
                if self.planes == 1
                else (self.height, self.width, self.planes)
            )
            self.frame_pixels = self.height * self.width
            self.frame_bytes = self.frame_pixels * self.planes * self.bpp // 8

            self.frames = read_int32(f)
            data_size = self.frames * self.frame_bytes

            self.observer = read_str(f, 40)
            self.instrument = read_str(f, 40)
            self.telescope = read_str(f, 40)
            self.datetime = self.timestamp(np.array([read_int64(f)]))[0]
            self.datetime_utc = self.timestamp(np.array([read_int64(f)]))[0]

            assert (
                f.tell() == self.header_size
            ), f"Current position: {f.tell()}, expected header size: {self.header_size}"

            f.seek(data_size, 1)  # Skip image data, jump to trailer (timestamps)
            self.timestamps_utc = self.timestamp(np.fromfile(f, dtype="<i8"))
            num_ts = self.timestamps_utc.shape[0]
            if num_ts > 0 and num_ts != self.frames:
                warnings.warn(
                    f"Number of timestamps at trailer ({num_ts}) does not match the "
                    f"number of frames specified in the header ({self.frames})"
                )

            self.f = None
            self.mmap = None

    @staticmethod
    def timestamp(tdelta64_100ns):
        # tdelta64_100ns: timestamps at the trailer of the .ser file are expressed in 100ns units
        # datetime support up to microsecond resolution; here we simply truncate the last digit
        # because we won't be working as such time resolution anyway.
        # This is a vectorized version of: timedelta(microseconds=tdelta64_100ns//10) + datetime(1, 1, 1)
        # Note: numpy.datetime64 won't store timezone info, so it does makes sense to create the
        # reference date as datetime(1, 1, 1, tzinfo=timezone.utc)
        ref = np.datetime64(datetime(1, 1, 1))
        return (tdelta64_100ns // 10).astype("timedelta64[us]") + ref

    def __enter__(self):
        self.f = open(self.fname, "rb")
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.f.close()
        self.f = None

    def get_frame(self, frame):
        if frame >= self.frames:
            raise ValueError(
                f"Requested frame ({frame}) out of range ({self.frames} frames)"
            )

        frame_start = self.header_size + frame * self.frame_bytes

        no_context = self.f is None
        if no_context:
            self.__enter__()

        self.f.seek(frame_start)
        img = np.fromfile(self.f, dtype=self.dtype, count=self.frame_pixels)

        if no_context:
            self.__exit__(None, None, None)

        return img.reshape(self.shape)

    def as_memmap(self):
        if self.mmap is None:
            self.mmap = np.memmap(
                self.fname,
                self.dtype,
                offset=self.header_size,
                shape=(self.frames,) + self.shape,
            )
        return self.mmap

    def close_memmap(self):
        # TODO: can cause kernel crashes
        #   https://github.com/numpy/numpy/issues/13510
        if self.mmap is not None and not self.mmap._mmap.closed:
            self.mmap._mmap.close()
        else:
            warnings.warn("Nothing to close")

    def __str__(self):
        return (
            f"SER File: {self.fname}\n"
            f"Image Data: {self.frames}x {self.shape} {self.dtype} {self.color}\n"
            f"Date: {str(self.datetime)} ({str(self.datetime_utc)} UTC)\n"
            f"Observer: '{self.observer}'\n"
            f"Instrument: '{self.instrument}'\n"
            f"Telescope: '{self.instrument}'\n"
            f"Frame Timestamps: {len(self.timestamps_utc)}\n"
        )

    def _repr_html_(self):
        return self.__str__().replace("\n", "<br/>")
