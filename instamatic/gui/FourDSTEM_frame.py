import numpy as np
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

# Beam shift overhead for the microscope
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

        self.panel = None
        self.frame_delay = 500

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
        self.b_center_get = Button(frame, width=10, text='Get Center', command=self.get_center)
        self.b_center_get.grid(row=2, column=4, sticky='W')

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

        self.makepanel()
        self.panel.grid(row=0, column=1, sticky='EW')

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.pack(side='top', fill='x', padx=10, pady=10)

        frame = Frame(self)

        self.StartScanButton = Button(frame, text='Start Scanning', command=self.start_scan, state=NORMAL)
        self.StartScanButton.grid(row=0, column=0, sticky='EW')
        self.PauseScanButton = Button(frame, text='Pause Scanning', command=self.pause_scan, state=DISABLED)
        self.PauseScanButton.grid(row=0, column=1, sticky='EW')
        self.ContinueScanButton = Button(frame, text='Continue Scanning', command=self.continue_scan, state=DISABLED)
        self.ContinueScanButton.grid(row=0, column=1, sticky='EW')
        self.StopScanButton = Button(frame, text='Stop Scanning', command=self.stop_scan, state=DISABLED)
        self.StopScanButton.grid(row=0, column=2, sticky='EW')

        self.StartPreviewButton = Button(frame, text='Start Preview', command=self.start_preview, state=NORMAL)
        self.StartPreviewButton.grid(row=1, column=0, sticky='EW')
        self.StopPreviewButton = Button(frame, text='Stop Preview', command=self.stop_preview, state=DISABLED)
        self.StopPreviewButton.grid(row=1, column=1, sticky='EW')
        self.StartAcquireButton = Button(frame, text='Start Acquire', command=self.start_acquire, state=NORMAL)
        self.StartAcquireButton.grid(row=1, column=2, sticky='EW')
        self.StopAcquireButton = Button(frame, text='Stop Acquire', command=self.stop_acquire, state=DISABLED)
        self.StopAcquireButton.grid(row=1, column=3, sticky='EW')

        self.StartCollectButton = Button(frame, text='Start Acquire Raw Images', command=self.start_acq_raw_img, state=NORMAL)
        self.StartCollectButton.grid(row=2, columnspan=2, column=0, sticky='EW')
        self.StopCollectButton = Button(frame, text='Stop Acquire Raw Images', command=self.stop_acq_raw_img, state=DISABLED)
        self.StopCollectButton.grid(row=2, columnspan=2, column=2, sticky='EW')

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.pack(side='bottom', fill='x', padx=10, pady=10)

        self.stopEvent = threading.Event()
        self.stopPreviewEvent = threading.Event()

    def init_vars(self):
        self.var_dwell_time = DoubleVar(value=BS_OVERHEAD)
        self.var_exposure_time = DoubleVar(value=BS_OVERHEAD)
        self.var_haadf_min_radius = IntVar(value=round(self.cam_x*2/3))
        self.var_bf_max_radius = IntVar(value=round(self.cam_x/3))
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
        '''find the center of the diffraction pattern'''
        img = self.ctrl.get_image(self.var_exposure_time.get())
        img, scale = autoscale(img)
        pixel_cent = find_beam_center(img) * self.binsize / scale
        self.var_center_x.set(pixel_cent[0])
        self.var_center_y.set(pixel_cent[1])

    def makepanel(self, resolution=(128, 128)):
        image = Image.fromarray(np.zeros(resolution))
        image = ImageTk.PhotoImage(image)

        self.panel = Label(master, image=image)
        self.panel.image = image


    def start_scan(self):
        params = self.get_params('start')
        self.q.put(('scan_beam', params))
        self.triggerEvent.set()
        self.StartScanButton.config(state=DISABLED)
        self.PauseScanButton.config(state=NORMAL)
        self.StopScanButton.config(state=NORMAL)

    def pause_scan(self):
        params = self.get_params('pause')
        self.q.put(('scan_beam', params))
        self.triggerEvent.set()
        self.PauseScanButton.config(state=DISABLED)
        self.ContinueScanButton.config(state=NORMAL)
        self.StopScanButton.config(state=DISABLED)

    def continue_scan(self):
        params = self.get_params('continue')
        self.q.put(('scan_beam', params))
        self.triggerEvent.set()
        self.PauseScanButton.config(state=NORMAL)
        self.ContinueScanButton.config(state=DISABLED)
        self.StopScanButton.config(state=NORMAL)

    def stop_scan(self):
        params = self.get_params('stop')
        self.q.put(('scan_beam', params))
        self.triggerEvent.set()
        self.StartScanButton.config(state=NORMAL)
        self.PauseScanButton.config(state=DISABLED)
        self.StopScanButton.config(state=DISABLED)

    def start_virtual_img(self, event=None):
        self.virtual_img = virtual_img = FourDSTEM.VIRTUALIMGBUF.get() # obtain data from the buffer

        # the display range in ImageTk is from 0 to 256
        tmp = virtual_img - np.min(virtual_img)
        virtual_img = tmp * (256.0 / (1 + np.percentile(tmp, 99.5)))  # use 128x128 array for faster calculation

        image = Image.fromarray(virtual_img)

        image = image.resize((4*self.var_nx.get(), 4*self.var_ny.get()))

        image = ImageTk.PhotoImage(image=image)

        self.panel.configure(image=image)
        # keep a reference to avoid premature garbage collection
        self.panel.image = image

        if self.stopPreviewEvent.is_set():
            self.stopPreviewEvent.clear()
            return

        self.after(self.frame_delay, self.start_virtual_img)

    def start_preview(self):
        params = self.get_params('start')
        self.q.put(('preview_FourDSTEM', params))
        self.start_virtual_img()
        self.triggerEvent.set()
        self.StartPreviewButton.config(state=DISABLED)
        self.StopPreviewButton.config(state=NORMAL)

    def stop_preview(self):
        params = self.get_params('stop')
        self.q.put(('preview_FourDSTEM', params))
        self.triggerEvent.set()
        self.stopPreviewEvent.set()
        while True:
            time.sleep(1)
            if not self.stopPreviewEvent.is_set():
                break
        self.StartPreviewButton.config(state=NORMAL)
        self.StopPreviewButton.config(state=DISABLED)

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

    def get_params(self, task=None):
        if taks == 'start':
            params = {'dwell_time': self.var_dwell_time.get(),
                      'exposure_time': self.var_exposure_time.get(),
                      'haadf_min_radius': self.var_haadf_min_radius.get(),
                      'bf_max_radius': self.var_bf_max_radius.get(),
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
                      'save_hdf5_raw_imgs': self.var_save_hdf5_raw_imgs.get(),
                      'task': task}
        else:
            params = {'task': task}
        return params

