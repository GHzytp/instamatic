import threading
from tkinter import *
from tkinter.ttk import *
import decimal

from .base_module import BaseModule
from .modules import MODULES
from instamatic.utils.widgets import Spinbox
from instamatic import config
from instamatic import TEMController

class ExperimentalTOMO(LabelFrame):
    """GUI panel to perform a simple TOMO experiment using discrete rotation
    steps."""

    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Electron Tomography')
        self.parent = parent
        self.ctrl = TEMController.get_instance()
        self.roi = None
        sbwidth = 7
        self.collectEvent = threading.Event()
        self.collectEvent.set()
        self.stop_event = threading.Event()

        try:
            self.stream_frame = [module for module in MODULES if module.name == 'stream'][0].frame
        except IndexError:
            self.stream_frame = None

        self.software_binsize = config.settings.software_binsize
        if self.software_binsize is None:
            self.dimension = self.ctrl.cam.dimensions
        else:
            self.dimension = (round(self.ctrl.cam.dimensions[0]/self.software_binsize), round(self.ctrl.cam.dimensions[1]/self.software_binsize))

        self.init_vars()

        frame = Frame(self)
        Label(frame, text='Exposure (s)').grid(row=4, column=0, sticky='W')
        self.e_exposure_time = Spinbox(frame, textvariable=self.var_exposure_time, width=sbwidth, from_=0.1, to=10.0, increment=0.1)
        self.e_exposure_time.grid(row=4, column=1, sticky='W', padx=5)

        Label(frame, text='Tilt (deg)').grid(row=4, column=2, sticky='W')
        self.e_tilt_range = Spinbox(frame, textvariable=self.var_tilt_range, width=sbwidth, from_=0, to=5.0, increment=0.1)
        self.e_tilt_range.grid(row=4, column=3, sticky='W', padx=5)

        Label(frame, text='Step (deg)').grid(row=4, column=4, sticky='W')
        self.e_stepsize = Spinbox(frame, textvariable=self.var_stepsize, width=sbwidth, from_=-3.0, to=3.0, increment=0.1)
        self.e_stepsize.grid(row=4, column=5, sticky='W', padx=5)

        Label(frame, text='Interval (s)').grid(row=4, column=6, sticky='W')
        self.e_wait_interval = Spinbox(frame, textvariable=self.var_wait_interval, width=sbwidth, from_=0, to=20, increment=0.1)
        self.e_wait_interval.grid(row=4, column=7, sticky='W', padx=5)

        frame.pack(side='top', fill='x', padx=5, pady=5)

        frame = Frame(self)

        Checkbutton(frame, text='Align', variable=self.var_align, command=self.do_align).grid(row=1, column=0, sticky='EW', padx=5)
        Checkbutton(frame, text='Align ROI', variable=self.var_align_roi, command=self.align_roi).grid(row=1, column=1, sticky='EW')
        self.e_x0 = Spinbox(frame, textvariable=self.var_x0, width=sbwidth, from_=0, to=self.dimension[0], increment=0.1, state=DISABLED)
        self.e_x0.grid(row=1, column=2, sticky='W', padx=5)
        self.e_y0 = Spinbox(frame, textvariable=self.var_y0, width=sbwidth, from_=0, to=self.dimension[1], increment=0.1, state=DISABLED)
        self.e_y0.grid(row=1, column=3, sticky='W')
        self.e_x1 = Spinbox(frame, textvariable=self.var_x1, width=sbwidth, from_=self.var_x0.get(), to=self.dimension[0], increment=0.1, state=DISABLED)
        self.e_x1.grid(row=1, column=4, sticky='W', padx=5)
        self.e_y1 = Spinbox(frame, textvariable=self.var_y1, width=sbwidth, from_=self.var_y0.get(), to=self.dimension[1], increment=0.1, state=DISABLED)
        self.e_y1.grid(row=1, column=5, sticky='W')
        self.UpdateROIButton = Button(frame, text='Update ROI', command=self.update_roi, state=DISABLED)
        self.UpdateROIButton.grid(row=1, column=6, sticky='EW', padx=5)

        frame.pack(side='top', fill='x', padx=5, pady=5)

        frame = Frame(self)
        self.StartButton = Button(frame, text='Start Collection', command=self.start_collection)
        self.StartButton.grid(row=1, column=0, sticky='EW')
        self.ContinueButton = Button(frame, text='Continue', command=self.continue_collection, state=DISABLED)
        self.ContinueButton.grid(row=1, column=1, sticky='EW', padx=5)        
        self.FinalizeButton = Button(frame, text='Finalize', command=self.stop_collection, state=DISABLED)
        self.FinalizeButton.grid(row=1, column=2, sticky='EW')

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        Separator(frame, orient=HORIZONTAL).grid(row=2, columnspan=3, sticky='ew', pady=5)

        frame.pack(side='top', fill='x', padx=5, pady=5)

        frame = Frame(self)

        Label(frame, text='End angle').grid(row=0, column=0, sticky='W')
        self.e_end_angle = Spinbox(frame, textvariable=self.var_end_angle, width=sbwidth, from_=-75.0, to=75.0, increment=0.1)
        self.e_end_angle.grid(row=0, column=1, sticky='W', padx=5)
        Label(frame, text='Mag').grid(row=0, column=2, sticky='W')
        self.e_eucentric_tilt = Spinbox(frame, textvariable=self.var_magnification_index, width=sbwidth, from_=0, to=10, increment=1)
        self.e_eucentric_tilt.grid(row=0, column=3, sticky='W', padx=5)
        Label(frame, text='Stage tilt (deg)').grid(row=0, column=4, sticky='W')
        self.e_eucentric_tilt = Spinbox(frame, textvariable=self.var_stage_tilt, width=sbwidth, from_=-10.0, to=10.0, increment=0.01)
        self.e_eucentric_tilt.grid(row=0, column=5, sticky='W', padx=5)
        self.AutoEucentricButton = Button(frame, text='Auto Eucentric', command=self.auto_eucentric_height, state=NORMAL)
        self.AutoEucentricButton.grid(row=0, column=6, sticky='EW')

        Label(frame, text='Defocus (nm)').grid(row=1, column=0, sticky='W')
        self.e_defocus = Spinbox(frame, textvariable=self.var_defocus, width=sbwidth, from_=-20000, to=20000, increment=1)
        self.e_defocus.grid(row=1, column=1, sticky='W', padx=5)
        Label(frame, text='Cs (mm)').grid(row=1, column=2, sticky='W')
        self.e_cs = Spinbox(frame, textvariable=self.var_cs, width=sbwidth, from_=-2, to=2, increment=0.01)
        self.e_cs.grid(row=1, column=3, sticky='W', padx=5)
        Label(frame, text='Beam Tilt (deg)').grid(row=1, column=4, sticky='W')
        self.e_beam_tilt = Spinbox(frame, textvariable=self.var_beam_tilt, width=sbwidth, from_=-5.0, to=5.0, increment=0.01)
        self.e_beam_tilt.grid(row=1, column=5, sticky='W', padx=5)
        self.AutoFocusButton = Button(frame, text='Auto Focus', command=self.auto_focus, state=NORMAL)
        self.AutoFocusButton.grid(row=1, column=6, sticky='EW')

        Label(frame, text='Watershed a').grid(row=2, column=0, sticky='W')
        self.e_watershed_a = Spinbox(frame, textvariable=self.var_watershed_a, width=sbwidth, from_=0.1, to=75, increment=0.1)
        self.e_watershed_a.grid(row=2, column=1, sticky='W', padx=5)
        Label(frame, text='Low').grid(row=2, column=2, sticky='W')
        self.e_low_interval = Spinbox(frame, textvariable=self.var_low_interval, width=sbwidth, from_=1, to=20, increment=1)
        self.e_low_interval.grid(row=2, column=3, sticky='W', padx=5)
        Label(frame, text='High interval').grid(row=2, column=4, sticky='W')
        self.e_high_interval = Spinbox(frame, textvariable=self.var_high_interval, width=sbwidth, from_=1, to=10, increment=1)
        self.e_high_interval.grid(row=2, column=5, sticky='W', padx=5)
        auto_tomo_option = ['stage tilt only', 'stage and beam tilt']
        self.e_auto_tomo_option = OptionMenu(frame, self.var_auto_tomo_option, 'stage tilt only', *auto_tomo_option)
        self.e_auto_tomo_option.grid(row=2, column=6, columnspan=2, sticky='W')

        frame.pack(side='top', fill='x', padx=5, pady=5)

        frame = Frame(self)
        Label(frame, text='Output formats:').grid(row=5, columnspan=2, sticky='EW')
        Checkbutton(frame, text='TIFF (.tiff)', variable=self.var_save_tiff, state=NORMAL).grid(row=5, column=2, sticky='EW')
        Checkbutton(frame, text='MRC (.mrc)', variable=self.var_save_mrc, state=NORMAL).grid(row=5, column=3, sticky='EW')
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=1)
        frame.grid_columnconfigure(3, weight=1)

        frame.pack(side='top', fill='x', padx=5, pady=5)

        frame = Frame(self)
        self.StartAutoButton = Button(frame, text='Start Auto Collection', command=self.start_auto_collection)
        self.StartAutoButton.grid(row=1, column=0, sticky='EW')  
        self.PauseAutoButton = Button(frame, text='Pause Auto Collection', command=self.pause_or_continue_auto_collection, state=DISABLED)
        self.PauseAutoButton.grid(row=1, column=1, sticky='EW')   
        self.StopAutoButton = Button(frame, text='Stop Auto Collection', command=self.stop_auto_collection, state=DISABLED)
        self.StopAutoButton.grid(row=1, column=2, sticky='EW')

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)

        frame.pack(side='bottom', fill='x', padx=5, pady=5)

        self.stopEvent = threading.Event()
        self.collectEvent = threading.Event()
        self.collectEvent.set()
        
    def init_vars(self):
        self.var_exposure_time = DoubleVar(value=1.0)
        #self.var_exposure_time.trace('w', self.check_exposure_time)
        self.var_tilt_range = DoubleVar(value=1.0)
        self.var_stepsize = DoubleVar(value=1.0)
        self.var_wait_interval = DoubleVar(value=1.0)

        self.var_save_tiff = BooleanVar(value=False)
        self.var_save_mrc = BooleanVar(value=True)

        self.var_align = BooleanVar(value=True)
        self.var_align_roi = BooleanVar(value=False)
        self.var_x0 = IntVar(value=int(self.dimension[0]*0.25))
        self.var_y0 = IntVar(value=int(self.dimension[1]*0.25))
        self.var_x1 = IntVar(value=int(self.dimension[0]*0.75))
        self.var_y1 = IntVar(value=int(self.dimension[1]*0.75))

        self.var_end_angle = DoubleVar(value=70.0)
        self.var_magnification_index = IntVar(value=7)
        self.var_defocus = IntVar(value=-5000)
        self.var_cs = DoubleVar(value=0.0)
        self.var_beam_tilt = DoubleVar(value=1.0)
        self.var_stage_tilt = DoubleVar(value=5.0)

        self.var_watershed_a = DoubleVar(value=40.0)
        self.var_low_interval = IntVar(value=1)
        self.var_high_interval = IntVar(value=1)
        self.var_auto_tomo_option = StringVar(value='stage tilt only')

    def pause_or_continue_auto_collection(self):
        if self.collectEvent.is_set():
            self.collectEvent.clear()
            self.PauseAutoButton.config(text='Continue')
        else:
            self.collectEvent.set()
            self.PauseAutoButton.config(text='Pause')

    def do_align(self):
        pass

    def enable_roi(self):
        self.e_x0.config(state=NORMAL)
        self.e_y0.config(state=NORMAL)
        self.e_x1.config(state=NORMAL)
        self.e_y1.config(state=NORMAL)
        self.UpdateROIButton.config(state=NORMAL)

    def disable_roi(self):
        self.e_x0.config(state=DISABLED)
        self.e_y0.config(state=DISABLED)
        self.e_x1.config(state=DISABLED)
        self.e_y1.config(state=DISABLED)
        self.UpdateROIButton.config(state=DISABLED)

    def align_roi(self):
        self.roi = [[self.var_x0.get(), self.var_y0.get()], [self.var_x1.get(), self.var_y1.get()]]
        if self.stream_frame.roi is None:
            if self.var_align_roi.get():
                self.stream_frame.roi = self.stream_frame.panel.create_rectangle(self.roi[0][1], self.roi[0][0], self.roi[1][1], self.roi[1][0], outline='yellow')
                self.enable_roi()
        else:
            if self.var_align_roi.get():
                self.stream_frame.panel.itemconfigure(self.stream_frame.roi, state='normal')
                self.enable_roi()
            else:
                self.stream_frame.panel.itemconfigure(self.stream_frame.roi, state='hidden')
                self.disable_roi()

    def update_roi(self):
        self.roi = [[self.var_x0.get(), self.var_y0.get()], [self.var_x1.get(), self.var_y1.get()]]
        if self.stream_frame.roi is None:
            self.stream_frame.roi = self.stream_frame.panel.create_rectangle(self.roi[0][1], self.roi[0][0], self.roi[1][1], self.roi[1][0], outline='yellow')
        else:
            self.stream_frame.panel.coords(self.stream_frame.roi, self.roi[0][1], self.roi[0][0], self.roi[1][1], self.roi[1][0])

    def auto_eucentric_height(self):
        self.check_exposure_time()
        params = {'stage_tilt': self.var_stage_tilt.get(), 
                  'exposure_time': self.var_exposure_time.get(),
                  'wait_interval': self.var_wait_interval.get(),
                  'defocus': self.var_defocus.get(),
                  'align': self.var_align.get(),
                  'align_roi': self.var_align_roi.get(),
                  'roi': self.roi}
        self.q.put(('eucentric_auto', params))
        self.triggerEvent.set()


    def auto_focus(self):
        self.check_exposure_time()
        params = {'beam_tilt': self.var_beam_tilt.get(), 
                  'exposure_time': self.var_exposure_time.get(),
                  'wait_interval': self.var_wait_interval.get(),
                  'defocus': self.var_defocus.get(),
                  'cs': self.var_cs.get(),
                  'align': self.var_align.get(),
                  'align_roi': self.var_align_roi.get(),
                  'roi': self.roi}
        self.q.put(('focus_auto', params))
        self.triggerEvent.set()

    def check_exposure_time(self):
        if config.camera.interface == "DM":
            try:
                frametime = config.settings.default_frame_time
                n = decimal.Decimal(str(self.var_exposure_time.get())) / decimal.Decimal(str(frametime))
                self.var_exposure_time.set(decimal.Decimal(str(frametime)) * int(n))
            except TclError as e:
                if 'expected floating-point number but got ""' in e.args[0]:
                    pass

    def set_trigger(self, trigger=None, q=None):
        self.triggerEvent = trigger
        self.q = q

    def start_collection(self):
        self.check_exposure_time()
        self.StartButton.config(state=DISABLED)
        self.ContinueButton.config(state=NORMAL)
        self.FinalizeButton.config(state=NORMAL)
        self.e_exposure_time.config(state=DISABLED)
        self.e_stepsize.config(state=DISABLED)
        params = self.get_params(task='start')
        self.q.put(('tomo', params))
        self.triggerEvent.set()

    def continue_collection(self):
        params = self.get_params(task='continue')
        self.q.put(('tomo', params))
        self.triggerEvent.set()

    def stop_collection(self):
        self.StartButton.config(state=NORMAL)
        self.ContinueButton.config(state=DISABLED)
        self.FinalizeButton.config(state=DISABLED)
        self.e_exposure_time.config(state=NORMAL)
        self.e_stepsize.config(state=NORMAL)
        params = self.get_params(task='stop')
        self.q.put(('tomo', params))
        self.triggerEvent.set()

    def start_auto_collection(self):
        self.check_exposure_time()
        self.StartAutoButton.config(state=DISABLED)
        self.PauseAutoButton.config(state=NORMAL)
        self.StopAutoButton.config(state=NORMAL)
        self.e_exposure_time.config(state=DISABLED)
        self.e_stepsize.config(state=DISABLED)
        self.e_end_angle.config(state=DISABLED)
        params = self.get_params()
        params['auto_tomo_option'] = self.var_auto_tomo_option.get()
        params['watershed_angle'] = self.var_watershed_a.get()
        params['high_angle_interval'] = self.var_high_interval.get()
        params['low_angle_interval'] = self.var_low_interval.get()
        self.q.put(('tomo_auto', params))
        self.triggerEvent.set()

    def stop_auto_collection(self):
        self.StartAutoButton.config(state=NORMAL)
        self.PauseAutoButton.config(state=DISABLED)
        self.StopAutoButton.config(state=DISABLED)
        self.e_exposure_time.config(state=NORMAL)
        self.e_stepsize.config(state=NORMAL)
        self.e_end_angle.config(state=NORMAL)
        self.stop_event.set()

    def get_params(self, task=None):
        params = {'exposure_time': self.var_exposure_time.get(),
                  'tilt_range': self.var_tilt_range.get(),
                  'stepsize': self.var_stepsize.get(),
                  'wait_interval': self.var_wait_interval.get(),
                  'write_tiff': self.var_save_tiff.get(),
                  'write_mrc': self.var_save_mrc.get(),
                  'align': self.var_align.get(),
                  'align_roi': self.var_align_roi.get(),
                  'roi': self.roi,
                  'end_angle': self.var_end_angle.get(),
                  'continue_event': self.continue_event,
                  'stop_event': self.stop_event,
                  'task': task}
        return params


