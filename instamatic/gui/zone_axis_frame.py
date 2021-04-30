import numpy as np
import time
import threading
import atexit
import pickle
from tkinter import *
from tkinter.ttk import *

from PIL import Image
from PIL import ImageTk

from .base_module import BaseModule
from instamatic import config
from instamatic.utils.widgets import Spinbox
from instamatic.tools import find_beam_center_thresh, relativistic_wavelength

    
class GrabbingError(RuntimeError):
    pass

class ImageGrabber:
    """Continuously read out the camera for continuous acquisition.
    The callback function is used to send the frame back to the parent routine.
    """
    def __init__(self, ctrl, exposure, callback):
        self.ctrl = ctrl
        self.exposure = exposure
        self.callback = callback

        self.dimension = self.ctrl.cam.getCameraDimensions()
        self.frame = np.zeros((self.dimension[0], self.dimension[1]))
        self.thread = None

        self.lock = threading.Lock()

        self.stopEvent = threading.Event()

    def run(self):
        try:
            while not self.stopEvent.is_set():
                n = round(self.exposure / self.ctrl.cam.default_exposure)
                # print(f'n: {n}')
                for _ in range(n):
                    self.ctrl.cam.frame_updated.wait()
                    self.frame = self.frame + self.ctrl.cam.frame
                    self.ctrl.cam.frame_updated.clear()
                frame = self.frame / n
                self.callback(frame.astype(np.uint16))
                self.frame = np.zeros((self.dimension[0], self.dimension[1]))
        except:
            raise GrabbingError(f'ImageGrabber encountered en error!')

    def start_loop(self):
        """Obtaining frames from stream_buffer (after processing)"""
        self.thread = threading.Thread(target=self.run, args=(), daemon=True)
        self.thread.start()

    def stop(self):
        self.stopEvent.set()

class VideoStream:
    """Handle the continuous stream of incoming data from the ImageGrabber."""

    def __init__(self, ctrl, exposure):
        self.ctrl = ctrl
        self.exposure = exposure
        self.dimension = self.ctrl.cam.getCameraDimensions()
        self.frame = np.zeros((self.dimension[0], self.dimension[1]), dtype=np.uint16)
        
        self.grabber = self.setup_grabber()

        self.start()

    def start(self):
        self.grabber.start_loop()

    def send_frame(self, frame):
        self.grabber.lock.acquire(True)
        self.frame = frame
        self.grabber.lock.release()

    def setup_grabber(self):
        grabber = ImageGrabber(ctrl=self.ctrl, exposure=self.exposure, callback=self.send_frame)
        atexit.register(grabber.stop)
        return grabber

    def close(self):
        self.grabber.stop()


