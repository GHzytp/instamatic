import numpy as np
import time
import threading
from tkinter import *
from tkinter.ttk import *

from PIL import Image
from PIL import ImageTk

from .base_module import BaseModule
from instamatic import config
from instamatic.utils.widgets import Spinbox
from instamatic.image_utils import autoscale
from instamatic.tools import find_beam_center

from instamatic.experiments import FourDSTEM
from instamatic.experiments.FourDSTEM import virtualimage_stream

# Beam shift overhead for the microscope
BEAMSCAN_OVERHEAD = 0.003

class ExperimentalFourDSTEM(LabelFrame):
    """Software controlled beam shift operation for 4DSTEM. Currently only works for FEI microscope 
    because of the low overhead of beamshift function"""
    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='4DSTEM/Scanning Nanodiffraction')

        self.parent = parent

        from instamatic import TEMController
        self.ctrl = TEMController.get_instance()
        self.cam_x, self.cam_y = self.ctrl.cam.getCameraDimensions()
        self.binsize = self.ctrl.cam.default_binsize

        if self.cam_x != self.cam_y:
            raise RuntimeWarning("It is recommended to use a camera with equal x and y length")
            self.cam_x = min(self.cam_x, self.cam_y)

        self.panel = None
        self.frame_delay = 600
        self.virtualimage_stream = virtualimage_stream.VideoStream()

        self.init_vars()

        frame = Frame(self)
        Label(frame, text='Scanning Pattern', width=20).grid(row=0, column=0, sticky='W')
        scan_options = ['XY scan', 'YX scan', 'XY snake scan', 'YX snake scan', 'Spiral scan']
        self.e_scan_pattern = OptionMenu(frame, self.var_scan_pattern, 'XY scan', *scan_options)
        self.e_scan_pattern.grid(row=0, column=1, sticky='W', padx=5)
        frame.pack(side='top', fill='x', padx=5, pady=5)

        frame = Frame(self)
        
        Label(frame, text='Dwell Time (s)', width=20).grid(row=0, column=0, sticky='W')
        e_dwell_time = Spinbox(frame, width=10, textvariable=self.var_dwell_time, from_=BEAMSCAN_OVERHEAD, to=3.0, increment=0.001)
        e_dwell_time.grid(row=0, column=1, sticky='EW', padx=5)
        Label(frame, text='Exposure Time (s)', width=20).grid(row=0, column=2, sticky='W')
        e_dwell_time = Spinbox(frame, width=10, textvariable=self.var_exposure_time, from_=BEAMSCAN_OVERHEAD, to=3.0, increment=0.001)
        e_dwell_time.grid(row=0, column=3, sticky='EW', padx=5)

        Label(frame, text='HAADF min radius/pix', width=20).grid(row=1, column=0, sticky='W')
        e_haadf_min_radius = Spinbox(frame, width=10, textvariable=self.var_haadf_min_radius, from_=self.cam_x*2/3, to=self.cam_x, increment=1)
        e_haadf_min_radius.grid(row=1, column=1, sticky='EW', padx=5)
        Label(frame, text='BF max radius/pix', width=20).grid(row=1, column=2, sticky='W')
        e_bf_max_radius = Spinbox(frame, width=10, textvariable=self.var_bf_max_radius, from_=1, to=self.cam_x/3, increment=1)
        e_bf_max_radius.grid(row=1, column=3, sticky='EW', padx=5)

        Label(frame, text='Center X (pix)', width=20).grid(row=2, column=0, sticky='W')
        e_center_x = Spinbox(frame, width=10, textvariable=self.var_center_x, from_=0, to=self.cam_x, increment=1)
        e_center_x.grid(row=2, column=1, sticky='EW', padx=5)
        Label(frame, text='Center Y (pix)', width=20).grid(row=2, column=2, sticky='W')
        e_center_y = Spinbox(frame, width=10, textvariable=self.var_center_y, from_=0, to=self.cam_x, increment=1)
        e_center_y.grid(row=2, column=3, sticky='EW', padx=5)
        self.b_center_get = Button(frame, width=15, text='Get Center', command=self.get_center)
        self.b_center_get.grid(row=2, column=4, sticky='W', padx=5)

        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=1)
        frame.grid_columnconfigure(3, weight=1)
        frame.grid_columnconfigure(4, weight=1)
        frame.grid_columnconfigure(5, weight=1)
        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Label(frame, text='Interval X/nm', width=12).grid(row=2, column=0, sticky='W')
        e_interval_x = Spinbox(frame, width=10, textvariable=self.var_interval_x, from_=1, to=1000, increment=0.1)
        e_interval_x.grid(row=2, column=1, sticky='EW', padx=5)

        Label(frame, text='Interval Y/nm', width=12).grid(row=2, column=2, sticky='W')
        e_interval_y = Spinbox(frame, width=10, textvariable=self.var_interval_y, from_=1, to=1000, increment=0.1)
        e_interval_y.grid(row=2, column=3, sticky='EW', padx=5)

        Label(frame, text='NX', width=5).grid(row=2, column=4, sticky='W')
        e_nx = Spinbox(frame, width=10, textvariable=self.var_nx, from_=2, to=128, increment=1)
        e_nx.grid(row=2, column=5, sticky='EW', padx=5)

        Label(frame, text='NY', width=5).grid(row=2, column=6, sticky='W')
        e_ny = Spinbox(frame, width=10, textvariable=self.var_ny, from_=2, to=128, increment=1)
        e_ny.grid(row=2, column=7, sticky='EW', padx=5)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Label(frame, text='Select virtual image types:').grid(row=4, columnspan=2, sticky='EW')
        Checkbutton(frame, text='HAADF', variable=self.var_haadf).grid(row=4, column=2, sticky='EW')
        Checkbutton(frame, text='ADF', variable=self.var_adf).grid(row=4, column=3, sticky='EW')
        Checkbutton(frame, text='BF', variable=self.var_bf).grid(row=4, column=4, sticky='EW')

        Label(frame, text='Select output formats for virtual images:').grid(row=5, columnspan=3, sticky='EW')
        Checkbutton(frame, text='.tiff', variable=self.var_save_tiff_4DSTEM).grid(row=5, column=3, sticky='EW')
        Checkbutton(frame, text='.hdf5', variable=self.var_save_hdf5_4DSTEM).grid(row=5, column=4, sticky='EW')

        Label(frame, text='Select output formats for raw images:').grid(row=6, columnspan=3, sticky='EW')
        Checkbutton(frame, text='.tiff', variable=self.var_save_tiff_raw_imgs).grid(row=6, column=3, sticky='EW')
        Checkbutton(frame, text='.hdf5', variable=self.var_save_hdf5_raw_imgs).grid(row=6, column=4, sticky='EW')

        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=1)
        frame.grid_columnconfigure(3, weight=1)
        frame.grid_columnconfigure(4, weight=1)
        frame.pack(side='top', fill='x', padx=5, pady=5)

        frame = Frame(self)

        self.lb_col = Label(frame, text='')
        self.lb_col.grid(row=0, column=0, columnspan=4, padx=5, pady=5, sticky='EW')

        self.StartScanButton = Button(frame, text='Start Scanning', command=self.start_scan, state=NORMAL)
        self.StartScanButton.grid(row=2, column=0, sticky='EW')
        self.StopScanButton = Button(frame, text='Stop Scanning', command=self.stop_scan, state=DISABLED)
        self.StopScanButton.grid(row=2, column=1, padx=10, sticky='EW')
        self.PauseScanButton = Button(frame, text='Pause Scanning', command=self.pause_scan, state=DISABLED)
        self.PauseScanButton.grid(row=3, column=0, sticky='EW')
        self.ContinueScanButton = Button(frame, text='Continue Scanning', command=self.continue_scan, state=DISABLED)
        self.ContinueScanButton.grid(row=3, column=1, padx=10, sticky='EW')
        Separator(frame, orient=HORIZONTAL).grid(row=4, columnspan=2, sticky='EW', padx=10, pady=5)

        self.StartPreviewButton = Button(frame, text='Start Preview', command=self.start_preview, state=NORMAL)
        self.StartPreviewButton.grid(row=5, column=0, sticky='EW')
        self.StopPreviewButton = Button(frame, text='Stop Preview', command=self.stop_preview, state=DISABLED)
        self.StopPreviewButton.grid(row=5, column=1, padx=10, sticky='EW')
        Separator(frame, orient=HORIZONTAL).grid(row=6, columnspan=2, sticky='EW', padx=10, pady=5)

        self.StartAcquireButton = Button(frame, text='Start Acquire', command=self.start_acquire, state=NORMAL)
        self.StartAcquireButton.grid(row=7, column=0, sticky='EW')
        self.StopAcquireButton = Button(frame, text='Stop Acquire', command=self.stop_acquire, state=DISABLED)
        self.StopAcquireButton.grid(row=7, column=1, padx=10, sticky='EW')

        self.StartAcqRawImgButton = Button(frame, text='Start Acquire Raw Img', command=self.start_acq_raw_img, state=NORMAL)
        self.StartAcqRawImgButton.grid(row=8, column=0, sticky='EW')
        self.StopAcqRawImgButton = Button(frame, text='Stop Acquire Raw Img', command=self.stop_acq_raw_img, state=DISABLED)
        self.StopAcqRawImgButton.grid(row=8, column=1, padx=10, sticky='EW')
        Separator(frame, orient=HORIZONTAL).grid(row=9, columnspan=2, sticky='EW', padx=10, pady=5)

        self.StartAcqOneButton = Button(frame, text='Acquire One Virtual Img', command=self.acq_one_virtual_img, state=NORMAL)
        self.StartAcqOneButton.grid(row=10, column=0, sticky='EW')
        Checkbutton(frame, text='Save Raw Images', variable=self.var_save_raw_imgs).grid(row=10, column=1, padx=10, sticky='EW')

        x = self.var_nx.get() * self.var_interval_x.get()
        y = self.var_ny.get() * self.var_interval_y.get()
        ratio = min(200/x, 200/y)
        image = Image.fromarray(np.zeros((int(ratio*x), int(ratio*y))))
        image = ImageTk.PhotoImage(image)

        self.panel = Label(frame, image=image)
        self.panel.image = image
        self.panel.grid(row=2, rowspan=9, column=2, sticky='EW')

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.pack(side='bottom', fill='x', padx=5, pady=5)

        self.stopPreviewEvent = threading.Event()
        self.acqFinishedEvent = threading.Event()

    def init_vars(self):
        self.var_dwell_time = DoubleVar(value=BEAMSCAN_OVERHEAD)
        self.var_exposure_time = DoubleVar(value=BEAMSCAN_OVERHEAD)
        self.var_scan_pattern = StringVar(value='XY scan')
        self.var_haadf_min_radius = IntVar(value=round(self.cam_x*2/5))
        self.var_bf_max_radius = IntVar(value=round(self.cam_x/6))
        self.var_center_x = DoubleVar(value=self.cam_x/2)
        self.var_center_y = DoubleVar(value=self.cam_x/2)
        self.var_interval_x = DoubleVar(value=100)
        self.var_interval_y = DoubleVar(value=100)
        self.var_nx = IntVar(value=4)
        self.var_ny = IntVar(value=4)
        self.var_save_tiff_4DSTEM = BooleanVar(value=True)
        self.var_save_hdf5_4DSTEM = BooleanVar(value=True)
        self.var_save_tiff_raw_imgs = BooleanVar(value=True)
        self.var_save_hdf5_raw_imgs = BooleanVar(value=True)
        self.var_haadf = BooleanVar(value=True)
        self.var_adf = BooleanVar(value=False)
        self.var_bf = BooleanVar(value=False)
        self.var_save_raw_imgs = BooleanVar(value=True)

    def get_center(self):
        '''find the center of the diffraction pattern'''
        img, h = self.ctrl.get_image(self.var_exposure_time.get())
        pixel_cent = find_beam_center(img)
        self.var_center_x.set(pixel_cent[0])
        self.var_center_y.set(pixel_cent[1])

    def start_scan(self):
        params = self.get_params('start')
        self.q.put(('scan_beam', params))
        self.triggerEvent.set()
        self.StartScanButton.config(state=DISABLED)
        self.PauseScanButton.config(state=NORMAL)
        self.StopScanButton.config(state=NORMAL)
        self.lb_col.config(text='Beam scan started. Before click preview or acquire functions, you must click STOP SCAN.')

    def pause_scan(self):
        params = self.get_params('pause')
        self.q.put(('scan_beam', params))
        self.triggerEvent.set()
        self.PauseScanButton.config(state=DISABLED)
        self.ContinueScanButton.config(state=NORMAL)
        self.StopScanButton.config(state=DISABLED)
        self.lb_col.config(text='Beam scan paused. Before click preview or acquire functions, you must click STOP SCAN.')

    def continue_scan(self):
        params = self.get_params('continue')
        self.q.put(('scan_beam', params))
        self.triggerEvent.set()
        self.PauseScanButton.config(state=NORMAL)
        self.ContinueScanButton.config(state=DISABLED)
        self.StopScanButton.config(state=NORMAL)
        self.lb_col.config(text='Beam scan continued. Before click preview or acquire functions, you must click STOP SCAN.')

    def stop_scan(self):
        params = self.get_params('stop')
        self.q.put(('scan_beam', params))
        self.triggerEvent.set()
        self.StartScanButton.config(state=NORMAL)
        self.PauseScanButton.config(state=DISABLED)
        self.StopScanButton.config(state=DISABLED)
        self.lb_col.config(text='Beam scan stopped. Now you can move to other operations.')

    def start_virtual_img(self, event=None):
        #self.virtual_img = virtual_img = FourDSTEM.VIRTUALIMGBUF.get() # obtain data from the buffer
        virtual_img = self.virtualimage_stream.frame
        # the display range in ImageTk is from 0 to 256
        tmp = virtual_img - np.min(virtual_img)
        virtual_img = tmp * (256.0 / (1 + np.percentile(tmp, 99.5)))  # use 128x128 array for faster calculation

        image = Image.fromarray(virtual_img)

        x = self.var_nx.get() * self.var_interval_x.get()
        y = self.var_ny.get() * self.var_interval_y.get()
        ratio = min(200/x, 200/y)
        image = image.resize((int(ratio*x), int(ratio*y)))

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
        self.triggerEvent.set()
        self.start_virtual_img()

        self.StartPreviewButton.config(state=DISABLED)
        self.StopPreviewButton.config(state=NORMAL)
        self.lb_col.config(text='Preview virtual image started. Be sure to click STOP PREVIEW before you start any other operations.')

    def stop_preview(self):
        params = self.get_params('stop')
        self.q.put(('preview_FourDSTEM', params))
        self.triggerEvent.set()
        self.stopPreviewEvent.set()

        self.StartPreviewButton.config(state=NORMAL)
        self.StopPreviewButton.config(state=DISABLED)
        self.lb_col.config(text='Preview virtual image stopped. Now you can start other operations.')

    def start_acquire(self):
        params = self.get_params('start')
        self.q.put(('acquire_FourDSTEM', params))
        self.triggerEvent.set()
        self.start_virtual_img()

        self.StartAcquireButton.config(state=DISABLED)
        self.StopAcquireButton.config(state=NORMAL)
        self.lb_col.config(text='Acquire virtual image started. Be sure to click STOP ACQUIRE before you start any other operations.')

    def stop_acquire(self):
        params = self.get_params('stop')
        self.q.put(('acquire_FourDSTEM', params))
        self.triggerEvent.set()
        self.stopPreviewEvent.set()

        self.StartAcquireButton.config(state=NORMAL)
        self.StopAcquireButton.config(state=DISABLED)
        self.lb_col.config(text='Acquire virtual image stopped. Now you can start other operations.')

    def start_acq_raw_img(self):
        params = self.get_params('start')
        self.q.put(('acquire_raw_img', params))
        self.triggerEvent.set()
        self.start_virtual_img()

        self.StartAcqRawImgButton.config(state=DISABLED)
        self.StopAcqRawImgButton.config(state=NORMAL)
        self.lb_col.config(text='Acquire raw image started. Be sure to stop the acquisition before you start any other operations.')

    def stop_acq_raw_img(self):
        params = self.get_params('stop')
        self.q.put(('acquire_raw_img', params))
        self.triggerEvent.set()
        self.stopPreviewEvent.set()

        self.StartAcqRawImgButton.config(state=NORMAL)
        self.StopAcqRawImgButton.config(state=DISABLED)
        self.lb_col.config(text='Acquire raw image stopped. Now you can start other operations.')

    def acq_one_virtual_img(self):
        params = self.get_params('start')
        self.q.put(('acquire_one_virtual_img', params))
        self.triggerEvent.set()
        self.start_virtual_img()

        if self.var_save_raw_imgs:
            self.lb_col.config(text='Acquiring one virtual image and corresponding raw images. Do not start any other operations')
        else:
            self.lb_col.config(text='Acquiring one virtual image. Do not start any other operations')
        self.StartAcqOneButton.config(state=DISABLED)

        def acquisition_finished():
            self.acqFinishedEvent.wait()
            self.stopPreviewEvent.set()
            self.StartAcqOneButton.config(state=NORMAL)
            self.lb_col.config(text = 'Acquisition finished. Now you can start other operations.')
            self.acqFinishedEvent.clear()
        p = threading.Thread(target=acquisition_finished, args=())
        p.start()
        
        
    def set_trigger(self, trigger=None, q=None):
        self.triggerEvent = trigger
        self.q = q

    def get_params(self, task=None):
        if task == 'start':
            params = {'scan_pattern': self.var_scan_pattern.get(),
                      'dwell_time': self.var_dwell_time.get(),
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
                      'save_tiff_4DSTEM': self.var_save_tiff_4DSTEM.get(),
                      'save_hdf5_4DSTEM': self.var_save_hdf5_4DSTEM.get(),
                      'save_tiff_raw_imgs': self.var_save_tiff_raw_imgs.get(),
                      'save_hdf5_raw_imgs': self.var_save_hdf5_raw_imgs.get(),
                      'save_raw_imgs': self.var_save_raw_imgs.get(),
                      'acquisition_finished': self.acqFinishedEvent,
                      'task': task}
        else:
            params = {'task': task}
        return params

