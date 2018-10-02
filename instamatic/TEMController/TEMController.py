#!/usr/bin/env python

import time
from instamatic.formats import write_tiff

from instamatic import config
from instamatic.camera import Camera
from .microscope import Microscope

from typing import Tuple
import numpy as np


default_cam = config.camera.name
default_tem = config.microscope.name
use_server  = config.cfg.use_tem_server


def initialize(tem_name: str=default_tem, cam_name: str=default_cam, stream: bool=True) -> "TEMController":
    """Initialize TEMController object giving access to the TEM and Camera interfaces

    tem_name: Name of the TEM to use
    cam_name: Name of the camera to use, can be set to 'None' to skip camera initialization
    stream: Open the camera as a stream (this enables `TEMController.show_stream()`)
    """

    print("Microscope: {}{}".format(tem_name, ' (server)' if use_server else ''))
    print("Camera    : {}{}".format(cam_name, ' (stream)' if (cam_name and stream) else ''))

    tem = Microscope(tem_name, use_server=use_server)
    
    if cam_name:
        cam = Camera(cam_name, as_stream=stream)
    else:
        cam = None

    ctrl = TEMController(tem=tem, cam=cam)

    return ctrl


class Deflector(object):
    """Generic microscope deflector object defined by X/Y values
    Must be subclassed to set the self._getter, self._setter functions"""
    def __init__(self, tem):
        super().__init__()
        self._tem = tem
        self._getter = None
        self._setter = None
        self.key = "def"

    def __repr__(self):
        x, y = self.get()
        return "{}(x={x}, y={y})".format(self.name, x=x, y=y)

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def set(self, x: int, y: int):
        self._setter(x, y)

    def get(self) -> Tuple[int, int]:
        return self._getter()

    @property
    def x(self) -> int:
        x, y = self.get()
        return x

    @x.setter
    def x(self, value: int):
        self.set(value, self.y)

    @property
    def y(self) -> int:
        x, y = self.get()
        return y

    @y.setter
    def y(self, value: int):
        self.set(self.x, value)

    @property
    def xy(self) -> Tuple[int, int]:
        return self.get()

    @xy.setter
    def xy(self, values: Tuple[int, int]):
        x, y = values
        self.set(x=x, y=y)

    def neutral(self):
        self._tem.setNeutral(self.key)


class Lens(object):
    """Generic microscope lens object defined by one value
    Must be subclassed to set the self._getter, self._setter functions"""
    def __init__(self, tem):
        super().__init__()
        self._tem = tem
        self._getter = None
        self._setter = None
        self.key = "lens"
        
    def __repr__(self):
        try:
            value = self.value
        except ValueError:
            value="n/a"
        return "{}(value={value})".format(self.name, value=value)

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def set(self, value: int):
        self._setter(value)

    def get(self) -> int:
        return self._getter()

    @property
    def value(self) -> int:
        return self.get()

    @value.setter
    def value(self, value: int):
        self.set(value)


class DiffFocus(Lens):
    """DiffFocus control"""
    def __init__(self, tem):
        super().__init__(tem=tem)
        self._getter = self._tem.getDiffFocus
        self._setter = self._tem.setDiffFocus

    def set(self, value: int, confirm_mode: bool=True):
        """confirm_mode: verify that TEM is set to the correct mode ('diff').
            IL1 maps to different values in image and diffraction mode. 
            Turning it off results in a 2x speed-up in the call, but it will silently fail if the TEM is in the wrong mode."""
        self._setter(value, confirm_mode=confirm_mode)


class Brightness(Lens):
    """Brightness control"""
    def __init__(self, tem):
        super().__init__(tem=tem)
        self._getter = self._tem.getBrightness
        self._setter = self._tem.setBrightness

    def max(self):
        self.set(65535)

    def min(self):
        self.set(0)


class Magnification(Lens):
    """Magnification control. The magnification can be set directly, or
    by passing the corresponding index"""
    def __init__(self, tem):
        super().__init__(tem=tem)
        self._getter = self._tem.getMagnification
        self._setter = self._tem.setMagnification
        self._indexgetter = self._tem.getMagnificationIndex
        self._indexsetter = self._tem.setMagnificationIndex

    def __repr__(self):
        value = self.value
        index = self.index
        return "Magnification(value={}, index={})".format(value, index)

    @property
    def index(self) -> int:
        return self._indexgetter()

    @index.setter
    def index(self, index: int):
        self._indexsetter(index)

    def increase(self) -> None:
        try:
            self.index += 1
        except ValueError:
            print("Error: Cannot go to higher magnification (current={}).".format(self.value))

    def decrease(self) -> None:
        try:
            self.index -= 1
        except ValueError:
            print("Error: Cannot go to higher magnification (current={}).".format(self.value))


