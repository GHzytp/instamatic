import datetime
import os
import Time
from pathlib import Path

import h5py
import threading
import queue
import numpy as np
from skimage.registration import phase_cross_correlation
from tqdm.auto import tqdm

from instamatic import config
from instamatic.formats import write_tiff
from instamatic.processing.ImgConversionTPX import ImgConversionTPX as ImgConversion
from instamatic.image_utils import translate_image

from .virtualimage import get_mask_circ, get_mask_ann

VIRTUALIMGBUF = queue.Queue()

class Experiment:
    """Initialize 4DSTEM experiment.

    ctrl:
        Instance of instamatic.TEMController.TEMController
    path:
        `str` or `pathlib.Path` object giving the path to save data at
    log:
        Instance of `logging.Logger`
    flatfield:
        Path to flatfield correction image
    unblank_beam:
        Whether beam should be automatically unblanked before experiment
    mode:
        Which mode the experiment is running in, choices: 'simulate', 'footfree', None (default)
    footfree_rotate_to:
        In 'footfree' mode, rotate to this angle
    enable_image_interval:
        Gives the interval with which to defocs the pattern slightly for tracking purposes,
        default is set to 99999 so it never occurs.
    diff_defocus:
        Image interval only - Defocus value to apply when defocused images are used for tracking
    exposure_time_image:
        Image interval only - Exposure time for defocused images
    write_tiff, write_xds, write_dials, write_red:
        Specify which data types/input files should be written
    stop_event:
        Instance of `threading.Event()` that signals the experiment to be terminated.
    """

    def __init__(self, ctrl,
                 path: str = None,
                 log=None,
                 flatfield: str = None,
                 dwell_time: float = 0.003,
                 exposure_time: float = 0.01,
                 haadf_min_radius: int = 300,
                 bf_max_radius: int = 100,
                 center_x: float = 256.0,
                 center_y: float = 256.0,
                 interval_x: float = 100.0,
                 interval_y: float = 100.0,
                 nx: int = 32,
                 ny: int = 32,
                 haadf: bool = True,
                 adf: bool = False,
                 bf: bool = False,
                 save_mrc_4DSTEM: bool = True,
                 save_hdf5_4DSTEM: bool = False,
                 save_mrc_raw_imgs: bool = True,
                 save_hdf5_raw_imgs: bool = False):
        self.ctrl = ctrl
        self.path = path
        self.logger = log
        self.cam_interface = ctrl.cam.interface
        self.flatfield = flatfield
        self.dwell_time = dwell_time
        self.exposure_time = exposure_time
        self.haadf_min_radius = haadf_min_radius
        self.bf_max_radius = bf_max_radius
        self.center_x = center_x
        self.center_y = center_y
        self.interval_x = interval_x
        self.interval_y = interval_y
        self.nx = nx
        self.ny = ny
        self.haadf = haadf
        self.adf = adf
        self.bf = bf
        self.save_mrc_4DSTEM = save_mrc_4DSTEM
        self.save_hdf5_4DSTEM = save_hdf5_4DSTEM
        self.save_mrc_raw_imgs = save_mrc_raw_imgs
        self.save_hdf5_raw_imgs = save_hdf5_raw_imgs

        if self.path is not None:
            self.setup_path()

        self.buffer = []

        self.physical_pixelsize = config.camera.physical_pixelsize  # mm
        self.wavelength = config.microscope.wavelength  # angstrom

        self.stopScanEvent = threading.Event()
        self.continueScanEvent = threading.Event()
        self.continueScanEvent.set()

        self.stopPreviewEvent = threading.Event()
        self.stopAcqEvent = threading.Event()
        self.stopAcqRawImgEvent = threading.Event()

    def start_collection(self, exposure_time: float, end_angle: float, stepsize: float):
        """Start or continue data collection for `tilt_range` degrees with
        steps given by `stepsize`, To finalize data collection and write data
        files, run `self.finalize`.

        The number of images collected is defined by `tilt_range / stepsize`.

        exposure_time:
            Exposure time for each image in seconds
        tilt_range:
            Tilt range starting from the current angle in degrees. Must be positive.
        stepsize:
            Step size for the angle in degrees, controls the direction and can be positive or negative
        """
        pass

    def setup_path(self):
        self.path = Path(self.path)
        self.mrc_path = self.path / 'mrc'
        self.hdf5_path = self.path / 'hdf5'

        self.mrc_path.mkdir(exist_ok=True, parents=True)
        self.hdf5_path.mkdir(exist_ok=True, parents=True)

    def generate_scan_pattern(self):
        start_x = -self.interval_x * (self.nx - 1) / 2
        end_x = self.interval_x * (self.nx + 1) / 2
        start_y = self.interval_y * (self.ny - 1) / 2
        end_y =self.interval_y * (self.ny + 1) / 2
        x = np.arange(start_x, end_x, self.interval_x)
        y = np.arange(start_y, end_y, self.interval_y)
        xv, yv = np.meshgrid(x, y)
        return xv, yv

    def scan_beam(self):
        pos_x, pox_y = self.generate_scan_pattern()
        while not self.stopScanEvent.is_set():
            self.continueScanEvent.wait()
            for i in pos_x:
                for j in pos_y:
                    self.ctrl.beamshift.xy = (i, j)
                
    def start_scan_beam(self):
        t = threading.Thread(target=self.scan_beam, args=(), daemon=True)
        t.start()
        
    def pause_scan_beam(self):
        self.continueScanEvent.clear()

    def continue_scan_beam(self):
        self.continueScanEvent.set()

    def stop_scan_beam(self):
        self.stopScanEvent.set()

    def preview(self, q):
        buf = np.zeros((self.nx, self.ny))
        while not self.stopPreviewEvent.is_set():
            for i, x in enuemrate(pos_x):
                for j, y in enumerate(pos_y):
                    self.ctrl.beamshift.xy = (x, y)
                    self.ctrl.cam.frame_updated.wait()
                    img, h = self.ctrl.cam.frame
                    self.ctrl.cam.frame_updated.clear()
                    buf[i, j] = np.sum(img[xmin:xmax,ymin:ymax] * self, mask)
            q.put(buf)


    def start_preview(self):
        pos_x, pox_y = self.generate_scan_pattern()
        self.ctrl.cam.frame_updated.wait()
        img = self.ctrl.cam.frame
        self.ctrl.cam.frame_updated.clear()
        if self.haadf == True:
            xmin, xmax = max(0,int(np.floor(x0-Ro))), min(img.shape[0],int(np.ceil(x0+Ro)))
            ymin, ymax = max(0,int(np.round(y0-Ro))), min(img.shape[1],int(np.ceil(y0+Ro)))
            self.mask = get_mask_ann(img, self.center_x, self.center_y, self.haadf_min_radius, min(img.shape))
        elif self.adf == True:
            xmin, xmax = max(0,int(np.floor(x0-Ro))), min(img.shape[0],int(np.ceil(x0+Ro)))
            ymin, ymax = max(0,int(np.round(y0-Ro))), min(img.shape[1],int(np.ceil(y0+Ro)))
            self.mask = get_mask_ann(img, self.center_x, self.center_y, self.bf_max_radius, self.haadf_min_radius)
        elif self.bf == True:
            xmin, xmax = max(0,int(np.floor(x0-R))), min(img.shape[0],int(np.ceil(x0+R)))
            ymin, ymax = max(0,int(np.round(y0-R))), min(img.shape[1],int(np.ceil(y0+R)))
            self.mask = get_mask_circ(img, self.center_x, self.center_y, self.bf_max_radius)

        t = threading.Thread(target=self.preview, args=(VIRTUALIMGBUF,))
        t.start()


    def stop_preview(self):
        self.stopPreviewEvent.set()

    def start_acquire(self):
        pass

    def stop_acquire(self):
        pass

    def start_acq_raw_img(self):
        pass

    def stop_acq_raw_img(self):
        pass


    def finalize(self):
        """Finalize data collection after `self.start_collection` has been run.

        Write data in `self.buffer` to path given by `self.path`.
        """
        if not hasattr(self, 'end_angle'):
            self.end_angle = self.ctrl.stage.a

        self.logger.info(f'Data saving path: {self.path}')

        with open(self.path / 'summary.txt', 'a') as f:
            print(f'Rotation range: {self.end_angle-self.start_angle:.2f} degrees', file=f)
            print(f'Exposure Time: {self.exposure_time:.3f} s', file=f)
            print(f'Spot Size: {self.spotsize}', file=f)
            print(f'Magnification: {self.magnification}', file=f)
            print(f'Pixelsize: {self.pixelsize} nm/pixel', file=f)
            print(f'Physical pixelsize: {self.physical_pixelsize} um', file=f)
            print(f'Wavelength: {self.wavelength} Angstrom', file=f)
            print(f'Rotation axis: {self.rotation_axis} radians', file=f)
            print(f'Stepsize: {self.stepsize:.4f} degrees', file=f)
            print(f'Number of frames: {self.nframes}', file=f)

        img_conv = ImgConversion(buffer=self.buffer,
                                 osc_angle=self.stepsize,
                                 start_angle=self.start_angle,
                                 end_angle=self.end_angle,
                                 rotation_axis=self.rotation_axis,
                                 acquisition_time=self.exposure_time,
                                 flatfield=self.flatfield,
                                 pixelsize=self.pixelsize,
                                 physical_pixelsize=self.physical_pixelsize,
                                 wavelength=self.wavelength
                                 )

        print('Writing data files...')
        img_conv.threadpoolwriter(tiff_path=self.tiff_path,
                                  mrc_path=self.mrc_path,
                                  workers=8)

        print('Writing input files...')
        img_conv.write_ed3d(self.mrc_path)

        print('Data Collection and Conversion Done.')
        print()

        return True


def main():
    from instamatic import TEMController
    ctrl = TEMController.initialize()

    import logging
    log = logging.getLogger(__name__)

    exposure_time = 0.5
    end_angle = 10
    stepsize = 1.0

    i = 1
    while True:
        expdir = f'experiment_{i}'
        if os.path.exists(expdir):
            i += 1
        else:
            break

    print(f'\nData directory: {expdir}')

    red_exp = Experiment(ctrl=ctrl, path=expdir, log=log, flatfield=None)
    red_exp.start_collection(exposure_time=exposure_time, end_angle=end_angle, stepsize=stepsize)

    input('Press << Enter >> to start the experiment... ')

    while not input(f'\nPress << Enter >> to continue for another {tilt_range} degrees. [any key to finalize] '):
        red_exp.start_collection(exposure_time=exposure_time, end_angle=end_angle, stepsize=stepsize)

    red_exp.finalize()


if __name__ == '__main__':
    main()
