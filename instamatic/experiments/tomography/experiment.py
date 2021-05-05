import datetime
import os
import time
import threading
from pathlib import Path

import numpy as np
from skimage.registration import phase_cross_correlation
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
from instamatic.image_utils import translate_image


class Experiment:
    """Initialize stepwise rotation electron diffraction experiment.

    ctrl:
        Instance of instamatic.TEMController.TEMController
    path:
        `str` or `pathlib.Path` object giving the path to save data at
    log:
        Instance of `logging.Logger`
    flatfield:
        Path to flatfield correction image
    """

    def __init__(self, ctrl, path: str = None, log=None, flatfield=None):
        super().__init__()
        self.ctrl = ctrl
        try:
            self.path = Path(path)
        except:
            self.path = Path('.')
        self.logger = log
        self.flatfield = flatfield

        self.offset = 0
        self.current_angle = None
        self.buffer = []

        self.img_ref = None
        self.num_beam_tilt = 0
        self.imageshift2matrix = np.array(config.calibration.image_shift2_matrix).reshape(2, 2)
        self.beam_tilt_matrix_D = np.array(config.calibration.beam_tilt_matrix_D).reshape(2, 2)
        self.beam_tilt_matrix_img = np.array(config.calibration.beam_tilt_matrix_img).reshape(2, 2)
        self.stage_matrix_angle = np.array(config.calibration.stage_matrix_angle).reshape(2, 2)
        self.stage_matrix_angle_D = np.array(config.calibration.stage_matrix_angle_D).reshape(2, 2)

        self.binsize = ctrl.cam.default_binsize
        self.rotation_axis = config.calibration.camera_rotation_vs_stage_xy
        self.wavelength = config.microscope.wavelength  # angstrom

    def obtain_image(self, exposure_time, align, align_roi, roi):
        if align_roi:
            img, h = self.ctrl.get_image(exposure_time, align=align, roi=roi)
        else:
            img, h = self.ctrl.get_image(exposure_time, align=align)
        return img, h

    def start_collection(self, exposure_time: float, tilt_range: float, stepsize: float, wait_interval: float, 
                        align: bool, align_roi: bool, roi: list):
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
        ctrl = self.ctrl
        image_mode = ctrl.mode.get()
        if image_mode in ('diff', 'D'):
            raise RuntimeError('Must in imaging mode to perform tomogrpahy.')

        self.spotsize = self.ctrl.spotsize
        self.now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.logger.info(f'Data recording started at: {self.now}')
        self.logger.info(f'Exposure time: {exposure_time} s, Tilt range: {tilt_range}, step size: {stepsize}')

        if stepsize < 0:
            tilt_range = -abs(tilt_range)
        else:
            tilt_range = abs(tilt_range)

        if self.current_angle is None:
            self.start_angle = start_angle = ctrl.stage.a
            ctrl.stage.eliminate_backlash_a(target_angle=start_angle+tilt_range)
        else:
            start_angle = self.current_angle + stepsize

        tilt_positions = np.arange(start_angle + stepsize, start_angle + tilt_range + stepsize, stepsize)
        print(f'\nStart_angle: {start_angle:.3f}')

        for i, angle in enumerate(tqdm(tilt_positions)):
            time.sleep(wait_interval)
            j = i + self.offset
            img, h = self.obtain_image(exposure_time, align, align_roi, roi)
            ctrl.stage.a = angle
            self.buffer.append((j, img, h))

        self.offset += len(tilt_positions)
        self.nframes = j + 1

        self.end_angle = end_angle = ctrl.stage.a

        self.magnification = int(self.ctrl.magnification.get())
        self.stepsize = stepsize
        self.exposure_time = exposure_time

        with open(self.path / 'summary.txt', 'a') as f:
            print(f'{self.now}: Data collected from {start_angle:.2f} degree to {end_angle:.2f} degree in {len(tilt_positions)} frames.', file=f)
            print(f'Data collected from {start_angle:.2f} degree to {end_angle:.2f} degree in {len(tilt_positions)} frames.')

        self.logger.info('Data collected from {start_angle:.2f} degree to {end_angle:.2f} degree (magnification: {magnification} mm).')

        self.current_angle = angle
        print(f'Done, current angle = {self.current_angle:.2f} degrees')

    def get_current_defocus(self, exposure_time: float, wait_interval: float, align: bool, align_roi: bool, 
                        roi: list, cs: float, defocus: int, beam_tilt: float):
        self.ctrl.beamtilt.xy = (0, 0)
        matrix = np.linalg.inv(self.stage_matrix_angle_D) @ self.beam_tilt_matrix_D
        beamtilt = 2 / self.wavelength * np.sin(np.pi/180*np.array([beam_tilt, 0])) @ matrix
        # Applying defocus
        self.ctrl.objfocus.set(defocus)
        # Acquiring image at negative beam tilt
        self.ctrl.beamtilt.xy = -beamtilt
        time.sleep(wait_interval)
        img_negative_1, h = self.obtain_image(exposure_time, align, align_roi, roi)
        # Acquiring image at positive beam tilt
        self.ctrl.beamtilt.xy = beamtilt
        time.sleep(wait_interval)
        img_positive, h = self.obtain_image(exposure_time, align, align_roi, roi)
        # Acquiring image at negative beam tilt
        self.ctrl.beamtilt.xy = -beamtilt
        time.sleep(wait_interval)
        img_negative_2, h = self.obtain_image(exposure_time, align, align_roi, roi)
        # Measuring shift...
        shift_focus = self.calc_shift_images(img_negative_1, img_positive, align_roi, roi)
        shift_focus = shift_focus * h['ImagePixelsize']
        print(f"Beam tilt {-beam_tilt} -> {beam_tilt} shift: {shift_focus} nm")
        shift_drift = self.calc_shift_images(img_negative_1, img_negative_2, align_roi, roi)
        print(f"Drift {-beam_tilt} -> {-beam_tilt}: {np.linalg.norm(shift_drift)} nm")
        # Measured defocus
        direction =  self.calc_direction(shift_focus, beam_tilt, matrix)
        # Actual defocus is the opposite of the direction to 0 defocus
        measured_defocus = - direction * (np.linalg.norm(shift_focus) / 2 / np.tan(np.deg2rad(beam_tilt)) - cs * 1e6 * np.tan(np.deg2rad(beam_tilt))**2)
        print(f'Meansured defocus: {measured_defocus} nm')
        self.ctrl.beamtilt.xy = (0, 0)

        return measured_defocus

    def start_auto_focus(self, exposure_time: float, wait_interval: float, align: bool, align_roi: bool, 
                        roi: list, cs: float, defocus: int, beam_tilt: float):
        """Auto focus method used in FEI TEM Tomography. D = 2Mb(f+cs*b^2)
        Formula from https://www.sciencedirect.com/science/article/abs/pii/030439918790146X
        """
        image_mode = self.ctrl.mode.get()
        if image_mode in ('diff', 'D'):
            raise RuntimeError('Must in imaging mode to perform auto focus.')

        current_focus = self.ctrl.objfocus.value
        target_focus = current_focus + defocus
        delta_defocus_corase = defocus - self.get_current_defocus(exposure_time=exposure_time, wait_interval=wait_interval, align=align, 
                            align_roi=align_roi, roi=roi, cs=cs, defocus=target_focus, beam_tilt=beam_tilt)

        if messagebox.askokcancel("Continue", f"Change of focus is {delta_defocus_corase}. Change the defocus and continue?"):
            target_focus = target_focus + delta_defocus_corase
            delta_defocus_fine = defocus - self.get_current_defocus(exposure_time=exposure_time, wait_interval=wait_interval,  
                                align=align, align_roi=align_roi, roi=roi, cs=cs, defocus=target_focus, beam_tilt=beam_tilt)
            print(f'Change of focus is {delta_defocus_fine}.')
            self.ctrl.objfocus.set(target_focus+delta_defocus_fine-defocus)
        else:
            self.ctrl.objfocus.set(current_focus)

    def calc_direction(self, shift, tilt, matrix_angle):
        # Calculate the direction to obtain 0 defocus (in focus) results. 
        # For defocus adjustment, the actual defocus value needs to be calculated, so minus is added
        # shift calculated from images obtained at -tilt to +tilt, shift consistent with numpy convention (Y, X)
        # pos = shift @ matrix => shift = pos @ inv(matrix)
        # The coodination system of shift will not change, while the coodination system of pos will change.
        arr = np.array([tilt, 0]) @ np.linalg.inv(matrix_angle)
        if tilt > 0:
            if shift @ arr < 0:
                direction = -1
            elif shift @ arr > 0:
                direction = 1
        elif tilt < 0:
            if shift @ arr < 0:
                direction = 1
            elif shift @ arr > 0:
                direction = -1
        return direction

    def start_auto_eucentric_height(self, exposure_time: float, wait_interval: float, align: bool, align_roi: bool, 
                        roi: list, defocus: int, stage_tilt: float):
        """Find eucentric height automatically using the method in FEI TEM Tomography"""
        image_mode = self.ctrl.mode.get()
        if image_mode in ('diff', 'D'):
            raise RuntimeError('Must in imaging mode to perform auto eucentric height.')

        current_defocus = self.ctrl.objfocus.value
        self.ctrl.objfocus.set(current_defocus+defocus)
        # Acquiring image at 0°
        self.ctrl.stage.a = 0
        self.ctrl.stage.eliminate_backlash_a(target_angle=-stage_tilt)
        time.sleep(wait_interval)
        img_0_1, h = self.obtain_image(exposure_time, align, align_roi, roi)
        # Acquiring image at tilt: stage_tilt
        self.ctrl.stage.a = -stage_tilt
        time.sleep(wait_interval)
        img_tilt_1, h = self.obtain_image(exposure_time, align, align_roi, roi)
        # Measuring shift...
        shift_tilt = self.calc_shift_images(img_tilt_1, img_0_1, align_roi, roi)
        shift_tilt = shift_tilt * h['ImagePixelsize']
        print(f"Stage tilt {-stage_tilt} -> 0 shift: {shift_tilt} nm")
        direction = self.calc_direction(shift_tilt, stage_tilt, self.stage_matrix_angle)
        delta_z = direction * np.linalg.norm(shift_tilt) / np.tan(np.deg2rad(stage_tilt))
        print(f'Meansured height change: {delta_z} nm')
        # Moving z
        if messagebox.askokcancel("Continue", f"Change of z height is {delta_z}. Move stage and continue?"):
            z = self.ctrl.stage.z
            self.ctrl.stage.z = z + delta_z
            # Acquiring image at tilt: -3*stage_tilt
            self.ctrl.stage.a = - stage_tilt * 3
            self.ctrl.stage.eliminate_backlash_a(target_angle=stage_tilt * 3)
            time.sleep(wait_interval)
            img_tilt_2_minus, h = self.obtain_image(exposure_time, align, align_roi, roi)
            # Acquiring image at tilt: 3*stage_tilt
            self.ctrl.stage.a = stage_tilt * 3
            time.sleep(wait_interval)
            img_tilt_2_plus, h = self.obtain_image(exposure_time, align, align_roi, roi)
            # Measuring shift...
            shift_tilt_3 = self.calc_shift_images(img_tilt_2_minus, img_tilt_2_plus, align_roi, roi)
            shift_tilt_3 = shift_tilt_3 * h['ImagePixelsize']
            print(f"Stage tilt {-stage_tilt*3} -> {stage_tilt*3} shift: {shift_tilt_3} nm")
            direction = self.calc_direction(shift_tilt_3, stage_tilt, self.stage_matrix_angle)
            delta_z = direction * np.linalg.norm(shift_tilt_3) / 2 / np.tan(np.deg2rad(stage_tilt*3))
            print(f'Meansured height change: {delta_z} nm')
            # Moving z
            z = self.ctrl.stage.z
            self.ctrl.stage.z = z + delta_z
            self.ctrl.stage.a = 0
        self.ctrl.objfocus.set(current_defocus)


    def start_auto_collection_stage_tilt(self, exposure_time: float, end_angle: float, stepsize: float, wait_interval: float, 
                        align: bool, align_roi: bool, roi: list, continue_event: threading.Event, stop_event: threading.Event, cs: float,
                        defocus: int, beam_tilt: float, watershed_angle: float, high_angle_interval: int, low_angle_interval: int):
        """Start automatic data collection from current angle to end angle with steps given by `stepsize`. 
        Auto tracking: how many image-beam shift (beampos) needed for achieve certain distance (shift) in nm, beampos = shift*r
        During the tilt series acquisition, the height of the sample will not change. Focus was adjusted by adjusting objective defocus
        exposure_time:
            Exposure time for each image in seconds
        stepsize:
            Step size for the angle in degrees, controls the direction and can be positive or negative
        """
        ctrl = self.ctrl
        image_mode = ctrl.mode.get()
        if image_mode in ('diff', 'D'):
            raise RuntimeError('Must in imaging mode to perform automatic tomogrpahy.')

        stage_matrix = ctrl.get_stagematrix()
        self.spotsize = self.ctrl.spotsize
        self.now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.logger.info(f'Data recording started at: {self.now}')
        self.logger.info(f'Exposure time: {exposure_time} s, End angle: {end_angle}, step size: {stepsize}')
        
        self.start_angle = start_angle = ctrl.stage.a
        self.ctrl.imageshift2.set(0, 0)

        if stepsize < 0:
            if end_angle >= start_angle:
                return 0
        elif stepsize == 0:
            return 0
        else:
            if end_angle <= start_angle:
                return 0

        ctrl.stage.eliminate_backlash_a(target_angle=end_angle)
        beam_shift = np.array([0.0, 0.0])
        continue_event.set()
        stop_event.clear()

        if not messagebox.askokcancel("Continue", "Check target position and continue"):
            return False

        current_defocus = self.ctrl.objfocus.value
        self.ctrl.objfocus.set(current_defocus+defocus)

        tilt_positions = np.arange(start_angle, end_angle, stepsize)
        print(f'\nStart_angle: {start_angle:.3f}')

        for i, angle in enumerate(tqdm(tilt_positions), 1):
            continue_event.wait()
            if stop_event.is_set():
                break

            ctrl.stage.a = angle          
            time.sleep(wait_interval)
            # adjust defocus
            if np.abs(angle) > watershed_angle and (i + 1) % high_angle_interval == 0:
                delta_defocus = defocus - self.get_current_defocus(exposure_time=exposure_time, wait_interval=wait_interval, align=align, 
                            align_roi=align_roi, roi=roi, cs=cs, defocus=current_defocus+defocus, beam_tilt=beam_tilt)
                current_defocus = current_defocus + delta_defocus
                time.sleep(wait_interval)
            elif np.abs(angle) <= watershed_angle and (i + 1) % low_angle_interval == 0:
                delta_defocus = defocus - self.get_current_defocus(exposure_time=exposure_time, wait_interval=wait_interval, align=align, 
                            align_roi=align_roi, roi=roi, cs=cs, defocus=current_defocus+defocus, beam_tilt=beam_tilt)
                current_defocus = current_defocus + delta_defocus
                time.sleep(wait_interval)
            
            img, h = self.obtain_image(exposure_time, align, align_roi, roi)

            if i == 1:
                img_ref = img

            # suppose eccentric height is near 0 degree
            
            shift = self.calc_shift_images(img_ref, img, align_roi, roi) # down y+, right x+
            print(f'Relative shift to img_ref: {shift}')
            shift = shift * h['ImagePixelsize'] @ self.imageshift2matrix
            beam_shift -= shift
            
            if np.linalg.norm(beam_shift) >= 2000:
                x,y = self.ctrl.stage.xy
                stage_shift = beam_shift / h['ImagePixelsize'] @ np.linalg.inv(self.imageshift2matrix) @ stage_matrix
                print(stage_matrix)
                print(f'Beam shift: {beam_shift}; Stage shift: {stage_shift}')
                self.ctrl.stage.set(x=x+stage_shift[0], y=y+stage_shift[1]) # almost up y+, right x+
                beam_shift = np.array([0.0, 0.0])

            self.ctrl.imageshift2.set(beam_shift[0], beam_shift[1]) # almost up y+, right x+

            self.buffer.append((i, img, h))

        if stop_event.is_set():
            self.nframes = i
        else:
            self.nframes = i + 1

        self.end_angle = end_angle = ctrl.stage.a
        self.magnification = int(ctrl.magnification.value)
        self.stepsize = stepsize
        self.exposure_time = exposure_time
        self.ctrl.imageshift2.set(0, 0)

        return True

    def start_auto_collection_stage_beam_tilt(self, exposure_time: float, end_angle: float, stepsize: float, wait_interval: float, 
                        align: bool, align_roi: bool, roi: list, continue_event: threading.Event, stop_event: threading.Event, num_beam_tilt: int,
                        cs: float, defocus: int, watershed_angle: float, high_angle_interval: int, low_angle_interval: int):
        """Start automatic data collection from current angle to end angle combined with stage tilt and beam tilt.
        Auto tracking: how many image-beam shift (beampos) needed for achieve certain distance (shift) in nm, beampos = shift*r
        exposure_time:
            Exposure time for each image in seconds
        stepsize:
            Step size for the angle in degrees, controls the direction and can be positive or negative
        """
        ctrl = self.ctrl
        image_mode = ctrl.mode.get()
        if image_mode in ('diff', 'D'):
            raise RuntimeError('Must in imaging mode to perform automatic tomogrpahy.')

        stage_matrix = ctrl.get_stagematrix()
        beamtilt_matrix = np.linalg.inv(self.stage_matrix_angle_D) @ self.beam_tilt_matrix_D
        self.spotsize = self.ctrl.spotsize
        self.now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.logger.info(f'Data recording started at: {self.now}')
        self.logger.info(f'Exposure time: {exposure_time} s, End angle: {end_angle}, step size: {stepsize}')

        counter = 1
        self.num_beam_tilt = num_beam_tilt
        if self.num_beam_tilt % 2 != 0:
            raise RuntimeError('The number of beam tilt must be a even number.')
        beam_tilt_angle_list = []
        for i in range(self.num_beam_tilt):
            if i < self.num_beam_tilt // 2:
                beam_tilt_angle_list.append((i - self.num_beam_tilt // 2) * stepsize)
            else:
                beam_tilt_angle_list.append((i - self.num_beam_tilt // 2 + 1) * stepsize)
        

        self.start_angle = start_angle = ctrl.stage.a

        if stepsize < 0:
            if end_angle >= start_angle:
                return 0
        elif stepsize == 0:
            return 0
        else:
            if end_angle <= start_angle:
                return 0

        ctrl.stage.eliminate_backlash_a(target_angle=end_angle)
        beam_shift = np.array([0.0, 0.0])
        self.ctrl.imageshift2.set(0, 0)
        img_tilted = []
        continue_event.set()
        stop_event.clear()

        if not messagebox.askokcancel("Continue", "Check target position and continue"):
            return False

        tilt_positions = np.arange(start_angle, end_angle, stepsize * (self.num_beam_tilt+1))
        print(f'\nStart_angle: {start_angle - (self.num_beam_tilt/2) * stepsize:.3f}')

        current_defocus = self.ctrl.objfocus.value
        self.ctrl.objfocus.set(current_defocus+defocus)

        for i, angle in enumerate(tqdm(tilt_positions), 1):
            continue_event.wait()
            if stop_event.is_set():
                break

            ctrl.stage.a = angle 
            self.ctrl.beamtilt.set(x=0, y=0)         
            time.sleep(wait_interval)
            img_0, h = self.obtain_image(exposure_time, align, align_roi, roi)

            for beam_tilt_angle in beam_tilt_angle_list:
                beam_tilt = 2 / self.wavelength * np.sin(np.pi/180*np.array([beam_tilt_angle, 0])) @ beamtilt_matrix
                self.ctrl.beamtilt.set(x=beam_tilt[0], y=beam_tilt[1])
                time.sleep(wait_interval)
                img, h = self.obtain_image(exposure_time, align, align_roi, roi)
                img_tilted.append(img)
                
            if i == 1:
                img_ref = img_0

            for j in range(self.num_beam_tilt + 1):
                if j < self.num_beam_tilt // 2:
                    self.buffer.append((counter, img_tilted[j], h))
                elif j == self.num_beam_tilt // 2:
                    self.buffer.append((counter, img_0, h))
                elif j > self.num_beam_tilt // 2:
                    self.buffer.append((counter, img_tilted[j-1], h))
                counter += 1

            # suppose eccentric height is near 0 degree, adjust beam position or stage position
            shift = self.calc_shift_images(img_ref, img_0, align_roi, roi) # down y+, right x+
            shift = shift / h['ImagePixelsize'] @ self.imageshift2matrix
            beam_shift -= shift
            
            if np.linalg.norm(beam_shift) >= 1000:
                x, y = self.ctrl.stage.xy
                stage_shift = beam_shift @ np.linalg.inv(self.imageshift2matrix) @ stage_matrix
                self.ctrl.stage.set(x=x+stage_shift[0], y=y+stage_shift[1]) # almost up y+, right x+
                beam_shift = np.array([0.0, 0.0])

            self.ctrl.imageshift2.set(beam_shift[0], beam_shift[1]) # almost up y+, right x+

            # adjust defocus
            shift_focus = self.calc_shift_images(img_tilted[0], img_tilted[-1], align_roi, roi)
            shift_focus = shift_focus * h['ImagePixelsize']
            print(f"Beam tilt {-self.num_beam_tilt // 2 * stepsize} -> {self.num_beam_tilt // 2 * stepsize} shift: {shift_focus} nm")
            # Measured defocus
            direction =  self.calc_direction(shift_focus, self.num_beam_tilt//2*stepsize, beamtilt_matrix)
            delta_defocus = defocus + direction * np.linalg.norm(shift_focus) / 2 / np.tan(np.deg2rad(self.num_beam_tilt // 2 * stepsize)) - cs * 1e6 * np.tan(np.deg2rad(self.num_beam_tilt // 2 * stepsize))**2
            print(f'Change defocus: {delta_defocus} nm')
            current_defocus = current_defocus + delta_defocus
            self.ctrl.objfocus.set(current_defocus+defocus)
            img_tilted = []

        if stop_event.is_set():
            self.nframes = i * (self.num_beam_tilt + 1)
        else:
            self.nframes = (i + 1) * (self.num_beam_tilt + 1)

        self.end_angle = end_angle = ctrl.stage.a
        self.magnification = int(ctrl.magnification.value)
        self.stepsize = stepsize
        self.exposure_time = exposure_time
        self.ctrl.imageshift2.set(0, 0)

        return True

    def focus_image(self, img):
        """Return the distance of sample movement between the beam tilt"""
        return 0, 0

    def calc_shift_images(self, img_ref, img, align_roi, roi):
        """Return the distance between the collected image and the reference image. 1024*1024 image will take 124ms. So subsampling to 512*512. Takes around 23ms"""
        if align_roi:
            shift, error, phasediff = phase_cross_correlation(img_ref[roi[0][0]:roi[1][0], roi[0][1]:roi[1][1]], img[roi[0][0]:roi[1][0], roi[0][1]:roi[1][1]], upsample_factor=10)
        else:
            shift, error, phasediff = phase_cross_correlation(img_ref, img, upsample_factor=10)
        return shift 

    def finalize(self, write_tiff=True, write_mrc=True):
        """Finalize data collection after `self.start_collection` has been run.
        Write data in `self.buffer` to path given by `self.path`.
        """
        if not hasattr(self, 'end_angle'):
            self.end_angle = self.ctrl.stage.a

        software_binsize = config.settings.software_binsize
        if software_binsize is None:
            self.pixelsize = config.calibration[self.ctrl.mode.state]['pixelsize'][self.magnification] * self.binsize 
            self.physical_pixelsize = config.camera.physical_pixelsize * self.binsize 
        else:
            self.pixelsize = config.calibration[self.ctrl.mode.state]['pixelsize'][self.magnification] * self.binsize * software_binsize 
            self.physical_pixelsize = config.camera.physical_pixelsize * self.binsize * software_binsize 

        self.logger.info(f'Data saving path: {self.path}')

        self.tiff_path = self.path / 'tiff' if write_tiff else None
        self.mrc_path = self.path / 'mrc' if write_mrc else None

        with open(self.path / 'summary.txt', 'a') as f:
            print(f'Rotation range: {self.end_angle-self.start_angle+2*(self.num_beam_tilt/2)*self.stepsize:.2f} degrees', file=f)
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
                                 osc_angle=abs(self.stepsize),
                                 start_angle=self.start_angle-(self.num_beam_tilt/2)*self.stepsize,
                                 end_angle=self.end_angle+(self.num_beam_tilt/2)*self.stepsize,
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

        if self.mrc_path is not None:
            print('Writing input files...')
            img_conv.write_ed3d(self.mrc_path)

        print('Data Collection and Conversion Done.')
        print()

        self.num_beam_tilt = 0

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
