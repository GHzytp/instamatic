import numpy as np
import time
import threading
import pickle
from tkinter import *
from tkinter.ttk import *
from tqdm import tqdm

from .base_module import BaseModule
from instamatic import config
from instamatic.utils.fit import fit_affine_transformation
from instamatic.utils.spinbox import Spinbox
from instamatic.utils import suppress_stderr
from instamatic.image_utils import autoscale
from instamatic.image_utils import imgscale
from instamatic.tools import find_beam_center

from skimage.registration import phase_cross_correlation

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

class CalibrationFrame(LabelFrame):
    """GUI frame for common TEM calibrations: stage, beam tilt, beam shift, image shift, diffraction shift"""
    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Calibration')

        self.parent = parent

        from instamatic import TEMController
        self.ctrl = TEMController.get_instance()
        self.mode = self.ctrl.mode.state
        self.calib_path = config.locations['work'] / 'calibration'
        self.click = 0
        self.counter = 0

        self.cam_buffer = []

        self.init_vars()

        frame = Frame(self)

        Label(frame, text='Exposure Time', width=15).grid(row=0, column=0, sticky='W')
        self.e_exposure_time = Spinbox(frame, width=15, textvariable=self.var_exposure_time, from_=self.ctrl.cam.default_exposure*2, to=30, increment=self.ctrl.cam.default_exposure)
        self.e_exposure_time.grid(row=0, column=1, sticky='EW', padx=5)
        Label(frame, text='Screen Current', width=15).grid(row=0, column=2, sticky='W')
        self.e_current = Spinbox(frame, width=15, textvariable=self.var_current, from_=0, to=300, increment=0.1)
        self.e_current.grid(row=0, column=3, sticky='EW', padx=5)
        self.StartButton = Button(frame, text='Start Cam Calib', command=self.start_cam_calib, state=NORMAL)
        self.StartButton.grid(row=1, column=0, sticky='EW')
        self.ContinueButton = Button(frame, text='Continue Calib', command=self.continue_cam_calib, state=DISABLED)
        self.ContinueButton.grid(row=1, column=1, sticky='EW', padx=5)
        self.StopButton = Button(frame, text='Stop Cam Calib', command=self.stop_cam_calib, state=DISABLED)
        self.StopButton.grid(row=1, column=2, sticky='EW')
        self.b_toggle_screen = Checkbutton(frame, text='Toggle screen', variable=self.var_toggle_screen, command=self.toggle_screen, state=NORMAL)
        self.b_toggle_screen.grid(row=1, column=3, sticky='EW', padx=10)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Label(frame, text='Grid Size', width=15).grid(row=0, column=0, sticky='W')
        self.e_grid_size = Spinbox(frame, width=10, textvariable=self.var_grid_size, from_=0, to=20, increment=1, state=NORMAL)
        self.e_grid_size.grid(row=0, column=1, sticky='EW', padx=5)
        Label(frame, text='Step Size', width=15).grid(row=0, column=2, sticky='W')
        self.e_step_size = Spinbox(frame, width=10, textvariable=self.var_step_size, from_=0, to=10000, increment=1, state=NORMAL)
        self.e_step_size.grid(row=0, column=3, sticky='EW', padx=5)
        
        Label(frame, text='Diff Defocus', width=15).grid(row=1, column=0, sticky='W')
        self.e_diff_focus= Spinbox(frame, width=10, textvariable=self.var_diff_defocus, from_=-100000, to=100000, increment=1, state=NORMAL)
        self.e_diff_focus.grid(row=1, column=1, sticky='EW', padx=5)
        self.c_toggle_defocus = Checkbutton(frame, text='Toggle defocus', variable=self.var_toggle_diff_defocus, command=self.toggle_diff_defocus, state=NORMAL)
        self.c_toggle_defocus.grid(row=1, column=2, sticky='W')
        if self.ctrl.tem.interface == "fei":
            self.o_mode = OptionMenu(frame, self.var_mode, self.mode, 'LM', 'Mi', 'SA', 'Mh', 'LAD', 'D', command=self.set_mode)
        else:
            self.o_mode = OptionMenu(frame, self.var_mode, self.mode, 'diff', 'mag1', 'mag2', 'lowmag', 'samag', command=self.set_mode)
        self.o_mode.grid(row=1, column=3, sticky='EW', padx=5)
        self.set_gui_diffobj()

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        self.lb_coll0 = Label(frame, text='')
        self.lb_coll0.grid(row=2, column=0, sticky='EW', pady=5)
        self.lb_coll1 = Label(frame, text='')
        self.lb_coll1.grid(row=3, column=0, sticky='EW')

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.fig.subplots_adjust(left=0.1, bottom=0.07, right=0.95, top=0.95, wspace=0, hspace=0)
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.canvas = FigureCanvasTkAgg(self.fig, frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, padx=5)
        self.toolbar = NavigationToolbar2Tk(self.canvas, frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.grid(row=1, column=0, padx=5)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        self.BeamShiftCalibButton = Button(frame, text='Start BeamShift Calib', command=self.start_beamshift_calib, state=NORMAL)
        self.BeamShiftCalibButton.grid(row=0, column=0, sticky='EW', padx=5)
        self.BeamTiltCalibButton = Button(frame, text='Start BeamTilt Calib', command=self.start_beamtilt_calib, state=NORMAL)
        self.BeamTiltCalibButton.grid(row=0, column=1, sticky='EW', padx=5)
        self.IS1CalibButton = Button(frame, text='Start IS1 Calib', command=self.start_IS1_calib, state=NORMAL)
        self.IS1CalibButton.grid(row=0, column=2, sticky='EW', padx=5)
        self.IS2CalibButton = Button(frame, text='Start IS2 Calib', command=self.start_IS2_calib, state=NORMAL)
        self.IS2CalibButton.grid(row=1, column=0, sticky='EW', padx=5)
        self.DiffShiftCalibButton = Button(frame, text='Start DiffShift Calib', command=self.start_diffshift_calib, state=NORMAL)
        self.DiffShiftCalibButton.grid(row=1, column=1, sticky='EW', padx=5)
        self.StageCalibButton = Button(frame, text='Start Stage Calib', command=self.start_stage_calib, state=NORMAL)
        self.StageCalibButton.grid(row=1, column=1, sticky='EW', padx=5)

        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=1)
        frame.pack(side='bottom', fill='x', expand=False, padx=5, pady=5)

    def init_vars(self):
        self.var_toggle_screen = BooleanVar(value=False)
        self.var_current = DoubleVar(value=0)
        self.var_exposure_time = DoubleVar(value=round(int(1.5/self.ctrl.cam.default_exposure)*self.ctrl.cam.default_exposure, 1))
        self.var_diff_defocus = IntVar(value=15000)
        self.var_toggle_diff_defocus = IntVar(value=0)
        self.var_grid_size = IntVar(value=5)
        self.var_step_size = IntVar(value=1000)
        self.var_mode = StringVar(value=self.mode)

    def set_trigger(self, trigger=None, q=None):
        self.triggerEvent = trigger
        self.q = q

    def toggle_screen(self):
        toggle = self.var_toggle_screen.get()

        if toggle:
            self.ctrl.screen.up()
        else:
            self.ctrl.screen.down()

    def disable_widgets(self):
        pass

    def enable_widgets(self):
        pass

    def start_cam_calib(self):
        self.cam_buffer = []
        self.counter = 0

        exposure = round(int(self.var_exposure_time.get()/self.ctrl.cam.default_exposure)*self.ctrl.cam.default_exposure, 1)
        self.var_exposure_time.set(exposure)
        if self.click == 0:
            self.lb_coll0.config(text='Camera calibration. Please blank the beam and input current to 0')
            self.lb_coll1.config(text='Click Start Cam Calib again.')
            self.cam_calib_path = self.calib_path / 'CamCalib'
            self.cam_calib_path.mkdir(parents=True, exist_ok=True)
            self.click = 1
        elif self.click == 1:
            self.lb_coll0.config(text='Camera calibration started')
            self.lb_coll1.config(text='Adjust screen current to a value and put the value to the Screen Current spinbox')
            self.StartButton.config(state=DISABLED)
            self.ContinueButton.config(state=NORMAL)
            self.StopButton.config(state=NORMAL)
            outfile = self.cam_calib_path / f'calib_cam_{self.counter}_{self.var_current.get():04d}'
            comment = f'Calib camera {self.counter}: screen current = {self.var_current.get()}'
            img, h = self.ctrl.get_image(exposure=exposure, out=outfile, comment=comment)
            self.counter = self.counter + 1
            self.cam_buffer.append((0, img.mean()))
            self.click = 0

    def continue_cam_calib(self):
        current = self.var_current.get()
        self.lb_coll1.config(text=f'Now screen current is {current}')
        outfile = self.cam_calib_path / f'calib_cam_{self.counter:04d}_{current:.3f}'
        comment = f'Calib camera {self.counter:04d}: screen current = {current:.3f}'
        img, h = self.ctrl.get_image(exposure=self.var_exposure_time.get(), out=outfile, comment=comment)
        self.counter = self.counter + 1
        self.cam_buffer.append((current, img.mean()))

    def stop_cam_calib(self):
        self.lb_coll0.config(text='Camera calibration finished')
        self.lb_coll1.config(text=f'Results saved to {self.cam_calib_path}')
        self.StartButton.config(state=NORMAL)
        self.ContinueButton.config(state=DISABLED)
        self.StopButton.config(state=DISABLED)
        array = np.array(self.cam_buffer)
        self.ax.scatter(array[:,0], array[:,1])
        self.canvas.draw()

    def GUI_DiffFocus(self):
        self.c_toggle_defocus.config(state=NORMAL)
        self.e_diff_focus.config(state=NORMAL)

    def GUI_ObjFocus(self):
        self.c_toggle_defocus.config(state=DISABLED)
        self.e_diff_focus.config(state=DISABLED)

    def set_gui_diffobj(self):
        if self.ctrl.tem.interface == 'fei':
            if self.ctrl.mode.state in ('D','LAD'):
                self.GUI_DiffFocus()
            else:
                self.GUI_ObjFocus()
        else:
            if self.ctrl.mode.state == 'diff':
                self.GUI_DiffFocus()
            else:
                self.GUI_ObjFocus()

    def set_mode(self, event=None):
        if self.ctrl.tem.interface == 'fei':
            if self.var_mode.get() in ('D', 'LAD'):
                self.ctrl.tem.setProjectionMode('diffraction')
                self.var_mode.set(self.ctrl.mode.state)
                self.q.put(('ctrl', {'task': 'in_diff_state'}))
                self.triggerEvent.set()
            else:
                self.ctrl.tem.setProjectionMode('imaging')
                self.var_mode.set(self.ctrl.mode.state)
                self.q.put(('ctrl', {'task': 'in_img_state'}))
                self.triggerEvent.set()
            self.set_gui_diffobj()
        else:
            self.ctrl.mode.set(self.var_mode.get())
            self.set_gui_diffobj()

    def toggle_diff_defocus(self):
        toggle = self.var_toggle_diff_defocus.get()
        difffocus = self.var_diff_defocus.get()

        self.q.put(('toggle_difffocus', {'value': difffocus, 'toggle': toggle}))
        self.triggerEvent.set()

    @suppress_stderr
    def beamshift_calib(self):
        exposure = self.var_exposure_time.get()
        grid_size = self.var_grid_size.get()
        step_size = self.var_step_size.get()
        binsize = self.ctrl.cam.default_binsize

        outfile = self.beamshift_calib_path / 'calib_beamshift_center'

        img_cent, h_cent = self.ctrl.get_image(exposure=exposure, out=outfile, comment='Beam in center of image')
        x_cent, y_cent = beamshift_cent = np.array(self.ctrl.beamshift.get())

        magnification = self.ctrl.magnification.get()
        step_size = 2500.0 / magnification * step_size

        self.lb_coll0.config(text=f'Beam Shift calibration started. Gridsize: {grid_size} | Stepsize: {step_size:.2f}')
        img_cent, scale = autoscale(img_cent)

        pixel_cent = find_beam_center(img_cent) * binsize / scale
        print('Beamshift: x={} | y={}'.format(*beamshift_cent))
        print('Pixel: x={} | y={}'.format(*pixel_cent))

        shifts = []
        beampos = []

        n = (grid_size - 1) / 2  # number of points = n*(n+1)
        x_grid, y_grid = np.meshgrid(np.arange(-n, n + 1) * step_size, np.arange(-n, n + 1) * step_size)
        tot = grid_size * grid_size

        i = 0
        with tqdm(total=100, ncols=60, bar_format='{l_bar}{bar}') as pbar:
            for dx, dy in np.stack([x_grid, y_grid]).reshape(2, -1).T:
                self.ctrl.beamshift.set(x=x_cent + dx, y=y_cent + dy)
                self.lb_coll1.config(text=str(pbar))
                outfile = self.beamshift_calib_path / f'calib_beamshift_{i:04d}'

                comment = f'Calib beam shift {i}: dx={dx} - dy={dy}'
                img, h = self.ctrl.get_image(exposure=exposure, out=outfile, comment=comment, header_keys='BeamShift')
                img = imgscale(img, scale)

                shift, error, phasediff = phase_cross_correlation(img_cent, img, upsample_factor=10)

                beamshift = np.array(self.ctrl.beamshift.get())
                beampos.append(beamshift)
                shifts.append(shift)
                pbar.update(100/tot)
                i += 1
            self.lb_coll1.config(text=str(pbar))

        self.ctrl.beamshift.set(*beamshift_cent) # reset beam to center

        shifts = np.array(shifts) * binsize / scale
        beampos = np.array(beampos) - np.array(beamshift_cent)

        fit_result = fit_affine_transformation(shifts, beampos, rotation=True, scaling=True, translation=True)
        r = fit_result.r
        t = fit_result.t
        r_i = np.linalg.inv(r)
        beampos_ = np.dot(beampos-t, r_i)
        self.lb_coll0.config(text='Beam Shift calibration finished. Please click Beam Shift Calib again to plot.')

        with open(self.beamshift_calib_path / 'calib_beamshift.pickle', 'wb') as f:
            pickle.dump([r, t, shifts, beampos_], f)

    def start_beamshift_calib(self):
        if self.click == 0:
            self.lb_coll0.config(text='Calibrate beam shift 1. Go to desired mag 2. Adjust to desired intensity')
            self.lb_coll1.config(text='Click Start Beam Shift Calib again.')
            if self.var_mode.get() in ('D', 'LAD', 'diff'):
                self.beamshift_calib_path = self.calib_path / 'BeamShiftCalib_D'
            else:
                self.beamshift_calib_path = self.calib_path / 'BeamShiftCalib'
            self.beamshift_calib_path.mkdir(parents=True, exist_ok=True)
            self.click = 1
        elif self.click == 1:
            self.ax.cla()
            self.canvas.draw()
            self.lb_coll0.config(text='Beam Shift calibration started')
            self.lb_coll1.config(text='')
            t = threading.Thread(target=self.beamshift_calib, args=(), daemon=True)
            t.start()
            self.click = 2
        elif self.click == 2:
            with open(self.beamshift_calib_path / 'calib_beamshift.pickle', 'rb') as f:
                r, t, shifts, beampos = pickle.load(f)
            self.ax.scatter(*shifts.T, marker='>', label='Observed')
            self.ax.scatter(*beampos.T, marker='<', label='Theoretical')
            self.ax.legend()
            self.canvas.draw()
            self.click = 0

    @suppress_stderr
    def beamtilt_calib(self):
        with tqdm(total=100, ncols=50, bar_format='{l_bar}{bar}') as pbar:
            for i in range(10):
                self.lb_coll1.config(text=str(pbar))
                time.sleep(1)
                pbar.update(10)
            self.lb_coll1.config(text=str(pbar))

    def start_beamtilt_calib(self):
        if self.click == 0:
            self.lb_coll0.config(text='Calibrate beam tilt 1. Go to desired cam length 2. Center the DP')
            self.lb_coll1.config(text='Click Start Beam Tilt Calib again.')
            self.click = 1
        elif self.click == 1:
            self.lb_coll0.config(text='Beam Tilt calibration started')
            self.lb_coll1.config(text='')
            t = threading.Thread(target=self.beamtilt_calib, args=(), daemon=True)
            t.start()
            self.click = 0

    @suppress_stderr
    def IS1_calib(self):
        with tqdm(total=100, ncols=50, bar_format='{l_bar}{bar}') as pbar:
            for i in range(10):
                self.lb_coll1.config(text=str(pbar))
                time.sleep(1)
                pbar.update(10)
            self.lb_coll1.config(text=str(pbar))

    def start_IS1_calib(self):
        if self.click == 0:
            self.lb_coll0.config(text='Calibrate Image Shift 1')
            self.lb_coll1.config(text='Click Start Image Shift 1 Calib again.')
            self.click = 1
        elif self.click == 1:
            self.lb_coll0.config(text='Image Shift 1 calibration started')
            self.lb_coll1.config(text='')
            t = threading.Thread(target=self.IS1_calib, args=(), daemon=True)
            t.start()
            self.click = 0

    @suppress_stderr
    def IS2_calib(self):
        with tqdm(total=100, ncols=50, bar_format='{l_bar}{bar}') as pbar:
            for i in range(10):
                self.lb_coll1.config(text=str(pbar))
                time.sleep(1)
                pbar.update(10)
            self.lb_coll1.config(text=str(pbar))

    def start_IS2_calib(self):
        if self.click == 0:
            self.lb_coll0.config(text='Calibrate Image Shift 2')
            self.lb_coll1.config(text='Click Start Image Shift 2 Calib again.')
            self.click = 1
        elif self.click == 1:
            self.lb_coll0.config(text='Image Shift 2 calibration started')
            self.lb_coll1.config(text='')
            t = threading.Thread(target=self.IS2_calib, args=(), daemon=True)
            t.start()
            self.click = 0

    @suppress_stderr
    def diffshift_calib(self):
        with tqdm(total=100, ncols=50, bar_format='{l_bar}{bar}') as pbar:
            for i in range(10):
                self.lb_coll1.config(text=str(pbar))
                time.sleep(1)
                pbar.update(10)
            self.lb_coll1.config(text=str(pbar))

    def start_diffshift_calib(self):
        if self.click == 0:
            self.lb_coll0.config(text='Calibrate stage vs camera 1. Go to image mode 2. Find area with particles.')
            self.lb_coll1.config(text='Click Start Stage Calib again.')
            self.click = 1
        elif self.click == 1:
            self.lb_coll0.config(text='Stage calibration started')
            self.lb_coll1.config(text='')
            t = threading.Thread(target=self.diffshift_calib, args=(), daemon=True)
            t.start()
            self.click = 0

    @suppress_stderr
    def stage_calib(self):
        with tqdm(total=100, ncols=50, bar_format='{l_bar}{bar}') as pbar:
            for i in range(10):
                self.lb_coll1.config(text=str(pbar))
                time.sleep(1)
                pbar.update(10)
            self.lb_coll1.config(text=str(pbar))

    def start_stage_calib(self):
        if self.click == 0:
            self.lb_coll0.config(text='Calibrate stage vs camera 1. Go to image mode 2. Find area with particles.')
            self.lb_coll1.config(text='Click Start Stage Calib again.')
            self.click = 1
        elif self.click == 1:
            self.lb_coll0.config(text='Stage calibration started')
            self.lb_coll1.config(text='')
            t = threading.Thread(target=self.stage_calib, args=(), daemon=True)
            t.start()
            self.click = 0

module = BaseModule(name='Calibration', display_name='Calib', tk_frame=CalibrationFrame, location='bottom')
commands = {}

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
    import queue
    import logging
    from .io_frame import module as io_module
    
    logger = logging.getLogger(__name__)

    root = Tk()
    root.title('Calibration')
    trigger = threading.Event()
    q = queue.Queue(maxsize=1)
    ctrl = CalibrationFrame(root)
    ctrl.pack(side='top', fill='both', expand=True)
    ctrl.set_trigger(trigger=trigger, q=q)
    ctrl.module_io = io_module.initialize(root)
    ctrl.log = logger

    p = threading.Thread(target=run, args=(ctrl,trigger,q,))
    p.start()

    root.mainloop()
    ctrl.ctrl.close()