class GunShift(Deflector):
    """GunShift control"""
    def __init__(self, tem):
        super().__init__(tem=tem)
        self._setter = self._tem.setGunShift
        self._getter = self._tem.getGunShift
        self.key = "GUN1"


class GunTilt(Deflector):
    """GunTilt control"""
    def __init__(self, tem):
        super().__init__(tem=tem)
        self._setter = self._tem.setGunTilt
        self._getter = self._tem.getGunTilt
        self._tem = tem
        self.key = "GUN2"


class BeamShift(Deflector):
    """BeamShift control"""
    def __init__(self, tem):
        super().__init__(tem=tem)
        self._setter = self._tem.setBeamShift
        self._getter = self._tem.getBeamShift
        self.key = "CLA1"


class BeamTilt(Deflector):
    """BeamTilt control"""
    def __init__(self, tem):
        super().__init__(tem=tem)
        self._setter = self._tem.setBeamTilt
        self._getter = self._tem.getBeamTilt
        self.key = "CLA2"
        

class DiffShift(Deflector):
    """DiffShift control"""
    def __init__(self, tem):
        super().__init__(tem=tem)
        self._setter = self._tem.setDiffShift
        self._getter = self._tem.getDiffShift
        self.key = "PLA"
        
 
class ImageShift1(Deflector):
    """ImageShift control"""
    def __init__(self, tem):
        super().__init__(tem=tem)
        self._setter = self._tem.setImageShift1
        self._getter = self._tem.getImageShift1
        self.key = "IS1"

class ImageShift2(Deflector):
    """ImageShift control"""
    def __init__(self, tem):
        super().__init__(tem=tem)
        self._setter = self._tem.setImageShift2
        self._getter = self._tem.getImageShift2
        self.key = "IS1"
   

class StagePosition(object):
    """StagePosition control"""
    def __init__(self, tem):
        super().__init__()
        self._tem = tem
        self._setter = self._tem.setStagePosition
        self._getter = self._tem.getStagePosition
        
    def __repr__(self):
        x, y, z, a, b = self.get()
        return "{}(x={x:.1f}, y={y:.1f}, z={z:.1f}, a={a:.1f}, b={b:.1f})".format(self.name, x=x, y=y, z=z, a=a, b=b)

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def set(self, x: int=None, y: int=None, z: int=None, a: int=None, b: int=None, wait: bool=True):
        """wait: bool, block until stage movement is complete"""
        self._setter(x, y, z, a, b, wait=wait)

    def get(self) -> Tuple[int, int, int, int, int]:
        return self._getter()

    @property
    def x(self) -> int:
        x, y, z, a, b = self.get()
        return x

    @x.setter
    def x(self, value: int):
        self.set(x=value)

    @property
    def y(self) -> int:
        x, y, z, a, b = self.get()
        return y

    @property
    def xy(self) -> Tuple[int, int]:
        x, y, z, a, b = self.get()
        return x, y

    @xy.setter
    def xy(self, values: Tuple[int, int]):
        x, y = values
        self.set(x=x, y=y)

    @y.setter
    def y(self, value: int):
        self.set(y=value)

    def move_in_projection(self, delta_x: int, delta_y: int):
        r"""y and z are always perpendicular to the sample stage. To achieve the movement
        in the projection, x and yshould be broken down into the components z' and y'.

        y = y' * cos(a)
        z = y' * sin(a)

        z'|  / z
          | /
          |/_____ y'
           \ a
            \
             \ y
        """
        x, y, z, a, b = self.get()
        a = np.radians(a)
        x = x + delta_x
        y = y + delta_y * np.cos(a)
        z = z - delta_y * np.sin(a)
        self.set(x=x, y=y, z=z)

    def move_along_optical_axis(self, delta_z: int):
        """See `StagePosition.move_in_projection`"""
        x, y, z, a, b = self.get()
        a = np.radians(a)
        y = y + delta_z * np.sin(a)
        z = z + delta_z * np.cos(a)
        self.set(y=y, z=z) 

    @property
    def z(self) -> int:
        x, y, z, a, b = self.get()
        return z

    @z.setter
    def z(self, value: int):
        self.set(z=value)

    @property
    def a(self) -> int:
        x, y, z, a, b = self.get()
        return a

    @a.setter
    def a(self, value: int):
        self.set(a=value)

    @property
    def b(self) -> int:
        x, y, z, a, b = self.get()
        return b

    @b.setter
    def b(self, value: int):
        self.set(b=value)

    def neutral(self) -> None:
        """Reset the position of the stage to the 0-position"""
        self.set(x=0, y=0, z=0, a=0, b=0)

    def is_moving(self) -> bool:
        """Return 'True' if the stage is moving"""
        return self._tem.isStageMoving()

    def stop(self) -> None:
        """This will halt the stage preemptively if `wait=False` is passed to StagePosition.set"""
        self._tem.stopStage()


