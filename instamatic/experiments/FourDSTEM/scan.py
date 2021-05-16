import datetime
import os
import time
from pathlib import Path

import numpy as np
from tqdm.auto import tqdm
from tkinter import messagebox

from instamatic import config


class Scanner:
    """Scanning deflector over a line, rectangle, circle, precession, etc ...

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
        self.wavelength = config.microscope.wavelength  # angstrom

        self.beam_shift_matrix_C3 = np.array(config.calibration.beam_shift_matrix_C3).reshape(2, 2)
        self.beam_tilt_matrix_D = np.array(config.calibration.beam_tilt_matrix_D).reshape(2, 2)
        self.diffraction_shift_matrix = np.array(config.calibration.diffraction_shift_matrix).reshape(2, 2)
        self.stage_matrix_angle_D = np.array(config.calibration.stage_matrix_angle_D).reshape(2, 2)

    def beam_shift_scan_line(self, pixelsize: float, scan_from: tuple, scan_to: tuple, n: int, orig_pos: tuple, 
                            event_start, event_stop, event_sync_scan=None, event_sync_cam=None, func=None):
        """scan the beam along a line
        orig_pos: position of the beam on the image in pixel coordination of numpy convention (Y,X)
        """
        orig_beampos = self.ctrl.beamshift.xy
        pos0 = np.linspace(scan_from[0], scan_to[0], n)
        pos1 = np.linspace(scan_from[1], scan_to[1], n)
        pos = np.array([pos0, pos1]).T - orig_pos
        beampos = pixelsize * pos @ self.beam_shift_matrix_C3 + orig_beampos

        event_start.wait()

        if event_sync_cam is None and event_sync_scan is None:
            while not event_stop.set():
                for beam in beampos:
                    self.ctrl.beamshift.xy = beam
        elif event_sync_cam is not None and event_sync_scan is not None:
            while not event_stop.set():
                for beam in beampos:
                    event_sync_cam.wait()
                    event_sync_cam.clear()
                    self.ctrl.beamshift.xy = beam
                    event_sync_scan.set()
        else:
            print('Two sync events must be None not not None at the same time.')

        self.ctrl.beamshift.xy = orig_beampos

    def generate_scan_pattern(self, pixelsize, scan_pattern, scan_from, scan_to, nx, ny, orig_pos, orig_beampos):
        pos0 = np.linspace(scan_from[0], scan_to[0], nx)
        pos1 = np.linspace(scan_from[1], scan_to[1], ny)
        pos = np.array([pos0, pos1]).T - orig_pos
        beampos = pixelsize * pos @ self.beam_shift_matrix_C3 + orig_beampos

        if scan_pattern == 'XY scan':
            xv, yv = np.meshgrid(beampos[0], beampos[1])
        elif scan_pattern == 'YX scan':
            yv, xv = np.meshgrid(beampos[0], beampos[1])
        elif scan_pattern == 'XY snake scan':
            xv, yv = np.meshgrid(beampos[0], beampos[1])
            xv[1::2, :] = xv[1::2, ::-1]
        elif scan_pattern == 'YX snake scan':
            yv, xv = np.meshgrid(beampos[0], beampos[1])
            yv[1::2, :] = yv[1::2, ::-1]
        elif scan_pattern == 'Spiral scan':
            raise NotImplementedError('Spiral scan did not implemented.')
        return xv, yv

    def beam_shift_scan_rectangle(self, pixelsize: float, scan_pattern: str, scan_from: tuple, scan_to: tuple, nx: int, ny: int, 
                                orig_pos: tuple, event_start, event_stop, event_sync_scan=None, event_sync_cam=None, func=None):
        """scan the beam within a rectangle
        orig_pos: position of the beam on the image in pixel coordination of numpy convention (Y,X)
        """
        orig_beampos = self.ctrl.beamshift.xy

        beampos_x, beampos_y = self.generate_scan_pattern(pixelsize, scan_from, scan_to, nx, ny, orig_pos, orig_beampos)
        shape = beampos_x.shape

        event_start.wait()

        if event_sync_cam is None and event_sync_scan is None:
            while not event_stop.is_set():
                for i in range(shape[0]):
                    for j in range(shape[1]):
                        self.ctrl.beamshift.xy = (beampos_x[i, j], beampos_y[i, j])
        elif event_sync_cam is not None and event_sync_scan is not None:
            while not event_stop.is_set():
                for i in range(shape[0]):
                    for j in range(shape[1]):
                        event_sync_cam.wait()
                        event_sync_cam.clear()
                        self.ctrl.beamshift.xy = (beampos_x[i, j], beampos_y[i, j])
                        event_sync_scan.set()
        else:
            print('Two sync events must be None not not None at the same time.')

        self.ctrl.beamshift.xy = orig_beampos

    def beam_precession(self, angle: float, num_sampling: int, event_start, event_stop, event_sync_tilt=None, event_sync_cam=None, func=None):
        # beam tilt in a circular motion and descan it
        theta = np.arange(0, 360, num_sampling)
        tilt_x = angle * cos(theta)
        tilt_y = angle * sin(theta)
        beamtilt_list = - 2 / self.wavelength * np.sin(np.pi/180*np.array([tilt_x, tilt_y]).T) @ np.linalg.inv(self.stage_matrix_angle_D) @ self.beam_tilt_matrix_D
        diffraction_shift_list = - beamtilt_list @ np.linalg.inv(self.beam_tilt_matrix_D) @ self.diffraction_shift_matrix

        event_start.wait()

        if event_sync_cam is None and event_sync_tilt is None:
            while not event_stop.is_set():
                for beamtilt, diffraction_shift in zip(beamtilt_list, diffraction_shift_list):
                    self.ctrl.beamtilt.xy = beamtilt
                    self.ctrl.diffshift.xy = diffraction_shift

        elif event_sync_cam is not None and event_sync_tilt is not None:
            while not event_stop.is_set():
                for beamtilt, diffraction_shift in zip(beamtilt_list, diffraction_shift_list):
                    event_sync_cam.wait()
                    event_sync_cam.clear()
                    self.ctrl.beamtilt.xy = beamtilt
                    self.ctrl.diffshift.xy = diffraction_shift
                    event_sync_tilt.set()
        else:
            print('Two sync events must be None not not None at the same time.')

    def beam_precession_scan_line(self, angle: float, num_sampling: int, pixelsize: float, scan_from: tuple, scan_to: tuple, n: int, 
                                orig_pos: tuple, event_start, event_stop, event_sync_scan, event_sync_tilt=None, event_sync_cam=None, func=None):
        # precession at one spot and then move, along a line.
        orig_beampos = self.ctrl.beamshift.xy
        pos0 = np.linspace(scan_from[0], scan_to[0], n)
        pos1 = np.linspace(scan_from[1], scan_to[1], n)
        pos = np.array([pos0, pos1]).T - orig_pos
        beampos = pixelsize * pos @ self.beam_shift_matrix_C3 + orig_beampos

        theta = np.arange(0, 360, num_sampling)
        tilt_x = angle * cos(theta)
        tilt_y = angle * sin(theta)
        beamtilt_list = - 2 / self.wavelength * np.sin(np.pi/180*np.array([tilt_x, tilt_y]).T) @ np.linalg.inv(self.stage_matrix_angle_D) @ self.beam_tilt_matrix_D
        diffraction_shift_list = - beamtilt_list @ np.linalg.inv(self.beam_tilt_matrix_D) @ self.diffraction_shift_matrix

        event_start.wait()

        if event_sync_cam is None and event_sync_tilt is None:
            while not event_stop.is_set():
                for beam in beampos:
                    self.ctrl.beamshift.xy = beam
                    event_sync_scan.set()
                    for beamtilt, diffraction_shift in zip(beamtilt_list, diffraction_shift_list):
                        self.ctrl.beamtilt.xy = beamtilt
                        self.ctrl.diffshift.xy = diffraction_shift

        elif event_sync_cam is not None and event_sync_tilt is not None:
            while not event_stop.is_set():
                for beam in beampos:
                    self.ctrl.beamshift.xy = beam
                    event_sync_scan.set()
                    for beamtilt, diffraction_shift in zip(beamtilt_list, diffraction_shift_list):
                        event_sync_cam.wait()
                        event_sync_cam.clear()
                        self.ctrl.beamtilt.xy = beamtilt
                        self.ctrl.diffshift.xy = diffraction_shift
                        event_sync_tilt.set()
        else:
            print('Two sync events must be None not not None at the same time.')

    def beam_precession_scan_rectangle(self, angle: float, num_sampling: int, pixelsize: float, scan_pattern: str, scan_from: tuple, scan_to: tuple, nx: int, ny: int,
                                orig_pos: tuple, event_start, event_stop, event_sync_scan, event_sync_tilt=None, event_sync_cam=None, func=None):
        # precession at one spot and then move, across a rectangle area.
        orig_beampos = self.ctrl.beamshift.xy
        beampos_x, beampos_y = self.generate_scan_pattern(pixelsize, scan_from, scan_to, nx, ny, orig_pos, orig_beampos)
        shape = beampos_x.shape

        theta = np.arange(0, 360, num_sampling)
        tilt_x = angle * cos(theta)
        tilt_y = angle * sin(theta)
        beamtilt_list = - 2 / self.wavelength * np.sin(np.pi/180*np.array([tilt_x, tilt_y]).T) @ np.linalg.inv(self.stage_matrix_angle_D) @ self.beam_tilt_matrix_D
        diffraction_shift_list = - beamtilt_list @ np.linalg.inv(self.beam_tilt_matrix_D) @ self.diffraction_shift_matrix

        event_start.wait()

        if event_sync_cam is None and event_sync_tilt is None:
            while not event_stop.is_set():
                for i in range(shape[0]):
                    for j in range(shape[1]):
                        self.ctrl.beamshift.xy = (beampos_x[i, j], beampos_y[i, j])
                        event_sync_scan.set()
                        for beamtilt, diffraction_shift in zip(beamtilt_list, diffraction_shift_list):
                            self.ctrl.beamtilt.xy = beamtilt
                            self.ctrl.diffshift.xy = diffraction_shift

        elif event_sync_cam is not None and event_sync_tilt is not None:
            while not event_stop.is_set():
                for i in range(shape[0]):
                    for j in range(shape[1]):
                        self.ctrl.beamshift.xy = (beampos_x[i, j], beampos_y[i, j])
                        event_sync_scan.set()
                        for beamtilt, diffraction_shift in zip(beamtilt_list, diffraction_shift_list):
                            event_sync_cam.wait()
                            event_sync_cam.clear()
                            self.ctrl.beamtilt.xy = beamtilt
                            self.ctrl.diffshift.xy = diffraction_shift
                            event_sync_tilt.set()
        else:
            print('Two sync events must be None not not None at the same time.')
