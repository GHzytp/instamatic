import numpy as np
import time
from tkinter import *
from tkinter.ttk import *

from instamatic import config
from instamatic.utils.spinbox import Spinbox

class ConfigFrame(LabelFrame):
    """GUI frame for common TEM configuration, ie: sample holder, camera configuration..."""
    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Configuration')
        # default settings
        self.microscope_config = config.microscope
        self.microscope_holder_options = self.avaliable_holders()
        self.camera_config = config.camera
        self.calibration_config = config.calibration
        self.holder_config = config.holder

        self.init_vars()

        frame = Frame(self)

        Label(frame, text='Microscope', width=15).grid(row=0, column=0, sticky='EW')
        microscope_options = self.get_items('microscope')
        self.e_microscope = OptionMenu(frame, width=15, textvariable=self.var_microscope, self.microscope_config.name, *microscope_options, command=self.set_microscope)
        self.e_microscope.grid(row=0, column=1, sticky='EW', padx=5)
        Label(frame, text='Camera', width=15).grid(row=0, column=2, sticky='EW')
        camera_options = self.get_items('camera')
        self.e_camera = OptionMenu(frame, width=15, textvariable=self.var_camera, self.camera_config.name, *camera_options, command=self.set_camera)
        self.e_camera.grid(row=0, column=3, sticky='EW', padx=5)
        Label(frame, text='Calibration', width=15).grid(row=1, column=0, sticky='EW')
        calibration_options = self.get_items('Calibration')
        self.e_calibration = OptionMenu(frame, width=15, textvariable=self.var_calibration, self.calibration_config.name, *calibration_options, command=self.set_calibration)
        self.e_calibration.grid(row=1, column=1, sticky='EW', padx=5)
        Label(frame, text='External Holder', width=15).grid(row=1, column=2, sticky='EW')
        holder_options = self.get_items('holder')
        self.e_holder = OptionMenu(frame, width=15, textvariable=self.var_holder, self.holder_config.name, *holder_options, command=self.set_holder)
        self.e_holder.grid(row=1, column=3, sticky='EW', padx=5)
        Separator(frame, orient=HORIZONTAL).grid(row=2, columnspan=4, sticky='EW', padx=5, pady=5)

        frame.pack(side='bottom', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Label(frame, text='Microscope Holder', width=15).grid(row=0, column=0, sticky='EW')
        self.e_microscope_holder = Spinbox(frame, width=15, textvariable=self.var_diff_defocus, from_=-100000, to=100000, increment=1, state=NORMAL)
        self.e_microscope_holder.grid(row=0, column=1, sticky='EW', padx=5)
        Label(frame, text='Processing', width=15).grid(row=1, column=0, sticky='EW')
        self.e_processing = Spinbox(frame, width=15, textvariable=self.var_processing, from_=1, to=3, increment=1, state=NORMAL)
        self.e_processing.grid(row=1, column=1, sticky='EW', padx=5)
        Label(frame, text='Read Mode', width=15).grid(row=1, column=2, sticky='EW')
        self.e_read_mode = Spinbox(frame, width=15, textvariable=self.var_read_mode, from_=0, to=20, increment=1, state=NORMAL)
        self.e_read_mode.grid(row=1, column=3, sticky='EW', padx=5)
        Label(frame, text='Quality Level', width=15).grid(row=2, column=0, sticky='EW')
        self.e_quality_level = Spinbox(frame, width=15, textvariable=self.var_quality_level, from_=0, to=20, increment=1, state=NORMAL)
        self.e_quality_level.grid(row=2, column=1, sticky='EW', padx=5)
        Label(frame, text='Is Continuous', width=15).grid(row=2, column=2, sticky='EW')
        self.e_is_continuous = OptionMenu(frame, width=15, textvariable=self.var_is_continuous, 'Yes', 'Yes', 'No', command=self.set_is_continuous)
        self.e_is_continuous.grid(row=2, column=3, sticky='EW', padx=5)

        frame.pack(side='bottom', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        self.ConfirmConfigButton = Button(frame, text='Confirm Config', command=self.confirm_config, state=NORMAL)
        self.ConfirmConfigButton.grid(row=0, column=0, sticky='EW', padx=5)
        self.DefaultConfigButton = Button(frame, text='Use Default Config', command=self.use_default_config, state=NORMAL)
        self.DefaultConfigButton.grid(row=0, column=1, sticky='EW', padx=5)

        frame.pack(side='bottom', fill='x', expand=False, padx=5, pady=5)


    def init_vars(self):
        self.var_microscope = StringVar(value=self.microscope_config.name)
        self.var_camera = StringVar(value=self.camera_config.name)
        self.var_calibration = StringVar(value=self.calibration_config.name)
        self.var_holder = StringVar(value=self.holder.name)
        self.var_microscope_holder = StringVar(value=self.microscope_holder_options[0])
        self.var_is_continuous = StringVar(value='Yes')

    def avaliable_holders(self):
        pass

    def get_items(self, obj: str):
        pass

    def set_microscope(self):
        self.microscope_holder_options = self.avaliable_holders()

    def set_microscope_holder(self):
        pass

    def set_camera(self):
        pass

    def set_calibration(self):
        pass

    def set_holder(self):
        pass

    def set_is_continuous(self):
        pass

    def confirm_config(self):
        pass

    def use_default_config(self):
        config.load_all()
        


if __name__ == '__main__':
    root = Tk()
    ConfigFrame(root).pack(side='top', fill='both', expand=True)
    root.mainloop()