def acquire_FourDSTEM(controller, **kwargs):
    controller.log.info('Acquire 4DSTEM virtual images')
    task = kwargs.pop('task')
    exp_param = kwargs

    if task == 'start':
        expdir = controller.module_io.get_new_experiment_directory()
        expdir.mkdir(exist_ok=True, parents=True)
        flatfield = controller.module_io.get_flatfield()
        controller.exp = FourDSTEM.Experiment(ctrl=controller.ctrl, path=expdir, flatfield=flatfield, log=controller.log, **exp_param)
        controller.exp.start_acquire()
    elif task == 'stop':
        controller.exp.stop_acquire()
        del controller.exp

def preview_FourDSTEM(controller, **kwargs):
    task = kwargs.pop('task')
    exp_param = kwargs
    
    if task == 'start':
        flatfield = controller.module_io.get_flatfield()
        controller.exp = FourDSTEM.Experiment(ctrl=controller.ctrl, path=None, flatfield=flatfield, log=controller.log, **exp_param)
        controller.exp.start_preview()
    elif task == 'stop':
        controller.exp.stop_preview()
        del controller.exp

def acquire_raw_img(controller, **kwargs):
    controller.log.info('Acquire 4DSTEM raw images')
    task = kwargs.pop('task')
    exp_param = kwargs

    if task == 'start':
        expdir = controller.module_io.get_new_experiment_directory()
        expdir.mkdir(exist_ok=True, parents=True)
        flatfield = controller.module_io.get_flatfield()
        controller.exp = FourDSTEM.Experiment(ctrl=controller.ctrl, path=expdir, flatfield=flatfield, log=controller.log, **exp_param)
        controller.exp.start_acq_raw_img()
    elif task == 'stop':
        controller.exp.stop_acq_raw_img()
        del controller.exp

