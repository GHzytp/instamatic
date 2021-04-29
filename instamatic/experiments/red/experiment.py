import datetime
import os
import time
from pathlib import Path

import numpy as np
from tqdm.auto import tqdm
from tkinter import messagebox

from instamatic import config
from instamatic.formats import write_tiff
if config.camera.interface == "DM":
    from instamatic.processing.ImgConversionDM import ImgConversionDM as ImgConversion
elif config.camera.interface == "timepix":
    from instamatic.processing.ImgConversionTPX import ImgConversionTPX as ImgConversion
elif config.camera.interface == "emmenu":
    from instamatic.processing.ImgConversionTVIPS import ImgConversionTVIPS as ImgConversion
else:
    from instamatic.processing.ImgConversion import ImgConversion


class Experiment:
    """Initialize stepwise rotation electron diffraction experiment (no beam tilt). During stage rotation, the sample may drift.

    ctrl:
        Instance of instamatic.TEMController.TEMController
    path:
        `str` or `pathlib.Path` object giving the path to save data at
    log:
        Instance of `logging.Logger`
    flatfield:
        Path to flatfield correction image
    """

    def __init__(self, ctrl, path: str = None, log=None, flatfield=None, do_stretch_correction=False, 
                stretch_amplitude=0.0, stretch_azimuth=0.0, stretch_cent_x=0.0, stretch_cent_y=0.0):
        super().__init__()
        self.ctrl = ctrl
        self.path = Path(path)

        self.tiff_image_path = self.path / 'tiff_image'
        self.tiff_image_path.mkdir(exist_ok=True, parents=True)

        self.do_stretch_correction = do_stretch_correction
        self.stretch_azimuth = stretch_azimuth  # deg
        self.stretch_amplitude = stretch_amplitude  # %
        self.stretch_cent_x = stretch_cent_x
        self.stretch_cent_y = stretch_cent_y

        self.logger = log
        self.camtype = ctrl.cam.name

        self.flatfield = flatfield

        self.offset = 1
        self.current_angle = None
        self.buffer = []
        self.binsize = ctrl.cam.default_binsize
        self.wavelength = config.microscope.wavelength  # angstrom
        self.rotation_axis = config.calibration.camera_rotation_vs_stage_xy
        self.pixelsize = None

        self.beam_tilt_matrix_D = np.array(config.calibration.beam_tilt_matrix_D).reshape(2, 2)
        self.diffraction_shift_matrix = np.array(config.calibration.diffraction_shift_matrix).reshape(2, 2)

    def start_collection_stage_tilt(self, exposure_time: float, tilt_range: float, stepsize: float, enable_diff_image:bool, diff_defocus: int, wait_interval: float):
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
        self.enable_beam_tilt = False
        self.spotsize = self.ctrl.spotsize
        self.now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.logger.info(f'Data recording started at: {self.now}')
        self.logger.info(f'Exposure time: {exposure_time} s, Tilt range: {tilt_range}, step size: {stepsize}')

        ctrl = self.ctrl

        if ctrl.mode.state not in ('D', 'diff'):
            print('Must in diffraction mode to perform RED data collection.')
            return

        if self.pixelsize is None:
            self.camera_length = int(self.ctrl.magnification.get())
            software_binsize = config.settings.software_binsize
            if software_binsize is None:
                self.pixelsize = config.calibration[self.ctrl.mode.state]['pixelsize'][self.camera_length] * self.binsize 
                self.physical_pixelsize = config.camera.physical_pixelsize * self.binsize 
            else:
                self.pixelsize = config.calibration[self.ctrl.mode.state]['pixelsize'][self.camera_length] * self.binsize * software_binsize 
                self.physical_pixelsize = config.camera.physical_pixelsize * self.binsize * software_binsize 

        if stepsize < 0:
            tilt_range = -abs(tilt_range)
        else:
            tilt_range = abs(tilt_range)

        if self.current_angle is None:
            self.start_angle = start_angle = ctrl.stage.a
        else:
            start_angle = self.current_angle + stepsize
        tilt_positions = np.arange(start_angle, start_angle + tilt_range, stepsize)
        print(f'\nStart_angle: {start_angle:.3f}')

        for i, angle in enumerate(tqdm(tilt_positions)):
            ctrl.stage.a = angle
            time.sleep(wait_interval/2)
            j = i + self.offset
            img, h = self.ctrl.get_image(exposure_time, header_keys='StagePosition')
            self.buffer.append((j, img, h))

        self.offset += len(tilt_positions)
        self.nframes = j

        self.end_angle = end_angle = ctrl.stage.a

        self.stepsize = stepsize
        self.exposure_time = exposure_time

        with open(self.path / 'summary.txt', 'a') as f:
            print(f'{self.now}: Data collected from {start_angle:.2f} degree to {end_angle:.2f} degree in {len(tilt_positions)} frames.', file=f)
            print(f'Data collected from {start_angle:.2f} degree to {end_angle:.2f} degree in {len(tilt_positions)} frames.')

        self.logger.info(f'Data collected from {start_angle:.2f} degree to {end_angle:.2f} degree (camera length: {self.camera_length} mm).')

        if enable_diff_image:
            self.diff_focus_proper = self.ctrl.difffocus.value
            self.diff_focus_defocused = diff_defocus + self.diff_focus_proper

            self.ctrl.difffocus.set(self.diff_focus_defocused, confirm_mode=False)
            time.sleep(wait_interval)
            fn = self.tiff_image_path / f'image_{self.offset}.tiff'
            img, h = self.ctrl.get_image(exposure_time / 2, header_keys='StagePosition')
            write_tiff(fn, img, header=h)
            self.ctrl.difffocus.set(self.diff_focus_proper, confirm_mode=False)

        self.current_angle = angle
        print(f'Done, current angle = {self.current_angle:.2f} degrees')

    def start_collection_stage_beam_tilt(self, exposure_time: float, stepsize: float, enable_diff_image: bool, diff_defocus: int, 
                                        wait_interval: float, beam_tilt_num: int, tilt_num: int):
        self.enable_beam_tilt = True
        self.beam_tilt_num = beam_tilt_num
        self.spotsize = self.ctrl.spotsize
        self.now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.logger.info(f'Data recording started at: {self.now}')
        self.logger.info(f'Exposure time: {exposure_time} s, Tilt number: {tilt_num}, step size: {stepsize}')

        ctrl = self.ctrl

        if ctrl.mode.state not in ('D', 'diff'):
            print('Must in diffraction mode to perform RED data collection.')
            return

        self.beamtilt_bak = ctrl.beamtilt.get()
        self.diffraction_shift_bak = ctrl.diffshift.get()

        if self.pixelsize is None:
            self.camera_length = int(self.ctrl.magnification.get())
            software_binsize = config.settings.software_binsize
            if software_binsize is None:
                self.pixelsize = config.calibration[self.ctrl.mode.state]['pixelsize'][self.camera_length] * self.binsize 
                self.physical_pixelsize = config.camera.physical_pixelsize * self.binsize 
            else:
                self.pixelsize = config.calibration[self.ctrl.mode.state]['pixelsize'][self.camera_length] * self.binsize * software_binsize 
                self.physical_pixelsize = config.camera.physical_pixelsize * self.binsize * software_binsize 
            # shift in Å-1 = angle(degree) * matrix    theta = arcsin(1/d * lambda/2) * 180/pi = 1/d * lambda/2 * 180/pi
            self.stage_matrix = np.pi / 180 * 2 / self.wavelength * np.array(config.calibration[self.ctrl.mode.state]['stagematrix'][self.camera_length]).reshape(2, 2) * self.pixelsize

        for _ in range(tilt_num):
            if self.current_angle is None:
                self.start_angle = start_angle = ctrl.stage.a
                ctrl.stage.eliminate_backlash_a(target_angle=start_angle+stepsize/2)
                if not messagebox.askokcancel("Continue", "Check crystal position and continue"):
                    return
            else:
                start_angle = self.current_angle + stepsize/2 + stepsize/beam_tilt_num
                ctrl.stage.a = start_angle
            beam_tilt_positions = np.linspace(start_angle - stepsize/2, start_angle + stepsize/2, beam_tilt_num + 1)
            print(f'\nStart_angle: {start_angle:.3f}')

            for i, angle in enumerate(tqdm(beam_tilt_positions)):
                # angle change (degree) -> shift in diff pattern (stage_matrix in diff mode, Å-1) -> beam_tilt
                beam_tilt = np.array([angle, 0]) @ self.stage_matrix @ self.beam_tilt_matrix_D + self.beamtilt_bak
                self.ctrl.beamtilt.set(x=beam_tilt[0], y=beam_tilt[1])
                # beam-tilt induced shift in diffraction pattern compensated by diffraction shift
                diffraction_shift = - beam_tilt @ np.linalg.inv(self.beam_tilt_matrix_D) @ self.diffraction_shift_matrix + self.diffraction_shift_bak
                self.ctrl.diffshift.set(x=diffraction_shift[0], y=diffraction_shift[1])
                time.sleep(wait_interval/2)
                j = i + self.offset
                img, h = self.ctrl.get_image(exposure_time)
                self.buffer.append((j, img, h))

            self.offset += len(beam_tilt_positions)
            self.nframes = j

            self.stepsize = stepsize
            self.exposure_time = exposure_time

            with open(self.path / 'summary.txt', 'a') as f:
                print(f'{self.now}: Data collected from {start_angle-stepsize/2:.2f} degree to {start_angle+stepsize/2:.2f} degree in {len(beam_tilt_positions)} frames.', file=f)
                print(f'Data collected from {start_angle-stepsize/2:.2f} degree to {start_angle+stepsize/2:.2f} degree in {len(beam_tilt_positions)} frames.')

            self.logger.info(f'Data collected from {start_angle-stepsize/2:.2f} degree to {start_angle+stepsize/2:.2f} degree (camera length: {self.camera_length} mm).')

            self.current_angle = angle
            print(f'Done, current angle = {self.current_angle:.2f} degrees')

        if enable_diff_image:
            self.diff_focus_proper = self.ctrl.difffocus.value
            self.diff_focus_defocused = diff_defocus + self.diff_focus_proper

            self.ctrl.difffocus.set(self.diff_focus_defocused, confirm_mode=False)
            time.sleep(wait_interval)
            fn = self.tiff_image_path / f'image_{self.offset}.tiff'
            img, h = self.ctrl.get_image(exposure_time / 2, header_keys='StagePosition')
            write_tiff(fn, img, header=h)
            self.ctrl.difffocus.set(self.diff_focus_proper, confirm_mode=False)

        self.end_angle = end_angle = ctrl.stage.a

    def finalize(self, write_tiff=True, write_xds=True, write_dials=True, write_red=True, write_cbf=True, write_pets=True):
        """Finalize data collection after `self.start_collection` has been run.

        Write data in `self.buffer` to path given by `self.path`.
        """
        self.logger.info(f'Data saving path: {self.path}')
        
        self.tiff_path = self.path / 'tiff' if write_tiff else None
        self.mrc_path = self.path / 'RED' if write_red else None
        self.smv_path = self.path / 'SMV' if (write_xds or write_dials) else None
        self.cbf_path = self.path / 'CBF' if write_cbf else None

        if self.enable_beam_tilt:
            stepsize = self.stepsize / self.beam_tilt_num
            self.ctrl.beamtilt.xy = self.beamtilt_bak
            self.ctrl.diffshift.xy = self.diffraction_shift_bak
        else:
            stepsize = self.stepsize

        with open(self.path / 'summary.txt', 'a') as f:
            if self.enable_beam_tilt:
                print(f'Rotation range: {self.end_angle-self.start_angle+self.stepsize:.2f} degrees', file=f)
            else:
                print(f'Rotation range: {self.end_angle-self.start_angle:.2f} degrees', file=f)
            print(f'Exposure Time: {self.exposure_time:.3f} s', file=f)
            print(f'Spot Size: {self.spotsize}', file=f)
            print(f'Camera length: {self.camera_length} mm', file=f)
            print(f'Pixelsize: {self.pixelsize} Angstrom^(-1)/pixel', file=f)
            print(f'Physical pixelsize: {self.physical_pixelsize} um', file=f)
            print(f'Wavelength: {self.wavelength} Angstrom', file=f)
            print(f'Rotation axis: {self.rotation_axis} radians', file=f)
            print(f'Stepsize: {stepsize:.4f} degrees', file=f)
            print(f'Number of frames: {self.nframes}', file=f)
            print(f'Apply stretch correction: {self.do_stretch_correction}', file=f)
            if self.do_stretch_correction:
                print(f'Stretch amplitude: {self.stretch_azimuth} %', file=f)
                print(f'Stretch azimuth: {self.stretch_amplitude} degrees', file=f)
                print(f'Stretch center x: {self.stretch_cent_x} pixel', file=f)
                print(f'Stretch center y: {self.stretch_cent_y} pixel', file=f)

        if self.enable_beam_tilt:
            img_conv = ImgConversion(buffer=self.buffer,
                                     osc_angle=stepsize,
                                     start_angle=self.start_angle-self.stepsize/2,
                                     end_angle=self.end_angle+self.stepsize/2,
                                     rotation_axis=self.rotation_axis,
                                     acquisition_time=self.exposure_time,
                                     flatfield=self.flatfield,
                                     pixelsize=self.pixelsize,
                                     physical_pixelsize=self.physical_pixelsize,
                                     wavelength=self.wavelength,
                                     do_stretch_correction=self.do_stretch_correction,
                                     stretch_amplitude=self.stretch_amplitude,
                                     stretch_azimuth=self.stretch_azimuth,
                                     stretch_cent_x=self.stretch_cent_x,
                                     stretch_cent_y=self.stretch_cent_y)
        else:
            img_conv = ImgConversion(buffer=self.buffer,
                                     osc_angle=stepsize,
                                     start_angle=self.start_angle,
                                     end_angle=self.end_angle,
                                     rotation_axis=self.rotation_axis,
                                     acquisition_time=self.exposure_time,
                                     flatfield=self.flatfield,
                                     pixelsize=self.pixelsize,
                                     physical_pixelsize=self.physical_pixelsize,
                                     wavelength=self.wavelength,
                                     do_stretch_correction=self.do_stretch_correction,
                                     stretch_amplitude=self.stretch_amplitude,
                                     stretch_azimuth=self.stretch_azimuth,
                                     stretch_cent_x=self.stretch_cent_x,
                                     stretch_cent_y=self.stretch_cent_y)

        print('Writing data files...')
        img_conv.threadpoolwriter(tiff_path=self.tiff_path,
                                  mrc_path=self.mrc_path,
                                  smv_path=self.smv_path,
                                  cbf_path=self.cbf_path,
                                  workers=8)

        print('Writing input files...')
        if write_dials:
            img_conv.to_dials(self.smv_path)
        if write_red:
            img_conv.write_ed3d(self.mrc_path)
        if write_xds or write_dials:
            img_conv.write_xds_inp(self.smv_path)
        if write_pets:
            img_conv.write_pets_inp(self.path)

        img_conv.write_beam_centers(self.path)

        print('Data Collection and Conversion Done.')
        print()

        return True


def main():
    from instamatic import TEMController
    ctrl = TEMController.initialize()

    import logging
    log = logging.getLogger(__name__)

    exposure_time = 0.5
    tilt_range = 10
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
    red_exp.start_collection(exposure_time=exposure_time, tilt_range=tilt_range, stepsize=stepsize)

    input('Press << Enter >> to start the experiment... ')

    while not input(f'\nPress << Enter >> to continue for another {tilt_range} degrees. [any key to finalize] '):
        red_exp.start_collection(exposure_time=exposure_time, tilt_range=tilt_range, stepsize=stepsize)

    red_exp.finalize()


if __name__ == '__main__':
    main()
