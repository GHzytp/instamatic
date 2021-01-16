import numpy as np
import time
import threading
import atexit
from pathlib import Path
from tkinter import *
from tkinter.ttk import *
import tkinter

from PIL import Image
from PIL import ImageTk

from .base_module import BaseModule
from instamatic import config
from instamatic.utils.widgets import Spinbox
from .io_frame import module as io_module

class ExperimentalFocusSeries(LabelFrame):
    """GUI frame for collecting focus series data"""
    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Acqurie Focus Series')

        self.parent = parent
        self.workdrc = Path(config.settings.work_directory)

        from instamatic import TEMController
        self.ctrl = TEMController.get_instance()
        #self.io_module = io_module.initialize(parent)
        self.cam_x, self.cam_y = self.ctrl.cam.getCameraDimensions()

        self.image_buffer = []

        self.init_vars()

        frame = Frame(self)

        Label(frame, text='Exposure Time', width=15).grid(row=0, column=0, sticky='W')
        e_exposure_time = Spinbox(frame, width=10, textvariable=self.var_exposure_time, from_=self.ctrl.cam.default_exposure*2, to=30, increment=self.ctrl.cam.default_exposure)
        e_exposure_time.grid(row=0, column=1, sticky='EW', padx=5)

        Label(frame, text='Focus Interval', width=15).grid(row=0, column=2, sticky='W')
        e_exposure_time = Spinbox(frame, width=10, textvariable=self.var_focus_interval, from_=-10000, to=10000, increment=1)
        e_exposure_time.grid(row=0, column=3, sticky='EW', padx=5)

        Checkbutton(frame, text='Beam unblanker', variable=self.var_unblank_beam, command=self.toggle_unblankbeam).grid(row=0, column=4, sticky='EW')
        Checkbutton(frame, text='Align frames', variable=self.var_align_frames).grid(row=0, column=5, sticky='EW')

        Checkbutton(frame, text='Save frames', variable=self.var_save_frames).grid(row=2, column=0, sticky='EW')

        self.directory = Entry(frame, width=50, textvariable=self.var_directory)
        self.directory.grid(row=2, column=1, columnspan=4, sticky='EW', padx=10, pady=5)

        self.BrowseButton = Button(frame, text='Browse..', command=self.browse_directory)
        self.BrowseButton.grid(row=2, column=5, sticky='EW', pady=5)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        self.lb_col = Label(frame, text='')
        self.lb_col.grid(row=0, column=0, columnspan=3, padx=5, sticky='EW')

        self.b_acquire_one_image = Button(frame, width=20, text='Acquire One Image', command=self.acquire_one_image, state=NORMAL)
        self.b_acquire_one_image.grid(row=1, column=0, sticky='W', padx=5)
        
        Separator(frame, orient=HORIZONTAL).grid(row=2, sticky='EW', padx=5, pady=5)

        self.b_acquire_focus_series = Button(frame, width=20, text='Acquire Focus Series', command=self.acquire_focus_series, state=NORMAL)
        self.b_acquire_focus_series.grid(row=3, column=0, sticky='W', padx=5)
        self.b_pause_acquisition = Button(frame, width=20, text='Pause Acquisition', command=self.pause_acquisition, state=DISABLED)
        self.b_pause_acquisition.grid(row=4, column=0, sticky='W', padx=5)
        self.b_continue_acquisition = Button(frame, width=20, text='Continue Acquiren', command=self.continue_acquisition, state=DISABLED)
        self.b_continue_acquisition.grid(row=5, column=0, sticky='W', padx=5)
        self.b_stop_acquisition = Button(frame, width=20, text='Stop Acqusition', command=self.stop_acquisition, state=DISABLED)
        self.b_stop_acquisition.grid(row=6, column=0, sticky='W', padx=5)

        Separator(frame, orient=HORIZONTAL).grid(row=7, sticky='EW', padx=5, pady=5)

        self.b_save_image_buffer = Button(frame, width=20, text='Save Image Buffer', command=self.save_image_buffer, state=NORMAL)
        self.b_save_image_buffer.grid(row=8, column=0, sticky='W', padx=5)

        self.l_dummy = Label(frame, text='', width=20)
        self.l_dummy.grid(row=9, column=0, pady=100)

        image = Image.fromarray(np.zeros((self.cam_x, self.cam_y)))
        self.ratio = min(400 / self.cam_x, 400 / self.cam_y)
        self.dim_x = int(self.ratio * self.cam_x)
        self.dim_y = int(self.ratio * self.cam_y)
        image = image.resize((self.dim_x, self.dim_y))
        self.image = image = ImageTk.PhotoImage(image)

        self.panel = Label(frame, image=image)
        self.panel.image = image
        self.panel.grid(row=1, rowspan=9, column=1, sticky='EW')

        self.frame_slide = tkinter.Scale(frame, variable=self.var_frame_num, from_=0, to=0, resolution=1, length=250, 
                showvalue=0, orient=VERTICAL, command=self.show_frame)
        self.frame_slide.grid(row=1, rowspan=9, column=2, sticky='NS')

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        frame.pack(side='bottom', fill='x', expand=False, padx=5, pady=5)

    def init_vars(self):
        self.var_exposure_time = DoubleVar(value=round(round(1.5/self.ctrl.cam.default_exposure)*self.ctrl.cam.default_exposure, 1))
        self.var_focus_interval = IntVar(value=30)
        self.var_unblank_beam = BooleanVar(value=True)
        self.var_align_frames = BooleanVar(value=False)
        self.var_directory = StringVar(value=self.workdrc.absolute())
        self.var_frame_num = IntVar(value=0)
        self.var_save_frames = BooleanVar(value=True)

    def browse_directory(self):
        drc = tkinter.filedialog.askdirectory(parent=self.parent, title='Select working directory')
        if not drc:
            return
        drc = Path(drc).absolute()
        self.var_directory.set(drc)

    def toggle_unblankbeam(self):
        toggle = self.var_unblank_beam.get()

        if toggle:
            self.ctrl.beam.unblank()
        else:
            self.ctrl.beam.blank()

    def acquire_one_image(self):
        self.image_buffer = []

        if self.var_align_frames.get():
            pass
        else:
            img, h = self.ctrl.get_image(self.var_exposure_time.get())
            self.image_buffer.append((img, h))
            tmp = img - np.min(img[::8, ::8])
            image = tmp * (256.0 / (1 + np.percentile(tmp[::8, ::8], 99.5)))
            image = Image.fromarray(image)
            image = image.resize((self.dim_x, self.dim_y))
            self.image = image = ImageTk.PhotoImage(image)

            self.panel.configure(image=image)

            self.var_frame_num.set(1)
            self.lb_col.config(text='Acquired one image')
            self.frame_slide.config(from_=1, to=1)

    def acquire_focus_series(self):
        pass

    def pause_acquisition(self):
        pass

    def continue_acquisition(self):
        pass

    def stop_acquisition(self):
        pass

    def show_frame(self, value):
        pass

    def save_image_buffer(self):
        pass


module = BaseModule(name='FocusSeries', display_name='FocusSeries', tk_frame=ExperimentalFocusSeries, location='bottom')
commands = {}

if __name__ == '__main__':
    root = Tk()
    ExperimentalFocusSeries(root).pack(side='top', fill='both', expand=True)
    root.mainloop()
    