class TEMController(object):
    """TEMController object that enables access to all defined microscope controls

    tem: Microscope control object (e.g. instamatic/TEMController/simu_microscope.SimuMicroscope)
    cam: Camera control object (see instamatic.camera) [optional]
    """

    def __init__(self, tem, cam=None):
        super(TEMController, self).__init__()

        self.tem = tem
        self.cam = cam

        self.gunshift = GunShift(tem)
        self.guntilt = GunTilt(tem)
        self.beamshift = BeamShift(tem)
        self.beamtilt = BeamTilt(tem)
        self.imageshift1 = ImageShift1(tem)
        self.imageshift2 = ImageShift2(tem)
        self.diffshift = DiffShift(tem)
        self.stageposition = StagePosition(tem)
        self.magnification = Magnification(tem)
        self.brightness = Brightness(tem)
        self.difffocus = DiffFocus(tem)

        self.autoblank = False
        self._saved_settings = {}
        print()
        print(self)
        self.store()

    @property
    def spotsize(self) -> int:
        return self.tem.getSpotSize()

    @spotsize.setter
    def spotsize(self, value: int):
        self.tem.setSpotSize(value)

    def mode_lowmag(self):
        self.tem.setFunctionMode("lowmag")

    def mode_mag1(self):
        self.tem.setFunctionMode("mag1")

    def mode_samag(self):
        self.tem.setFunctionMode("samag")

    def mode_diffraction(self):
        self.tem.setFunctionMode("diff")

    @property
    def mode(self):
        """Returns one of 'mag1', 'mag2', 'lowmag', 'samag', 'diff'"""
        return self.tem.getFunctionMode()

    @mode.setter
    def mode(self, value: str):
        """Should be one of 'mag1', 'mag2', 'lowmag', 'samag', 'diff'"""
        self.tem.setFunctionMode(value)

    @property
    def beamblank(self):
        return self.tem.isBeamBlanked()

    @beamblank.setter
    def beamblank(self, on: bool):
        self.tem.setBeamBlank(on)

    def __repr__(self):
        return "\n".join(("Mode: {}".format(self.tem.getFunctionMode()),
                          str(self.gunshift),
                          str(self.guntilt),
                          str(self.beamshift),
                          str(self.beamtilt),
                          str(self.imageshift1),
                          str(self.imageshift2),
                          str(self.diffshift),
                          str(self.stageposition),
                          str(self.magnification),
                          str(self.difffocus),
                          str(self.brightness),
                          "SpotSize({})".format(self.spotsize),
                          "Saved settings: {}".format(", ".join(self._saved_settings.keys()))))

    def to_dict(self, *keys) -> dict:
        """
        Store microscope parameters to dict

        keys: tuple of str (optional)
            If any keys are specified, dict is returned with only the given properties
        
        self.to_dict('all') or self.to_dict() will return all properties
        """
        
        ## Each of these costs about 62 ms per call, stageposition is 265 ms per call
        funcs = { 
            'FunctionMode': self.tem.getFunctionMode,
            'GunShift': self.gunshift.get,
            'GunTilt': self.guntilt.get,
            'BeamShift': self.beamshift.get,
            'BeamTilt': self.beamtilt.get,
            'ImageShift1': self.imageshift1.get,
            'ImageShift2': self.imageshift2.get,
            'DiffShift': self.diffshift.get,
            # 'StagePosition': self.stageposition.get,
            'Magnification': self.magnification.get,
            'DiffFocus': self.difffocus.get,
            'Brightness': self.brightness.get,
            'SpotSize': self.tem.getSpotSize
        }

        dct = {}

        if "all" in keys or not keys:
            keys = funcs.keys()

        for key in keys:
            try:
                dct[key] = funcs[key]()
            except ValueError:
                pass

        return dct

    def from_dict(self, dct: dict):
        """Restore microscope parameters from dict"""

        funcs = {
            # 'FunctionMode': self.tem.setFunctionMode,
            'GunShift': self.gunshift.set,
            'GunTilt': self.guntilt.set,
            'BeamShift': self.beamshift.set,
            'BeamTilt': self.beamtilt.set,
            'ImageShift1': self.imageshift1.set,
            'ImageShift2': self.imageshift2.set,
            'DiffShift': self.diffshift.set,
            'StagePosition': self.stageposition.set,
            'Magnification': self.magnification.set,
            'DiffFocus': self.difffocus.set,
            'Brightness': self.brightness.set,
            'SpotSize': self.tem.setSpotSize
        }

        mode = dct["FunctionMode"]
        self.tem.setFunctionMode(mode)

        for k, v in dct.items():
            if k in funcs:
                func = funcs[k]
            else:
                continue
            
            try:
                func(*v)
            except TypeError:
                func(v)

        # print self

    def getRawImage(self, exposure: float=0.5, binsize: int=1) -> np.ndarray:
        """Simplified function equivalent to `getImage` that only returns the raw data array"""
        return self.cam.getImage(exposure=exposure, binsize=binsize)

    def getImage(self, exposure: float=0.5, binsize: int=1, comment: str="", out: str=None, plot: bool=False, verbose: bool=False, header_keys: Tuple[str]="all") -> Tuple[np.ndarray, dict]:
        """Retrieve image as numpy array from camera

        Parameters:
            exposure: float, 
                exposure time in seconds
            binsize: int, 
                which binning to use for the image, must be 1, 2, or 4
            comment: str, 
                arbitrary comment to add to the header file under 'ImageComment'
            out: str, 
                path or filename to which the image/header is saved (defaults to tiff)
            plot: bool, 
                toggle whether to show the image using matplotlib after acquisition
            full_header: bool,
                return the full header

        Returns:
            image: np.ndarray, headerfile: dict
                a tuple of the image as numpy array and dictionary with all the tem parameters and image attributes

        Usage:
            img, h = self.getImage()
        """

        if not self.cam:
            raise AttributeError("{} object has no attribute 'cam' (Camera has not been initialized)".format(repr(self.__class__.__name__)))

        if not header_keys:
            h = {}
        else:
            h = self.to_dict(header_keys)

        if self.autoblank and self.beamblank:
            self.beamblank = False

        arr = self.cam.getImage(exposure=exposure, binsize=binsize)
        
        if self.autoblank:
            self.beamblank = True

        h["ImageGetTime"] = time.time()
        h["ImageExposureTime"] = exposure
        h["ImageBinSize"] = binsize
        h["ImageResolution"] = arr.shape
        h["ImageComment"] = comment
        h["ImageCameraName"] = self.cam.name
        h["ImageCameraDimensions"] = self.cam.dimensions

        if verbose:
            print("Image acquired - shape: {}, size: {:.0f} kB".format(arr.shape, arr.nbytes / 1024))

        if out:
            write_tiff(out, arr, header=h)

        if plot:
            import matplotlib.pyplot as plt
            plt.imshow(arr)
            plt.show()

        return arr, h

    def store(self, name: str="stash"):
        """Stores current settings to dictionary.
        Multiple settings can be stored under different names."""
        d = self.to_dict()
        d.pop("StagePosition", None)
        self._saved_settings[name] = d

    def restore(self, name: str="stash"):
        """Restsores settings from dictionary by the given name."""
        d = self._saved_settings[name]
        self.from_dict(d)
        print("Microscope alignment restored from '{}'".format(name))

    def close(self):
        try:
            self.cam.close()
        except AttributeError:
            pass

    def show_stream(self):
        """If the camera has been opened as a stream, start a live view in a tkinter window"""
        try:
           self.cam.show_stream()
        except AttributeError:
            print("Cannot open live view. The camera interface must be initialized as a stream object.")


def main_entry():
    import argparse
    description = """Python program to control Jeol TEM"""

    parser = argparse.ArgumentParser(  # usage=usage,
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    # parser.add_argument("args",
    #                     type=str, metavar="FILE",
    #                     help="Path to save cif")

    parser.add_argument("-u", "--simulate",
                        action="store_true", dest="simulate",
                        help="""Simulate microscope connection (default False)""")
    
    parser.set_defaults(
        simulate=False,
        tem="simtem",
    )

    options = parser.parse_args()
    ctrl = initialize()

    from IPython import embed
    embed(banner1="\nAssuming direct control.\n")
    ctrl.close()


if __name__ == '__main__':
    from IPython import embed
    ctrl = initialize()
    
    embed(banner1="\nAssuming direct control.\n")

    ctrl.close()
