import threading
import time
from datetime import datetime
from tkinter import *
from tkinter.ttk import *

import numpy as np
import numexpr as ne
from PIL import Image
from PIL import ImageEnhance
from PIL import ImageTk

from .base_module import BaseModule
from instamatic import config
from instamatic.formats import read_tiff
from instamatic.formats import write_tiff
from instamatic.processing import apply_stretch_correction, apply_flatfield_correction
from instamatic.utils.widgets import Spinbox, Hoverbox
from instamatic.TEMController import get_instance

class VideoStreamFrame(LabelFrame):
    """GUI panel to continuously display the last frame streamed from the
    camera."""

    def __init__(self, parent, stream, app=None):
        LabelFrame.__init__(self, parent, text='Stream')

        self.parent = parent

        self.stream = stream
        self.app = app
        self.binsize = self.stream.default_binsize
        self.dimension = self.stream.dimension
        self.ctrl = get_instance()

        if self.stream.cam.interface=="DM":
            self.image_stream = self.ctrl.image_stream
            self.frame_delay = max(int(self.stream.frametime / 2 * 1000), 50)
            self.frametime = self.stream.frametime / 2
        else:
            self.frame_delay = 50
            self.frametime = self.stream.frametime / 2

        self.panel = None

        self.brightness = 1.0
        self.display_range = self.display_range_default = self.stream.cam.dynamic_range
        # Maximum number from image readout

        self.auto_contrast = True

        self.resize_image = False
        self.frame = np.zeros(self.dimension)

        self.last = time.perf_counter()
        self.nframes = 1
        self.update_frequency = 0.25
        self.last_interval = self.frametime

        self._atexit_funcs = []

        #######################

        self.parent = parent

        self.init_vars()
        self.buttonbox(self)
        self.header(self)
        self.makepanel(self, dimension=self.dimension)

        try:
            self.parent.wm_title('Video stream')
            self.parent.wm_protocol('WM_DELETE_WINDOW', self.close)
        except AttributeError:
            pass

        self.parent.bind('<Escape>', self.close)

        self.start_stream()

    def init_vars(self):
        self.var_fps = DoubleVar()
        self.var_interval = DoubleVar()

        self.var_frametime = DoubleVar()
        self.var_frametime.set(self.frametime)
        self.var_frametime.trace_add('write', self.update_frametime)

        self.var_brightness = DoubleVar(value=self.brightness)
        self.var_brightness.trace_add('write', self.update_brightness)

        self.var_display_range = DoubleVar(value=self.display_range_default)
        self.var_display_range.trace_add('write', self.update_display_range)

        self.var_resize_image = BooleanVar(value=self.resize_image)
        self.var_resize_image.trace_add('write', self.update_resize_image)

        self.var_auto_contrast = BooleanVar(value=self.auto_contrast)
        self.var_auto_contrast.trace_add('write', self.update_auto_contrast)

        self.var_show_center = BooleanVar(value=True)
        self.var_show_res = BooleanVar(value=True)
        self.var_resolution = DoubleVar(value=0)

        self.var_apply_stretch = BooleanVar(value=False)
        self.var_azimuth = DoubleVar(value=config.calibration.stretch_azimuth)
        self.var_amplitude = DoubleVar(value=config.calibration.stretch_amplitude)
        self.var_cent_x = DoubleVar(value=self.dimension[0]/2)
        self.var_cent_y = DoubleVar(value=self.dimension[1]/2)

    def buttonbox(self, master):
        if self.stream.cam.interface=="DM" and config.settings.buffer_stream_use_thread:
            frame = Frame(master)
            self.btn_save = Button(frame, text='Save Image', command=self.saveImage)
            self.btn_save.pack(side='left', expand=True, fill='both', padx=5)
            self.btn_pause = Button(frame, text='Pause Stream', command=self.pause_stream, state=NORMAL)
            self.btn_pause.pack(side='left', expand=True, fill='both', padx=5)
            self.btn_continue = Button(frame, text='Continue Stream', command=self.continue_stream, state=DISABLED)
            self.btn_continue.pack(side='left', expand=True, fill='both', padx=5)
            frame.pack(side='bottom', fill='both')
        else:
            btn = Button(master, text='Save image', command=self.saveImage)
            btn.pack(side='bottom', fill='both', padx=5)

    def header(self, master):
        ewidth = 6
        lwidth = 12

        frame = Frame(master)

        self.cb_resize = Checkbutton(frame, text='Increase size', variable=self.var_resize_image)
        self.cb_resize.grid(row=1, column=4)

        self.cb_contrast = Checkbutton(frame, text='Auto contrast', variable=self.var_auto_contrast)
        self.cb_contrast.grid(row=1, column=5)

        self.e_frametime = Spinbox(frame, width=ewidth, textvariable=self.var_frametime, from_=0.0, to=100.0, increment=0.1)

        Label(frame, width=lwidth, text='exposure (s)').grid(row=1, column=6)
        self.e_frametime.grid(row=1, column=7)

        self.e_fps = Entry(frame, width=ewidth, textvariable=self.var_fps, state=DISABLED)
        self.e_interval = Entry(frame, width=ewidth, textvariable=self.var_interval, state=DISABLED)

        Label(frame, text='fps:').grid(row=1, column=0)
        self.e_fps.grid(row=1, column=1, sticky='we')
        Label(frame, width=lwidth, text='interval (ms):').grid(row=1, column=2)
        self.e_interval.grid(row=1, column=3, sticky='we')

        frame.pack()

        frame = Frame(master)
        
        self.e_brightness = Spinbox(frame, width=ewidth, textvariable=self.var_brightness, from_=0.0, to=10.0, increment=0.1)

        Label(frame, text='Brightness').grid(row=1, column=0)
        self.e_brightness.grid(row=1, column=1)

        Label(frame, width=lwidth, text='DisplayRange').grid(row=1, column=2)
        self.e_display_range = Spinbox(frame, width=ewidth, textvariable=self.var_display_range, from_=1, to=self.display_range_default, increment=1000)
        self.e_display_range.grid(row=1, column=3)

        Checkbutton(frame, text='Apply Stretch', variable=self.var_apply_stretch, command=self.apply_stretch).grid(row=1, column=4, sticky='W')
        self.e_amplitude = Spinbox(frame, textvariable=self.var_amplitude, width=6, from_=0.0, to=100.0, increment=0.01)
        self.e_amplitude.grid(row=1, column=5, sticky='EW')
        Hoverbox(self.e_amplitude, 'Stretch amplitude')
        self.e_azimuth = Spinbox(frame, textvariable=self.var_azimuth, width=6, from_=-180.0, to=180.0, increment=0.01)
        self.e_azimuth.grid(row=1, column=6, sticky='EW')
        Hoverbox(self.e_azimuth, 'Stretch azimuth')
        self.e_cent_x = Spinbox(frame, textvariable=self.var_cent_x, width=6, from_=0.0, to=self.dimension[0], increment=0.1)
        self.e_cent_x.grid(row=1, column=7, sticky='EW')
        Hoverbox(self.e_cent_x, 'Stretch center position X')
        self.e_cent_y = Spinbox(frame, textvariable=self.var_cent_y, width=6, from_=0.0, to=self.dimension[1], increment=0.1)
        self.e_cent_y.grid(row=1, column=8, sticky='EW')
        Hoverbox(self.e_cent_y, 'Stretch center position Y')

        frame.pack()

        frame = Frame(master)

        Checkbutton(frame, width=15, text='Show Center', variable=self.var_show_center, command=self.show_center).grid(row=1, column=0, sticky='we')
        Checkbutton(frame, width=15, text='Show Resolution', variable=self.var_show_res, command=self.show_res).grid(row=1, column=1, sticky='we', padx=5)
        self.l_resolution = Label(frame, width=15, text='')
        self.l_resolution.grid(row=1, column=2)
        self.e_resolution = Entry(frame, width=15, textvariable=self.var_resolution, state=DISABLED)
        self.e_resolution.grid(row=1, column=3, padx=5)
        self.check_tem_state()
        Button(frame, width=ewidth, text='Check', command=self.check_tem_state).grid(row=1, column=4)

        frame.pack()

    def makepanel(self, master, dimension=(512, 512)):
        if self.panel is None:
            image = Image.fromarray(np.zeros(dimension, dtype=np.float32))
            image = ImageTk.PhotoImage(image)
            self.image = image

            overflow = Image.new('RGBA', (dimension[1], dimension[0]), 'blue')
            self.alpha = alpha = Image.fromarray(np.zeros(dimension, dtype=np.uint8))
            overflow.putalpha(alpha)
            overflow_tk = ImageTk.PhotoImage(overflow)
            self.overflow = overflow
            self.overflow_tk = overflow_tk

            #self.panel = Label(master, image=image)
            #self.panel.image = image
            self.panel = Canvas(master, width=dimension[1], height=dimension[0])
            self.image_on_panel = self.panel.create_image(0, 0, anchor=NW, image=image)
            self.overflow_on_panel = self.panel.create_image(0, 0, anchor=NW, image=overflow_tk)
            self.center_panel = self.panel.create_oval(dimension[1]/2-5, dimension[0]/2-5, dimension[1]/2+5, dimension[0]/2+5, width=5, outline='green')
            if dimension[0] > dimension[1]:
                self.res_shell_panel = self.panel.create_oval(0, (dimension[0]-dimension[1])/2, dimension[1], (dimension[1]+dimension[0])/2, outline='red')
            else:
                self.res_shell_panel = self.panel.create_oval((dimension[1]-dimension[0])/2, 0, (dimension[1]+dimension[0])/2, dimension[0], outline='red')
            self.panel.pack(side='left', padx=5, pady=5)

    def apply_stretch(self):
        pass

    def show_center(self):
        if self.var_show_center.get():
            self.panel.itemconfigure(self.center_panel, state='normal')
        else:
            self.panel.itemconfigure(self.center_panel, state='hidden')

    def show_res(self):
        if self.var_show_res.get():
            self.panel.itemconfigure(self.res_shell_panel, state='normal')
        else:
            self.panel.itemconfigure(self.res_shell_panel, state='hidden')

    def check_tem_state(self):
        mode = self.ctrl.mode.state
        if mode in ('D', 'LAD', 'diff'):
            self.l_resolution.config(text='Resolution (Å)')
            camera_length = self.ctrl.magnification.get()
            if config.settings.software_binsize is None:
                pixelsize = config.calibration[mode]['pixelsize'][camera_length] * self.binsize
            else:
                pixelsize = config.calibration[mode]['pixelsize'][camera_length] * self.binsize * config.settings.software_binsize
            self.var_resolution.set(round(1 / (pixelsize * min(self.dimension) / 2), 2))
        else:
            self.l_resolution.config(text='Resolution (nm)')
            mag = self.ctrl.magnification.get()
            software_binsize = config.settings.software_binsize
            if config.settings.software_binsize is None:
                pixelsize = config.calibration[mode]['pixelsize'][mag] * self.binsize
            else:
                pixelsize = config.calibration[mode]['pixelsize'][mag] * self.binsize * software_binsize
            self.var_resolution.set(round(pixelsize * min(self.dimension) / 2, 1))

    def pause_stream(self):
        self.image_stream.pause_streaming()
        self.btn_continue.config(state=NORMAL)
        self.btn_pause.config(state=DISABLED)

    def continue_stream(self):
        self.image_stream.continue_streaming()
        self.btn_continue.config(state=DISABLED)
        self.btn_pause.config(state=NORMAL)

    def update_resize_image(self, name, index, mode):
        # print name, index, mode
        try:
            self.resize_image = self.var_resize_image.get()
        except BaseException:
            pass

    def update_auto_contrast(self, name, index, mode):
        # print name, index, mode
        try:
            self.auto_contrast = self.var_auto_contrast.get()
        except BaseException:
            pass

    def update_frametime(self, name, index, mode):
        # print name, index, mode
        try:
            self.frametime = self.var_frametime.get()
        except BaseException:
            pass
        else:
            self.stream.update_frametime(self.frametime)

    def update_brightness(self, name, index, mode):
        # print name, index, mode
        try:
            self.brightness = self.var_brightness.get()
        except BaseException:
            pass

    def update_display_range(self, name, index, mode):
        try:
            val = self.var_display_range.get()
            self.display_range = max(1, val)
        except BaseException:
            pass

    def saveImage(self):
        """Dump the current frame to a file."""
        self.q.put(('save_image', {'frame': self.frame}))
        self.triggerEvent.set()

    def set_trigger(self, trigger=None, q=None):
        self.triggerEvent = trigger
        self.q = q

    def close(self):
        self.stream.close()
        self.parent.quit()
        # for func in self._atexit_funcs:
        # func()

    def start_stream(self):
        self.stream.update_frametime(self.frametime)
        self.after(500, self.on_frame)

    def on_frame(self, event=None):
        #self.stream.lock.acquire(True)
        self.frame = frame = self.stream.frame
        #self.stream.lock.release()
        overflow_alpha = ne.evaluate('(frame > 64000) * 255')
        overflow_alpha = Image.fromarray(overflow_alpha.astype(np.uint8))
        self.overflow.putalpha(overflow_alpha)
        self.overflow_tk = overflow_tk = ImageTk.PhotoImage(image=self.overflow)
        self.panel.itemconfig(self.overflow_on_panel, image=overflow_tk)

        # the display range in ImageTk is from 0 to 256
        if self.auto_contrast:
            tmp = frame - np.min(frame[::8, ::8])
            large = np.percentile(tmp[::8, ::8], 99.5)
            frame = ne.evaluate('tmp * (256.0 / (1 + large))')  # use 128x128 array for faster calculation

            if self.var_apply_stretch.get():
                center = [self.var_cent_x.get(), self.var_cent_y.get()]
                azimuth = self.var_azimuth.get()
                amplitude = self.var_amplitude.get()
                frame = apply_stretch_correction(frame, center=center, azimuth=azimuth, amplitude=amplitude)

            image = Image.fromarray(frame)
        elif self.display_range != self.display_range_default:
            image = np.clip(frame, 0, self.display_range)
            image = (256.0 / self.display_range) * image
            if self.var_apply_stretch.get():
                center = [self.var_cent_x.get(), self.var_cent_y.get()]
                azimuth = self.var_azimuth.get()
                amplitude = self.var_amplitude.get()
                image = apply_stretch_correction(image, center=center, azimuth=azimuth, amplitude=amplitude)
            image = Image.fromarray(image)
        else:
            if self.var_apply_stretch.get():
                center = [self.var_cent_x.get(), self.var_cent_y.get()]
                azimuth = self.var_azimuth.get()
                amplitude = self.var_amplitude.get()
                frame = apply_stretch_correction(frame, center=center, azimuth=azimuth, amplitude=amplitude)
            image = Image.fromarray(frame)

        if self.brightness != 1:
            image = ImageEnhance.Brightness(image.convert('L')).enhance(self.brightness)
            # Can also use ImageEnhance.Sharpness or ImageEnhance.Contrast if needed

        if self.resize_image:
            image = image.resize((950, 950))

        

        image = ImageTk.PhotoImage(image=image)

        #self.panel.configure(image=image)
        self.panel.itemconfig(self.image_on_panel, image=image)
        # keep a reference to avoid premature garbage collection
        self.image = image

        self.update_frametimes()
        # self.parent.update_idletasks()

        self.after(self.frame_delay, self.on_frame)

    def update_frametimes(self):
        self.current = time.perf_counter()
        delta = self.current - self.last

        if delta > self.update_frequency:
            interval = delta / self.nframes

            interval = (interval * 0.5) + (self.last_interval * 0.5)

            fps = 1.0 / interval

            self.var_fps.set(round(fps, 2))
            self.var_interval.set(round(interval * 1000, 2))
            self.last = self.current
            self.nframes = 1

            self.last_interval = interval
        else:
            self.nframes += 1


module = BaseModule(name='stream', display_name='Stream', tk_frame=VideoStreamFrame, location='left')
commands = {}


def start_gui(stream):
    """Pass a camera stream object, and open a simple live-view window This is
    meant to be used in an interactive python shell."""
    root = Tk()
    vsframe = VideoStreamFrame(root, stream=stream)
    vsframe.pack(side='top', fill='both', expand=True)
    root.mainloop()
    root.destroy()


def ipy_embed(*args, **kwargs):
    """Embed an ipython terminal."""
    import IPython
    IPython.embed(*args, **kwargs)


if __name__ == '__main__':
    from instamatic import config
    from instamatic.camera.videostream import VideoStream
    from instamatic import TEMController

    TEMController.TEMController._cam = VideoStream(cam=config.camera.name)
    ctrl = TEMController.get_instance()

    t = threading.Thread(target=start_gui, args=(TEMController.TEMController._cam,))
    t.start()

    import IPython
    IPython.embed()