def acquire_data_TOMO(controller, **kwargs):
    controller.log.info('Start tomography data collection experiment')
    from instamatic.experiments import TOMO

    task = kwargs['task']

    exposure_time = kwargs['exposure_time']
    tilt_range = kwargs['tilt_range']
    stepsize = kwargs['stepsize']
    wait_interval = kwargs['wait_interval']
    write_tiff = kwargs['write_tiff']
    write_mrc = kwargs['write_mrc']
    align = kwargs['align']
    align_roi = kwargs['align_roi']
    roi = kwargs['roi']

    if task == 'start':
        flatfield = controller.module_io.get_flatfield()

        expdir = controller.module_io.get_new_experiment_directory()
        expdir.mkdir(exist_ok=True, parents=True)

        controller.tomo_exp = TOMO.Experiment(ctrl=controller.ctrl, path=expdir, log=controller.log,
                                            flatfield=flatfield)
        controller.tomo_exp.start_collection(exposure_time=exposure_time, tilt_range=tilt_range, stepsize=stepsize, 
                        wait_interval=wait_interval, align=align, align_roi=align_roi, roi=roi)
    elif task == 'continue':
        controller.tomo_exp.start_collection(exposure_time=exposure_time, tilt_range=tilt_range, stepsize=stepsize, 
                        wait_interval=wait_interval, align=align, align_roi=align_roi, roi=roi)    
    elif task == 'stop':
        controller.tomo_exp.finalize(write_tiff=write_tiff, write_mrc=write_mrc)
        del controller.tomo_exp

