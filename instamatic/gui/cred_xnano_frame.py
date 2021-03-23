import threading
import time
from datetime import datetime
from tkinter import *
from tkinter.ttk import *
from numpy import pi

from .base_module import BaseModule
from .modules import MODULES
from instamatic.holder.holder import get_instance
from instamatic.utils.widgets import Spinbox, Hoverbox
from instamatic import config
from instamatic import TEMController

class ExperimentalcREDXnano(LabelFrame):
    """GUI panel for holder function testing."""

    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='cRED data collection using XNano holder')
        self.parent = parent
        self.tem_ctrl = TEMController.get_instance()
        self.image_stream = self.tem_ctrl.image_stream
        self.stream_frame = [module for module in MODULES if module.name == 'stream'][0].frame
        self.rec_path = config.locations['work'] / 'rec'

        self.init_vars()

        frame = Frame(self)

        self.ConnectButton = Button(frame, text='Connect Holder', command=self.connect, state=NORMAL)
        self.ConnectButton.grid(row=0, column=0, sticky='EW', padx=5)
        Hoverbox(self.ConnectButton, 'Connect to a holder, enable all the operations. Close the GUI to disconnect.')

        Label(frame, text='Holder ID:').grid(row=0, column=1, sticky='W')
        self.lb_holder_id = Label(frame, width=10, textvariable=self.var_holder_id)
        self.lb_holder_id.grid(row=0, column=2, sticky='EW', padx=5)

        Label(frame, text='Angle:').grid(row=0, column=3, sticky='W')
        self.lb_angle = Label(frame, width=5, text='0.0')
        self.lb_angle.grid(row=0, column=4, sticky='EW', padx=5)
        self.GetAngleButton = Button(frame, text='Get Angle', command=self.get_angle, state=DISABLED)
        self.GetAngleButton.grid(row=0, column=5, sticky='EW')
        Hoverbox(self.GetAngleButton, 'Read current angle, unit is degree.')
        Label(frame, text='Distance:').grid(row=0, column=6, sticky='W', padx=5)
        self.lb_distance = Label(frame, width=5, text='0.0')
        self.lb_distance.grid(row=0, column=7, sticky='EW')
        self.GetDistButton = Button(frame, text='Get Distance', command=self.get_distance, state=DISABLED)
        self.GetDistButton.grid(row=0, column=8, sticky='EW', padx=5)
        Hoverbox(self.GetDistButton, 'Read current distance, unit is mm.')

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)
        
        frame = Frame(self)

        Label(frame, text='Axis:').grid(row=1, column=0, sticky='W')
        self.e_axis = Spinbox(frame, width=8, textvariable=self.var_axis, from_=0, to=3, increment=1, state=DISABLED)
        self.e_axis.grid(row=1, column=1, sticky='EW', padx=5, pady=5)
        Hoverbox(self.e_axis, 'The axis to move: 0->x, 1->y, 2->z, 3->alpha')
        Label(frame, text='Pulse:').grid(row=1, column=2, sticky='W')
        self.e_pulse = Spinbox(frame, width=8, textvariable=self.var_pulse, from_=0, to=255, increment=1, state=DISABLED)
        self.e_pulse.grid(row=1, column=3, sticky='EW', padx=5, pady=5)
        Hoverbox(self.e_pulse, 'Number of pulses or steps. 255 is an exception. 255 will make the holder rotate forever.')
        Label(frame, text='Speed:').grid(row=1, column=4, sticky='W')
        self.e_speed = Spinbox(frame, width=8, textvariable=self.var_speed, from_=0, increment=1, state=DISABLED)
        self.e_speed.grid(row=1, column=5, sticky='EW', padx=5, pady=5)
        Hoverbox(self.e_speed, 'Pulse length, unit is Hz')
        Label(frame, text='Amp:').grid(row=1, column=6, sticky='W')
        self.e_amp = Spinbox(frame, width=8, textvariable=self.var_amp, from_=-25122, to=25122, increment=1, state=DISABLED)
        self.e_amp.grid(row=1, column=7, sticky='EW', padx=5, pady=5)
        Hoverbox(self.e_amp, 'Voltage applied to drive the holder, unit is (150/32767V). '
                             'The largeest volage that the driver box can output is 115V. '
                             'When the value is negative, the holder will move to the opposite direction.')
        Label(frame, text='Angle:').grid(row=1, column=8, sticky='W')
        self.e_angle = Spinbox(frame, width=8, textvariable=self.var_angle, from_=-180.0, to=180.0, increment=0.01, state=DISABLED)
        self.e_angle.grid(row=1, column=9, sticky='EW', padx=5, pady=5)
        Hoverbox(self.e_angle, 'Target angle, unit degree')
        Label(frame, text='Interval').grid(row=2, column=8, sticky='W')
        self.e_interval = Spinbox(frame, width=8, textvariable=self.var_interval, from_=1, to=10000, increment=1, state=DISABLED)
        self.e_interval.grid(row=2, column=9, sticky='EW', padx=5, pady=5)
        Hoverbox(self.e_interval, 'Record time interval, unit: ms')

        self.CoarseMoveButton = Button(frame, text='Coarse Move', command=self.coarse_move, state=DISABLED)
        self.CoarseMoveButton.grid(row=2, column=0, columnspan=2, sticky='EW')
        Hoverbox(self.CoarseMoveButton, 'Holder coarse move. Need to fill in axis, pulses, speed and amp.')
        self.StopCoarseMoveButton = Button(frame, text='Stop', command=self.stop_coarse_move, state=DISABLED)
        self.StopCoarseMoveButton.grid(row=2, column=2, columnspan=2, sticky='EW', padx=5)
        self.FineMoveButton = Button(frame, text='Fine Move', command=self.fine_move, state=DISABLED)
        self.FineMoveButton.grid(row=2, column=4, columnspan=2, sticky='EW')
        Hoverbox(self.FineMoveButton, 'Holder fine move. Need to fill in axis and amp')
        self.RotateToButton = Button(frame, text='Rotate To', command=self.rotate_to, state=DISABLED)
        self.RotateToButton.grid(row=2, column=6, columnspan=2, sticky='EW', padx=5)
        Hoverbox(self.RotateToButton, 'Holder rotation move. Need to fill in angle and amp.')

        self.RotateRecordButton = Button(frame, text='Rotate&Record', command=self.rotate_record, state=DISABLED)
        self.RotateRecordButton.grid(row=3, column=0, columnspan=2, sticky='EW')
        Hoverbox(self.RotateRecordButton, 'Holder rotate and record angles and corresponding images. Need to fill in interval, angle and amp.')
        self.StopRecordButton = Button(frame, text='Stop Record', command=self.stop_record, state=DISABLED)
        self.StopRecordButton.grid(row=3, column=2, columnspan=2, sticky='EW', padx=5)
        Hoverbox(self.StopRecordButton, 'Stop recording angles')
        self.SaveImgButton = Button(frame, text='Save Img', command=self.save_img, state=DISABLED)
        self.SaveImgButton.grid(row=3, column=4, columnspan=2, sticky='EW')
        Hoverbox(self.SaveImgButton, 'Save images in tiff file. The meta data was stored in the head file.')
        
        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Label(frame, text='Compensation Coefficients:').grid(row=1, column=0, columnspan=3, sticky='W')
        self.coff_0 = Spinbox(frame, textvariable=self.var_coff_0, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_0.focus()
        self.coff_0.grid(row=1, column=3, sticky='EW', padx=5)
        Hoverbox(self.coff_0, 'Compensation Coefficient 0')
        self.coff_1 = Spinbox(frame, textvariable=self.var_coff_1, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_1.focus()
        self.coff_1.grid(row=1, column=4, sticky='EW')
        Hoverbox(self.coff_1, 'Compensation Coefficient 1')
        self.coff_2 = Spinbox(frame, textvariable=self.var_coff_2, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_2.focus()
        self.coff_2.grid(row=1, column=5, sticky='EW', padx=5)
        Hoverbox(self.coff_2, 'Compensation Coefficient 2')
        self.coff_3 = Spinbox(frame, textvariable=self.var_coff_3, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_3.focus()
        self.coff_3.grid(row=1, column=6, sticky='EW')
        Hoverbox(self.coff_3, 'Compensation Coefficient 3')
        self.coff_4 = Spinbox(frame, textvariable=self.var_coff_4, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_4.focus()
        self.coff_4.grid(row=1, column=7, sticky='EW', padx=5)
        Hoverbox(self.coff_4, 'Compensation Coefficient 4')
        self.coff_5 = Spinbox(frame, textvariable=self.var_coff_5, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_5.focus()
        self.coff_5.grid(row=1, column=8, sticky='EW')
        Hoverbox(self.coff_5, 'Compensation Coefficient 5')

        self.coff_6 = Spinbox(frame, textvariable=self.var_coff_6, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_6.focus()
        self.coff_6.grid(row=2, column=0, sticky='EW')
        Hoverbox(self.coff_6, 'Compensation Coefficient 6')
        self.coff_7 = Spinbox(frame, textvariable=self.var_coff_7, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_7.focus()
        self.coff_7.grid(row=2, column=1, sticky='EW', padx=5)
        Hoverbox(self.coff_7, 'Compensation Coefficient 7')
        self.coff_8 = Spinbox(frame, textvariable=self.var_coff_8, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_8.focus()
        self.coff_8.grid(row=2, column=2, sticky='EW')
        Hoverbox(self.coff_8, 'Compensation Coefficient 8')
        self.coff_9 = Spinbox(frame, textvariable=self.var_coff_9, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_9.focus()
        self.coff_9.grid(row=2, column=3, sticky='EW', padx=5)
        Hoverbox(self.coff_9, 'Compensation Coefficient 9')
        self.coff_10 = Spinbox(frame, textvariable=self.var_coff_10, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_10.focus()
        self.coff_10.grid(row=2, column=4, sticky='EW')
        Hoverbox(self.coff_10, 'Compensation Coefficient 10')
        self.coff_11 = Spinbox(frame, textvariable=self.var_coff_11, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_11.focus()
        self.coff_11.grid(row=2, column=5, sticky='EW', padx=5)
        Hoverbox(self.coff_11, 'Compensation Coefficient 11')
        self.coff_12 = Spinbox(frame, textvariable=self.var_coff_12, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_12.focus()
        self.coff_12.grid(row=2, column=6, sticky='EW')
        Hoverbox(self.coff_12, 'Compensation Coefficient 12')
        self.coff_13 = Spinbox(frame, textvariable=self.var_coff_13, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_13.focus()
        self.coff_13.grid(row=2, column=7, sticky='EW', padx=5)
        Hoverbox(self.coff_13, 'Compensation Coefficient 13')
        self.coff_14 = Spinbox(frame, textvariable=self.var_coff_14, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_14.focus()
        self.coff_14.grid(row=2, column=8, sticky='EW')
        Hoverbox(self.coff_14, 'Compensation Coefficient 14')
        self.coff_15 = Spinbox(frame, textvariable=self.var_coff_15, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_15.focus()
        self.coff_15.grid(row=3, column=0, sticky='EW')
        Hoverbox(self.coff_15, 'Compensation Coefficient 15')

        self.coff_16 = Spinbox(frame, textvariable=self.var_coff_16, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_16.focus()
        self.coff_16.grid(row=3, column=1, sticky='EW', padx=5)
        Hoverbox(self.coff_16, 'Compensation Coefficient 16')
        self.coff_17 = Spinbox(frame, textvariable=self.var_coff_17, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_17.focus()
        self.coff_17.grid(row=3, column=2, sticky='EW')
        Hoverbox(self.coff_17, 'Compensation Coefficient 17')
        self.coff_18 = Spinbox(frame, textvariable=self.var_coff_18, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_18.focus()
        self.coff_18.grid(row=3, column=3, sticky='EW', padx=5)
        Hoverbox(self.coff_18, 'Compensation Coefficient 18')
        self.coff_19 = Spinbox(frame, textvariable=self.var_coff_19, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_19.focus()
        self.coff_19.grid(row=3, column=4, sticky='EW')
        Hoverbox(self.coff_19, 'Compensation Coefficient 19')
        self.coff_20 = Spinbox(frame, textvariable=self.var_coff_20, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_20.focus()
        self.coff_20.grid(row=3, column=5, sticky='EW', padx=5)
        Hoverbox(self.coff_20, 'Compensation Coefficient 20')
        self.coff_21 = Spinbox(frame, textvariable=self.var_coff_21, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_21.focus()
        self.coff_21.grid(row=3, column=6, sticky='EW')
        Hoverbox(self.coff_21, 'Compensation Coefficient 21')
        self.coff_22 = Spinbox(frame, textvariable=self.var_coff_22, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_22.focus()
        self.coff_22.grid(row=3, column=7, sticky='EW', padx=5)
        Hoverbox(self.coff_22, 'Compensation Coefficient 22')
        self.coff_23 = Spinbox(frame, textvariable=self.var_coff_23, width=6, from_=-100, to=100, increment=0.01, state=DISABLED)
        self.coff_23.focus()
        self.coff_23.grid(row=3, column=8, sticky='EW')
        Hoverbox(self.coff_23, 'Compensation Coefficient 23')

        self.StartCalibrateButton = Button(frame, text='Start', width=8, command=self.start_calibration, state=DISABLED)
        self.StartCalibrateButton.grid(row=4, column=0, sticky='EW')
        self.StopCalibrateButton = Button(frame, text='Stop', width=8, command=self.stop_calibration, state=DISABLED)
        self.StopCalibrateButton.grid(row=4, column=1, sticky='EW', padx=5)
        self.GetCompCoeffButton =  Button(frame, text='Get', width=8, command=self.get_comp_coeff, state=DISABLED)
        self.GetCompCoeffButton.grid(row=4, column=2, sticky='EW')
        self.SetCompCoeffButton =  Button(frame, text='Set', width=8, command=self.set_comp_coeff, state=DISABLED)
        self.SetCompCoeffButton.grid(row=4, column=3, sticky='EW', padx=5)
        self.LoadCompCoeffButton =  Button(frame, text='Load', width=8, command=self.load_comp_coeff, state=DISABLED)
        self.LoadCompCoeffButton.grid(row=4, column=4, sticky='EW')
        self.SaveCompCoeffButton =  Button(frame, text='Save', width=8, command=self.save_comp_coeff, state=DISABLED)
        self.SaveCompCoeffButton.grid(row=4, column=5, sticky='EW', padx=5)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Separator(frame, orient=HORIZONTAL).grid(row=0, columnspan=10, sticky='ew', pady=5)

        Label(frame, text='Exposure time (s):').grid(row=1, column=0, sticky='W')
        exposure_time = Spinbox(frame, textvariable=self.var_exposure_time, width=10, from_=0.0, to=100.0, increment=0.01)
        exposure_time.grid(row=1, column=1, sticky='W', padx=5)
        if self.image_stream is not None:
            self.ExposureButton = Button(frame, text='Confirm Exposure', command=self.confirm_exposure_time, state=NORMAL)
            self.ExposureButton.grid(row=1, column=2, sticky='W')
        Checkbutton(frame, text='Beam unblanker', variable=self.var_unblank_beam, command=self.toggle_unblankbeam).grid(row=1, column=3, sticky='W', padx=5)
        Checkbutton(frame, text='Toggle screen', variable=self.var_toggle_screen, command=self.toggle_screen).grid(row=1, column=4, sticky='W')

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Label(frame, text='Image interval:').grid(row=5, column=0, sticky='W')
        self.e_image_interval = Spinbox(frame, textvariable=self.var_image_interval, width=8, from_=1, to=9999, increment=1, state=DISABLED)
        self.e_image_interval.grid(row=5, column=1, sticky='W', padx=5)
        Label(frame, text='Diff defocus:').grid(row=5, column=2, sticky='W')
        self.e_diff_defocus = Spinbox(frame, textvariable=self.var_diff_defocus, width=8, from_=-10000, to=10000, increment=100, state=DISABLED)
        self.e_diff_defocus.grid(row=5, column=3, sticky='W', padx=5)
        Checkbutton(frame, text='Enable img interval', variable=self.var_enable_image_interval, command=self.toggle_interval_buttons).grid(row=5, column=4, sticky='W')
        self.RelaxButton = Button(frame, text='Relax beam', command=self.relax_beam, state=DISABLED)
        self.RelaxButton.grid(row=5, column=5, sticky='EW', padx=5)

        Label(frame, text='Img exposure (s):').grid(row=6, column=0, sticky='W')
        if self.image_stream is not None:
            self.e_image_exposure = Spinbox(frame, textvariable=self.var_exposure_time_image, width=8, from_=0.0, to=100.0, increment=self.image_stream.frametime, state=DISABLED)
        else:
            self.e_image_exposure = Spinbox(frame, textvariable=self.var_exposure_time_image, width=8, from_=0.0, to=100.0, increment=0.01, state=DISABLED)
        self.e_image_exposure.grid(row=6, column=1, sticky='W', padx=5)

        Label(frame, text='Start angle (±):').grid(row=6, column=2, sticky='W')
        self.e_defocus_start_angle = Spinbox(frame, textvariable=self.var_defocus_start_angle, width=8, from_=-80.0, to=80.0, increment=1.0, state=DISABLED)
        self.e_defocus_start_angle.grid(row=6, column=3, sticky='W', padx=5)
        self.c_toggle_defocus = Checkbutton(frame, text='Toggle defocus', variable=self.var_toggle_diff_defocus, command=self.toggle_diff_defocus, state=DISABLED)
        self.c_toggle_defocus.grid(row=6, column=4, sticky='W')
        
        Label(frame, text='Initial frames').grid(row=7, column=0, sticky='W')
        self.e_start_frames = Spinbox(frame, textvariable=self.var_start_frames, width=8, from_=0, to=10, increment=1, state=DISABLED)
        self.e_start_frames.grid(row=7, column=1, sticky='W', padx=5)
        Label(frame, text='Initial interval').grid(row=7, column=2, sticky='W')
        self.e_start_frames_interval = Spinbox(frame, textvariable=self.var_start_frames_interval, width=8, from_=2, to=10, increment=1, state=DISABLED)
        self.e_start_frames_interval.grid(row=7, column=3, sticky='W', padx=5)

        Label(frame, text='Low angle interval').grid(row=8, column=0, sticky='W')
        self.e_low_angle_interval = Spinbox(frame, textvariable=self.var_low_angle_image_interval, width=8, from_=0, to=100, increment=1, state=DISABLED)
        self.e_low_angle_interval.grid(row=8, column=1, sticky='W', padx=5)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)
        Label(frame, text='Select output formats:').grid(row=5, columnspan=2, sticky='EW')
        Checkbutton(frame, text='TIFF (.tiff)', variable=self.var_save_tiff).grid(row=5, column=2, sticky='EW')
        Checkbutton(frame, text='XDS (.smv)', variable=self.var_save_xds).grid(row=5, column=3, sticky='EW')
        Checkbutton(frame, text='CBF (.cbf)', variable=self.var_save_cbf).grid(row=5, column=4, sticky='EW')
        Checkbutton(frame, text='DIALS (.smv)', variable=self.var_save_dials).grid(row=6, column=2, sticky='EW')
        Checkbutton(frame, text='REDp (.mrc)', variable=self.var_save_red).grid(row=6, column=3, sticky='EW')
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=1)
        frame.grid_columnconfigure(3, weight=1)
        frame.grid_columnconfigure(4, weight=1)

        frame.pack(side='top', fill='x', padx=5, pady=5)

        frame = Frame(self)
        self.CollectionButton = Button(frame, text='Start Collection', command=self.start_collection)
        self.CollectionButton.grid(row=1, column=0, sticky='EW')

        self.CollectionStopButton = Button(frame, text='Stop Collection', command=self.stop_collection, state=DISABLED)
        self.CollectionStopButton.grid(row=1, column=1, sticky='EW')

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.pack(side='bottom', fill='x', padx=10, pady=10)
        

    def init_vars(self):
        self.holder_ctrl = None
        self.var_holder_id = IntVar(value=0)
        self.var_angle = DoubleVar(value=0.0)
        self.var_interval = IntVar(value=100)
        self.var_axis = IntVar(value=0)
        self.var_pulse = IntVar(value=0)
        self.var_speed = IntVar(value=0)
        self.var_amp = IntVar(value=0)
        self.var_coff_0 = DoubleVar(value=0.0)
        self.var_coff_1 = DoubleVar(value=0.0)
        self.var_coff_2 = DoubleVar(value=0.0)
        self.var_coff_3 = DoubleVar(value=0.0)
        self.var_coff_4 = DoubleVar(value=0.0)
        self.var_coff_5 = DoubleVar(value=0.0)
        self.var_coff_6 = DoubleVar(value=0.0)
        self.var_coff_7 = DoubleVar(value=0.0)
        self.var_coff_8 = DoubleVar(value=0.0)
        self.var_coff_9 = DoubleVar(value=0.0)
        self.var_coff_10 = DoubleVar(value=0.0)
        self.var_coff_11 = DoubleVar(value=0.0)
        self.var_coff_12 = DoubleVar(value=0.0)
        self.var_coff_13 = DoubleVar(value=0.0)
        self.var_coff_14 = DoubleVar(value=0.0)
        self.var_coff_15 = DoubleVar(value=0.0)
        self.var_coff_16 = DoubleVar(value=0.0)
        self.var_coff_17 = DoubleVar(value=0.0)
        self.var_coff_18 = DoubleVar(value=0.0)
        self.var_coff_19 = DoubleVar(value=0.0)
        self.var_coff_20 = DoubleVar(value=0.0)
        self.var_coff_21 = DoubleVar(value=0.0)
        self.var_coff_22 = DoubleVar(value=0.0)
        self.var_coff_23 = DoubleVar(value=0.0)
        self.stopRecEvent = threading.Event()
        self.stopColEvent = threading.Event()

        self.var_exposure_time = DoubleVar(value=0.1)
        self.var_unblank_beam = BooleanVar(value=False)
        self.var_toggle_screen = BooleanVar(value=False)
        self.var_image_interval = IntVar(value=10)
        self.var_low_angle_image_interval = IntVar(value=30)
        if self.tem_ctrl.tem.interface == "fei":
            self.var_diff_defocus = IntVar(value=42000)
        else:
            self.var_diff_defocus = IntVar(value=1500)
        self.var_enable_image_interval = BooleanVar(value=False)
        self.var_toggle_diff_defocus = BooleanVar(value=False)
        self.var_start_frames = IntVar(value=5)
        self.var_start_frames_interval = IntVar(value=2)
        self.var_defocus_start_angle = DoubleVar(value=0.0)
        self.var_start_frames = IntVar(value=5)
        self.var_start_frames_interval = IntVar(value=2)
        self.var_defocus_start_angle = DoubleVar(value=0.0)

        if self.image_stream is not None:
            self.var_exposure_time_image = DoubleVar(value=self.image_stream.frametime)
        else:
            self.var_exposure_time_image = DoubleVar(value=0.01)

        self.var_save_tiff = BooleanVar(value=False)
        self.var_save_xds = BooleanVar(value=True)
        self.var_save_dials = BooleanVar(value=True)
        self.var_save_red = BooleanVar(value=True)
        self.var_save_cbf = BooleanVar(value=False)

    def toggle_unblankbeam(self):
        toggle = self.var_unblank_beam.get()

        if toggle:
            self.tem_ctrl.beam.unblank()
        else:
            self.tem_ctrl.beam.blank()

    def toggle_screen(self):
        toggle = self.var_toggle_screen.get()

        if toggle:
            self.tem_ctrl.screen.up()
        else:
            self.tem_ctrl.screen.down()

    def confirm_exposure_time(self):
        if config.settings.buffer_stream_use_thread:
            n = decimal.Decimal(str(self.var_exposure_time.get())) / decimal.Decimal(str(self.image_stream.frametime))
            self.var_exposure_time.set(decimal.Decimal(str(self.image_stream.frametime)) * int(n))
            # self.image_stream.exposure = self.var_exposure_time.get()
        else:
            self.image_stream.stop()
            n = decimal.Decimal(str(self.var_exposure_time.get())) / decimal.Decimal(str(self.image_stream.frametime))
            self.var_exposure_time.set(decimal.Decimal(str(self.image_stream.frametime)) * int(n))
            #self.image_stream.exposure = self.var_exposure_time.get()
            self.image_stream.start_loop()

    def toggle_interval_buttons(self):
        enable = self.var_enable_image_interval.get()
        if enable:
            self.e_image_interval.config(state=NORMAL)
            self.e_image_exposure.config(state=NORMAL)
            self.e_diff_defocus.config(state=NORMAL)
            self.c_toggle_defocus.config(state=NORMAL)
            self.RelaxButton.config(state=NORMAL)
            self.e_defocus_start_angle.config(state=NORMAL)
            self.e_start_frames.config(state=NORMAL)
            self.e_start_frames_interval.config(state=NORMAL)
            self.e_low_angle_interval.config(state=NORMAL)
        else:
            self.e_image_interval.config(state=DISABLED)
            self.e_image_exposure.config(state=DISABLED)
            self.e_diff_defocus.config(state=DISABLED)
            self.c_toggle_defocus.config(state=DISABLED)
            self.RelaxButton.config(state=DISABLED)
            self.e_defocus_start_angle.config(state=DISABLED)
            self.e_defocus_start_angle.set(0)
            self.e_start_frames.config(state=DISABLED)
            self.e_start_frames_interval.config(state=DISABLED)
            self.e_low_angle_interval.config(state=DISABLED)

    def toggle_diff_defocus(self):
        toggle = self.var_toggle_diff_defocus.get()
        difffocus = self.var_diff_defocus.get()

        self.q.put(('toggle_difffocus', {'value': difffocus, 'toggle': toggle}))
        self.triggerEvent.set()

    def relax_beam(self):
        difffocus = self.var_diff_defocus.get()

        self.q.put(('relax_beam', {'value': difffocus}))
        self.triggerEvent.set()

    def start_collection(self):
        if self.var_toggle_diff_defocus.get():
            self.var_toggle_diff_defocus.set(False)
            self.toggle_diff_defocus()

        self.CollectionStopButton.config(state=NORMAL)
        self.CollectionButton.config(state=DISABLED)

        self.stopColEvent.clear()

        params = self.get_params()
        self.q.put(('cred', params))

        self.triggerEvent.set()

    def stop_collection(self):
        self.stopColEvent.set()

        self.CollectionStopButton.config(state=DISABLED)
        self.CollectionButton.config(state=NORMAL)

    def connect(self):
        t = threading.Thread(target=self.wait_holder, args=(), daemon=True)
        t.start()
        self.holder_ctrl = self.tem_ctrl.holder
        
    def wait_holder(self):
        self.ConnectButton.config(state=DISABLED)
        for i in range(5):
            time.sleep(0.5)
            if self.holder_ctrl.getHolderId() != 0:
                time.sleep(0.5)
                self.enable_operations()
                self.var_holder_id.set(hex(self.holder_ctrl.getHolderId()))
                break
            print("Wait for XNano holder...")
        if i == 4:
            print("Please connect to a XNano holder.")
            self.ConnectButton.config(state=NORMAL)

    def validate(self, action, index, value_if_allowed, prior_value, text, validation_type, trigger_type, widget_name):
        if value_if_allowed:
            try:
                value = float(value_if_allowed)
                if value >= -1 and value <= 1:
                    return True
                else:
                    return False
            except ValueError:
                return False
        else:
            return False

    def get_angle(self):
        self.lb_angle.config(text=self.holder_ctrl.getAngle()*180/pi) 

    def get_distance(self):
        self.lb_distance.config(text=self.holder_ctrl.getDistance())

    def coarse_move(self):
        self.holder_ctrl.holderMove(self.var_axis.get(), self.var_pulse.get(), self.var_speed.get(), self.var_amp.get())

    def stop_coarse_move(self):
        self.holder_ctrl.holderStop()

    def fine_move(self):
        self.holder_ctrl.holderFine(self.var_axis.get(), self.var_amp.get())

    def rotate_to(self):
        self.holder_ctrl.holderRotateTo(self.var_angle.get()*pi/180, self.var_amp.get())

    def rotate_record(self):
        num = 1
        self.xnano_rec_path = self.rec_path / f'XNanoRec_{num}'
        success = False
        while not success:
            try:
                self.xnano_rec_path.mkdir(parents=True)
                success = True
            except OSError:
                num += 1
                self.xnano_rec_path = self.rec_path / f'XNanoRec_{num}'

        self.holder_ctrl.holderRotateTo(self.var_angle.get()*pi/180, self.var_amp.get())
        t_record_angle = threading.Thread(target=self.record_angle, args=(), daemon=True)
        t_record_angle.start()

    def record_angle(self):
        self.stopRecEvent.clear()
        num = 1
        current_angle = self.holder_ctrl.getAngle()*180/pi
        target_angle = self.var_angle.get()*180/pi
        angle_list = []
        if self.var_amp.get() > 0:
            rotation_direction = 1
        elif self.var_amp.get() < 0:
            rotation_direction = -1
        else:
            raise RuntimeError('Amp value not set.')

        while round(current_angle, 1) != round(target_angle, 1) and rotation_direction * (current_angle - target_angle) < 0 and not self.stopRecEvent.is_set():
            current_angle = self.holder_ctrl.getAngle()*180/pi
            outfile = self.xnano_rec_path / f'{num:05d}.tiff'
            comment = f'Saved image with XNano holder: current angle = {current_angle:.2f}'
            img, _ = self.tem_ctrl.get_image(exposure=self.var_exposure_time.get(), out=outfile, comment=comment)
            angle_list.append(current_angle)
            num += 1
            time.sleep(self.var_interval.get()/1000)

        with open(self.xnano_rec_path / 'angle.tlt', 'w') as f:
            for angle in angle_list:
                f.write(f'{angle:.2f}\n')

        self.stopRecEvent.clear()

    def stop_record(self):
        self.stopRecEvent.set()

    def save_img(self):
        num = 1
        self.xnano_save_path = self.rec_path / f'XNanoSavedImg'
        self.xnano_save_path.mkdir(parents=True, exist_ok=True)
        outfile = self.xnano_save_path / f'{num:05d}.tiff'
        while outfile.is_file():
            num += 1
            outfile = self.xnano_save_path / f'{num:05d}.tiff'
        current_angle = self.holder_ctrl.getAngle()*180/pi
        comment = f'Saved image with XNano holder: current angle = {current_angle:.2f}'
        img, _ = self.tem_ctrl.get_image(exposure=self.var_exposure_time.get(), out=outfile, comment=comment)

    def start_calibration(self):
        pass

    def stop_calibration(self):
        pass

    def get_comp_coeff(self):
        table = self.holder_ctrl.getCompCoef()
        self.var_coff_0.set(table[0])
        self.var_coff_1.set(table[1])
        self.var_coff_2.set(table[2])
        self.var_coff_3.set(table[3])
        self.var_coff_4.set(table[4])
        self.var_coff_5.set(table[5])
        self.var_coff_6.set(table[6])
        self.var_coff_7.set(table[7])
        self.var_coff_8.set(table[8])
        self.var_coff_9.set(table[9])
        self.var_coff_10.set(table[10])
        self.var_coff_11.set(table[11])
        self.var_coff_12.set(table[12])
        self.var_coff_13.set(table[13])
        self.var_coff_14.set(table[14])
        self.var_coff_15.set(table[15])
        self.var_coff_16.set(table[16])
        self.var_coff_17.set(table[17])
        self.var_coff_18.set(table[18])
        self.var_coff_19.set(table[19])
        self.var_coff_20.set(table[20])
        self.var_coff_21.set(table[21])
        self.var_coff_22.set(table[22])
        self.var_coff_23.set(table[23])

    def set_comp_coeff(self):
        table = self.holder_ctrl.getCompCoef()
        table[0] = self.var_coff_0.get()
        table[1] = self.var_coff_1.get()
        table[2] = self.var_coff_2.get()
        table[3] = self.var_coff_3.get()
        table[4] = self.var_coff_4.get()
        table[5] = self.var_coff_5.get()
        table[6] = self.var_coff_6.get()
        table[7] = self.var_coff_7.get()
        table[8] = self.var_coff_8.get()
        table[9] = self.var_coff_9.get()
        table[10] = self.var_coff_10.get()
        table[11] = self.var_coff_11.get()
        table[12] = self.var_coff_12.get()
        table[13] = self.var_coff_13.get()
        table[14] = self.var_coff_14.get()
        table[15] = self.var_coff_15.get()
        table[16] = self.var_coff_16.get()
        table[17] = self.var_coff_17.get()
        table[18] = self.var_coff_18.get()
        table[19] = self.var_coff_19.get()
        table[20] = self.var_coff_20.get()
        table[21] = self.var_coff_21.get()
        table[22] = self.var_coff_22.get()
        table[23] = self.var_coff_23.get()
        self.holder_ctrl.setCompCoef(table)

    def load_comp_coeff(self):
        pass

    def save_comp_coeff(self):
        pass

    def enable_operations(self):
        self.GetAngleButton.config(state=NORMAL)
        self.GetDistButton.config(state=NORMAL)
        self.e_amp.config(state=NORMAL)
        self.e_speed.config(state=NORMAL)
        self.e_pulse.config(state=NORMAL)
        self.e_axis.config(state=NORMAL)
        self.e_angle.config(state=NORMAL)
        self.e_interval.config(state=NORMAL)
        self.CoarseMoveButton.config(state=NORMAL)
        self.StopCoarseMoveButton.config(state=NORMAL)
        self.FineMoveButton.config(state=NORMAL)
        self.RotateToButton.config(state=NORMAL)
        self.RotateRecordButton.config(state=NORMAL)
        self.StopRecordButton.config(state=NORMAL)
        self.SaveImgButton.config(state=NORMAL)
        self.coff_0.config(state=NORMAL)
        self.coff_1.config(state=NORMAL)
        self.coff_2.config(state=NORMAL)
        self.coff_3.config(state=NORMAL)
        self.coff_4.config(state=NORMAL)
        self.coff_5.config(state=NORMAL)
        self.coff_6.config(state=NORMAL)
        self.coff_7.config(state=NORMAL)
        self.coff_8.config(state=NORMAL)
        self.coff_9.config(state=NORMAL)
        self.coff_10.config(state=NORMAL)
        self.coff_11.config(state=NORMAL)
        self.coff_12.config(state=NORMAL)
        self.coff_13.config(state=NORMAL)
        self.coff_14.config(state=NORMAL)
        self.coff_15.config(state=NORMAL)
        self.coff_16.config(state=NORMAL)
        self.coff_17.config(state=NORMAL)
        self.coff_18.config(state=NORMAL)
        self.coff_19.config(state=NORMAL)
        self.coff_20.config(state=NORMAL)
        self.coff_21.config(state=NORMAL)
        self.coff_22.config(state=NORMAL)
        self.coff_23.config(state=NORMAL)
        self.StartCalibrateButton.config(state=NORMAL)
        self.StopCalibrateButton.config(state=NORMAL)
        self.SetCompCoeffButton.config(state=NORMAL)
        self.GetCompCoeffButton.config(state=NORMAL)
        self.LoadCompCoeffButton.config(state=NORMAL)
        self.SaveCompCoeffButton.config(state=NORMAL)

    def disable_operations(self):
        self.GetAngleButton.config(state=DISABLED)
        self.GetDistButton.config(state=DISABLED)
        self.e_amp.config(state=DISABLED)
        self.e_speed.config(state=DISABLED)
        self.e_pulse.config(state=DISABLED)
        self.e_axis.config(state=DISABLED)
        self.e_angle.config(state=DISABLED)
        self.CoarseMoveButton.config(state=DISABLED)
        self.StopCoarseMoveButton.config(state=DISABLED)
        self.FineMoveButton.config(state=DISABLED)
        self.RotateToButton.config(state=DISABLED)
        self.RotateRecordButton.config(state=DISABLED)
        self.StopRecordButton.config(state=DISABLED)
        self.coff_0.config(state=DISABLED)
        self.coff_1.config(state=DISABLED)
        self.coff_2.config(state=DISABLED)
        self.coff_3.config(state=DISABLED)
        self.coff_4.config(state=DISABLED)
        self.coff_5.config(state=DISABLED)
        self.coff_6.config(state=DISABLED)
        self.coff_7.config(state=DISABLED)
        self.coff_8.config(state=DISABLED)
        self.coff_9.config(state=DISABLED)
        self.coff_10.config(state=DISABLED)
        self.coff_11.config(state=DISABLED)
        self.coff_12.config(state=DISABLED)
        self.coff_13.config(state=DISABLED)
        self.coff_14.config(state=DISABLED)
        self.coff_15.config(state=DISABLED)
        self.coff_16.config(state=DISABLED)
        self.coff_17.config(state=DISABLED)
        self.coff_18.config(state=DISABLED)
        self.coff_19.config(state=DISABLED)
        self.coff_20.config(state=DISABLED)
        self.coff_21.config(state=DISABLED)
        self.coff_22.config(state=DISABLED)
        self.coff_23.config(state=DISABLED)
        self.StartCalibrateButton.config(state=DISABLED)
        self.StopCalibrateButton.config(state=DISABLED)
        self.SetCompCoeffButton.config(state=DISABLED)
        self.GetCompCoeffButton.config(state=DISABLED)
        self.LoadCompCoeffButton.config(state=DISABLED)
        self.SaveCompCoeffButton.config(state=DISABLED)

    def set_trigger(self, trigger=None, q=None):
        self.triggerEvent = trigger
        self.q = q

    def get_params(self):
        params = {'exposure_time': self.var_exposure_time.get(),
                  'exposure_time_image': self.var_exposure_time_image.get(),
                  'unblank_beam': self.var_unblank_beam.get(),
                  'enable_image_interval': self.var_enable_image_interval.get(),
                  'image_interval': self.var_image_interval.get(),
                  'low_angle_image_interval': self.var_low_angle_image_interval.get(),
                  'diff_defocus': self.var_diff_defocus.get(),
                  'start_frames': self.var_start_frames.get(),
                  'start_frames_interval': self.var_start_frames_interval.get(),
                  'defocus_start_angle': self.var_defocus_start_angle.get(),
                  'write_tiff': self.var_save_tiff.get(),
                  'write_xds': self.var_save_xds.get(),
                  'write_dials': self.var_save_dials.get(),
                  'write_red': self.var_save_red.get(),
                  'do_stretch_correction': self.stream_frame.var_apply_stretch.get(),
                  'stretch_amplitude': self.stream_frame.var_amplitude.get(),
                  'stretch_azimuth': self.stream_frame.var_azimuth.get(),
                  'stretch_cent_x': self.stream_frame.var_cent_x.get(),
                  'stretch_cent_y': self.stream_frame.var_cent_y.get(),
                  'stop_event': self.stopColEvent,
                  'holder_ctrl': self.holder_ctrl,
                  'amplitude': self.var_amp.get(),
                  'angle': self.var_angle.get()}
        return params


def acquire_data_cRED_XNano(controller, **kwargs):
    controller.log.info('Start cRED experiment using XNano holder')
    from instamatic.experiments import cRED_XNano

    expdir = controller.module_io.get_new_experiment_directory()
    expdir.mkdir(exist_ok=True, parents=True)

    cexp = cRED_XNano.Experiment(ctrl=controller.ctrl, path=expdir, flatfield=controller.module_io.get_flatfield(), log=controller.log, **kwargs)

    success = cexp.start_collection()

    if not success:
        return

    controller.log.info('Finish cRED experiment using XNano holder')

    if controller.use_indexing_server:
        controller.q.put(('autoindex', {'task': 'run', 'path': cexp.smv_path}))
        controller.triggerEvent.set()

module = BaseModule(name='cred_xnano', display_name='cRED_XNano', tk_frame=ExperimentalcREDXnano, location='bottom')
commands = {'cred_xnano': acquire_data_cRED_XNano}

if __name__ == '__main__':
    root = Tk()
    ExperimentalcREDXnano(root).pack(side='top', fill='both', expand=True)
    root.mainloop()
