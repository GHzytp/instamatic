import threading
from tkinter import *
from tkinter.ttk import *
import tkinter

from .base_module import BaseModule
from instamatic import config
from instamatic.utils.spinbox import Spinbox
from instamatic.image_utils import autoscale
from instamatic.tools import find_beam_center

from instamatic.experiments import FourDSTEM

BS_OVERHEAD = 0.003

class ExperimentalFourDSTEM(LabelFrame):
    """Software controlled beam shift operation for 4DSTEM. Currently only works for FEI microscope 
    because of the low overhead of beamshift function"""
    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='FourDSTEM')

        self.parent = parent

        from instamatic import TEMController
        self.ctrl = TEMController.get_instance()
        self.cam_x, self.cam_y = self.ctrl.cam.getCameraDimensions()
        self.binsize = self.ctrl.cam.default_binsize

        if self.cam_x != self.cam_y:
            raise RuntimeWarning("It is recommended to use a camera with equal x and y length")
            self.cam_x = min(self.cam_x, self.cam_y)

        self.init_vars()

        frame = Frame(self)
        Label(frame, text='Dwell Time(s)', width=10).grid(row=1, column=0, columnspan=2, sticky='W')
        e_dwell_time = Spinbox(frame, width=10, textvariable=self.var_dwell_time, from_=BS_OVERHEAD, to=3.0, increment=0.001)
        e_dwell_time.grid(row=1, column=2, sticky='EW')
        Label(frame, text='Exposure Time(s)', width=10).grid(row=1, column=3, columnspan=2, sticky='W')
        e_dwell_time = Spinbox(frame, width=10, textvariable=self.var_exposure_time, from_=BS_OVERHEAD, to=3.0, increment=0.001)
        e_dwell_time.grid(row=1, column=4, sticky='EW')

        Label(frame, text='HAADF min radius(pix)', width=10).grid(row=1, column=0, columnspan=2, sticky='W')
        e_haadf_min_radius = Spinbox(frame, width=10, textvariable=self.var_haadf_min_radius, from_=self.cam_x*2/3, to=self.cam_x, increment=1)
        e_haadf_min_radius.grid(row=1, column=2, sticky='EW')
        Label(frame, text='BF max radius(pix)', width=10).grid(row=1, column=3, columnspan=2, sticky='W')
        e_bf_max_radius = Spinbox(frame, width=10, textvariable=self.var_bf_max_radius, from_=1, to=self.cam_x/3, increment=1)
        e_bf_max_radius.grid(row=1, column=5, sticky='EW')

        Label(frame, text='Center X', width=10).grid(row=2, column=0, sticky='W')
        e_center_x = Spinbox(frame, width=10, textvariable=self.var_center_x, from_=0, to=self.cam_x, increment=1)
        e_center_x.grid(row=2, column=1, sticky='EW')
        Label(frame, text='Center Y', width=10).grid(row=2, column=2, sticky='W')
        e_center_y = Spinbox(frame, width=10, textvariable=self.var_center_y, from_=0, to=self.cam_x, increment=1)
        e_center_y.grid(row=2, column=3, sticky='EW')
        self.b_center = Button(frame, width=10, text='Set Center', command=self.set_center)
        self.b_center.grid(row=2, column=4, sticky='W')
        self.b_center_get = Button(frame, width=10, text='Get Center', command=self.get_center)
        self.b_center_get.grid(row=2, column=5, sticky='W')

        frame.pack(side='top', fill='x', expand=False, padx=10, pady=10)

        frame = Frame(self)

        Label(frame, text='Interval X(nm)', width=10).grid(row=2, column=0, sticky='W')
        e_interval_x = Spinbox(frame, width=10, textvariable=self.var_interval_x, from_=0.1, to=1000, increment=0.001)
        e_interval_x.grid(row=2, column=1, sticky='EW')

        Label(frame, text='Interval Y(nm)', width=10).grid(row=2, column=2, sticky='W')
        e_interval_y = Spinbox(frame, width=10, textvariable=self.var_interval_y, from_=0.1, to=1000, increment=0.001)
        e_interval_y.grid(row=2, column=3, sticky='EW')

        Label(frame, text='NX', width=5).grid(row=2, column=4, sticky='W')
        e_nx = Spinbox(frame, width=10, textvariable=self.var_nx, from_=2, to=128, increment=1)
        e_nx.grid(row=2, column=5, sticky='EW')

        Label(frame, text='NY', width=5).grid(row=2, column=6, sticky='W')
        e_ny = Spinbox(frame, width=10, textvariable=self.var_ny, from_=2, to=128, increment=1)
        e_ny.grid(row=2, column=7, sticky='EW')

        frame.pack(side='top', fill='x', expand=False, padx=10, pady=10)

        frame = Frame(self)

        Label(frame, text='Select virtual image types:').grid(row=4, columnspan=2, sticky='EW')
        Checkbutton(frame, text='HAADF', variable=self.var_haadf).grid(row=4, column=2, sticky='EW')
        Checkbutton(frame, text='ADF', variable=self.var_adf).grid(row=4, column=3, sticky='EW')
        Checkbutton(frame, text='BF', variable=self.var_df).grid(row=4, column=4, sticky='EW')

        Label(frame, text='Select output formats for virtual images:').grid(row=5, columnspan=3, sticky='EW')
        Checkbutton(frame, text='.mrc', variable=self.var_save_mrc_4DSTEM).grid(row=5, column=3, sticky='EW')
        Checkbutton(frame, text='.hdf5', variable=self.var_save_hdf5_4DSTEM).grid(row=5, column=4, sticky='EW')

        Label(frame, text='Select output formats for raw images:').grid(row=6, columnspan=3, sticky='EW')
        Checkbutton(frame, text='.mrc', variable=self.var_save_mrc_raw_imgs).grid(row=6, column=3, sticky='EW')
        Checkbutton(frame, text='.hdf5', variable=self.var_save_hdf5_raw_imgs).grid(row=6, column=4, sticky='EW')

        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=1)
        frame.grid_columnconfigure(3, weight=1)
        frame.grid_columnconfigure(4, weight=1)
        frame.pack(side='top', fill='x', padx=10, pady=10)

        frame = Frame(self)
        self.CollectionButton = Button(frame, text='Start Preview', command=self.start_preview, state=NORMAL)
        self.CollectionButton.grid(row=1, column=0, sticky='EW')
        self.CollectionButton = Button(frame, text='Stop Preview', command=self.stop_preview, state=DISABLED)
        self.CollectionButton.grid(row=1, column=1, sticky='EW')
        self.CollectionButton = Button(frame, text='Start Acquire', command=self.start_acquire, state=NORMAL)
        self.CollectionButton.grid(row=1, column=2, sticky='EW')
        self.CollectionButton = Button(frame, text='Stop Acquire', command=self.stop_acquire, state=DISABLED)
        self.CollectionButton.grid(row=1, column=3, sticky='EW')

        self.CollectionButton = Button(frame, text='Start Acquire Raw Images', command=self.start_acq_raw_img, state=NORMAL)
        self.CollectionButton.grid(row=2, columnspan=2, column=0, sticky='EW')
        self.CollectionButton = Button(frame, text='Stop Acquire Raw Images', command=self.stop_acq_raw_img, state=DISABLED)
        self.CollectionButton.grid(row=2, columnspan=2, column=2, sticky='EW')

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.pack(side='bottom', fill='x', padx=10, pady=10)

        self.stopEvent = threading.Event()

    def init_vars(self):
        self.var_dwell_time = DoubleVar(value=BS_OVERHEAD)
        self.var_exposure_time = DoubleVar(value=BS_OVERHEAD)
        self.var_haadf_min_radius = IntVar(value=self.cam_x*2/3)
        self.var_bf_max_radius = IntVar(value=self.cam_x/3)
        self.var_center_x = DoubleVar(value=self.cam_x/2)
        self.var_center_y = DoubleVar(value=self.cam_x/2)
        self.var_interval_x = DoubleVar(value=100)
        self.var_interval_y = DoubleVar(value=100)
        self.var_nx = IntVar(value=32)
        self.var_nx = IntVar(value=32)
        self.var_save_mrc_4DSTEM = BooleanVar(value=True)
        self.var_save_hdf5_4DSTEM = BooleanVar(value=True)
        self.var_save_mrc_raw_imgs = BooleanVar(value=True)
        self.var_save_hdf5_raw_imgs = BooleanVar(value=True)
        self.var_haadf = BooleanVar(value=True)
        self.var_adf = BooleanVar(value=True)
        self.var_df = BooleanVar(value=False)

    def get_center(self):
        '''find the center of the '''
        img = self.ctrl.get_image(self.var_exposure_time.get())
        img, scale = autoscale(img)
        pixel_cent = find_beam_center(img) * self.binsize / scale
        self.var_center_x.set(pixel_cent[0])
        self.var_center_y.set(pixel_cent[1])

    def set_center(self):
        pass

    def start_preview(self):
        pass

    def stop_preview(self):
        pass

    def start_acquire(self):
        pass

    def stop_acquire(self):
        pass

    def start_acq_raw_img(self):
        pass

    def stop_acq_raw_img(self):
        pass

    def set_trigger(self, trigger=None, q=None):
        self.triggerEvent = trigger
        self.q = q

    def start_collection(self):
        params = self.get_params()
        self.q.put(('FourDSTEM', params))

    def stop_collection(self, event=None):
        self.stopEvent.set()

    def get_params(self):
        params = {'dwell_time': self.var_dwell_time.get(),
                  'exposure_time': self.var_exposure_time.get(),
                  'center_x': self.var_center_x.get(),
                  'center_y': self.var_center_y.get(),
                  'interval_x': self.var_interval_x.get(),
                  'interval_y': self.var_interval_y.get(),
                  'nx': self.var_nx.get(),
                  'ny': self.var_ny.get(),
                  'haadf': self.var_haadf.get(),
                  'adf': self.var_adf.get(),
                  'bf': self.var_bf.get(),
                  'save_mrc_4DSTEM': self.var_save_mrc_4DSTEM.get(),
                  'save_hdf5_4DSTEM': self.var_save_hdf5_4DSTEM.get(),
                  'save_mrc_raw_imgs': self.var_save_mrc_raw_imgs.get(),
                  'save_hdf5_raw_imgs': self.var_save_hdf5_raw_imgs.get()}
        return params

def acquire_FourDSTEM(controller, **kwargs):
    controller.log.info('Acquire 4DSTEM virtual images')

def preview_FourDSTEM(controller, **kwargs):
    pass

def acquire_raw_img(controller, **kwargs):
    controller.log.info('Acquire 4DSTEM raw images')


module = BaseModule(name='FourDSTEM', display_name='FourDSTEM', tk_frame=ExperimentalFourDSTEM, location='bottom')
commands = {'acquire_FourDSTEM': acquire_FourDSTEM,
            'preview_FourDSTEM': preview_FourDSTEM,
            'acquire_raw_img': acquire_raw_img}

if __name__ == '__main__':
    root = Tk()
    ExperimentalFourDSTEM(root).pack(side='top', fill='both', expand=True)
    root.mainloop()