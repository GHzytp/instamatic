import numpy as np
import time
import threading
import pickle
import yaml
from tkinter import *
from tkinter.ttk import *
from tqdm import tqdm

from .base_module import BaseModule
from instamatic import config
from instamatic.utils.fit import fit_affine_transformation
from instamatic.utils.widgets import Spinbox
from instamatic.utils import suppress_stderr
from instamatic.image_utils import autoscale, imgscale
from instamatic.formats import read_tiff, write_tiff
from instamatic.tools import find_beam_center

from skimage.registration import phase_cross_correlation

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

SCALE = config.settings.software_binsize

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
        self.binsize = self.ctrl.cam.default_binsize
        self.software_binsize = config.settings.software_binsize

        self.cam_buffer = []

        self.init_vars()

        frame = Frame(self)

        Label(frame, text='Exposure Time', width=15).grid(row=0, column=0, sticky='W')
        self.e_exposure_time = Spinbox(frame, width=12, textvariable=self.var_exposure_time, from_=self.ctrl.cam.default_exposure*2, to=30, increment=self.ctrl.cam.default_exposure)
        self.e_exposure_time.grid(row=0, column=1, sticky='EW', padx=5)
        Label(frame, text='Screen Current', width=15).grid(row=0, column=2, sticky='W')
        self.e_current = Spinbox(frame, width=13, textvariable=self.var_current, from_=0, to=300, increment=0.1)
        self.e_current.grid(row=0, column=3, sticky='EW', padx=5)
        self.b_toggle_screen = Checkbutton(frame, text='Toggle screen', variable=self.var_toggle_screen, command=self.toggle_screen, state=NORMAL)
        self.b_toggle_screen.grid(row=0, column=4, sticky='EW', padx=5)
        self.StartButton = Button(frame, text='Start Cam Calib', command=self.start_cam_calib, state=NORMAL)
        self.StartButton.grid(row=1, column=0, sticky='EW')
        self.ContinueButton = Button(frame, text='Continue Calib', command=self.continue_cam_calib, state=DISABLED)
        self.ContinueButton.grid(row=1, column=1, sticky='EW', padx=5)
        self.StopButton = Button(frame, text='Stop Cam Calib', command=self.stop_cam_calib, state=DISABLED)
        self.StopButton.grid(row=1, column=2, sticky='EW')
        self.DarkRefButton = Button(frame, text='Dark Reference', command=self.start_dark_reference, state=NORMAL)
        self.DarkRefButton.grid(row=1, column=3, sticky='EW', padx=5)
        self.GainNormButton = Button(frame, text='Gain Normalize', command=self.start_gain_normalize, state=NORMAL)
        self.GainNormButton.grid(row=1, column=4, sticky='EW')
        

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Label(frame, text='Grid Size', width=15).grid(row=0, column=0, sticky='W')
        self.e_grid_size = Spinbox(frame, width=10, textvariable=self.var_grid_size, from_=0, to=20, increment=1, state=NORMAL)
        self.e_grid_size.grid(row=0, column=1, sticky='EW', padx=5)
        Label(frame, text='Step Size', width=15).grid(row=0, column=2, sticky='W')
        self.e_step_size = Spinbox(frame, width=10, textvariable=self.var_step_size, from_=0, to=10000, increment=0.01, state=NORMAL)
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
        self.StageCalibButton.grid(row=1, column=2, sticky='EW', padx=5)

        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=1)
        frame.pack(side='bottom', fill='x', expand=False, padx=5, pady=5)

    def init_vars(self):
        self.var_toggle_screen = BooleanVar(value=False)
        self.var_current = DoubleVar(value=0)
        self.var_exposure_time = DoubleVar(value=round(round(1.5/self.ctrl.cam.default_exposure)*self.ctrl.cam.default_exposure, 1))
        self.var_diff_defocus = IntVar(value=15000)
        self.var_toggle_diff_defocus = IntVar(value=0)
        self.var_grid_size = IntVar(value=5)
        self.var_step_size = DoubleVar(value=1000)
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

    def disable_widgets(self, widget_list):
        """The widgets in the list will not be disabled"""
        self.e_exposure_time.config(state=DISABLED)
        self.e_current.config(state=DISABLED)
        self.StartButton.config(state=DISABLED)
        self.ContinueButton.config(state=DISABLED)
        self.StopButton.config(state=DISABLED)
        self.DarkRefButton.config(state=DISABLED)
        self.GainNormButton.config(state=DISABLED)
        self.b_toggle_screen.config(state=DISABLED)
        self.e_diff_focus.config(state=DISABLED)
        self.e_step_size.config(state=DISABLED)
        self.e_grid_size.config(state=DISABLED)
        self.c_toggle_defocus.config(state=DISABLED)
        self.BeamShiftCalibButton.config(state=DISABLED)
        self.BeamTiltCalibButton.config(state=DISABLED)
        self.IS1CalibButton.config(state=DISABLED)
        self.IS2CalibButton.config(state=DISABLED)
        self.DiffShiftCalibButton.config(state=DISABLED)
        self.StageCalibButton.config(state=DISABLED)
        self.o_mode.configure(state="disabled")

        for widget in widget_list:
            widget.config(state=NORMAL)

    def enable_widgets(self, widget_list):
        """The widgets in the list will not be enabled"""
        self.e_exposure_time.config(state=NORMAL)
        self.e_current.config(state=NORMAL)
        self.StartButton.config(state=NORMAL)
        self.ContinueButton.config(state=NORMAL)
        self.StopButton.config(state=NORMAL)
        self.DarkRefButton.config(state=NORMAL)
        self.GainNormButton.config(state=NORMAL)
        self.b_toggle_screen.config(state=NORMAL)
        self.e_diff_focus.config(state=NORMAL)
        self.e_step_size.config(state=NORMAL)
        self.e_grid_size.config(state=NORMAL)
        self.c_toggle_defocus.config(state=NORMAL)
        self.BeamShiftCalibButton.config(state=NORMAL)
        self.BeamTiltCalibButton.config(state=NORMAL)
        self.IS1CalibButton.config(state=NORMAL)
        self.IS2CalibButton.config(state=NORMAL)
        self.DiffShiftCalibButton.config(state=NORMAL)
        self.StageCalibButton.config(state=NORMAL)
        self.o_mode.configure(state="normal")

        for widget in widget_list:
            widget.config(state=DISABLED)

    def collect_image_cam_calib(self, outfile, comment):
        img, _ = self.ctrl.get_image(exposure=self.var_exposure_time.get(), out=outfile, comment=comment)
        self.cam_buffer.append((self.var_current.get(), img.mean()))

    def collect_image(self, outfile, comment):
        try:
            n = round(self.var_exposure_time.get()/self.ctrl.cam.default_exposure)
            if SCALE is None:
                arr = np.zeros(self.ctrl.cam.dimensions, dtype=np.float32)
            else:
                arr = np.zeros((round(self.ctrl.cam.dimensions[0]/SCALE),round(self.ctrl.cam.dimensions[1]/SCALE)), dtype=np.float32)
            self.ctrl.cam.block()
            t0 = time.perf_counter()
            for i in range(n):
                img, _ = self.ctrl.get_image(exposure=self.ctrl.cam.default_exposure)
                arr += img
            arr /= n
            t1 = time.perf_counter()
            self.ctrl.cam.unblock()
            write_tiff(outfile, arr, header=comment)
        finally:
            self.enable_widgets([self.ContinueButton, self.StopButton])

    @suppress_stderr
    def show_progress(self, n):
        tot = round(self.var_exposure_time.get()/self.ctrl.cam.default_exposure) * self.ctrl.cam.default_exposure
        interval = tot / n
        with tqdm(total=100, ncols=60, bar_format='{l_bar}{bar}') as pbar:
            for i in range(n):
                self.lb_coll1.config(text=str(pbar))
                time.sleep(interval)
                pbar.update(100/n)
            self.lb_coll1.config(text=str(pbar))

    def start_cam_calib(self):
        self.cam_buffer = []
        self.counter = 0

        exposure = round(round(self.var_exposure_time.get()/self.ctrl.cam.default_exposure)*self.ctrl.cam.default_exposure, 1)
        self.var_exposure_time.set(exposure)
        if self.click == 0:
            self.lb_coll0.config(text='Camera calibration. Please blank the beam and input current to 0')
            self.lb_coll1.config(text='Click Start Cam Calib again.')
            self.cam_calib_path = self.calib_path / 'CamCalib'
            self.cam_calib_path.mkdir(parents=True, exist_ok=True)
            self.disable_widgets([self.e_current, self.b_toggle_screen, self.StartButton, self.ContinueButton, self.StopButton])
            self.click = 1
        elif self.click == 1:
            try:
                self.lb_coll0.config(text='Camera calibration started')
                self.lb_coll1.config(text='Adjust screen current to a value and put the value to the Screen Current spinbox')
                self.StartButton.config(state=DISABLED)
                self.ContinueButton.config(state=NORMAL)
                self.StopButton.config(state=NORMAL)
                outfile = self.cam_calib_path / f'calib_cam_{self.counter}_{self.var_current.get():.3f}'
                comment = f'Calib camera {self.counter}: screen current = {self.var_current.get()}'
                t = threading.Thread(target=self.collect_image_cam_calib, args=(outfile,comment), daemon=True)
                t.start()
                t = threading.Thread(target=self.show_progress, args=(10,), daemon=True)
                t.start()
                self.counter = self.counter + 1
                self.click = 0
            except Exception as e:
                self.enable_widgets([])
                self.click = 0
                raise e

    def continue_cam_calib(self):
        try:
            current = self.var_current.get()
            self.lb_coll1.config(text=f'Now screen current is {current}')
            outfile = self.cam_calib_path / f'calib_cam_{self.counter:04d}_{current:.3f}'
            comment = f'Calib camera {self.counter:04d}: screen current = {current:.3f}'
            t = threading.Thread(target=self.collect_image_cam_calib, args=(outfile,comment), daemon=True)
            t.start()
            t = threading.Thread(target=self.show_progress, args=(10,), daemon=True)
            t.start()
            self.counter = self.counter + 1
        except Exception as e:
            self.enable_widgets([])
            raise e

    def stop_cam_calib(self):
        try:
            self.lb_coll0.config(text='Camera calibration finished')
            self.lb_coll1.config(text=f'Results saved to {self.cam_calib_path}')
            self.StartButton.config(state=NORMAL)
            self.ContinueButton.config(state=DISABLED)
            self.StopButton.config(state=DISABLED)
            array = np.array(self.cam_buffer)
            self.ax.scatter(array[:,0], array[:,1])
            self.canvas.draw()
        finally:
            self.enable_widgets([self.ContinueButton, self.StopButton])

    def start_dark_reference(self):
        exposure = round(round(self.var_exposure_time.get()/self.ctrl.cam.default_exposure)*self.ctrl.cam.default_exposure, 1)
        self.var_exposure_time.set(exposure)
        self.lb_coll0.config(text='Dark reference calibration started. Please make sure the beam is blanked for the camera.')
        self.lb_coll1.config(text='')
        self.cam_calib_path = self.calib_path / 'CamCalib'
        self.cam_calib_path.mkdir(parents=True, exist_ok=True)
        outfile = self.cam_calib_path / f'dark_reference'
        comment = f'Dark reference exposure {self.var_exposure_time.get():.1f}s'
        t = threading.Thread(target=self.collect_image, args=(outfile,comment), daemon=True)
        t.start()
        t = threading.Thread(target=self.show_progress, args=(100,), daemon=True)
        t.start()
        self.disable_widgets([])

    def gain_normalize(self, outfile, comment, dark_ref):
        try:
            n = round(self.var_exposure_time.get()/self.ctrl.cam.default_exposure)
            if SCALE is None:
                arr = np.zeros(self.ctrl.cam.dimensions, dtype=np.float32)
            else:
                arr = np.zeros((round(self.ctrl.cam.dimensions[0]/SCALE),round(self.ctrl.cam.dimensions[1]/SCALE)), dtype=np.float32)
            self.ctrl.cam.block()
            for i in range(n):
                img, _ = self.ctrl.get_image(exposure=self.ctrl.cam.default_exposure)
                arr += img
            arr /= n
            arr -= dark_ref
            arr = arr.mean() / arr
            self.ctrl.cam.unblock()
            write_tiff(outfile, arr, header=comment)
        finally:
            self.enable_widgets([self.ContinueButton, self.StopButton])

    def start_gain_normalize(self):
        exposure = round(round(self.var_exposure_time.get()/self.ctrl.cam.default_exposure)*self.ctrl.cam.default_exposure, 1)
        self.var_exposure_time.set(exposure)
        self.lb_coll0.config(text='Gain normalize calibration started. Make sure suitable beam current was adjusted.')
        self.lb_coll1.config(text='')
        self.cam_calib_path = self.calib_path / 'CamCalib'
        self.cam_calib_path.mkdir(parents=True, exist_ok=True)
        outfile = self.cam_calib_path / f'gain_normalize'
        comment = f'Gain normalize exposure {self.var_exposure_time.get():.1f}s'
        dark_ref, _ = read_tiff(self.cam_calib_path / f'dark_reference.tiff')
        t = threading.Thread(target=self.gain_normalize, args=(outfile,comment,dark_ref), daemon=True)
        t.start()
        t = threading.Thread(target=self.show_progress, args=(100,), daemon=True)
        t.start()
        self.disable_widgets([])

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
        try:
            exposure = self.var_exposure_time.get()
            grid_size = self.var_grid_size.get()
            step_size = self.var_step_size.get()

            outfile = self.beamshift_calib_path / 'calib_beamshift_center'

            img_cent, h_cent = self.ctrl.get_image(exposure=exposure, out=outfile, comment='Beam in center of image')
            x_cent, y_cent = beamshift_cent = np.array(self.ctrl.beamshift.get())

            magnification = self.ctrl.magnification.get()
            #step_size = 2500.0 / magnification * step_size

            self.lb_coll0.config(text=f'Beam Shift calibration started. Gridsize: {grid_size} | Stepsize: {step_size:.2f}')
            img_cent, scale = autoscale(img_cent)

            pixel_cent = find_beam_center(img_cent) * self.binsize / scale
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

            shifts = np.array(shifts) * self.binsize / scale
            beampos = np.array(beampos) - np.array(beamshift_cent)

            fit_result = fit_affine_transformation(shifts, beampos, rotation=True, scaling=True, translation=True)
            r = fit_result.r
            t = fit_result.t
            r_i = np.linalg.inv(r)
            beampos_ = np.dot(beampos-t, r_i)
            self.lb_coll0.config(text='Beam Shift calibration finished. Please click Beam Shift Calib again to plot.')

            with open(self.beamshift_calib_path / 'calib_beamshift.pickle', 'wb') as f:
                pickle.dump([r, t, shifts, beampos_], f)

            dct = {}
            dct['shifts'] = shifts.tolist()
            dct['beampos'] = beampos.tolist()
            dct['rotation'] = r.tolist()
            dct['translation'] = t.tolist()
            dct['rotation_inv'] = r_i.tolist()
            dct['pred_beampos'] = beampos_.tolist()

            with open (self.beamshift_calib_path / 'calib_beamshift.yaml', 'w') as f:
                yaml.dump(dct, f)

        except Exception as e:
            self.click = 0
            raise e

    def start_beamshift_calib(self):
        try:
            if self.click == 0:
                self.lb_coll0.config(text='Calibrate beam shift 1. Go to desired mag 2. Adjust to desired intensity')
                self.lb_coll1.config(text='Click Start Beam Shift Calib again.')
                if self.var_mode.get() in ('D', 'LAD', 'diff'):
                    self.beamshift_calib_path = self.calib_path / 'BeamShiftCalib_D'
                else:
                    self.beamshift_calib_path = self.calib_path / 'BeamShiftCalib'
                self.beamshift_calib_path.mkdir(parents=True, exist_ok=True)
                self.disable_widgets([self.BeamShiftCalibButton])
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
                self.lb_coll0.config(text='Thoery vs observed plotted.')
                self.lb_coll1.config(text='')
                self.enable_widgets([])
                self.click = 0
        except Exception as e:
            self.enable_widgets([])
            self.click = 0
            raise e

    @suppress_stderr
    def beamtilt_calib(self):
        try:
            exposure = self.var_exposure_time.get()
            grid_size = self.var_grid_size.get()
            step_size = self.var_step_size.get()

            outfile = self.beamtilt_calib_path / 'calib_beamtilt_center'

            img_cent, h_cent = self.ctrl.get_image(exposure=exposure, out=outfile, comment='Beam in center of image')
            x_cent, y_cent = beamtilt_cent = np.array(self.ctrl.beamtilt.get())

            magnification = self.ctrl.magnification.get()
            #step_size = 2500.0 / magnification * step_size

            self.lb_coll0.config(text=f'Beam Tilt calibration started. Gridsize: {grid_size} | Stepsize: {step_size:.2f}')
            img_cent, scale = autoscale(img_cent)

            pixel_cent = find_beam_center(img_cent) * self.binsize / scale
            print('Beamtilt: x={} | y={}'.format(*beamtilt_cent))
            print('Pixel: x={} | y={}'.format(*pixel_cent))

            shifts = []
            beampos = []

            n = (grid_size - 1) / 2  # number of points = n*(n+1)
            x_grid, y_grid = np.meshgrid(np.arange(-n, n + 1) * step_size, np.arange(-n, n + 1) * step_size)
            tot = grid_size * grid_size

            i = 0
            with tqdm(total=100, ncols=60, bar_format='{l_bar}{bar}') as pbar:
                for dx, dy in np.stack([x_grid, y_grid]).reshape(2, -1).T:
                    self.ctrl.beamtilt.set(x=x_cent + dx, y=y_cent + dy)
                    self.lb_coll1.config(text=str(pbar))
                    outfile = self.beamtilt_calib_path / f'calib_beamshift_{i:04d}'

                    comment = f'Calib beam tilt {i}: dx={dx} - dy={dy}'
                    img, h = self.ctrl.get_image(exposure=exposure, out=outfile, comment=comment, header_keys='BeamTilt')
                    img = imgscale(img, scale)

                    shift, error, phasediff = phase_cross_correlation(img_cent, img, upsample_factor=10)

                    beamtilt = np.array(self.ctrl.beamtilt.get())
                    beampos.append(beamtilt)
                    shifts.append(shift)
                    pbar.update(100/tot)
                    i += 1
                self.lb_coll1.config(text=str(pbar))

            self.ctrl.beamtilt.set(*beamtilt_cent) # reset beam to center

            shifts = np.array(shifts) * self.binsize / scale
            beampos = np.array(beampos) - np.array(beamtilt_cent)

            fit_result = fit_affine_transformation(shifts, beampos, rotation=True, scaling=True, translation=True)
            r = fit_result.r
            t = fit_result.t
            r_i = np.linalg.inv(r)
            beampos_ = np.dot(beampos-t, r_i)
            self.lb_coll0.config(text='Beam Tilt calibration finished. Please click Beam Tilt Calib again to plot.')

            with open(self.beamtilt_calib_path / 'calib_beamtilt.pickle', 'wb') as f:
                pickle.dump([r, t, shifts, beampos_], f)

            dct = {}
            dct['shifts'] = shifts.tolist()
            dct['beampos'] = beampos.tolist()
            dct['rotation'] = r.tolist()
            dct['translation'] = t.tolist()
            dct['rotation_inv'] = r_i.tolist()
            dct['pred_beampos'] = beampos_.tolist()

            with open (self.beamtilt_calib_path / 'calib_beamtilt.yaml', 'w') as f:
                yaml.dump(dct, f)

        except Exception as e:
            self.click = 0
            raise e

    def start_beamtilt_calib(self):
        try:
            if self.click == 0:
                self.lb_coll0.config(text='Calibrate beam tilt 1. Go to desired cam length 2. Center the DP')
                self.lb_coll1.config(text='Click Start Beam Tilt Calib again.')
                if self.var_mode.get() in ('D', 'LAD', 'diff'):
                    self.beamtilt_calib_path = self.calib_path / 'BeamTiltCalib_D'
                else:
                    self.beamtilt_calib_path = self.calib_path / 'BeamTiltCalib'
                self.beamtilt_calib_path.mkdir(parents=True, exist_ok=True)
                self.disable_widgets([self.BeamTiltCalibButton])
                self.click = 1
            elif self.click == 1:
                self.ax.cla()
                self.canvas.draw()
                self.lb_coll0.config(text='Beam Tilt calibration started')
                self.lb_coll1.config(text='')
                t = threading.Thread(target=self.beamtilt_calib, args=(), daemon=True)
                t.start()
                self.click = 2
            elif self.click == 2:
                with open(self.beamtilt_calib_path / 'calib_beamtilt.pickle', 'rb') as f:
                    r, t, shifts, beampos = pickle.load(f)
                self.ax.scatter(*shifts.T, marker='>', label='Observed')
                self.ax.scatter(*beampos.T, marker='<', label='Theoretical')
                self.ax.legend()
                self.canvas.draw()
                self.lb_coll0.config(text='Thoery vs observed plotted.')
                self.lb_coll1.config(text='')
                self.enable_widgets([])
                self.click = 0
        except Exception as e:
            self.enable_widgets([])
            self.click = 0
            raise e

    @suppress_stderr
    def IS1_calib(self):
        try:
            exposure = self.var_exposure_time.get()
            grid_size = self.var_grid_size.get()
            step_size = self.var_step_size.get()

            outfile = self.IS1_calib_path / 'calib_IS1_center'

            img_cent, h_cent = self.ctrl.get_image(exposure=exposure, out=outfile, comment='Beam in center of image')
            x_cent, y_cent = IS1_cent = np.array(self.ctrl.imageshift1.get())

            magnification = self.ctrl.magnification.get()
            #step_size = 2500.0 / magnification * step_size

            self.lb_coll0.config(text=f'Image Shift 1 calibration started. Gridsize: {grid_size} | Stepsize: {step_size:.2f}')
            img_cent, scale = autoscale(img_cent)

            pixel_cent = find_beam_center(img_cent) * self.binsize / scale
            print('IS1: x={} | y={}'.format(*IS1_cent))
            print('Pixel: x={} | y={}'.format(*pixel_cent))

            shifts = []
            beampos = []

            n = (grid_size - 1) / 2  # number of points = n*(n+1)
            x_grid, y_grid = np.meshgrid(np.arange(-n, n + 1) * step_size, np.arange(-n, n + 1) * step_size)
            tot = grid_size * grid_size

            i = 0
            with tqdm(total=100, ncols=60, bar_format='{l_bar}{bar}') as pbar:
                for dx, dy in np.stack([x_grid, y_grid]).reshape(2, -1).T:
                    self.ctrl.imageshift1.set(x=x_cent + dx, y=y_cent + dy)
                    self.lb_coll1.config(text=str(pbar))
                    outfile = self.IS1_calib_path / f'calib_IS1_{i:04d}'

                    comment = f'Calib image shift 1 {i}: dx={dx} - dy={dy}'
                    img, h = self.ctrl.get_image(exposure=exposure, out=outfile, comment=comment, header_keys='ImageShift1')
                    img = imgscale(img, scale)

                    shift, error, phasediff = phase_cross_correlation(img_cent, img, upsample_factor=10)

                    imageshift1 = np.array(self.ctrl.imageshift1.get())
                    beampos.append(imageshift1)
                    shifts.append(shift)
                    pbar.update(100/tot)
                    i += 1
                self.lb_coll1.config(text=str(pbar))

            self.ctrl.imageshift1.set(*IS1_cent) # reset beam to center

            shifts = np.array(shifts) * self.binsize / scale
            beampos = np.array(beampos) - np.array(IS1_cent)

            fit_result = fit_affine_transformation(shifts, beampos, rotation=True, scaling=True, translation=True)
            r = fit_result.r
            t = fit_result.t
            r_i = np.linalg.inv(r)
            beampos_ = np.dot(beampos-t, r_i)
            self.lb_coll0.config(text='Image Shift 1 calibration finished. Please click IS1 Calib again to plot.')

            with open(self.IS1_calib_path / 'calib_IS1.pickle', 'wb') as f:
                pickle.dump([r, t, shifts, beampos_], f)

            dct = {}
            dct['shifts'] = shifts.tolist()
            dct['beampos'] = beampos.tolist()
            dct['rotation'] = r.tolist()
            dct['translation'] = t.tolist()
            dct['rotation_inv'] = r_i.tolist()
            dct['pred_beampos'] = beampos_.tolist()

            with open (self.IS1_calib_path / 'calib_IS1.yaml', 'w') as f:
                yaml.dump(dct, f)

        except Exception as e:
            self.click = 0
            raise e

    def start_IS1_calib(self):
        try:
            if self.click == 0:
                self.lb_coll0.config(text='Calibrate Image Shift 1')
                self.lb_coll1.config(text='Click Start Image Shift 1 Calib again.')
                if self.var_mode.get() in ('D', 'LAD', 'diff'):
                    self.IS1_calib_path = self.calib_path / 'IS1Calib_D'
                else:
                    self.IS1_calib_path = self.calib_path / 'IS1Calib'
                self.IS1_calib_path.mkdir(parents=True, exist_ok=True)
                self.disable_widgets([self.IS1CalibButton])
                self.click = 1
            elif self.click == 1:
                self.ax.cla()
                self.canvas.draw()
                self.lb_coll0.config(text='Image Shift 1 calibration started')
                self.lb_coll1.config(text='')
                t = threading.Thread(target=self.IS1_calib, args=(), daemon=True)
                t.start()
                self.click = 2
            elif self.click == 2:
                with open(self.IS1_calib_path / 'calib_IS1.pickle', 'rb') as f:
                    r, t, shifts, beampos = pickle.load(f)
                self.ax.scatter(*shifts.T, marker='>', label='Observed')
                self.ax.scatter(*beampos.T, marker='<', label='Theoretical')
                self.ax.legend()
                self.canvas.draw()
                self.lb_coll0.config(text='Thoery vs observed plotted.')
                self.lb_coll1.config(text='')
                self.enable_widgets([])
                self.click = 0
        except Exception as e:
            self.enable_widgets([])
            self.click = 0
            raise e

    @suppress_stderr
    def IS2_calib(self):
        try:
            exposure = self.var_exposure_time.get()
            grid_size = self.var_grid_size.get()
            step_size = self.var_step_size.get()

            outfile = self.IS2_calib_path / 'calib_IS2_center'

            img_cent, h_cent = self.ctrl.get_image(exposure=exposure, out=outfile, comment='Beam in center of image')
            x_cent, y_cent = IS2_cent = np.array(self.ctrl.imageshift2.get())

            magnification = self.ctrl.magnification.get()
            #step_size = 2500.0 / magnification * step_size

            self.lb_coll0.config(text=f'Image Shift 2 calibration started. Gridsize: {grid_size} | Stepsize: {step_size:.2f}')
            img_cent, scale = autoscale(img_cent)

            pixel_cent = find_beam_center(img_cent) * self.binsize / scale
            print('IS2: x={} | y={}'.format(*IS2_cent))
            print('Pixel: x={} | y={}'.format(*pixel_cent))

            shifts = []
            beampos = []

            n = (grid_size - 1) / 2  # number of points = n*(n+1)
            x_grid, y_grid = np.meshgrid(np.arange(-n, n + 1) * step_size, np.arange(-n, n + 1) * step_size)
            tot = grid_size * grid_size

            i = 0
            with tqdm(total=100, ncols=60, bar_format='{l_bar}{bar}') as pbar:
                for dx, dy in np.stack([x_grid, y_grid]).reshape(2, -1).T:
                    self.ctrl.imageshift2.set(x=x_cent + dx, y=y_cent + dy)
                    self.lb_coll1.config(text=str(pbar))
                    outfile = self.IS2_calib_path / f'calib_IS2_{i:04d}'

                    comment = f'Calib image shift 2 {i}: dx={dx} - dy={dy}'
                    img, h = self.ctrl.get_image(exposure=exposure, out=outfile, comment=comment, header_keys='ImageShift2')
                    img = imgscale(img, scale)

                    shift, error, phasediff = phase_cross_correlation(img_cent, img, upsample_factor=10)

                    imageshift2 = np.array(self.ctrl.imageshift2.get())
                    beampos.append(imageshift2)
                    shifts.append(shift)
                    pbar.update(100/tot)
                    i += 1
                self.lb_coll1.config(text=str(pbar))

            self.ctrl.imageshift2.set(*IS2_cent) # reset beam to center

            shifts = np.array(shifts) * self.binsize / scale
            beampos = np.array(beampos) - np.array(IS2_cent)

            fit_result = fit_affine_transformation(shifts, beampos, rotation=True, scaling=True, translation=True)
            r = fit_result.r
            t = fit_result.t
            r_i = np.linalg.inv(r)
            beampos_ = np.dot(beampos-t, r_i)
            self.lb_coll0.config(text='Image Shift 2 calibration finished. Please click IS2 Calib again to plot.')

            with open(self.IS2_calib_path / 'calib_IS2.pickle', 'wb') as f:
                pickle.dump([r, t, shifts, beampos_], f)

            dct = {}
            dct['shifts'] = shifts.tolist()
            dct['beampos'] = beampos.tolist()
            dct['rotation'] = r.tolist()
            dct['translation'] = t.tolist()
            dct['rotation_inv'] = r_i.tolist()
            dct['pred_beampos'] = beampos_.tolist()

            with open (self.IS2_calib_path / 'calib_IS2.yaml', 'w') as f:
                yaml.dump(dct, f)

        except Exception as e:
            self.click = 0
            raise e

    def start_IS2_calib(self):
        try:
            if self.click == 0:
                self.lb_coll0.config(text='Calibrate Image Shift 2')
                self.lb_coll1.config(text='Click Start Image Shift 2 Calib again.')
                if self.var_mode.get() in ('D', 'LAD', 'diff'):
                    self.IS2_calib_path = self.calib_path / 'IS2Calib_D'
                else:
                    self.IS2_calib_path = self.calib_path / 'IS2Calib'
                self.IS2_calib_path.mkdir(parents=True, exist_ok=True)
                self.disable_widgets([self.IS2CalibButton])
                self.click = 1
            elif self.click == 1:
                self.ax.cla()
                self.canvas.draw()
                self.lb_coll0.config(text='Image Shift 2 calibration started')
                self.lb_coll1.config(text='')
                t = threading.Thread(target=self.IS2_calib, args=(), daemon=True)
                t.start()
                self.click = 2
            elif self.click == 2:
                with open(self.IS2_calib_path / 'calib_IS2.pickle', 'rb') as f:
                    r, t, shifts, beampos = pickle.load(f)
                self.ax.scatter(*shifts.T, marker='>', label='Observed')
                self.ax.scatter(*beampos.T, marker='<', label='Theoretical')
                self.ax.legend()
                self.canvas.draw()
                self.lb_coll0.config(text='Thoery vs observed plotted.')
                self.lb_coll1.config(text='')
                self.enable_widgets([])
                self.click = 0
        except Exception as e:
            self.enable_widgets([])
            self.click = 0
            raise e


    @suppress_stderr
    def diffshift_calib(self):
        try:
            state = self.ctrl.mode.state
            if state not in ('D', 'diff', 'LAD'):
                raise RuntimeError('Must in diffraction mode to do diffraction shift calibration')

            exposure = self.var_exposure_time.get()
            grid_size = self.var_grid_size.get()
            step_size = self.var_step_size.get()

            outfile = self.diffshift_calib_path / 'calib_diffshift_center'

            img_cent, h_cent = self.ctrl.get_image(exposure=exposure, out=outfile, comment='Beam in center of image')
            x_cent, y_cent = diffshift_cent = np.array(self.ctrl.diffshift.get())

            magnification = self.ctrl.magnification.get()
            #step_size = 2500.0 / magnification * step_size

            self.lb_coll0.config(text=f'Diff Shift calibration started. Gridsize: {grid_size} | Stepsize: {step_size:.2f}')
            img_cent, scale = autoscale(img_cent)

            if self.software_binsize is None:
                pixel_cent = find_beam_center(img_cent) * self.binsize / scale
            else:
                pixel_cent = find_beam_center(img_cent) * self.binsize * self.software_binsize / scale
            print('Diffshift: x={} | y={}'.format(*diffshift_cent))
            print('Pixel: x={} | y={}'.format(*pixel_cent))

            shifts = []
            beampos = []

            n = (grid_size - 1) / 2  # number of points = n*(n+1)
            x_grid, y_grid = np.meshgrid(np.arange(-n, n + 1) * step_size, np.arange(-n, n + 1) * step_size)
            tot = grid_size * grid_size

            i = 0
            with tqdm(total=100, ncols=60, bar_format='{l_bar}{bar}') as pbar:
                for dx, dy in np.stack([x_grid, y_grid]).reshape(2, -1).T:
                    self.ctrl.diffshift.set(x=x_cent + dx, y=y_cent + dy)
                    self.lb_coll1.config(text=str(pbar))
                    outfile = self.diffshift_calib_path / f'calib_diffshift_{i:04d}'

                    comment = f'Calib diff shift {i}: dx={dx} - dy={dy}'
                    img, h = self.ctrl.get_image(exposure=exposure, out=outfile, comment=comment, header_keys='DiffShift')
                    img = imgscale(img, scale)

                    shift, error, phasediff = phase_cross_correlation(img_cent, img, upsample_factor=10)

                    diffshift = np.array(self.ctrl.diffshift.get())
                    beampos.append(diffshift)
                    shifts.append(shift)
                    pbar.update(100/tot)
                    i += 1
                self.lb_coll1.config(text=str(pbar))

            self.ctrl.diffshift.set(*diffshift_cent) # reset beam to center

            if self.software_binsize is None:
                shifts = np.array(shifts) * self.binsize / scale
            else:
                shifts = np.array(shifts) * self.binsize * self.software_binsize / scale
            beampos = np.array(beampos) - np.array(diffshift_cent)

            fit_result = fit_affine_transformation(shifts, beampos, rotation=True, scaling=True, translation=True)
            r = fit_result.r
            t = fit_result.t
            r_i = np.linalg.inv(r)
            beampos_ = np.dot(beampos-t, r_i)
            self.lb_coll0.config(text='Diff Shift calibration finished. Please click Diff Shift Calib again to plot.')

            with open(self.diffshift_calib_path / 'calib_diffshift.pickle', 'wb') as f:
                pickle.dump([r, t, shifts, beampos_, pixel_cent], f)

            dct = {}
            dct['shifts'] = shifts.tolist()
            dct['beampos'] = beampos.tolist()
            dct['rotation'] = r.tolist()
            dct['translation'] = t.tolist()
            dct['rotation_inv'] = r_i.tolist()
            dct['pred_beampos'] = beampos_.tolist()
            dct['reference_pixel'] = pixel_cent.tolist()

            with open (self.diffshift_calib_path / 'calib_diffshift.yaml', 'w') as f:
                yaml.dump(dct, f)

        except Exception as e:
            self.click = 0
            raise e

    def start_diffshift_calib(self):
        try:
            if self.click == 0:
                self.lb_coll0.config(text='Calibrate Diff Shift')
                self.lb_coll1.config(text='Click Start Diff Shift Calib again.')
                if self.var_mode.get() in ('D', 'LAD', 'diff'):
                    self.diffshift_calib_path = self.calib_path / 'DiffCalib_D'
                else:
                    self.diffshift_calib_path = self.calib_path / 'DiffCalib'
                self.diffshift_calib_path.mkdir(parents=True, exist_ok=True)
                self.disable_widgets([self.DiffShiftCalibButton])
                self.click = 1
            elif self.click == 1:
                self.ax.cla()
                self.canvas.draw()
                self.lb_coll0.config(text='Diff Shift calibration started')
                self.lb_coll1.config(text='')
                t = threading.Thread(target=self.diffshift_calib, args=(), daemon=True)
                t.start()
                self.click = 2
            elif self.click == 2:
                with open(self.diffshift_calib_path / 'calib_diffshift.pickle', 'rb') as f:
                    r, t, shifts, beampos = pickle.load(f)
                self.ax.scatter(*shifts.T, marker='>', label='Observed')
                self.ax.scatter(*beampos.T, marker='<', label='Theoretical')
                self.ax.legend()
                self.canvas.draw()
                self.lb_coll0.config(text='Thoery vs observed plotted.')
                self.lb_coll1.config(text='')
                self.enable_widgets([])
                self.click = 0
        except Exception as e:
            self.enable_widgets([])
            self.click = 0
            raise e

    @suppress_stderr
    def stage_calib(self):
        try:
            state = self.ctrl.mode.state
            if state in ('D', 'diff', 'LAD'):
                raise RuntimeError('Must in imaging mode to do stage calibration')

            exposure = self.var_exposure_time.get()
            grid_size = self.var_grid_size.get()
            step_size = self.var_step_size.get()

            outfile = self.stage_calib_path / 'calib_stage_center'

            x_cent, y_cent = stage_cent = np.array(self.ctrl.stage.xy)
            self.ctrl.stage.set_xy_with_backlash_correction(*stage_cent, step=5000, settle_delay=0.32)
            img_cent, h_cent = self.ctrl.get_image(exposure=exposure, out=outfile, comment='Object in center of image')

            magnification = self.ctrl.magnification.get()
            #step_size = 2500.0 / magnification * step_size

            if self.software_binsize is None:
                    pixelsize = config.calibration[state]['pixelsize'][magnification] * self.binsize #nm->um
                else:
                    pixelsize = config.calibration[state]['pixelsize'][magnification] * self.binsize * self.software_binsize

            self.lb_coll0.config(text=f'Stage calibration started. Gridsize: {grid_size} | Stepsize: {step_size:.2f}')
            img_cent, scale = autoscale(img_cent)

            print('Stage: x={} | y={}'.format(*stage_cent))

            shifts = []
            stagepos = []

            n = (grid_size - 1) / 2  # number of points = n*(n+1)
            x_grid, y_grid = np.meshgrid(np.arange(-n, n + 1) * step_size, np.arange(-n, n + 1) * step_size)
            tot = grid_size * grid_size

            i = 0
            with tqdm(total=100, ncols=60, bar_format='{l_bar}{bar}') as pbar:
                for dx, dy in np.stack([x_grid, y_grid]).reshape(2, -1).T:
                    self.ctrl.stage.set_xy_with_backlash_correction(x=x_cent+dx, y=y_cent+dy, step=5000, settle_delay=0.32)
                    self.lb_coll1.config(text=str(pbar))
                    outfile = self.stage_calib_path / f'calib_beamshift_{i:04d}'

                    comment = f'Calib stage {i}: dx={dx} - dy={dy}'
                    img, h = self.ctrl.get_image(exposure=exposure, out=outfile, comment=comment, header_keys='StagePosition')
                    img = imgscale(img, scale)

                    shift, error, phasediff = phase_cross_correlation(img_cent, img, upsample_factor=10)

                    stageshift = np.array(self.ctrl.stage.xy)
                    stagepos.append(stageshift)
                    shifts.append(shift)
                    pbar.update(100/tot)
                    i += 1
                self.lb_coll1.config(text=str(pbar))

            self.ctrl.stage.xy = *stage_cent # reset beam to center

            shifts = np.array(shifts) * self.binsize / scale
            stagepos = (np.array(stagepos) - np.array(stage_cent)) / pixelsize # transform from nm to pixel

            fit_result = fit_affine_transformation(shifts, stagepos, rotation=True, scaling=False, translation=True)
            r = fit_result.r
            t = fit_result.t
            r_i = np.linalg.inv(r)
            stagepos_ = np.dot(stagepos-t, r_i)
            self.lb_coll0.config(text='Stage calibration finished. Please click Stage Calib again to plot.')

            with open(self.stage_calib_path / 'calib_stage.pickle', 'wb') as f:
                pickle.dump([r, t, shifts, stagepos_], f)

            dct = {}
            dct['shifts'] = shifts.tolist()
            dct['stagepos'] = stagepos.tolist()
            dct['rotation'] = r.tolist()
            dct['translation'] = t.tolist()
            dct['rotation_inv'] = r_i.tolist()
            dct['pred_stagepos'] = stagepos_.tolist()

            with open (self.stage_calib_path / 'calib_stage.yaml', 'w') as f:
                yaml.dump(dct, f)

        except Exception as e:
            self.click = 0
            raise e

    def start_stage_calib(self):
        try:
            if self.click == 0:
                self.lb_coll0.config(text='Calibrate stage vs camera 1. Go to image mode 2. Find area with particles.')
                self.lb_coll1.config(text='Click Start Stage Calib again.')
                if self.var_mode.get() in ('D', 'LAD', 'diff'):
                    self.stage_calib_path = self.calib_path / 'StageCalib_D'
                else:
                    self.stage_calib_path = self.calib_path / 'StageCalib'
                self.stage_calib_path.mkdir(parents=True, exist_ok=True)
                self.disable_widgets([self.StageCalibButton])
                self.click = 1
            elif self.click == 1:
                self.ax.cla()
                self.canvas.draw()
                self.lb_coll0.config(text='Stage calibration started')
                self.lb_coll1.config(text='')
                t = threading.Thread(target=self.stage_calib, args=(), daemon=True)
                t.start()
                self.click = 2
            elif self.click == 2:
                with open(self.stage_calib_path / 'calib_stage.pickle', 'rb') as f:
                    r, t, shifts, beampos = pickle.load(f)
                self.ax.scatter(*shifts.T, marker='>', label='Observed')
                self.ax.scatter(*beampos.T, marker='<', label='Theoretical')
                self.ax.legend()
                self.canvas.draw()
                self.enable_widgets([])
                self.click = 0
        except Exception as e:
            self.enable_widgets([])
            self.click = 0
            raise e


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