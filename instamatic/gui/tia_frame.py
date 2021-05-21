import threading
import time
from datetime import datetime
import tkinter
from tkinter import *
from tkinter.ttk import *
from tkinter import messagebox

import numpy as np
import numexpr as ne
from PIL import Image
from PIL import ImageEnhance
from PIL import ImageTk

from .base_module import BaseModule
from .modules import MODULES
from instamatic import config
from instamatic.formats import read_tiff, write_tiff
from instamatic.utils.widgets import Spinbox, Hoverbox
from instamatic.TEMController import get_instance

class TIAFrame(LabelFrame):
    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Operations from TIA')
        self.parent = parent
        self.frame = None
        self.frame_delay = 1000
        self.panel = None
        self.brightness = 1.0
        self.display_range = 65535
        self.start_event = threading.Event()
        self.start_event.clear()
        self.continue_event = threading.Event()
        self.continue_event.set()
        self.stop_event = threading.Event()
        self.stop_event.clear()
        self.ctrl = get_instance()
        self.stream_frame = [module for module in MODULES if module.name == 'stream'][0].frame
        self.dimension = (np.array(self.stream_frame.dimension)*0.9).astype(np.uint16)
        self.drc = config.locations['work']
        self.h = {}
        if self.ctrl.sw is None:
            self.window_options = []
            self.display_options = []
            self.image_options = []
            self.signal_options = []
        else:
            self.window_options = self.ctrl.sw.DisplayWindowNames()
            try:
                self.display_options = self.ctrl.sw.DisplayNames(self.window_options[0])
            except IndexError:
                self.display_options = []
            try:
                self.image_options = self.ctrl.sw.ObjectNames(self.window_options[0], self.display_options[0])['Images']
            except IndexError:
                self.image_options = []
            self.signal_options = self.ctrl.sw.SignalNames()

        self.init_vars()
        self.buttonbox(self)
        self.header(self)
        self.makepanel(self, dimension=self.dimension)

    def init_vars(self):
        self.var_brightness = DoubleVar(value=self.brightness)
        self.var_display_range = DoubleVar(value=self.display_range)
        self.var_auto_contrast = BooleanVar(value=True)
        self.var_cam_acq_mode = StringVar(value="single shot")
        self.var_interval = DoubleVar(value=1)

        self.var_window = StringVar(value="")
        self.var_display = StringVar(value="")
        self.var_image = StringVar(value="")
        self.var_signal = StringVar(value="")

    def buttonbox(self, master):
        frame = Frame(master)
        self.btn_acquire = Button(frame, text='Acquire Image', command=self.acquire_image)
        self.btn_acquire.grid(row=0, column=0, sticky='EW', padx=5)
        self.btn_save = Button(frame, text='Save Frame', command=self.save_frame)
        self.btn_save.grid(row=0, column=1, sticky='EW', padx=5)
        self.btn_start = Button(frame, text='Start Stream', command=self.start_stream, state=NORMAL)
        self.btn_start.grid(row=0, column=2, sticky='EW', padx=5)

        self.btn_pause = Button(frame, text='Pause Stream', command=self.pause_stream, state=DISABLED)
        self.btn_pause.grid(row=1, column=0, sticky='EW', padx=5)
        self.btn_continue = Button(frame, text='Continue Stream', command=self.continue_stream, state=DISABLED)
        self.btn_continue.grid(row=1, column=1, sticky='EW', padx=5)
        self.btn_stop = Button(frame, text='Stop Stream', command=self.stop_stream, state=DISABLED)
        self.btn_stop.grid(row=1, column=2, sticky='EW', padx=5)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=1)
        frame.pack(side='bottom', fill='both')

    def header(self, master):
        ewidth = 5
        lwidth = 10
        frame = Frame(master)
        self.cb_contrast = Checkbutton(frame, text='Auto contrast', variable=self.var_auto_contrast)
        self.cb_contrast.grid(row=1, column=1)
        Label(frame, text='Brightness').grid(row=1, column=2, padx=5)
        self.e_brightness = Spinbox(frame, width=ewidth, textvariable=self.var_brightness, from_=0.0, to=10.0, increment=0.1)
        self.e_brightness.grid(row=1, column=3)
        Label(frame, text=' Display Range').grid(row=1, column=4, padx=5)
        self.e_display_range = Spinbox(frame, width=ewidth, textvariable=self.var_display_range, from_=1, to=self.display_range, increment=1000)
        self.e_display_range.grid(row=1, column=5)
        Label(frame, text='Interval').grid(row=1, column=6, padx=5)
        self.e_interval = Spinbox(frame, width=ewidth, textvariable=self.var_interval, from_=0.3, to=10, increment=0.1)
        self.e_interval.grid(row=1, column=7)
        frame.pack()

        frame = Frame(master)
        Label(frame, width=8, text='Window:').grid(row=1, column=0)
        self.o_window = OptionMenu(frame, self.var_window, "", *self.window_options)
        self.o_window.config(width=lwidth)
        self.o_window.grid(row=1, column=1, sticky='EW')
        Button(frame, text='Update', command=self.get_window_name).grid(row=1, column=2, sticky='EW')
        Label(frame, width=8, text='Display:').grid(row=1, column=3)
        self.o_display = OptionMenu(frame, self.var_display, "", *self.display_options)
        self.o_display.config(width=lwidth)
        self.o_display.grid(row=1, column=4, sticky='EW')
        Button(frame, text='Update', command=self.get_display_name).grid(row=1, column=5, sticky='EW')

        Label(frame, width=8, text='Image:').grid(row=2, column=0)
        self.o_image = OptionMenu(frame, self.var_image, "", *self.image_options)
        self.o_image.config(width=lwidth)
        self.o_image.grid(row=2, column=1, sticky='EW')
        Button(frame, text='Update', command=self.get_image_name).grid(row=2, column=2, sticky='EW')
        Label(frame, width=8, text='Mode:').grid(row=2, column=3)
        self.o_cam_acq_mode = OptionMenu(frame, self.var_cam_acq_mode, "single shot", "single shot", "continuous")
        self.o_cam_acq_mode.config(width=lwidth)
        self.o_cam_acq_mode.grid(row=2, column=4, sticky='EW')
        Label(frame, width=8, text='Signal:').grid(row=2, column=5)
        self.o_signal = OptionMenu(frame, self.var_signal, "", *self.signal_options)
        self.o_signal.config(width=lwidth)
        self.o_signal.grid(row=2, column=6, sticky='EW')

        frame.pack()

    def makepanel(self, master, dimension=(512, 512)):
        if self.panel is None:
            self.frame_stream = np.zeros(dimension, dtype=np.float32)
            image = Image.fromarray(self.frame_stream)
            image = ImageTk.PhotoImage(image)
            self.image = image
            self.panel = Canvas(master, width=dimension[1], height=dimension[0])
            self.image_on_panel = self.panel.create_image(0, 0, anchor=NW, image=image)
            self.panel.pack(side='left', padx=5, pady=5)

    def get_window_name(self, event=None):
        self.window_options = self.ctrl.sw.DisplayWindowNames()
        menu = self.o_window["menu"]
        menu.delete(0, "end")
        for string in self.window_options:
            menu.add_command(label=string, command=tkinter._setit(self.var_window, string))
        self.get_display_name()
            
    def get_display_name(self, event=None):
        if self.var_window.get != '':
            self.display_options = self.ctrl.sw.DisplayNames(self.var_window.get())
            self.var_display.set("")
            menu = self.o_display["menu"]
            menu.delete(0, "end")
            for string in self.display_options:
                menu.add_command(label=string, command=tkinter._setit(self.var_display, string))
            self.var_display.set(self.display_options[0])
            self.get_image_name()

    def get_image_name(self, event=None):
        if self.var_window.get() != '' and self.var_display.get() != '':
            self.image_options = self.ctrl.sw.ObjectNames(self.var_window.get(), self.var_display.get())['Images']
            self.var_image.set("")
            menu = self.o_image["menu"]
            menu.delete(0, "end")
            for string in self.image_options:
                menu.add_command(label=string, command=tkinter._setit(self.var_image, string))
            self.var_image.set(self.image_options[0])

    def acquire_image(self):
        if self.ctrl.sw.IsAcquiring():
            print('TIA is acquiring an image already.')
            return
        if self.var_cam_acq_mode.get() == 'continuous':
            print('The acquisition mode of cam must be in single mode.')
            return
        window_name = self.var_window.get()
        display_name = self.var_display.get()
        image_name = self.var_image.get()
        if window_name == "" or display_name == "" or image_name == "":
            print('Please select the window or display or image name.')
            return
        arr, h = self.ctrl.get_tia_image(window_name, display_name, image_name)
        self.h = h
        self.image_info = self.ctrl.sw.getImageInfo(window_name, display_name, image_name)
        self.h['ImagePixelsize'] = self.image_info['Calibration']['DeltaX'] * 1e9
        self.h['ImageResolution'] = (self.image_info['PixelsX'], self.image_info['PixelsY'])
        timestamp = datetime.now().strftime('%H-%M-%S.%f')[:-3]  # cut last 3 digits for ms resolution
        outfile = self.drc / f'frame_{timestamp}.tiff'
        write_tiff(outfile, arr, header=self.h)
        self.frame = frame = arr

        if self.var_auto_contrast.get():
            tmp = frame - np.min(frame[::8, ::8])
            large = np.percentile(tmp[::8, ::8], 99.5)
            frame = ne.evaluate('tmp * (256.0 / (1 + large))')  # use 128x128 array for faster calculation
            image = Image.fromarray(frame)
        elif self.display_range != self.display_range_default:
            image = np.clip(frame, 0, self.display_range)
            image = (256.0 / self.display_range) * image
            image = Image.fromarray(image)
        else:
            image = Image.fromarray(frame)

        if self.brightness != 1:
            image = ImageEnhance.Brightness(image.convert('L')).enhance(self.brightness)

        image = image.resize(self.dimension)
        image = ImageTk.PhotoImage(image=image)
        self.panel.itemconfig(self.image_on_panel, image=image)
        self.image = image

    def save_frame(self):
        """Dump the current frame to a file."""
        self.q.put(('save_image', {'frame': self.frame}))
        self.triggerEvent.set()

    def stream(self):
        if self.ctrl.sw.IsAcquiring():
            print('TIA is acquiring an image already.')
            return
        self.h = {}
        window_name = self.var_window.get()
        display_name = self.var_display.get()
        image_name = self.var_image.get()
        if window_name == "" or display_name == "" or image_name == "":
            print('Please select the window or display or image name.')
            return
        self.image_info = self.ctrl.sw.getImageInfo(window_name, display_name, image_name)
        self.h['ImagePixelsize'] = self.image_info['Calibration']['DeltaX'] * 1e9
        self.h['ImageResolution'] = (self.image_info['PixelsX'], self.image_info['PixelsY'])

        if self.var_cam_acq_mode.get() == 'continuous':
            if self.ctrl.sw.CanStart:
                self.ctrl.sw.Start()
            else:
                print('Cannot start the camera now.')
                return
            while not self.stop_event.is_set():
                self.continue_event.wait()
                self.frame_stream = self.ctrl.sw.getImageArray(window_name, display_name, image_name)
                time.sleep(self.var_interval.get())
        elif self.var_cam_acq_mode.get() == 'single shot':
            while not self.stop_event.is_set():
                self.continue_event.wait()
                self.ctrl.sw.Acquire()
                self.frame_stream = self.ctrl.sw.getImageArray(window_name, display_name, image_name)

    def start_stream(self):
        self.start_event.set()
        self.stop_event.clear()
        self.continue_event.set()
        t = threading.Thread(target=self.stream, args=(), daemon=True)
        t.start()
        self.btn_start.config(state=DISABLED)
        self.btn_continue.config(state=NORMAL)
        self.btn_pause.config(state=NORMAL)
        self.btn_stop.config(state=NORMAL)
        self.after(int(self.var_interval.get()*1000), self.on_frame)

    def on_frame(self, event=None):
        self.frame = frame = self.frame_stream

        # the display range in ImageTk is from 0 to 256
        if self.var_auto_contrast.get():
            tmp = frame - np.min(frame[::8, ::8])
            large = np.percentile(tmp[::8, ::8], 99.5)
            frame = ne.evaluate('tmp * (256.0 / (1 + large))')  # use 128x128 array for faster calculation
            image = Image.fromarray(frame)
        elif self.display_range != self.display_range_default:
            image = np.clip(frame, 0, self.display_range)
            image = (256.0 / self.display_range) * image
            image = Image.fromarray(image)
        else:
            image = Image.fromarray(frame)

        if self.brightness != 1:
            image = ImageEnhance.Brightness(image.convert('L')).enhance(self.brightness)
            # Can also use ImageEnhance.Sharpness or ImageEnhance.Contrast if needed

        image = image.resize(self.dimension)
        image = ImageTk.PhotoImage(image=image)
        self.panel.itemconfig(self.image_on_panel, image=image)
        # keep a reference to avoid premature garbage collection
        self.image = image

        self.after(int(self.var_interval.get()*1000), self.on_frame)

    def pause_stream(self):
        self.continue_event.clear()
        self.btn_continue.config(state=NORMAL)
        self.btn_pause.config(state=DISABLED)

    def continue_stream(self):
        self.continue_event.set()
        self.btn_continue.config(state=DISABLED)
        self.btn_pause.config(state=NORMAL)

    def stop_stream(self):
        if self.var_cam_acq_mode == 'continuous':
            if self.ctrl.sw.CanStop:
                self.ctrl.sw.Stop()
        self.frame = None
        self.start_event.clear()
        self.continue_event.set()
        self.stop_event.set()
        self.btn_start.config(state=NORMAL)
        self.btn_continue.config(state=DISABLED)
        self.btn_pause.config(state=DISABLED)
        self.btn_stop.config(state=DISABLED)

    def set_trigger(self, trigger=None, q=None):
        self.triggerEvent = trigger
        self.q = q


module = BaseModule(name='tia', display_name='TIA', tk_frame=TIAFrame, location='left')
commands = {}

if __name__ == '__main__':
    root = Tk()
    TIAFrame(root).pack(side='top', fill='both', expand=True)
    root.mainloop()