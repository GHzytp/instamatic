import datetime
import os
import time
from pathlib import Path

import numpy as np
from tqdm.auto import tqdm
from tkinter import messagebox
from skimage.registration import phase_cross_correlation

from instamatic.gui.modules import MODULES
from instamatic import config
from instamatic.formats import write_tiff, read_tiff_header, read_tiff
from instamatic.experiments import TOMO
from instamatic.image_utils import imgscale_target_shape

class Experiment:
    """Initialize data acquisition workflows for grid atlas.

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

        self.binsize = ctrl.cam.default_binsize
        self.software_binsize = config.settings.software_binsize
        self.beam_shift_matrix_C3 = np.array(config.calibration.beam_shift_matrix_C3).reshape(2, 2)
        try:
            self.tia_frame = [module for module in MODULES if module.name == 'tia'][0].frame
        except IndexError:
            self.tia_frame = None

    def obtain_image(self, exposure_time, align, align_roi, roi):
        if align_roi:
            img, h = self.ctrl.get_image(exposure_time, align=align, roi=roi)
        else:
            img, h = self.ctrl.get_image(exposure_time, align=align)
        return img, h

    def eliminate_backlash(self, ctrl):
        print('Attempting to eliminate backlash...')
        ctrl.stage.eliminate_backlash_xy()

    def collect_montage(self, exposure_time: float, align: bool, align_roi: bool, roi: list, blank_beam: bool, num_img: int, 
                        filepath: str, mag: int, image_scale: float, save_origin=True):
        gm = self.ctrl.grid_montage()
        current_pos = self.ctrl.stage.xy
        pos, px_center, stage_center = gm.setup(nx=num_img, ny=num_img, stage_shift=current_pos)
        if num_img > 1:
            gm.start(exposure_time=exposure_time, align=align, align_roi=align_roi, roi=roi, save=save_origin, blank_beam=blank_beam, pre_acquire=self.eliminate_backlash)
        elif num_img == 1:
            gm.start(exposure_time=exposure_time, align=align, align_roi=align_roi, roi=roi, save=save_origin, blank_beam=blank_beam, backlash=False)
        m = gm.to_montage()
        m.calculate_montage_coords()
        #m.optimize_montage_coords()
        stitched = m.stitch()
        h = {}
        h['is_montage'] = True
        h['center_pos'] = current_pos
        h['magnification'] = mag
        h['ImageResolution'] = stitched.shape
        h['stage_matrix'] = self.ctrl.get_stagematrix() # normalized need to multiple pixelsize
        h['ImagePixelsize'] = image_scale
        write_tiff(filepath, stitched, header=h)
        self.ctrl.stage.xy = current_pos

    def from_whole_grid_list(self, whole_grid, grid_dir, stop_event, sample_name: str, exposure_time: float, wait_interval: float, auto_height: bool,
                        blank_beam: bool, num_img: int, align: bool, align_roi: bool, roi: list, defocus: int, stage_tilt: float):
        # go to the position at grid square level, find the eucentric height, take a montage
        stop_event.clear()
        mag = self.ctrl.magnification.get()
        if mag != config.calibration.magnification_levels[1]:
            if messagebox.askokcancel("Continue", f"Change magnification to {config.calibration.magnification_levels[1]}?"):
                self.ctrl.magnification.set(config.calibration.magnification_levels[1])
            else:
                print(f'Must be in {config.calibration.magnification_levels[1]}x magnification.')
                return
        if num_img != 1:
            if not messagebox.askokcancel("Continue", f"The montage is composed of {num_img*num_img}. Is it right?"):
                return
        no_square_img_df = whole_grid[whole_grid['img_location'].isna()]
        num = len(whole_grid) - len(no_square_img_df)
        state = self.ctrl.mode.state
        if self.software_binsize is None:
            image_scale = config.calibration[state]['pixelsize'][mag] * self.binsize #nm->um
        else:
            image_scale = config.calibration[state]['pixelsize'][mag] * self.binsize * self.software_binsize

        for index, point in no_square_img_df.iterrows():
            self.ctrl.stage.xy = point['pos_x'], point['pos_y']
            if auto_height:
                tomo_exp = TOMO.Experiment(ctrl=self.ctrl, log=self.logger, flatfield=self.flatfield)
                tomo_exp.start_auto_eucentric_height(exposure_time=exposure_time, wait_interval=wait_interval, align=align, 
                                        align_roi=align_roi, roi=roi, defocus=defocus, stage_tilt=stage_tilt, blank_beam=blank_beam, ask=False)
                whole_grid.loc[index, 'pos_z'] = np.round(self.ctrl.stage.z)
            square_dir = grid_dir / f"Sqaure_{num+1}"
            square_dir.mkdir(exist_ok=True, parents=True)
            filepath = square_dir / f'square_{sample_name}.tiff'
            if num_img == 1:
                self.ctrl.stage.eliminate_backlash_xy()
            self.collect_montage(exposure_time, align, align_roi, roi, blank_beam, num_img, filepath, mag, image_scale, save_origin=False)
            whole_grid.loc[index, 'img_location'] = Path(square_dir.name) / f'square_{sample_name}.tiff'
            num += 1
            if stop_event.is_set():
                stop_event.clear()
                break

    def from_grid_square_list(self, whole_grid, grid_square, grid_dir, pred_z, stop_event, sample_name: str, blank_beam: bool,
                        exposure_time: float, wait_interval: float,  align: bool, align_roi: bool, roi: list, defocus: int,
                        mag_shift: bool, mag_shift_x: int, mag_shift_y: int):
        # go to the position at target level, predict the eucentric height, take an image. Shift exists between different magnification. 
        stop_event.clear()
        mag = self.ctrl.magnification.get()
        if mag != config.calibration.magnification_levels[2]:
            if messagebox.askokcancel("Continue", f"Change magnification to {config.calibration.magnification_levels[2]}?"):
                self.ctrl.magnification.set(config.calibration.magnification_levels[2])
            else:
                print(f'Must be in {config.calibration.magnification_levels[2]}x magnification.')
                return
        square_img_df = whole_grid[whole_grid['img_location'].notna()]
        current_defocus = self.ctrl.objfocus.value
        self.ctrl.objfocus.value = current_defocus + defocus
        for index1, grid in square_img_df.iterrows():
            grid_num = grid['grid']
            square_img = grid['img_location']
            no_target_img_df = grid_square[(grid_square['grid']==grid_num) & (grid_square['img_location'].isna())]
            num = len(grid_square[grid_square['grid']==grid_num]) - len(no_target_img_df)

            header = read_tiff_header(grid_dir/square_img)
            stage_matrix = np.array(header['stage_matrix'])
            mag_induced_stageshift = np.array([mag_shift_x, mag_shift_y]) @ stage_matrix

            for index2, point in no_target_img_df.iterrows(): 
                if mag_shift:
                    self.ctrl.stage.set_xy_with_backlash_correction(x=point['pos_x']+mag_induced_stageshift[0], y=point['pos_y']+mag_induced_stageshift[1])
                else:
                    self.ctrl.stage.set_xy_with_backlash_correction(x=point['pos_x'], y=point['pos_y'])
                    
                if blank_beam:
                    self.ctrl.beam.unblank(wait_interval)
                time.sleep(wait_interval)
                current_pos = self.ctrl.stage.xy
                arr, h = self.obtain_image(exposure_time, align, align_roi, roi)
                if blank_beam:
                    self.ctrl.beam.blank()
                h['is_montage'] = False
                h['center_pos'] = current_pos
                h['stage_matrix'] = self.ctrl.get_stagematrix() # normalized need to multiple pixelsize
                target_dir = grid_dir / Path(grid['img_location']).parent / f"Target_{num+1}"
                target_dir.mkdir(exist_ok=True, parents=True)
                filepath = target_dir / f'target_{sample_name}.tiff'
                write_tiff(filepath, arr, header=h)

                if mag_shift:
                    grid_square.loc[index2, 'pos_x'] = current_pos[0]
                    grid_square.loc[index2, 'pos_y'] = current_pos[1]
                if pred_z is None:
                    grid_square.loc[index2, 'pos_z'] = np.round(self.ctrl.stage.z)
                else:
                    grid_square.loc[index2, 'pos_z'] = np.round(pred_z(*current_pos))
                grid_square.loc[index2, 'img_location'] = Path(target_dir.parent.name) / Path(target_dir.name) / f'target_{sample_name}.tiff'
                num += 1
                if stop_event.is_set():
                    self.ctrl.objfocus.value = current_defocus
                    stop_event.clear()
                    return
        self.ctrl.objfocus.value = current_defocus

    def from_target_list(self, grid_square, target, grid_dir, stop_event, sample_name: str, blank_beam: bool, exposure_time: float, 
                        wait_interval: float, target_mode: str, align: bool, align_roi: bool, roi: list):
        # In diffraction mode, use beam shift to each crystal location and collection diffraction pattern.
        stop_event.clear()
        self.ctrl.beamshift.xy = (0, 0)
        if target_mode == 'TEM':
            if not messagebox.askokcancel("Continue", f"Please make sure the beam was in probe mode or C3 aperture was inserted. The default position of the probe is located at the center of the image."):
                return
        else:
            if not messagebox.askokcancel("Continue", f"Please make sure the microscope is in STEM mode and the beam is quasi-parallel. Please make sure the STEM image has the same dimension as target image."):
                return
            if self.tia_frame is None:
                print('TIA frame must present for auto acquisition at target level in STEM mode.')
                return
        state = self.ctrl.mode.state
        if state not in ('D', 'diff'):
            print(f'Please switch to diffraction mode.')
        #    return 
        cam_len = self.ctrl.magnification.get()
        target_img_df = grid_square[grid_square['img_location'].notna()]

        for index1, square in target_img_df.iterrows():
            grid_num = square['grid']
            square_num = square['square']
            target_img = square['img_location']
            target_dir = (grid_dir/target_img).parent
            header = read_tiff_header(grid_dir/target_img)
            target_img_shape = np.array(header['ImageResolution'])
            target_img_pixelsize = header['ImagePixelsize']
            target_pixel_center = target_img_shape / 2 # default position of the probe is the center of the image
            no_diff_targets = target[(target['grid']==grid_num) & (target['square']==square_num) & (target['diff_location'].isna())]
            num = len(target[(target['grid']==grid_num) & (target['square']==square_num)]) - len(no_diff_targets)
            drift = np.array([0, 0])
            if target_mode == 'STEM&HAADF':
                target_stem_img_arr, h_stem = self.tia_frame.acquire_image(save_file=target_dir/f'target_stem_{sample_name}.tiff')
                target_stem_img_arr = np.invert(target_stem_img_arr)
                target_img_arr, h = read_tiff(target_img)
                print(f"STEM: {h_stem['ImagePixelsize']}, TEM: {h['ImagePixelsize']}.")
                print(f"STEM size: {target_stem_img_arr.shape}, TEM size: {target_img_arr.shape}.")
                tem_stem_scale = h['ImagePixelsize'] / h_stem['ImagePixelsize']
                target_img_arr = imgscale_target_shape(target_img_arr, tem_stem_scale, target_stem_img_arr.shape)
                drift = phase_cross_correlation(target_stem_img_arr, target_img_arr) # numpy coordinate
            for index2, point in no_diff_targets.iterrows(): 
                # beam shift
                if target_mode == 'TEM':
                    beam_shift = target_img_pixelsize * (target_pixel_center - np.array((point['y'], point['x']))) @ self.beam_shift_matrix_C3
                    self.ctrl.beamshift.xy = beam_shift
                else:
                    target_coord =  np.array((point['y'], point['x'])) # numpy coordinate
                    target_coord = (target_coord - target_pixel_center) * tem_stem_scale + drift # numpy coordinate
                    target_coord[0] = - target_coord[0] # tia coordinate x left y up
                    target_coord_frac = target_coord / target_stem_img_arr.shape * 2  # tia coordinate x left y up
                    if abs(target_coord_frac[0]) <= 1 and  abs(target_coord_frac[1]) <= 1:
                        self.ctrl.sw.MoveBeam(*target_coord_frac)
                    else:
                        print(f"Point {index2} {target_coord} skipped due to boundary limitation of the STEM image.")
                        continue
                if blank_beam:
                    self.ctrl.beam.unblank(wait_interval)
                else:
                    time.sleep(wait_interval)
                arr, h = self.obtain_image(exposure_time, align, align_roi, roi)
                if blank_beam:
                    self.ctrl.beam.blank()
                filepath = target_dir / f'target_diff_{sample_name}_{num}.tiff'
                write_tiff(filepath, arr, header=h)
                target.loc[index2, 'diff_location'] = Path(target_dir.parent.name) / Path(target_dir.name) / f'target_diff_{sample_name}_{num}.tiff'
                num += 1
                if stop_event.is_set():
                    stop_event.clear()
                    if target_mode == 'TEM':
                        self.ctrl.beamshift.xy = (0, 0)
                    else:
                        self.ctrl.sw.MoveBeam(0, 0)
                    return
            if target_mode == 'TEM':
                self.ctrl.beamshift.xy = (0, 0)
            else:
                self.ctrl.sw.MoveBeam(0, 0)

    def design_acqusition_scheme(self):
        pass