class ExperimentalZoneAxis(LabelFrame):
    """GUI frame for find zone axis for crystals. When a crystal near a zone axis, tilt this crystal to zone axis"""
    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Find Zone Axis')

        self.parent = parent

        from instamatic import TEMController
        self.ctrl = TEMController.get_instance()
        self.cam_x, self.cam_y = self.ctrl.cam.getCameraDimensions()
        self.binsize = self.ctrl.cam.default_binsize

        if self.cam_x != self.cam_y:
            raise RuntimeWarning("It is recommended to use a camera with equal x and y length")

        self.canvas = None
        if self.ctrl.cam.interface == 'DM':
            self.frame_delay = int(self.ctrl.cam.default_exposure / 2 * 1000)
        else:
            self.frame_delay = 50
        
        self.stopEvent = threading.Event()
        self.update_image = True
        self.wavelength = relativistic_wavelength(self.ctrl.high_tension) # unit: Angstrom
        self.beamtilt_bak = None
        self.diffshift_bak = None
        self.stage_bak = None
        self.beam_tilt_matrix_D = np.array(config.calibration.beam_tilt_matrix_D).reshape(2, 2)
        self.diffraction_shift_matrix = np.array(config.calibration.diffraction_shift_matrix).reshape(2, 2)

        self._drag_data = {"x": 0, "y": 0}

        self.init_vars()

        self.image_stream = VideoStream(self.ctrl, self.var_exposure_time.get())

        frame = Frame(self)

        Label(frame, text='Exposure Time', width=15).grid(row=0, column=0, sticky='W')
        e_exposure_time = Spinbox(frame, width=10, textvariable=self.var_exposure_time, from_=self.ctrl.cam.default_exposure*2, to=30, increment=self.ctrl.cam.default_exposure)
        e_exposure_time.grid(row=0, column=1, sticky='EW', padx=5)
        self.b_exposure_time = Button(frame, width=15, text='Confirm', command=self.confirm_exposure)
        self.b_exposure_time.grid(row=0, column=2, sticky='EW', padx=5)
        Label(frame, text='Threshold', width=10).grid(row=0, column=3, sticky='E')
        e_center_x = Spinbox(frame, width=10, textvariable=self.var_threshold, from_=0, to=65535, increment=1)
        e_center_x.grid(row=0, column=4, sticky='EW', padx=5)

        Label(frame, text='Center X (pix)', width=15).grid(row=1, column=0, sticky='W')
        e_center_x = Spinbox(frame, width=10, textvariable=self.var_center_x, from_=0, to=self.cam_x, increment=1)
        e_center_x.grid(row=1, column=1, sticky='EW', padx=5)
        Label(frame, text='Center Y (pix)', width=13).grid(row=1, column=2, sticky='E')
        e_center_y = Spinbox(frame, width=10, textvariable=self.var_center_y, from_=0, to=self.cam_y, increment=1)
        e_center_y.grid(row=1, column=3, sticky='EW', padx=5)
        self.b_center_get = Button(frame, width=12, text='Get Center', command=self.get_center)
        self.b_center_get.grid(row=1, column=4, sticky='W', padx=5)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Label(frame, text='Laue Circle x:', width=15).grid(row=3, column=0, sticky='W')
        e_laue_circle_x = Spinbox(frame, width=10, textvariable=self.var_laue_circle_x, from_=-1e7, to=1e7, increment=1)
        e_laue_circle_x.grid(row=3, column=1, sticky='EW', padx=5)
        Label(frame, text='y:', width=2).grid(row=3, column=2, sticky='E')
        e_laue_circle_y = Spinbox(frame, width=10, textvariable=self.var_laue_circle_y, from_=-1e7, to=1e7, increment=1)
        e_laue_circle_y.grid(row=3, column=3, sticky='EW', padx=5)
        Label(frame, text='r:', width=2).grid(row=3, column=4, sticky='E')
        e_laue_circle_r = Spinbox(frame, width=10, textvariable=self.var_laue_circle_r, from_=1, to=1e7, increment=1)
        e_laue_circle_r.grid(row=3, column=5, sticky='EW', padx=5)
        self.b_reset = Button(frame, width=10, text='Reset', command=self.reset_laue_circle)
        self.b_reset.grid(row=3, column=6, sticky='EW', padx=5)

        Checkbutton(frame, text='Beam unblanker', variable=self.var_unblank_beam, command=self.toggle_unblankbeam).grid(row=4, column=0, sticky='EW')

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        self.lb_col = Label(frame, text='')
        self.lb_col.grid(row=0, column=0, columnspan=2, padx=5, sticky='EW')

        self.b_start_laue_circle = Button(frame, width=15, text='Find Laue Circle', command=self.start_find_laue_circle, state=NORMAL)
        self.b_start_laue_circle.grid(row=1, column=0, sticky='W', padx=5)
        self.b_pause_stream = Button(frame, width=15, text='Pause Stream', command=self.pause_stream, state=DISABLED)
        self.b_pause_stream.grid(row=2, column=0, sticky='W', padx=5)
        self.b_stop_laue_circle = Button(frame, width=15, text='Stop Find', command=self.stop_find_laue_circle, state=DISABLED)
        self.b_stop_laue_circle.grid(row=3, column=0, sticky='W', padx=5)
        Separator(frame, orient=HORIZONTAL).grid(row=4, sticky='EW', padx=5, pady=5)

        self.b_trial_beam_tilt = Button(frame, width=15, text='Trial Beam Tilt', command=self.trial_beam_tilt, state=NORMAL)
        self.b_trial_beam_tilt.grid(row=5, column=0, sticky='W', padx=5)
        self.b_stop_trial_beam_tilt = Button(frame, width=15, text='Stop Trial', command=self.stop_trial_beam_tilt, state=DISABLED)
        self.b_stop_trial_beam_tilt.grid(row=6, column=0, sticky='W', padx=5)
        Separator(frame, orient=HORIZONTAL).grid(row=7, sticky='EW', padx=5, pady=5)

        self.b_set_zone_axis = Button(frame, width=15, text='Set Zone Axis', command=self.set_zone_axis, state=NORMAL)
        self.b_set_zone_axis.grid(row=8, column=0, sticky='W', padx=5)
        self.b_unset_zone_axis = Button(frame, width=15, text='Unset Zone Axis', command=self.unset_zone_axis, state=DISABLED)
        self.b_unset_zone_axis.grid(row=9, column=0, sticky='W', padx=5)

        self.l_dummy = Label(frame, text='', width=15)
        self.l_dummy.grid(row=10, column=0, pady=80)

        image = Image.fromarray(np.zeros((self.cam_x, self.cam_y)))
        self.ratio = min(400 / self.cam_x, 400 / self.cam_y)
        self.dim_x = int(self.ratio * self.cam_x)
        self.dim_y = int(self.ratio * self.cam_y)
        image = image.resize((self.dim_x, self.dim_y))
        self.image = image = ImageTk.PhotoImage(image)

        self.canvas = Canvas(frame, width=self.dim_y, height=self.dim_x)
        self.image_on_canvas = self.canvas.create_image(0, 0, anchor=NW, image=image, state=DISABLED)
        self.circle = self.canvas.create_oval(0, 0, 10, 10, width=3, outline='green', state=DISABLED)
        x = self.var_laue_circle_x.get() * self.ratio
        y = self.var_laue_circle_y.get() * self.ratio
        r = self.var_laue_circle_r.get() * self.ratio
        self.arc = self.canvas.create_arc(x - r, y - r, x + r, y + r, start=0, extent=359.9, style=ARC, width=2, outline='red', state=NORMAL)
        self.canvas.grid(row=1, rowspan=10, column=1, sticky=E+W+S+N)
        
        frame.pack(side='bottom', fill='x', expand=False, padx=5, pady=5)

    def init_vars(self):
        self.var_exposure_time = DoubleVar(value=round(round(1.5/self.ctrl.cam.default_exposure)*self.ctrl.cam.default_exposure, 1))
        self.var_center_x = DoubleVar(value=self.cam_x / 2)
        self.var_center_y = DoubleVar(value=self.cam_y / 2)
        self.var_laue_circle_x = DoubleVar(value=self.cam_x / 2)
        self.var_laue_circle_y = DoubleVar(value=self.cam_y / 2)
        self.var_laue_circle_r = DoubleVar(value=self.cam_x / 2)
        self.var_threshold = IntVar(value=7000)
        self.var_unblank_beam = BooleanVar(value=True)

    def confirm_exposure(self):
        self.image_stream.grabber.exposure = self.var_exposure_time.get()

    def toggle_unblankbeam(self):
        toggle = self.var_unblank_beam.get()

        if toggle:
            self.ctrl.beam.unblank()
        else:
            self.ctrl.beam.blank()

    def get_center(self):
        '''find the center of the diffraction pattern'''
        img, h = self.ctrl.get_image(self.var_exposure_time.get())
        pixel_cent = find_beam_center_thresh(img, thresh=self.var_threshold.get())
        self.var_center_x.set(pixel_cent[1])
        self.var_center_y.set(pixel_cent[0])

    def reset_laue_circle(self):
        self.var_laue_circle_x.set(self.cam_x / 2)
        self.var_laue_circle_y.set(self.cam_y / 2)
        self.var_laue_circle_r.set(self.cam_x / 2)

    def start_stream(self, event=None):
        if self.update_image:
            img = self.image_stream.frame
            # the display range in ImageTk is from 0 to 256
            tmp = img - np.min(img[::8, ::8])
            img = tmp * (256.0 / (1 + np.percentile(tmp[::8, ::8], 99.5)))  # use 128x128 array for faster calculation

            image = Image.fromarray(img)
            image = image.resize((self.dim_x, self.dim_y))
            image = ImageTk.PhotoImage(image=image)

            self.canvas.itemconfig(self.image_on_canvas, image=image)
            # keep a reference to avoid premature garbage collection
            self.image = image

        center_pos = np.array([self.var_center_x.get(), self.var_center_y.get()]) * self.ratio
        self.canvas.coords(self.circle, center_pos[0]-5, center_pos[1]-5, center_pos[0]+5, center_pos[1]+5)

        x = self.var_laue_circle_x.get() * self.ratio
        y = self.var_laue_circle_y.get() * self.ratio
        r = self.var_laue_circle_r.get() * self.ratio
        self.canvas.coords(self.arc, x - r, y - r, x + r, y + r)

        if self.stopEvent.is_set():
            self.stopEvent.clear()
            return

        self.after(self.frame_delay, self.start_stream)

    def _on_mousewheel(self, event):
        """Begining drag of an object"""
        # record the item and its location
        r = self.var_laue_circle_r.get()
        self.var_laue_circle_r.set(r + 10 * (event.delta / 120))
        x = self.var_laue_circle_x.get() * self.ratio
        y = self.var_laue_circle_y.get() * self.ratio
        r = self.var_laue_circle_r.get() * self.ratio
        self.canvas.coords(self.arc, x - r, y - r, x + r, y + r)

    def _mouse_move_start(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _mouse_move_end(self, event):
        """End drag of an object"""
        # reset the drag information
        self._drag_data["x"] = 0
        self._drag_data["y"] = 0

    def _mouse_move(self, event):
        """Handle dragging of an object"""
        # compute how much the mouse has moved
        delta_x = event.x - self._drag_data["x"]
        delta_y = event.y - self._drag_data["y"]

        # move the object the appropriate amount
        x = self.var_laue_circle_x.get()
        y = self.var_laue_circle_y.get()
        r = self.var_laue_circle_r.get()
        self.var_laue_circle_x.set(x + delta_x)
        self.var_laue_circle_y.set(y + delta_y)
        x = self.var_laue_circle_x.get() * self.ratio
        y = self.var_laue_circle_y.get() * self.ratio
        r = self.var_laue_circle_r.get() * self.ratio
        self.canvas.coords(self.arc, x - r, y - r, x + r, y + r)
        # record the new position
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y


    def start_find_laue_circle(self):
        self.update_image = True
        self.start_stream()

        self.canvas.bind('<MouseWheel>', self._on_mousewheel)
        self.canvas.bind('<ButtonPress-1>', self._mouse_move_start)
        self.canvas.bind('<ButtonRelease-1>', self._mouse_move_end)
        self.canvas.bind("<B1-Motion>", self._mouse_move)

        self.b_start_laue_circle.config(state=DISABLED)
        self.b_pause_stream.config(state=NORMAL)
        self.b_stop_laue_circle.config(state=NORMAL)
        self.lb_col.config(text='Start to find the laue zone by forming a centered laue circle. Check the red arc.')

    def pause_stream(self):
        self.update_image = False

        self.b_start_laue_circle.config(state=DISABLED)
        self.b_pause_stream.config(state=DISABLED)
        self.b_stop_laue_circle.config(state=NORMAL)
        self.lb_col.config(text='Pause the stream and blank the beam. Adjust laue circle position and radius')

    def stop_find_laue_circle(self):
        self.stopEvent.set()

        self.canvas.unbind('<MouseWheel>')
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<ButtonRelease-1>')
        self.canvas.unbind("<B1-Motion>")

        self.b_start_laue_circle.config(state=NORMAL)
        self.b_pause_stream.config(state=DISABLED)
        self.b_stop_laue_circle.config(state=DISABLED)
        self.lb_col.config(text='Stop finding laue circle.')


    def trial_beam_tilt(self):
        camera_length = int(self.ctrl.magnification.value)
        # 2dsin(theta)=lambda => theta = lambda / 2 * (1 / d)
        software_binsize = config.settings.software_binsize
        if software_binsize is None:
            self.pixelsize = config.calibration[self.ctrl.mode.state]['pixelsize'][camera_length] * self.binsize 
        else:
            self.pixelsize = config.calibration[self.ctrl.mode.state]['pixelsize'][camera_length] * self.binsize * software_binsize  
        self.beamtilt_bak = self.ctrl.beamtilt.xy

        laue_circle_center = np.array([self.var_laue_circle_x.get(), self.var_laue_circle_y.get()])[::-1]
        beam_center = np.array([self.var_center_x.get(), self.var_center_y.get()])[::-1]
        beamtilt_target = self.pixelsize * (beam_center - laue_circle_center) @ self.beam_tilt_matrix_D + self.beamtilt_bak
        self.ctrl.beamtilt.xy = beamtilt_target

        self.diffshift_bak = self.ctrl.diffshift.xy
        diffshift_target = pixelsize * (-beam_center + laue_circle_center) @ self.diffraction_shift_matrix + self.diffshift_bak
        self.ctrl.diffshift.xy = diffshift_target

        self.b_trial_beam_tilt.config(state=DISABLED)
        self.b_stop_trial_beam_tilt.config(state=NORMAL)
        self.lb_col.config(text=f'Now the beam tilt is {beamtilt_target[0]:.2f}, {beamtilt_target[1]:.2f}. The diffshift is {diffshift_target[0]:.2f}, {diffshift_target[1]:.2f}.')

    def stop_trial_beam_tilt(self):
        self.ctrl.beamtilt.xy = self.beamtilt_bak
        self.ctrl.diffshift.xy = self.diffshift_bak

        self.b_trial_beam_tilt.config(state=NORMAL)
        self.b_stop_trial_beam_tilt.config(state=DISABLED)
        self.lb_col.config(text=f'The beam tilt restored to {self.beamtilt_bak[0]:.2f}, {self.beamtilt_bak[1]:.2f}. The diffshift is restored to {diffshift_bak[0]:.2f}, {diffshift_bak[1]:.2f}.')

    def set_zone_axis(self):
        '''Set the zone axis by moving stage, with backlash elimination '''
        camera_length = int(self.ctrl.magnification.value)
        software_binsize = config.settings.software_binsize
        if software_binsize is None:
            self.pixelsize = config.calibration[self.ctrl.mode.state]['pixelsize'][camera_length] * self.binsize 
        else:
            self.pixelsize = config.calibration[self.ctrl.mode.state]['pixelsize'][camera_length] * self.binsize * software_binsize 
        self.stage_matrix = np.pi / 180 * 2 / self.wavelength * np.array(config.calibration[self.ctrl.mode.state]['stagematrix'][camera_length]).reshape(2, 2)
        self.stage_bak = self.ctrl.stage.get()

        laue_circle_center = np.array([self.var_laue_circle_x.get(), self.var_laue_circle_y.get()])[::-1]
        beam_center = np.array([self.var_center_x.get(), self.var_center_y.get()])[::-1]
        movement = self.pixelsize * (beam_center - laue_circle_center) @ np.linalg.inv(self.stage_matrix)  # unit: degree
        alpha_target = self.stage_bak.a + movement[0]
        beta_target = self.stage_bak.b + movement[1]

        self.ctrl.stage.a = alpha_target
        self.ctrl.stage.b = beta_target

        self.b_set_zone_axis.config(state=DISABLED)
        self.b_unset_zone_axis.config(state=NORMAL)
        self.lb_col.config(text=f'The stage is tilted by {movement[0]:.2f} degree, {movement[1]:.2f} degree. Now the stage angle is {alpha_target:.2f} degree, {beta_target:.2f} degree')

    def unset_zone_axis(self):
        '''Return to the original position'''
        self.ctrl.stage.a = self.stage_bak.a
        self.ctrl.stage.b = self.stage_bak.b

        self.b_set_zone_axis.config(state=NORMAL)
        self.b_unset_zone_axis.config(state=DISABLED)
        self.lb_col.config(text=f'The stage tilt restored to {self.stage_bak.a:.2f} degree, {self.stage_bak.b:.2f} degree')


module = BaseModule(name='zone_axis', display_name='ZoneAxis', tk_frame=ExperimentalZoneAxis, location='bottom')
commands = {}

if __name__ == '__main__':
    root = Tk()
    ExperimentalZoneAxis(root).pack(side='top', fill='both', expand=True)
    root.mainloop()
    