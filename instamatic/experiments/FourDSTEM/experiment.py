import datetime
import os
import time
from pathlib import Path

import h5py
import threading
import queue
import numpy as np
from skimage.registration import phase_cross_correlation
from tqdm.auto import tqdm

import instamatic
from instamatic import config
from instamatic.formats import write_hdf5
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
        Gives the interval with which to defocs the scan_pattern slightly for tracking purposes,
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
                 scan_pattern: str = 'XY scan',
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
                 save_tiff_4DSTEM: bool = True,
                 save_hdf5_4DSTEM: bool = False,
                 save_tiff_raw_imgs: bool = True,
                 save_hdf5_raw_imgs: bool = False,
                 save_raw_imgs: bool = True,
                 acquisition_finished = None):
        self.ctrl = ctrl
        self.path = path
        self.logger = log
        self.cam_interface = ctrl.cam.interface
        self.flatfield = flatfield
        self.scan_pattern = scan_pattern
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
        self.save_tiff_4DSTEM = save_tiff_4DSTEM
        self.save_hdf5_4DSTEM = save_hdf5_4DSTEM
        self.save_tiff_raw_imgs = save_tiff_raw_imgs
        self.save_hdf5_raw_imgs = save_hdf5_raw_imgs
        self.save_raw_imgs = save_raw_imgs
        self.acquisition_finished = acquisition_finished

        self.physical_pixelsize = config.camera.physical_pixelsize
        self.wavelength = config.microscope.wavelength  # angstrom
        self.stretch_azimuth = config.camera.stretch_azimuth  # deg
        self.stretch_amplitude = config.camera.stretch_amplitude  # %
        self.spotsize = self.ctrl.spotsize


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

    def setup_path(self):
        self.path = Path(self.path)

        if self.save_tiff_4DSTEM or self.save_tiff_raw_imgs:
            self.tiff_path = self.path / 'tiff'
            self.tiff_path.mkdir(exist_ok=True, parents=True)

        if self.save_hdf5_4DSTEM or self.save_hdf5_raw_imgs:
            self.hdf5_path = self.path / 'hdf5'
            self.hdf5_path.mkdir(exist_ok=True, parents=True)

    def log_start_status(self):
        """Log the starting parameters."""
        self.now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.logger.info(f'Data recording started at: {self.now}')
        self.logger.info(f'Data collection exposure time: {self.exposure_time} s')
        self.logger.info(f'Beam scan dwell time: {self.dwell_time} s')
        self.logger.info(f'Data saving path: {self.path}')

        self.camera_length = int(self.ctrl.magnification.value)
        self.pixelsize = config.calibration[self.ctrl.mode.state]['pixelsize'][self.camera_length]

    def generate_scan_pattern(self):
        start_x = -self.interval_x * (self.nx - 1) / 2
        end_x = self.interval_x * (self.nx + 1) / 2
        start_y = -self.interval_y * (self.ny - 1) / 2
        end_y =self.interval_y * (self.ny + 1) / 2
        x = np.arange(start_x, end_x, self.interval_x)
        y = np.arange(start_y, end_y, self.interval_y)

        if self.scan_pattern == 'XY scan':
            xv, yv = np.meshgrid(x, y)
        elif self.scan_pattern == 'YX scan':
            yv, xv = np.meshgrid(x, y)
        elif self.scan_pattern == 'XY snake scan':
            xv, yv = np.meshgrid(x, y)
            xv[1::2, :] = xv[1::2, ::-1]
        elif self.scan_pattern == 'YX snake scan':
            yv, xv = np.meshgrid(x, y)
            yv[1::2, :] = yv[1::2, ::-1]
        elif self.scan_pattern == 'Spiral scan':
            raise NotImplementedError('Spiral scan did not implemented.')
        return xv, yv

    def generate_virtual_image(self, i: int, j: int, shape: np.array, buf: np.array, img: np.array):
        if self.scan_pattern == 'XY scan':
            buf[i, j] = np.sum(img[self.xmin:self.xmax,self.ymin:self.ymax] * self.mask).mean()
        elif self.scan_pattern == 'YX scan':
            buf[j, i] = np.sum(img[self.xmin:self.xmax,self.ymin:self.ymax] * self.mask).mean()
        elif self.scan_pattern == 'XY snake scan':
            if j % 2 == 1:
                x = shape[0] - i
                buf[x, j] = np.sum(img[self.xmin:self.xmax,self.ymin:self.ymax] * self.mask).mean()
            else:
                buf[i, j] = np.sum(img[self.xmin:self.xmax,self.ymin:self.ymax] * self.mask).mean()
        elif self.scan_pattern == 'YX snake scan':
            if i % 2 == 1:
                x = shape[0] - j
                buf[x, i] = np.sum(img[self.xmin:self.xmax,self.ymin:self.ymax] * self.mask).mean()
            else:
                buf[j, i] = np.sum(img[self.xmin:self.xmax,self.ymin:self.ymax] * self.mask).mean()
        elif self.scan_pattern == 'Spiral scan':
            raise NotImplementedError('Spiral scan did not implemented.')

    def get_mask(self):
        self.ctrl.cam.frame_updated.wait()
        img = self.ctrl.cam.frame
        self.ctrl.cam.frame_updated.clear()
        if self.haadf == True:
            self.xmin, self.xmax = max(0,int(np.floor(self.center_x-min(img.shape)))), min(img.shape[0],int(np.ceil(self.center_x+min(img.shape))))
            self.ymin, self.ymax = max(0,int(np.round(self.center_y-min(img.shape)))), min(img.shape[1],int(np.ceil(self.center_y+min(img.shape))))
            self.mask = get_mask_ann(img, self.center_x, self.center_y, self.haadf_min_radius, min(img.shape))
        elif self.adf == True:
            self.xmin, self.xmax = max(0,int(np.floor(self.center_x-self.haadf_min_radius))), min(img.shape[0],int(np.ceil(self.center_x+self.haadf_min_radius)))
            self.ymin, self.ymax = max(0,int(np.round(self.center_y-self.haadf_min_radius))), min(img.shape[1],int(np.ceil(self.center_y+self.haadf_min_radius)))
            self.mask = get_mask_ann(img, self.center_x, self.center_y, self.bf_max_radius, self.haadf_min_radius)
        elif self.bf == True:
            self.xmin, self.xmax = max(0,int(np.floor(self.center_x-self.bf_max_radius))), min(img.shape[0],int(np.ceil(self.center_x+self.bf_max_radius)))
            self.ymin, self.ymax = max(0,int(np.round(self.center_y-self.bf_max_radius))), min(img.shape[1],int(np.ceil(self.center_y+self.bf_max_radius)))
            self.mask = get_mask_circ(img, self.center_x, self.center_y, self.bf_max_radius)

    def log_end_status(self):
        with open(self.path / 'summary.txt', 'w') as f:
            print(f'Program: {instamatic.__long_title__}', file=f)
            print(f'Data Collection Time: {self.now}', file=f)
            print(f'Time Period Start: {self.t_start}', file=f)
            print(f'Time Period End: {self.t_end}', file=f)
            print(f'Total time: {self.total_time:.3f} s', file=f)
            print(f'Spot Size: {self.spotsize}', file=f)
            print(f'Camera length: {self.camera_length} mm', file=f)
            print(f'Pixelsize: {self.pixelsize} Angstrom^(-1)/pixel', file=f)
            print(f'Physical pixelsize: {self.physical_pixelsize} um', file=f)
            print(f'Wavelength: {self.wavelength} Angstrom', file=f)
            print(f'Stretch amplitude: {self.stretch_azimuth} %', file=f)
            print(f'Stretch azimuth: {self.stretch_amplitude} degrees', file=f)
            print(f'Number of points x-direction: {self.nx}, y-direction: {self.ny}', file=f)
            print(f'Interval x-direction: {self.interval_x} nm, y-direction: {self.interval_y} nm', file=f)
            print(f'Scan pattern: {self.scan_pattern}', file=f)
            
    def virtual_img_info(self):
        with open(self.path / 'summary.txt', 'a') as f:
            if self.haadf:
                print(f'Virtual image type: HAADF, minimum radius: {self.haadf_min_radius} pix', file=f)
            if self.adf:
                print(f'Virtual image type: ADF, minimum radius: {self.haadf_min_radius} pix, maximum radius: {self.bf_max_radius} pix', file=f)
            if self.bf:
                print(f'Virtual image type: BF, maximum radius: {self.bf_max_radius} pix', file=f)
            print(f'Center X: {self.center_x}, Center Y: {self.center_y}', file=f)

    def citation(self):
        with open(self.path / 'summary.txt', 'a') as f:
            print('', file=f)
            print('References:', file=f)
            print(' -', instamatic.__citation__, file=f)
            print(' -', instamatic.__citation_cred__, file=f)

    def scan_beam(self):
        pos_x, pos_y = self.generate_scan_pattern()
        shape = pos_x.shape
        while not self.stopScanEvent.is_set():
            self.continueScanEvent.wait()
            for i in range(shape[0]):
                for j in range(shape[1]):
                    self.ctrl.beamshift.xy = (pos_x[i, j], pos_y[i, j])
                
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
        pos_x, pos_y = self.generate_scan_pattern()
        shape = pos_x.shape
        while not self.stopPreviewEvent.is_set():
            for i in range(shape[0]):
                for j in range(shape[1]):
                    self.ctrl.beamshift.xy = (pos_x[i, j], pos_y[i, j])
                    self.ctrl.cam.frame_updated.wait()
                    img = self.ctrl.cam.frame.astype(np.uint16)
                    self.ctrl.cam.frame_updated.clear()
                    self.generate_virtual_image(i, j, shape, buf, img)
            q.put(buf.astype(np.uint16))

    def start_preview(self):
        self.get_mask()

        t = threading.Thread(target=self.preview, args=(VIRTUALIMGBUF,), daemon=True)
        t.start()

    def stop_preview(self):
        self.stopPreviewEvent.set()

    def acquire(self, q):
        self.buffer = []
        buf = np.zeros((self.nx, self.ny))
        pos_x, pos_y = self.generate_scan_pattern()
        shape = pos_x.shape
        # synchonization of camera and beam scan
        for _ in range(1):
            self.ctrl.cam.frame_updated.wait()
            img = self.ctrl.cam.frame.astype(np.uint16)
            self.ctrl.cam.frame_updated.clear()

        self.log_start_status()
        t0 = time.perf_counter()
        while not self.stopAcqEvent.is_set():
            for i in range(shape[0]):
                for j in range(shape[1]):
                    self.ctrl.beamshift.xy = (pos_x[i, j], pos_y[i, j])
                    self.ctrl.cam.frame_updated.wait()
                    img = self.ctrl.cam.frame.astype(np.uint16)
                    self.ctrl.cam.frame_updated.clear()
                    self.generate_virtual_image(i, j, shape, buf, img)
            q.put(buf.astype(np.uint16))
            self.buffer.append(buf.astype(np.uint16))
        t1 = time.perf_counter()

        self.t_start = t0
        self.t_end = t1
        self.total_time = t1 - t0
        self.finialize_acquire()

    def start_acquire(self):
        self.get_mask()

        t = threading.Thread(target=self.acquire, args=(VIRTUALIMGBUF,), daemon=True)
        t.start()

    def stop_acquire(self):
        self.stopAcqEvent.set()

    def finialize_acquire(self):
        self.logger.info(f'Data saving path: {self.path}')

        self.log_end_status()
        self.virtual_img_info()
        self.citation()

        if self.save_tiff_4DSTEM:
            for i in range(len(self.buffer)):
                img, header = self.buffer[i]
                fn = self.tiff_path / f'{i:07d}.tiff'
                write_tiff(fn, img)
        if self.save_hdf5_4DSTEM:
            fn = self.hdf5_path / f'imgs.h5'
            with h5py.File(fn, 'w') as hf:
                for i in range(len(self.buffer)):
                    img = self.buffer[i]
                    dset = hf.create_dataset(f'{i:07d}', data=img)

        print('Data Collection and Conversion Done.')
        print()

    def acq_raw_img(self):
        self.buffer = []
        pos_x, pos_y = self.generate_scan_pattern()
        shape = pos_x.shape
        # synchonization of camera and beam scan
        for _ in range(1):
            self.ctrl.cam.frame_updated.wait()
            img = self.ctrl.cam.frame.astype(np.uint16)
            self.ctrl.cam.frame_updated.clear()
        self.log_start_status()

        t0 = time.perf_counter()
        while not self.stopAcqRawImgEvent.is_set():
            for i in range(shape[0]):
                for j in range(shape[1]):
                    self.ctrl.beamshift.xy = (pos_x[i, j], pos_y[i, j])
                    self.ctrl.cam.frame_updated.wait()
                    img = self.ctrl.cam.frame.astype(np.uint16)
                    self.ctrl.cam.frame_updated.clear()
                    h = {'x': pos_x[i, j], 'y': pos_y[i, j]}
                    self.buffer.append((img, h))
        t1 = time.perf_counter()

        self.t_start = t0
        self.t_end = t1
        self.total_time = t1 - t0
        self.finalize_acq_raw_img()

    def start_acq_raw_img(self):
        t = threading.Thread(target=self.acq_raw_img, args=(), daemon=True)
        t.start()

    def stop_acq_raw_img(self):
        self.stopAcqRawImgEvent.set()

    def finalize_acq_raw_img(self):
        """Finalize data collection after `self.start_acq_raw_img` has been run.

        Write data in `self.buffer` to path given by `self.path`.
        """

        self.logger.info(f'Data saving path: {self.path}')

        self.log_end_status()
        self.citation()

        if self.save_tiff_raw_imgs:
            for i in range(len(self.buffer)):
                img, header = self.buffer[i]
                fn = self.tiff_path / f'{i:07d}.tiff'
                write_tiff(fn, img, header=header)
        if self.save_hdf5_raw_imgs:
            fn = self.hdf5_path / f'raw_imgs.h5'
            with h5py.File(fn, 'w') as hf:
                for i in range(len(self.buffer)):
                    img, header = self.buffer[i]
                    dset = hf.create_dataset(f'{i:07d}', data=img)
                    dset.attrs.update(header)

        print('Data Collection and Conversion Done.')
        print()

    def acquire_one_img(self, q):
        self.buffer = [] # buffer for raw images
        buf = np.zeros((self.nx, self.ny)) # virtual image
        pos_x, pos_y = self.generate_scan_pattern()
        shape = pos_x.shape
        # synchonization of camera and beam scan
        for _ in range(1):
            self.ctrl.cam.frame_updated.wait()
            img = self.ctrl.cam.frame.astype(np.uint16)
            self.ctrl.cam.frame_updated.clear()
        self.log_start_status()

        t0 = time.perf_counter()
        for i in range(shape[0]):
            for j in range(shape[1]):
                self.ctrl.beamshift.xy = (pos_x[i, j], pos_y[i, j])
                self.ctrl.cam.frame_updated.wait()
                img = self.ctrl.cam.frame.astype(np.uint16)
                self.ctrl.cam.frame_updated.clear()
                self.generate_virtual_image(i, j, shape, buf, img)
                h = {'x': pos_x[i, j], 'y': pos_y[i, j]}
                self.buffer.append((img, h))
        q.put(buf.astype(np.uint16))
        t1 = time.perf_counter()

        self.t_start = t0
        self.t_end = t1
        self.total_time = t1 - t0
        self.finalize_acq_one_img(img=buf.astype(np.uint16))

    def acquire_one_virtual_img(self):
        self.get_mask()

        t = threading.Thread(target=self.acquire_one_img, args=(VIRTUALIMGBUF,), daemon=True)
        t.start()

    def finalize_acq_one_img(self, img):
        self.logger.info(f'Data saving path: {self.path}')

        self.acquisition_finished.set()
        self.log_end_status()
        self.virtual_img_info()
        self.citation()

        if self.save_tiff_4DSTEM:
            write_tiff(self.path / 'img.tiff', img)
        if self.save_hdf5_4DSTEM:
            write_hdf5(self.path / 'img.h5', img)

        if self.save_raw_imgs:
            if self.save_tiff_raw_imgs:
                for i in range(len(self.buffer)):
                    img, header = self.buffer[i]
                    fn = self.tiff_path / f'{i:07d}.tiff'
                    write_tiff(fn, img, header=header)
            if self.save_hdf5_raw_imgs:
                fn = self.hdf5_path / f'raw_imgs.h5'
                with h5py.File(fn, 'w') as hf:
                    for i in range(len(self.buffer)):
                        img, header = self.buffer[i]
                        dset = hf.create_dataset(f'{i:07d}', data=img)
                        dset.attrs.update(header)

        print('Data Collection and Conversion Done.')
        print()

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