def acquire_data_TOMO_auto(controller, **kwargs):
    controller.log.info('Start automatic tomography data collection experiment')
    from instamatic.experiments import TOMO

    exposure_time = kwargs['exposure_time']
    end_angle = kwargs['end_angle']
    stepsize = kwargs['stepsize']
    wait_interval = kwargs['wait_interval']
    write_tiff = kwargs['write_tiff']
    write_mrc = kwargs['write_mrc']
    align = kwargs['align']
    align_roi = kwargs['align_roi']
    roi = kwargs['roi']
    continue_event = kwargs['continue_event']
    stop_event = kwargs['stop_event']
    watershed_angle = params['watershed_angle']
    high_angle_interval = params['high_angle_interval']
    low_angle_interval = params['low_angle_interval']

    flatfield = controller.module_io.get_flatfield()
    expdir = controller.module_io.get_new_experiment_directory()
    expdir.mkdir(exist_ok=True, parents=True)

    tomo_exp = TOMO.Experiment(ctrl=controller.ctrl, path=expdir, log=controller.log, flatfield=flatfield)
    if params['auto_tomo_option'] == 'stage tilt only':
        tomo_exp.start_auto_collection_stage_tilt(exposure_time=exposure_time, end_angle=end_angle, stepsize=stepsize, wait_interval=wait_interval, 
                            align=align, align_roi=align_roi, roi=roi, continue_event=continue_event, stop_event=stop_event, watershed_angle=watershed_angle,
                            high_angle_interval=high_angle_interval, low_angle_interval= low_angle_interval)
    elif params['auto_tomo_option'] == 'stage and beam tilt':
        num_beam_tilt = kwargs['num_beam_tilt']
        tomo_exp.start_auto_collection_stage_beam_tilt(exposure_time=exposure_time, end_angle=end_angle, stepsize=stepsize, wait_interval=wait_interval, 
                            align=align, align_roi=align_roi, roi=roi, continue_event=continue_event, stop_event=stop_event, num_beam_tilt=num_beam_tilt, 
                            watershed_angle=watershed_angle, high_angle_interval=high_angle_interval, low_angle_interval= low_angle_interval)
    tomo_exp.finalize(write_tiff=write_tiff, write_mrc=write_mrc)
   
    controller.log.info('Finish automatic tomography data collection experiment')