def acquire_one_virtual_img(controller, **kwargs):
    controller.log.info('Acquire 4DSTEM one virtual image')
    task = kwargs.pop('task')
    exp_param = kwargs

    expdir = controller.module_io.get_new_experiment_directory()
    expdir.mkdir(exist_ok=True, parents=True)
    flatfield = controller.module_io.get_flatfield()
    exp = FourDSTEM.Experiment(ctrl=controller.ctrl, path=expdir, flatfield=flatfield, log=controller.log, **exp_param)
    exp.acquire_one_virtual_img()

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
            'acquire_one_virtual_img': acquire_one_virtual_img,
            'scan_beam': scan_beam}

def run(ctrl, trigger, q):
    from .modules import JOBS

    while True:
        trigger.wait()
        trigger.clear()

        job, kwargs = q.get()
        try:
            print(job)
            func = JOBS[job]
        except KeyError:
            print(f'Unknown job: {job}')
            print(f'Kwargs:\n{kwargs}')
            continue
        func(ctrl, **kwargs)


if __name__ == '__main__':
    import threading
    import queue
    import logging
    from .io_frame import module as io_module
    
    logger = logging.getLogger(__name__)

    root = Tk()
    root.title('4DSTEM')
    trigger = threading.Event()
    q = queue.Queue(maxsize=1)
    ctrl = ExperimentalFourDSTEM(root)
    ctrl.pack(side='top', fill='both', expand=True)
    ctrl.set_trigger(trigger=trigger, q=q)
    ctrl.module_io = io_module.initialize(root)
    ctrl.log = logger

    p = threading.Thread(target=run, args=(ctrl,trigger,q,))
    p.start()

    root.mainloop()
    ctrl.ctrl.close()
