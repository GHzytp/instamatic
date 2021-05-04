import datetime
import os
import time
from pathlib import Path

import numpy as np
from tqdm.auto import tqdm
from tkinter import messagebox

from instamatic import config


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

    def obtain_image(self, exposure_time, align, align_roi, roi):
        if align_roi:
            img, h = self.ctrl.get_image(exposure_time, align=align, roi=roi)
        else:
            img, h = self.ctrl.get_image(exposure_time, align=align)
        return img, h

    def from_whole_grid_list(self, exposure_time: float, wait_interval: float, align: bool, align_roi: bool, roi: list):
        # go to the position at grid square level, find the eucentric height, take an image
        pass

    def from_grid_square_list(self, exposure_time: float, wait_interval: float, align: bool, align_roi: bool, roi: list):
        # go to the position at target level, predict the eucentric height, take an image
        pass 

    def from_target_list(self, exposure_time: float, wait_interval: float, align: bool, align_roi: bool, roi: list):
        # In diffraction mode, use beam shift to each crystal location and collection diffraction pattern.
        pass 