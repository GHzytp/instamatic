import datetime
import json
import socket
import time
from pathlib import Path

import numpy as np
import decimal

import instamatic
from instamatic import config
from instamatic.formats import write_tiff

if config.camera.interface == "DM":
    from instamatic.processing.ImgConversionDM import ImgConversionDM as ImgConversion
else:
    from instamatic.processing.ImgConversionTPX import ImgConversionTPX as ImgConversion


# degrees to rotate before activating data collection procedure
ACTIVATION_THRESHOLD = 0.2

use_vm = config.settings.use_VM_server_exe

def print_and_log(msg, logger=None):
    print(msg)
    if logger:
        logger.info(msg)

class Experiment:
    """Initialize continuous rotation electron diffraction experiment.

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
    enable_image_interval:
        Gives the interval with which to defocs the pattern slightly for tracking purposes,
        default is set to 99999 so it never occurs.
    diff_defocus:
        Image interval only - Defocus value to apply when defocused images are used for tracking
    exposure_time_image:
        Image interval only - Exposure time for defocused images
    write_tiff, write_xds, write_dials, write_red, write_cbf:
        Specify which data types/input files should be written
    stop_event:
        Instance of `threading.Event()` that signals the experiment to be terminated.
    """

    def __init__(self, ctrl,
                 path: str = None,
                 log=None,
                 flatfield: str = None,
                 exposure_time: float = 0.3,
                 unblank_beam: bool = False,
                 enable_image_interval: bool = False,
                 image_interval: int = 99999,
                 low_angle_image_interval: int = 99999,
                 diff_defocus: int = 0,
                 start_frames: int = 5,
                 start_frames_interval: int = 2,
                 defocus_start_angle: float = 0.0,
                 exposure_time_image: float = 0.01,
                 write_tiff: bool = True,
                 write_xds: bool = True,
                 write_dials: bool = True,
                 write_red: bool = True,
                 write_cbf: bool = True,
                 stop_event=None,
                 ):
        super().__init__()
        self.ctrl = ctrl
        self.path = Path(path)
        self.exposure = exposure_time
        self.unblank_beam = unblank_beam
        self.logger = log
        self.stopEvent = stop_event
        self.flatfield = flatfield

        self.diff_defocus = diff_defocus
        self.start_frames = start_frames
        self.start_frames_interval = start_frames_interval
        self.defocus_start_angle = defocus_start_angle
        self.exposure_image = exposure_time_image
        self.frametime = self.ctrl.cam.frametime

        self.write_tiff = write_tiff
        self.write_xds = write_xds
        self.write_dials = write_dials
        self.write_red = write_red
        self.write_cbf = write_cbf
        self.write_pets = write_tiff  # TODO

        self.image_interval_enabled = enable_image_interval
        if enable_image_interval:
            self.image_interval = image_interval
            print_and_log(f'Image interval enabled: every {self.image_interval} frames an image with defocus {self.diff_defocus} will be displayed (t={self.exposure_image} s).', logger=self.logger)
            self.low_angle_image_interval = low_angle_image_interval
            print_and_log(f'Image interval enabled: every {self.low_angle_image_interval} frames an image at low angle (lower than {self.defocus_start_angle}) with defocus {self.diff_defocus} will be displayed (t={self.exposure_image} s).', logger=self.logger)
        else:
            self.image_interval = 99999
            self.low_angle_image_interval = 99999
        
        self.relax_beam_before_experiment = self.image_interval_enabled and config.settings.cred_relax_beam_before_experiment

        self.track_stage_position = config.settings.cred_track_stage_positions
        self.binsize = self.ctrl.cam.default_binsize
        self.stage_positions = []

        if use_vm:
            self.s2 = socket.socket()
            vm_host = config.settings.VM_server_host
            vm_port = config.settings.VM_server_port
        try:
            self.s2.connect((vm_host, vm_port))
            print('VirtualBox server connected for autocRED.')
            self.s2_c = 1
        except BaseException:
            print('Is VM server running? Connection failed.')
            self.s2_c = 0

    def log_start_status(self):
        """Log the starting parameters."""
        self.now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.logger.info(f'Data recording started at: {self.now}')
        self.logger.info(f'Data collection exposure time: {self.exposure} s')
        self.logger.info(f'Data saving path: {self.path}')

    def log_end_status(self):
        """Log the experimental values, write file `cRED_log.txt`"""

        print_and_log(f'Rotated {self.total_angle:.2f} degrees from {self.start_angle:.2f} to {self.end_angle:.2f} in {self.nframes} frames (step: {self.osc_angle:.4f})', logger=self.logger)

        self.logger.info(f'Data collection camera length: {self.camera_length} mm')
        self.logger.info(f'Data collection spot size: {self.spotsize}')

        with open(self.path / 'cRED_XNano_log.txt', 'w') as f:
            print(f'Program: {instamatic.__long_title__}', file=f)
            print(f'Data Collection Time: {self.now}', file=f)
            print(f'Time Period Start: {self.t_start}', file=f)
            print(f'Time Period End: {self.t_end}', file=f)
            print(f'Starting angle: {self.start_angle:.2f} degrees', file=f)
            print(f'Ending angle: {self.end_angle:.2f} degrees', file=f)
            print(f'Rotation range: {self.end_angle-self.start_angle:.2f} degrees', file=f)
            print(f'Exposure Time: {self.exposure:.3f} s', file=f)
            print(f'Acquisition time: {self.acquisition_time:.3f} s', file=f)
            print(f'Total time: {self.total_time:.3f} s', file=f)
            print(f'Spot Size: {self.spotsize}', file=f)
            print(f'Camera length: {self.camera_length} mm', file=f)
            print(f'Pixelsize: {self.pixelsize} Angstrom^(-1)/pixel', file=f)
            print(f'Physical pixelsize: {self.physical_pixelsize} um', file=f)
            print(f'Wavelength: {self.wavelength} Angstrom', file=f)
            print(f'Stretch amplitude: {self.stretch_azimuth} %', file=f)
            print(f'Stretch azimuth: {self.stretch_amplitude} degrees', file=f)
            print(f'Rotation axis: {self.rotation_axis} radians', file=f)
            print(f'Oscillation angle: {self.osc_angle:.4f} degrees', file=f)
            print(f'Number of frames: {self.nframes_diff}', file=f)

            if self.image_interval_enabled:
                print(f'Image interval: every {self.image_interval} frames an image with defocus {self.diff_focus_defocused} (t={self.exposure_image} s).', file=f)
                print(f'Number of images: {self.nframes_image}', file=f)

            print('', file=f)
            print('References:', file=f)
            print(' -', instamatic.__citation__, file=f)
            print(' -', instamatic.__citation_cred__, file=f)

    def setup_paths(self):
        """Set up the paths for saving the data to."""
        print(f'\nOutput directory: {self.path}')
        self.tiff_path = self.path / 'tiff' if self.write_tiff else None
        self.smv_path = self.path / 'SMV' if (self.write_xds or self.write_dials) else None
        self.mrc_path = self.path / 'RED' if self.write_red else None
         self.cbf_path = self.path / 'CBF' if self.write_cbf else None

    def relax_beam(self, n_cycles: int = 5):
        """Relax the beam prior to the experiment by toggling between the
        defocused/focused states."""
        print(f'Relaxing beam ({n_cycles} cycles)', end='')

        for i in range(n_cycles):
            self.ctrl.difffocus.set(self.diff_focus_defocused)
            time.sleep(0.5)
            print(f'.', end='')
            self.ctrl.difffocus.set(self.diff_focus_proper)
            time.sleep(0.5)
            print(f'.', end='')

        print('Done.')

    def start_collection(self) -> bool:
        """Main experimental function, returns True if experiment runs
        normally, False if it is interrupted for whatever reason."""
        if self.image_interval_enabled:
            # Add value checking for exposure image to obtain a normal exposure time for defocused image
            if self.ctrl.cam.interface == 'DM':
                if self.frametime > self.exposure_image or self.exposure < self.exposure_image + self.frametime:
                    raise ValueError('Please adjust the exposure time for defocused image.')
            else:
                if self.frametime > self.exposure_image or self.exposure < self.exposure_image:
                    raise ValueError('Please adjust the exposure time for defocused image.')

        self.setup_paths()
        self.log_start_status()

        buffer = []
        image_buffer = []

        if self.ctrl.tem.interface=="fei":
            if self.ctrl.mode not in ('D','LAD'):
                self.ctrl.tem.setProjectionMode('diffraction')
        else:
            if self.ctrl.mode != 'diff':
                self.ctrl.mode.set('diff')

        if self.ctrl.difffocus is None:
            self.ctrl.difffocus = instamatic.TEMController.lenses.DiffFocus(self.ctrl.tem)

        self.diff_focus_proper = self.ctrl.difffocus.value
        self.diff_focus_defocused = self.diff_defocus + self.diff_focus_proper
        exposure_image = self.exposure_image

        if self.relax_beam_before_experiment:
            self.relax_beam()

        if self.unblank_beam:
            print('Unblanking beam')
            self.ctrl.beam.unblank()
            
        self.current_angle = self.start_angle
        self.ctrl.cam.block()

        i = 1

        t0 = time.perf_counter()

        while not self.stopEvent.is_set():
            if self.image_interval_enabled and ((i < self.start_frames and i % self.start_frames_interval == 0 ) or 
            (i % self.image_interval == 0 and np.abs(self.current_angle) > np.abs(self.defocus_start_angle)) or 
            (i % self.low_angle_image_interval == 0 and np.abs(self.current_angle) <= np.abs(self.defocus_start_angle))):
                t_start = time.perf_counter()
                acquisition_time = (t_start - t0) / (i - 1)

                self.ctrl.difffocus.set(self.diff_focus_defocused, confirm_mode=False)
                if self.ctrl.cam.interface == 'DM':
                    # One frame was removed for a clean defocused image so the exposure time for diffraction pattern
                    # should be larger than the total of frametime and exposure time for defocused image
                    time.sleep(self.frametime * 3)
                img, h = self.ctrl.get_image(exposure_image, header_keys=None)
                self.ctrl.difffocus.set(self.diff_focus_proper, confirm_mode=False)

                image_buffer.append((i, img, h))

                next_interval = t_start + acquisition_time
                # print(f"{i} BLOOP! {next_interval-t_start:.3f} {acquisition_time:.3f} {t_start-t0:.3f}")

                while time.perf_counter() > next_interval:
                    next_interval += acquisition_time
                    i += 1
                    print(f"{i} SKIP!  {next_interval-t_start:.3f} {acquisition_time:.3f}")

                if self.ctrl.cam.interface == 'DM':
                    diff = next_interval - time.perf_counter() - self.frametime
                else:
                    diff = next_interval - time.perf_counter()  # seconds

                if self.track_stage_position and diff > 0.1:
                    self.stage_positions.append((i, self.ctrl.stage.get()))

                time.sleep(diff)

            else:
                img, h = self.ctrl.get_image(self.exposure, header_keys=None)
                # print(f"{i} Image!")
                buffer.append((i, img, h))
                # print(f"Angle: {self.ctrl.stage.a}")

            i += 1

            if self.ctrl.tem.interface == 'fei':
                if not self.ctrl.tem.isStageMoving():
                    self.stopEvent.set()

        t1 = time.perf_counter()


        self.ctrl.cam.unblock()

        if self.mode == 'simulate':
            # simulate somewhat realistic end numbers
            self.ctrl.stage.x += np.random.randint(-100, 100)
            self.ctrl.stage.y += np.random.randint(-100, 100)
            self.ctrl.stage.a += np.random.randint(-60, 60)
            self.ctrl.magnification.set(330)

        self.end_position = self.ctrl.stage.get()
        self.end_angle = self.end_position[3]
        self.camera_length = int(self.ctrl.magnification.value)
        self.stage_positions.append((99999, self.end_position))

        is_moving = bool(self.ctrl.stage.is_moving())
        self.logger.info(f'Experiment finished, stage is moving: {is_moving}')

        if self.unblank_beam:
            print('Blanking beam')
            self.ctrl.beam.blank()

        # in case something went wrong starting data collection, return gracefully
        if i == 1:
            print_and_log(f'Data collection interrupted', logger=self.logger)
            return False

        self.spotsize = self.ctrl.spotsize
        self.nframes = i - 1  # len(buffer) can lie in case of frame skipping
        self.osc_angle = abs(self.end_angle - self.start_angle) / self.nframes
        self.t_start = t0
        self.t_end = t1
        self.total_time = t1 - t0
        self.acquisition_time = self.total_time / self.nframes
        self.total_angle = abs(self.end_angle - self.start_angle)
        self.rotation_axis = config.calibration.camera_rotation_vs_stage_xy

        software_binsize = config.settings.software_binsize
        if software_binsize is None:
            self.pixelsize = config.calibration[self.ctrl.mode.state]['pixelsize'][self.camera_length] * self.binsize  # Angstrom^(-1)/pixel
            self.physical_pixelsize = config.camera.physical_pixelsize * self.binsize  # mm
        else:
            self.pixelsize = config.calibration[self.ctrl.mode.state]['pixelsize'][self.camera_length] * self.binsize * software_binsize  # Angstrom^(-1)/pixel
            self.physical_pixelsize = config.camera.physical_pixelsize * self.binsize * software_binsize  # mm
            
        self.wavelength = config.microscope.wavelength  # angstrom
        self.stretch_azimuth = config.calibration.stretch_azimuth  # deg
        self.stretch_amplitude = config.calibration.stretch_amplitude  # %

        self.nframes_diff = len(buffer)
        self.nframes_image = len(image_buffer)

        self.log_end_status()

        if self.nframes <= 3:
            print_and_log(f'Not enough frames collected. Data will not be written (nframes={self.nframes})', logger=self.logger)
            return False

        self.write_data(buffer)
        self.write_image_data(image_buffer)

        print('Data Collection and Conversion Done.')

        pathsmv_str = str(self.smv_path)
        msg = {'path': pathsmv_str,
               'rotrange': self.total_angle,
               'nframes': self.nframes,
               'osc': self.osc_angle}
        msg_tosend = json.dumps(msg).encode('utf8')

        if self.s2_c:
            self.s2.send(msg_tosend)
            print('SMVs sent to XDS for processing.')

        return True

    def write_data(self, buffer: list):
        """Write diffraction data in the buffer.

        The image buffer is passed as a list of tuples, where each tuple contains the
        index (int), image data (2D numpy array), metadata/header (dict).

        The buffer index must start at 1.
        """

        img_conv = ImgConversion(buffer=buffer,
                                 osc_angle=self.osc_angle,
                                 start_angle=self.start_angle,
                                 end_angle=self.end_angle,
                                 rotation_axis=self.rotation_axis,
                                 acquisition_time=self.acquisition_time,
                                 flatfield=self.flatfield,
                                 pixelsize=self.pixelsize,
                                 physical_pixelsize=self.physical_pixelsize,
                                 wavelength=self.wavelength,
                                 stretch_amplitude=self.stretch_amplitude,
                                 stretch_azimuth=self.stretch_azimuth,
                                 )

        print('Writing data files...')
        img_conv.threadpoolwriter(tiff_path=self.tiff_path,
                                  mrc_path=self.mrc_path,
                                  smv_path=self.smv_path,
                                  cbf_path=self.cbf_path,
                                  workers=8)

        print('Writing input files...')
        if self.write_dials:
            img_conv.to_dials(self.smv_path)
        if self.write_red:
            img_conv.write_ed3d(self.mrc_path)
        if self.write_xds or self.write_dials:
            img_conv.write_xds_inp(self.smv_path)
        if self.write_pets:
            img_conv.write_pets_inp(self.path)

        img_conv.write_beam_centers(self.path)

    def write_image_data(self, buffer: list):
        """Write image data in the buffer.

        The image buffer is passed as a list of tuples, where each tuple
        contains the index (int), image data (2D numpy array),
        metadata/header (dict).
        """
        if buffer:
            drc = self.path / 'tiff_image'
            drc.mkdir(exist_ok=True)
            while len(buffer) != 0:
                i, img, h = buffer.pop(0)
                fn = drc / f'{i:05d}.tiff'
                write_tiff(fn, img, header=h)