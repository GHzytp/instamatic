import threading
import time
import pprint
import yaml
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import *
from tkinter.ttk import *

import mrcfile
import numpy as np
import pandas as pd

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.patches import Circle

from .base_module import BaseModule
from instamatic import config
from instamatic import TEMController
from instamatic.processing import apply_stretch_correction
from instamatic.tools import find_beam_center, find_beam_center_with_beamstop
from instamatic.utils.peakfinders2d import subtract_background_median, find_peaks_regionprops, im_reconstruct
from instamatic.utils.indexer import Indexer, get_indices
from instamatic.utils.projector import Projector
from instamatic.formats import read_tiff, read_hdf5, read_cbf
from instamatic.formats.mrc import read_image as read_mrc
from instamatic.formats.adscimage import read_adsc
from instamatic.formats.dm import dmReader
from instamatic.utils.widgets import Hoverbox, Spinbox, popupWindow


class IndexFrame(LabelFrame):
    """GUI panel for indexing diffraction patterns and powder patterns. In addition, calibrate the stretching of the powder ring."""

    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Indexing diffraction patterns and powder patterns')
        self.parent = parent
        self.ctrl = TEMController.get_instance()
        self.wavelength = config.microscope.wavelength
        self.img_path = None
        self.img = None
        self.img_center = None
        self.stretched_img = None
        self.img_find_peaks = None
        self.props_collection = None
        self.background_removed_img = None
        self.use_beamstop = False
        self.projector = None
        self.orientation_collection = None
        self.refined_orientation = None
        self.hkl_list_on_canvas = []
        self.spots_on_canvas = None
        self.counter = 0
        self.current_radius = None
        self.software_binsize = config.settings.software_binsize
        self.indexing_path = config.locations['work'] / 'indexing'

        self.init_vars()

        frame = Frame(self)

        self.RefineButton = Button(frame, text='Process All', width=10, command=self.process_all)
        self.RefineButton.grid(row=1, column=0, sticky='EW')
        self.e_exposure = Spinbox(frame, textvariable=self.var_exposure_time, width=8, from_=0.0, to=100.0, increment=0.01)
        self.e_exposure.grid(row=1, column=1, sticky='W', padx=5)
        Hoverbox(self.e_exposure, 'Exposure time for image acquisition')
        self.AcquireButton = Button(frame, text='Acquire', width=10, command=self.acquire_image)
        self.AcquireButton.grid(row=1, column=2, sticky='EW')
        self.OpenButton = Button(frame, text='Open', width=10, command=self.open_image)
        self.OpenButton.grid(row=1, column=3, sticky='EW', padx=5)
        self.ProjectButton = Button(frame, text='Project', width=10, command=self.project)
        self.ProjectButton.grid(row=1, column=4, sticky='EW')
        self.IndexButton = Button(frame, text='Index', width=10, command=self.index)
        self.IndexButton.grid(row=1, column=5, sticky='EW', padx=5)
        self.RefineButton = Button(frame, text='Refine', width=10, command=self.refine)
        self.RefineButton.grid(row=1, column=6, sticky='EW')
        self.e_name = Entry(frame, textvariable=self.var_name, width=8)
        self.e_name.grid(row=1, column=7, sticky='EW', padx=5)
        Hoverbox(self.e_name, 'Input name of the sample')

        self.e_amplitude = Spinbox(frame, textvariable=self.var_amplitude, width=8, from_=0.0, to=100.0, increment=0.01)
        self.e_amplitude.grid(row=2, column=0, sticky='EW')
        Hoverbox(self.e_amplitude, 'Stretch amplitude')
        self.e_azimuth = Spinbox(frame, textvariable=self.var_azimuth, width=8, from_=-180.0, to=180.0, increment=0.01)
        self.e_azimuth.grid(row=2, column=1, sticky='EW', padx=5)
        Hoverbox(self.e_azimuth, 'Stretch azimuth')
        Checkbutton(frame, text='Stretch', variable=self.var_apply_stretch, command=self.apply_stretch).grid(row=2, column=2, sticky='W')
        self.e_min_sigma = Spinbox(frame, textvariable=self.var_min_sigma, width=7, from_=0.0, to=10.0, increment=0.5)
        self.e_min_sigma.grid(row=2, column=3, sticky='EW', padx=5)
        Hoverbox(self.e_min_sigma, 'Minimal sigma for peak hunting')
        self.e_max_sigma = Spinbox(frame, textvariable=self.var_max_sigma, width=7, from_=0.0, to=20.0, increment=0.5)
        self.e_max_sigma.grid(row=2, column=4, sticky='EW')
        Hoverbox(self.e_max_sigma, 'Maximum sigma for peak hunting')
        self.e_threshold = Spinbox(frame, textvariable=self.var_threshold, width=7, from_=0.0, to=10.0, increment=0.1)
        self.e_threshold.grid(row=2, column=5, sticky='EW', padx=5)
        Hoverbox(self.e_threshold, 'Threshold level for peak hunting')
        self.e_min_size = Spinbox(frame, textvariable=self.var_min_size, width=7, from_=3, to=1000, increment=1)
        self.e_min_size.grid(row=2, column=6, sticky='EW')
        Hoverbox(self.e_min_size, 'Minimum pixels for each found peaks')
        Checkbutton(frame, text='Find Peaks', variable=self.var_find_peaks, command=self.find_peaks).grid(row=2, column=7, sticky='EW', padx=5)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Label(frame, text='Unit Cell:').grid(row=1, column=0, sticky='EW')
        Label(frame, text='a', anchor="e").grid(row=1, column=1, sticky='EW', padx=5)
        self.e_a = Entry(frame, textvariable=self.var_a, width=8, justify='center', state=NORMAL)
        self.e_a.grid(row=1, column=2, sticky='EW')
        Label(frame, text='Å').grid(row=1, column=3, sticky='EW')
        Label(frame, text='b', anchor="e").grid(row=1, column=4, sticky='EW', padx=5)
        self.e_b = Entry(frame, textvariable=self.var_b, width=8, justify='center', state=NORMAL)
        self.e_b.grid(row=1, column=5, sticky='EW')
        Label(frame, text='Å').grid(row=1, column=6, sticky='EW')
        Label(frame, text='c', anchor="e").grid(row=1, column=7, sticky='EW', padx=5)
        self.e_c = Entry(frame, textvariable=self.var_c, width=8, justify='center', state=NORMAL)
        self.e_c.grid(row=1, column=8, sticky='EW')
        Label(frame, text='Å').grid(row=1, column=9, sticky='EW')
        Label(frame, text='al', anchor="e").grid(row=1, column=10, sticky='EW', padx=5)
        self.e_alpha = Entry(frame, textvariable=self.var_alpha, width=8, justify='center', state=NORMAL)
        self.e_alpha.grid(row=1, column=11, sticky='EW')
        Label(frame, text='°').grid(row=1, column=12, sticky='EW')
        Label(frame, text='be', anchor="e").grid(row=1, column=13, sticky='EW', padx=5)
        self.e_beta = Entry(frame, textvariable=self.var_beta, width=8, justify='center', state=NORMAL)
        self.e_beta.grid(row=1, column=14, sticky='EW')
        Label(frame, text='°').grid(row=1, column=15, sticky='EW')
        Label(frame, text='ga', anchor="e").grid(row=1, column=16, sticky='EW', padx=5)
        self.e_gamma = Entry(frame, textvariable=self.var_gamma, width=8, justify='center', state=NORMAL)
        self.e_gamma.grid(row=1, column=17, sticky='EW')
        Label(frame, text='°').grid(row=1, column=18, sticky='EW')

        Label(frame, text='Space Group:', anchor="w").grid(row=2, column=0, columnspan=2, sticky='W')
        self.e_space_group = Entry(frame, textvariable=self.var_space_group, width=8, justify='center', state=NORMAL)
        self.e_space_group.grid(row=2, column=2, sticky='EW')
        Label(frame, text='dmax').grid(row=2, column=3, columnspan=2, sticky='EW', padx=5)
        self.e_dmax = Entry(frame, textvariable=self.var_dmax, width=8, justify='center', state=NORMAL)
        self.e_dmax.grid(row=2, column=5, sticky='EW')
        Label(frame, text='Å').grid(row=2, column=6, sticky='EW')
        Label(frame, text='dmin').grid(row=2, column=7, sticky='EW', padx=5)
        self.e_dmin = Entry(frame, textvariable=self.var_dmin, width=8, justify='center', state=NORMAL)
        self.e_dmin.grid(row=2, column=8, sticky='EW')
        Label(frame, text='Å').grid(row=2, column=9, sticky='EW')
        Label(frame, text='crystal thickness').grid(row=2, column=10, columnspan=4, sticky='E', padx=5)
        self.e_thickness = Entry(frame, textvariable=self.var_thickness, width=8, state=NORMAL)
        self.e_thickness.grid(row=2, column=14, sticky='EW')
        Label(frame, text='Å').grid(row=2, column=15, sticky='EW')

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        
        Checkbutton(frame, text='Show Center', variable=self.var_show_center, command=self.show_center).grid(row=1, column=1, sticky='W')
        self.e_sigma = Entry(frame, textvariable=self.var_sigma, width=5, justify='center', state=NORMAL)
        self.e_sigma.grid(row=1, column=2, sticky='EW', padx=5)
        Hoverbox(self.e_sigma, 'Sigma for find center without beam stop or percentile to segment with beam stop')
        Checkbutton(frame, text='Remove BKGD', variable=self.var_remove_background, command=self.remove_background).grid(row=1, column=3, sticky='W')
        self.e_bkgd = Entry(frame, textvariable=self.var_bkgd_level, width=5, justify='center', state=NORMAL)
        self.e_bkgd.grid(row=1, column=4, sticky='EW', padx=5)
        Hoverbox(self.e_bkgd, 'Background footprint to determine the background level')
        Checkbutton(frame, text='Show Index', variable=self.var_show_index, command=self.show_index).grid(row=1, column=5, sticky='W')
        Checkbutton(frame, text='Show HKL', variable=self.var_show_hkl).grid(row=1, column=6, sticky='W')
        Label(frame, text='Vmax').grid(row=1, column=7, sticky='EW')
        self.e_vmax = Entry(frame, textvariable=self.var_vmax, width=5, justify='center', state=NORMAL)
        self.e_vmax.grid(row=1, column=8, sticky='EW')
        self.IndexButton = Button(frame, text='Refresh', width=12, command=self.refresh)
        self.IndexButton.grid(row=1, column=9, sticky='EW', padx=5)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        if self.software_binsize is None:
            canvas_shape = np.array(config.camera.dimensions[::-1]) * 0.9 / 100
        else:
            canvas_shape = np.array(config.camera.dimensions[::-1]) / self.software_binsize * 0.9 / 100
        canvas_shape[0] += 1
        self.fig = Figure(figsize=canvas_shape, dpi=100)
        self.fig.subplots_adjust(left=0.1, bottom=0.07, right=0.95, top=0.95, wspace=0, hspace=0)
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.canvas = FigureCanvasTkAgg(self.fig, frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, padx=5)
        self.toolbar = NavigationToolbar2Tk(self.canvas, frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.grid(row=1, column=0, padx=5)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

    def init_vars(self):
        try:
            with open(self.indexing_path / 'params.yaml', 'r') as f:
                dct = yaml.load(f, Loader=yaml.Loader)
                print(dct)
            self.var_a = DoubleVar(value=dct['a'])
            self.var_b = DoubleVar(value=dct['b'])
            self.var_c = DoubleVar(value=dct['c'])
            self.var_alpha = DoubleVar(value=dct['alpha'])
            self.var_beta = DoubleVar(value=dct['beta'])
            self.var_gamma = DoubleVar(value=dct['gamma'])
            self.var_space_group = StringVar(value=dct['space_group'])
            self.var_dmax = DoubleVar(value=dct['dmax'])
            self.var_dmin = DoubleVar(value=dct['dmin'])
            self.var_sigma = DoubleVar(value=dct['sigma'])
            self.var_bkgd_level = IntVar(value=dct['bkgd_level'])
            self.var_azimuth = DoubleVar(value=dct['azimuth'])
            self.var_amplitude = DoubleVar(value=dct['amplitude'])
            self.var_min_sigma = DoubleVar(value=dct['min_sigma'])
            self.var_max_sigma = DoubleVar(value=dct['max_sigma'])
            self.var_threshold = DoubleVar(value=dct['threshold'])
            self.var_min_size = IntVar(value=dct['min_size'])
        except:
            self.var_a = DoubleVar(value=10.0)
            self.var_b = DoubleVar(value=10.0)
            self.var_c = DoubleVar(value=10.0)
            self.var_alpha = DoubleVar(value=90.0)
            self.var_beta = DoubleVar(value=90.0)
            self.var_gamma = DoubleVar(value=90.0)
            self.var_space_group = StringVar(value="")
            self.var_dmax = DoubleVar(value=20.0)
            self.var_dmin = DoubleVar(value=1.0)
            self.var_sigma = DoubleVar(value=20.0)
            self.var_bkgd_level = IntVar(value=20.0)
            self.var_azimuth = DoubleVar(value=config.calibration.stretch_azimuth)
            self.var_amplitude = DoubleVar(value=config.calibration.stretch_amplitude)
            self.var_min_sigma = DoubleVar(value=4.0)
            self.var_max_sigma = DoubleVar(value=5.0)
            self.var_threshold = DoubleVar(value=1.0)
            self.var_min_size = IntVar(value=20)
        self.var_apply_stretch = BooleanVar(value=False)
        self.var_show_center = BooleanVar(value=False)
        self.var_show_index = BooleanVar(value=False)
        self.var_exposure_time = DoubleVar(value=round(round(1.5/self.ctrl.cam.default_exposure)*self.ctrl.cam.default_exposure, 1))
        self.var_name = StringVar(value="")
        self.var_remove_background = BooleanVar(value=False)
        self.var_vmax = DoubleVar(value=500.0)
        self.var_find_peaks = BooleanVar(value=False)
        self.var_thickness = DoubleVar(value=400.0)
        self.var_show_hkl = BooleanVar(value=False)

    def process_all(self):
        if self.img is not None:
            sigma = self.var_sigma.get()
            if self.use_beamstop:
                center = find_beam_center_with_beamstop(self.img, z=sigma)
            else:
                center = find_beam_center(self.img, sigma=sigma)
            background_removed_img = subtract_background_median(self.img, footprint=self.var_bkgd_level.get())
            azimuth = self.var_azimuth.get()
            amplitude = self.var_amplitude.get()
            stretched_img = apply_stretch_correction(background_removed_img, center=center, azimuth=azimuth, amplitude=amplitude)
            min_sigma = self.var_min_sigma.get()
            max_sigma = self.var_max_sigma.get()
            threshold = self.var_threshold.get()
            min_size = self.var_min_size.get()
            props_collection = find_peaks_regionprops(stretched_img, min_sigma=min_sigma, max_sigma=max_sigma, 
                                    threshold=threshold, min_size=min_size, return_props=True)
            self.img_find_peaks = im_reconstruct(props_collection, stretched_img.shape)
            self.img_on_canvas.set_array(self.img_find_peaks)

            if self.indexer is not None:
                self.orientation_collection = self.indexer.find_orientation(self.img_find_peaks, center)
                self.refined_orientation = self.indexer.refine_all(self.img_find_peaks, self.orientation_collection)
                print('Refinement of indexing finished.')
            print('Saving processing parameters...')
            dct = {}
            dct['a'] = self.var_a.get()
            dct['b'] = self.var_b.get()
            dct['c'] = self.var_c.get()
            dct['alpha'] = self.var_alpha.get()
            dct['beta'] = self.var_beta.get()
            dct['gamma'] = self.var_gamma.get()
            dct['space_group'] = self.var_space_group.get()
            dct['dmin'] = self.var_dmin.get()
            dct['dmax'] = self.var_dmax.get()
            dct['bkgd_level'] = self.var_bkgd_level.get()
            dct['sigma'] = sigma
            dct['azimuth'] = azimuth
            dct['amplitude'] = amplitude
            dct['min_sigma'] = min_sigma
            dct['max_sigma'] = max_sigma
            dct['threshold'] = threshold
            dct['min_size'] = min_size
            with open(self.indexing_path / 'params.yaml', 'w') as f:
                yaml.dump(dct, f)
            print('Image processing finished.')
            self.canvas.draw()

    def acquire_image(self):
        self.ax.cla()
        self.counter = 0
        self.indexing_path.mkdir(parents=True, exist_ok=True)
        existing_tiff = len(list(self.indexing_path.glob('*.tiff')))
        filename = self.var_name.get() + f'_{existing_tiff:03}'
        self.img, self.img_header = self.ctrl.get_image(exposure=self.var_exposure_time.get(), out=self.indexing_path / filename)
        pprint.pprint(self.img_header)
        self.img_on_canvas = self.ax.imshow(self.img)
        self.ax.set_xlim(0, self.img.shape[1]-1)
        self.ax.set_ylim(self.img.shape[0]-1, 0)
        self.canvas.draw()

    def open_image(self):
        self.ax.cla()
        self.img_path = filedialog.askopenfilename(initialdir=config.locations['work'], title='Select an image', 
                            filetypes=(('mrc files', '*.mrc'), ('img files', '*.img'), ('dm3 files', '*.dm3'), ('dm4 files', '*.dm4'), ('hdf5 files', '*.h5'), ('smv files', '*.smv'), 
                                        ('tiff files', '*.tiff'), ('tif files', '*.tif'), ('cbf files', '*.cbf'), ('all files', '*.*')))
        if self.img_path != '':
            self.counter = 0
            self.img_path = Path(self.img_path)
            suffix = img_path.suffix
            if suffix in ('.tif', '.tiff'):
                self.img, self.img_header = read_tiff(self.img_path)
            elif suffix in ('.h5'):
                self.img, self.img_header = read_hdf5(self.img_path)
            elif suffix == '.mrc':
                #self.img, self.img_header = read_mrc(img_path)
                with mrcfile.open(self.img_path, permissive=True) as f:
                    self.img = f.data
                    self.img_header = {name:f.header[name] for name in f.header.dtype.names}
            elif suffix in ('.img', '.smv'):
                self.img, self.img_header = read_adsc(self.img_path)
            elif suffix == '.cbf':
                self.img, self.img_header = read_cbf(self.img_path)
            elif suffix in ('.dm3', '.dm4'):
                self.img = dmReader(self.img_path)['data']
                self.img_header = None
            pprint.pprint(self.img_header)
            self.img_on_canvas = self.ax.imshow(self.img)
            self.ax.set_xlim(0, self.img.shape[1]-1)
            self.ax.set_ylim(self.img.shape[0]-1, 0)
            self.canvas.draw()

    def open_from_frame(self):
        if self.img_path != '' and self.img_path is not None:
            self.counter = 0
            self.img_path = Path(self.img_path)
            self.img, self.img_header = read_tiff(self.img_path)
            pprint.pprint(self.img_header)
            self.img_on_canvas = self.ax.imshow(self.img)
            self.ax.set_xlim(0, self.img.shape[1]-1)
            self.ax.set_ylim(self.img.shape[0]-1, 0)
            self.canvas.draw()

    def show_center(self):
        if self.var_show_center.get():
            if self.use_beamstop:
                self.center = find_beam_center_with_beamstop(self.img, z=self.var_sigma.get())
            else:
                center = find_beam_center(self.img, sigma=self.var_sigma.get())
                print(center)
                self.center = find_beam_center(self.img[int(center[0])-20:int(center[0])+20, int(center[1])-20:int(center[1])+20], 
                                            sigma=self.var_sigma.get()/4) + center -21
                print(self.center)
            self.center_on_canvas = self.ax.plot(self.center[1], self.center[0], marker='o', color='r')
        else:
            self.center_on_canvas.pop(0).remove()
        self.canvas.draw()
        
    def remove_background(self):
        bkgd_level = self.var_bkgd_level.get()
        if self.var_remove_background.get():
            if self.img is not None:
                self.background_removed_img = subtract_background_median(self.img, footprint=bkgd_level)
                self.img_on_canvas.set_array(self.background_removed_img)
        else:
            self.img_on_canvas.set_array(self.img)
        self.canvas.draw()

    def find_peaks(self):
        min_sigma = self.var_min_sigma.get()
        max_sigma = self.var_max_sigma.get()
        threshold = self.var_threshold.get()
        min_size = self.var_min_size.get()
        if self.var_find_peaks.get():
            if self.var_apply_stretch.get():
                if self.stretched_img is not None:
                    self.props_collection = find_peaks_regionprops(self.stretched_img, min_sigma=min_sigma, max_sigma=max_sigma, 
                                    threshold=threshold, min_size=min_size, return_props=True)
                    self.img_find_peaks = im_reconstruct(self.props_collection, self.stretched_img.shape)
            else:
                if self.img is not None:
                    self.props_collection = find_peaks_regionprops(self.img, min_sigma=min_sigma, max_sigma=max_sigma, 
                                    threshold=threshold, min_size=min_size, return_props=True)
                    self.img_find_peaks = im_reconstruct(self.props_collection, self.img.shape)
            self.img_on_canvas.set_array(self.img_find_peaks)
        else:
            self.img_on_canvas.set_array(self.img)
        self.canvas.draw()

    def show_index(self):
        if self.var_show_index.get():
            if self.refined_orientation is not None:
                center_x = self.refined_orientation[0].center_x
                center_y = self.refined_orientation[0].center_y
                scale = self.refined_orientation[0].scale
                alpha = self.refined_orientation[0].alpha
                beta = self.refined_orientation[0].beta
                gamma = self.refined_orientation[0].gamma
                score = self.refined_orientation[0].score
                phase = self.refined_orientation[0].phase
            else:
                center_x = self.orientation_collection[0].center_x
                center_y = self.orientation_collection[0].center_y
                scale = self.orientation_collection[0].scale
                alpha = self.orientation_collection[0].alpha
                beta = self.orientation_collection[0].beta
                gamma = self.orientation_collection[0].gamma
                score = self.orientation_collection[0].score
                phase = self.orientation_collection[0].phase
            img = self.img_on_canvas.get_array()
            proj = self.projector.get_projection(alpha, beta, gamma)
            pks = proj[:, 3:5]
            i, j, proj = get_indices(pks, scale, (center_x, center_y), img.shape, hkl=proj)
            shape_factor = proj[:, 5:6].reshape(-1)
            hkl = proj[:, 0:3]
            if self.var_show_hkl.get():
                for idx, (h, k, l) in enumerate(hkl):
                    self.hkl_list_on_canvas.append(self.ax.annotate("{:.0f} {:.0f} {:.0f}".format(h, k, l), (j[idx], i[idx]), color="blue"))
            self.spots_on_canvas = self.ax.scatter(j, i, marker="+", c=shape_factor, cmap="viridis")
            
        else:
            if self.var_show_hkl.get():
                for hkl_on_canvas in self.hkl_list_on_canvas:
                    hkl_on_canvas.remove()
            self.spots_on_canvas.remove()
            self.hkl_list_on_canvas = []
        self.canvas.draw()


    def refresh(self):
        current_img = self.img_on_canvas.get_array()
        self.img_on_canvas.remove()
        self.img_on_canvas = self.ax.imshow(current_img, vmax=self.var_vmax.get(), cmap="gray")
        self.canvas.draw()

    def project(self):
        unit_cell = (self.var_a.get(), self.var_b.get(), self.var_c.get(), self.var_alpha.get(), self.var_beta.get(), self.var_gamma.get())
        space_group = self.var_space_group.get()
        name = self.var_name.get()
        dmin = self.var_dmin.get()
        dmax = self.var_dmax.get()
        thickness = self.var_thickness.get()
        self.state = self.ctrl.mode.state
        self.mag = self.ctrl.magnification.get()

        self.projector = Projector.from_parameters(params=unit_cell, spgr=space_group, name=name, dmin=dmin, dmax=dmax, thickness=thickness)
        try:
            self.pixelsize = self.img_header['ImagePixelsize']
            self.counter += 1
        except KeyError:
            self.pixelsize = popupWindow(self, 'Input pixel size', 'Pixel Size (Å-1/pixel)').get_value()
            self.counter = 0

        if self.counter > 2:
            self.pixelsize = popupWindow(self, 'Input pixel size', 'Pixel Size (Å-1/pixel)').get_value()
        try:
            self.pixelsize = float(self.pixelsize)
        except ValueError:
            raise ValueError(f'{self.pixelsize} is not a number. Please input a number in the pop up window')

        self.indexer = Indexer.from_projector(self.projector, pixelsize=self.pixelsize)

    def index(self):
        if self.var_find_peaks.get():
            if self.img_find_peaks is not None and self.indexer is not None and self.center is not None:
                self.orientation_collection = self.indexer.find_orientation(self.img_find_peaks, self.center)
                print('Indexing finished.')
        else:
            if self.img is not None and self.indexer is not None and self.center is not None:
                self.orientation_collection = self.indexer.find_orientation(self.img, self.center)
                print('Indexing finished.')

    def refine(self):
        if self.var_find_peaks.get():
            if self.img_find_peaks is not None and self.orientation_collection is not None:
                self.refined_orientation = self.indexer.refine_all(self.img_find_peaks, self.orientation_collection)
                print('Refinement of indexing finished.')
        else:
            if self.img is not None and self.orientation_collection is not None:
                self.refined_orientation = self.indexer.refine_all(self.img, self.orientation_collection)
                print('Refinement of indexing finished.')

    def apply_stretch(self):
        azimuth = self.var_azimuth.get()
        amplitude = self.var_amplitude.get()
        if self.center is not None:
            if self.var_apply_stretch.get():
                if self.var_remove_background.get():
                    if self.background_removed_img is not None and self.center is not None:
                        self.stretched_img = apply_stretch_correction(self.background_removed_img, center=self.center, azimuth=azimuth, amplitude=amplitude)
                else:
                    if self.img is not None and self.center is not None:
                        self.stretched_img = apply_stretch_correction(self.img, center=self.center, azimuth=azimuth, amplitude=amplitude)
                self.img_on_canvas.set_array(self.stretched_img)
                if self.current_radius is None:
                    self.circle_on_canvas = Circle((self.center[1], self.center[0]), self.img.shape[0]//3, color='blue', fill=False, linewidth=0.5)
                else:
                    self.circle_on_canvas = Circle((self.center[1], self.center[0]), self.current_radius, color='blue', fill=False, linewidth=0.5)
                self.ax.add_artist(self.circle_on_canvas)
                self.cid = self.fig.canvas.mpl_connect('scroll_event', self._mouse_scroll_stretch)
            else:
                self.img_on_canvas.set_array(self.img)
                self.fig.canvas.mpl_disconnect(self.cid)
                self.circle_on_canvas.remove()
            self.canvas.draw()

    def _mouse_scroll_stretch(self, event):
        navi_mode = self.ax.get_navigate_mode()
        if navi_mode not in (None, "") : return
        if not event.inaxes: return
        if event.inaxes != self.ax: return
        self.current_radius = self.circle_on_canvas.get_radius()
        if event.button == 'up':
            self.circle_on_canvas.set_radius(self.current_radius + 3)
        elif event.button == 'down':
            self.circle_on_canvas.set_radius(self.current_radius - 3)
        self.canvas.draw()
        

module = BaseModule(name='indexing', display_name='Indexing', tk_frame=IndexFrame, location='left')
commands = {}

if __name__ == '__main__':
    root = Tk()
    IndexFrame(root).pack(side='top', fill='both', expand=True)
    root.mainloop()