def eucentric_auto(controller, **kwargs):
    controller.log.info('Start automatic eucentric height')
    from instamatic.experiments import TOMO

    exposure_time = kwargs['exposure_time']
    wait_interval = kwargs['wait_interval']
    defocus = kwargs['defocus']
    stage_tilt = kwargs['stage_tilt']
    align = kwargs['align']
    align_roi = kwargs['align_roi']
    roi = kwargs['roi']
    
    flatfield = controller.module_io.get_flatfield()

    tomo_exp = TOMO.Experiment(ctrl=controller.ctrl, log=controller.log, flatfield=flatfield)
    success = tomo_exp.start_auto_eucentric_height(exposure_time=exposure_time, wait_interval=wait_interval, align=align, align_roi=align_roi, 
                        roi=roi, defocus=defocus, stage_tilt=stage_tilt)
   
    controller.log.info('Finish automatic eucentric height')

def focus_auto(controller, **kwargs):
    controller.log.info('Start automatic focusing')
    from instamatic.experiments import TOMO

    exposure_time = kwargs['exposure_time']
    wait_interval = kwargs['wait_interval']
    defocus = kwargs['defocus']
    cs = kwargs['cs']
    beam_tilt = kwargs['beam_tilt']
    align = kwargs['align']
    align_roi = kwargs['align_roi']
    roi = kwargs['roi']

    flatfield = controller.module_io.get_flatfield()

    tomo_exp = TOMO.Experiment(ctrl=controller.ctrl, log=controller.log, flatfield=flatfield)
    success = tomo_exp.start_auto_focus(exposure_time=exposure_time, wait_interval=wait_interval, align=align, align_roi=align_roi, 
                        roi=roi, cs=cs, defocus=defocus, beam_tilt=beam_tilt)
   
    controller.log.info('Finish automatic focusing')


module = BaseModule(name='tomo', display_name='TOMO', tk_frame=ExperimentalTOMO, location='bottom')
commands = {'tomo': acquire_data_TOMO, 'tomo_auto': acquire_data_TOMO_auto, 'eucentric_auto': eucentric_auto, 'focus_auto': focus_auto}


if __name__ == '__main__':
    root = Tk()
    ExperimentalTOMO(root).pack(side='top', fill='both', expand=True)
    root.mainloop()
