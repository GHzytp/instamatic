import threading
import time
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import *
from tkinter.ttk import *

import numpy as np
import pandas as pd

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from .base_module import BaseModule
from instamatic import config
from instamatic import TEMController
from instamatic.utils.indexer import Indexer
from instamatic.utils.projector import Projector
from instamatic.formats import read_tiff
from instamatic.utils.widgets import Hoverbox, Spinbox


class IndexFrame(LabelFrame):
    """GUI panel for indexing diffraction patterns and powder patterns. In addition, calibrate the stretching of the powder ring."""

    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Indexing diffraction patterns and powder patterns')
        self.parent = parent
        #self.ctrl = TEMController.get_instance()
        self.wavelength = config.microscope.wavelength

        self.init_vars()

        frame = Frame(self)

        Label(frame, text='Exposure(s)').grid(row=1, column=0, sticky='W')
        self.e_exposure = Spinbox(frame, textvariable=self.var_exposure_time, width=8, from_=0.0, to=100.0, increment=0.01)
        self.e_exposure.grid(row=1, column=1, sticky='W', padx=5)
        self.AcquireButton = Button(frame, text='Acquire', width=12, command=lambda:self.start_thread(self.acquire_image))
        self.AcquireButton.grid(row=1, column=2, sticky='EW')
        self.OpenButton = Button(frame, text='Open', width=12, command=self.open_image)
        self.OpenButton.grid(row=1, column=3, sticky='EW', padx=5)
        self.ProjectButton = Button(frame, text='Project', width=12, command=lambda:self.start_thread(self.project))
        self.ProjectButton.grid(row=1, column=4, sticky='EW')
        self.IndexButton = Button(frame, text='Index', width=12, command=lambda:self.start_thread(self.index))
        self.IndexButton.grid(row=1, column=5, sticky='EW', padx=5)

        Label(frame, text='Amplitude').grid(row=2, column=0, sticky='W')
        self.e_amplitude = Spinbox(frame, textvariable=self.var_amplitude, width=8, from_=0.0, to=100.0, increment=0.01)
        self.e_amplitude.grid(row=2, column=1, sticky='W', padx=5)
        Label(frame, text='Azimuth').grid(row=1, column=2, sticky='W')
        self.e_azimuth = Spinbox(frame, textvariable=self.var_azimuth, width=8, from_=-180.0, to=180.0, increment=0.01)
        self.e_azimuth.grid(row=2, column=3, sticky='W', padx=5)
        self.StretchButton = Button(frame, text='Stretch', width=12, command=self.apply_stretch)
        self.StretchButton.grid(row=1, column=4, sticky='EW', padx=5)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Label(frame, text='Unit Cell:').grid(row=1, column=0, sticky='EW')
        vcmd = (self.parent.register(self.validate), '%d', '%i', '%P', '%s', '%S', '%v', '%V', '%W')

        Label(frame, text='a', anchor="e").grid(row=1, column=1, sticky='EW', padx=5)
        self.e_a = Entry(frame, textvariable=self.var_a, width=8, justify='center', validate='key', validatecommand=vcmd, state=NORMAL)
        self.e_a.grid(row=1, column=2, sticky='EW')
        Label(frame, text='Å').grid(row=1, column=3, sticky='EW')

        Label(frame, text='b', anchor="e").grid(row=1, column=4, sticky='EW', padx=5)
        self.e_b = Entry(frame, textvariable=self.var_b, width=8, justify='center', validate='key', validatecommand=vcmd, state=NORMAL)
        self.e_b.grid(row=1, column=5, sticky='EW')
        Label(frame, text='Å').grid(row=1, column=6, sticky='EW')

        Label(frame, text='c', anchor="e").grid(row=1, column=7, sticky='EW', padx=5)
        self.e_c = Entry(frame, textvariable=self.var_c, width=8, justify='center', validate='key', validatecommand=vcmd, state=NORMAL)
        self.e_c.grid(row=1, column=8, sticky='EW')
        Label(frame, text='Å').grid(row=1, column=9, sticky='EW')

        Label(frame, text='al', anchor="e").grid(row=1, column=10, sticky='EW', padx=5)
        self.e_alpha = Entry(frame, textvariable=self.var_alpha, width=8, justify='center', validate='key', validatecommand=vcmd, state=NORMAL)
        self.e_alpha.grid(row=1, column=11, sticky='EW')
        Label(frame, text='°').grid(row=1, column=12, sticky='EW')

        Label(frame, text='be', anchor="e").grid(row=1, column=13, sticky='EW', padx=5)
        self.e_beta = Entry(frame, textvariable=self.var_beta, width=8, justify='center', validate='key', validatecommand=vcmd, state=NORMAL)
        self.e_beta.grid(row=1, column=14, sticky='EW')
        Label(frame, text='°').grid(row=1, column=15, sticky='EW')

        Label(frame, text='ga', anchor="e").grid(row=1, column=16, sticky='EW', padx=5)
        self.e_gamma = Entry(frame, textvariable=self.var_gamma, width=8, justify='center', validate='key', validatecommand=vcmd, state=NORMAL)
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

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        
        Checkbutton(frame, text='Show Center', variable=self.var_show_center, command=self.show_center).grid(row=1, column=1, sticky='W')
        self.e_sigma = Entry(frame, textvariable=self.var_sigma, width=5, justify='center', state=NORMAL)
        self.e_sigma.grid(row=1, column=2, sticky='EW', padx=5)
        Checkbutton(frame, text='Remove BKGD', variable=self.var_remove_background, command=self.remove_background).grid(row=1, column=3, sticky='W')
        self.e_bkgd = Entry(frame, textvariable=self.var_bkgd_level, width=5, justify='center', state=NORMAL)
        self.e_bkgd.grid(row=1, column=4, sticky='EW', padx=5)
        Checkbutton(frame, text='Show Index', variable=self.var_show_index, command=self.show_index).grid(row=1, column=5, sticky='W')
        
        Label(frame, text='Vmax').grid(row=1, column=6, sticky='EW')
        self.e_vmax = Entry(frame, textvariable=self.var_vmax, width=5, justify='center', state=NORMAL)
        self.e_vmax.grid(row=1, column=7, sticky='EW')
        self.IndexButton = Button(frame, text='Refresh', width=12, command=self.refresh)
        self.IndexButton.grid(row=1, column=8, sticky='EW', padx=5)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        canvas_shape = np.array(config.camera.dimensions) * 0.9 / 100
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
        #self.var_exposure_time = DoubleVar(value=round(round(1.5/self.ctrl.cam.default_exposure)*self.ctrl.cam.default_exposure, 1))
        self.var_exposure_time = DoubleVar(value=1.0)
        self.var_a = DoubleVar(value=10.0)
        self.var_b = DoubleVar(value=10.0)
        self.var_c = DoubleVar(value=10.0)
        self.var_alpha = DoubleVar(value=90.0)
        self.var_beta = DoubleVar(value=90.0)
        self.var_gamma = DoubleVar(value=90.0)
        self.var_space_group = StringVar(value="")
        self.var_dmax = DoubleVar(value=20.0)
        self.var_dmin = DoubleVar(value=1.0)
        self.var_show_center = BooleanVar(value=False)
        self.var_show_index = BooleanVar(value=False)
        self.var_sigma = DoubleVar(value=20.0)
        self.var_bkgd_level = DoubleVar(value=20.0)
        self.var_remove_background = BooleanVar(value=False)
        self.var_vmax = DoubleVar(value=500.0)
        self.var_azimuth = DoubleVar(value=config.calibration.stretch_azimuth)
        self.var_amplitude = DoubleVar(value=config.calibration.stretch_amplitude)

    def validate(self, action, index, value_if_allowed, prior_value, text, validation_type, trigger_type, widget_name):
        if value_if_allowed:
            try:
                value = float(value_if_allowed)
                return True
            except ValueError:
                return False
        else:
            return False

    def start_thread(self, func, args=()):
        t = threading.Thread(target=func, args=args, deamon=True)
        t.start()

    def acquire_image(self):
        arr, h = self.ctrl.get_image(exposure=self.var_exposure_time.get())

    def open_image(self):
        self.img_path = filedialog.askopenfilename(initialdir=config.locations['work'], title='Select an image', 
                            filetypes=(('tiff files', '*.tiff'), ('tif files', '*.tif'), ('all files', '*.*')))

    def show_center(self):
        pass

    def remove_background(self):
        pass

    def show_index(self):
        pass

    def refresh(self):
        pass

    def project(self):
        pass

    def index(self):
        pass

module = BaseModule(name='indexing', display_name='Indexing', tk_frame=IndexFrame, location='left')
commands = {}

if __name__ == '__main__':
    root = Tk()
    IndexFrame(root).pack(side='top', fill='both', expand=True)
    root.mainloop()