def acquire_FourDSTEM(controller, **kwargs):
    controller.log.info('Acquire 4DSTEM virtual images')
    task = kwargs.pop('task')
    exp_param = kwargs

    expdir = controller.module_io.get_new_experiment_directory()
    expdir.mkdir(exist_ok=True, parents=True)
    flatfield = controller.module_io.get_flatfield()

    exp = FourDSTEM.Experiment(ctrl=controller.ctrl, path=expdir, flatfield=flatfield, log=controller.log, **exp_param)

    success = exp.start_collection()

    if task == 'start':
        pass
    elif task == 'stop':
        pass

def preview_FourDSTEM(controller, **kwargs):
    task = kwargs.pop('task')
    exp_param = kwargs

    
    if task == 'start':
        flatfield = controller.module_io.get_flatfield()
        controller.exp = FourDSTEM.Experiment(ctrl=controller.ctrl, path=None, flatfield=flatfield, log=controller.log, **exp_param)
        controller.exp.start_preview()
    elif task == 'stop':
        controller.exp.stop_preview()

def acquire_raw_img(controller, **kwargs):
    controller.log.info('Acquire 4DSTEM raw images')
    task = kwargs.pop('task')
    exp_param = kwargs

    expdir = controller.module_io.get_new_experiment_directory()
    expdir.mkdir(exist_ok=True, parents=True)
    flatfield = controller.module_io.get_flatfield()

    exp = FourDSTEM.Experiment(ctrl=controller.ctrl, path=expdir, flatfield=flatfield, log=controller.log, **exp_param)

    success = exp.start_collection()

    if not success:
        return

    if task == 'start':
        pass
    elif task == 'stop':
        pass

def scan_beam(controller, **kwargs):
    task = kwargs.pop('task')
    exp_param = kwargs

    if task == 'start':
        flatfield = controller.module_io.get_flatfield()
        controller.exp = FourDSTEM.Experiment(ctrl=controller.ctrl, path=None, flatfield=flatfield, log=controller.log, **exp_param)
        controller.exp.start_scan_beam()
    elif task == 'pause':
        controller.exp.pause_scan_beam()
    elif task == 'continue':
        controller.exp.continue_scan_beam()
    elif task == 'stop':
        controller.exp.stop_scan_beam()
        del controller.exp


module = BaseModule(name='FourDSTEM', display_name='FourDSTEM', tk_frame=ExperimentalFourDSTEM, location='bottom')
commands = {'acquire_FourDSTEM': acquire_FourDSTEM,
            'preview_FourDSTEM': preview_FourDSTEM,
            'acquire_raw_img': acquire_raw_img,
            'scan_beam': scan_beam}

if __name__ == '__main__':
    root = Tk()
    ExperimentalFourDSTEM(root).pack(side='top', fill='both', expand=True)
    root.mainloop()