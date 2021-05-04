import threading
from tkinter import *
from tkinter.ttk import *
import decimal

from .base_module import BaseModule
from .modules import MODULES
from instamatic.utils.widgets import Spinbox
from instamatic import config
from instamatic import TEMController


class ExperimentalScan(LabelFrame):
    """GUI panel to perform scanning experiments"""

    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Scan')
        self.parent = parent
        self.binsize = self.ctrl.cam.default_binsize
        self.ctrl = TEMController.get_instance()

        self.init_vars()

    def init_vars(self):
        self.var_exposure_time = DoubleVar(value=BEAMSCAN_OVERHEAD)
        self.var_scan_pattern = StringVar(value='XY scan')
        self.var_n = IntVar(value=5)
        self.var_nx = IntVar(value=5)
        self.var_ny = IntVar(value=5)
        self.var_angle = DoubleVar(value=1.0)
        self.var_num_sampling = IntVar(value=60)
        

    def get_params(self, task=None):
        params = {}
        return params

def beam_shift_scan_line(controller, **kwargs):
    from instamatic.experiments import Scanner
    
    flatfield = controller.module_io.get_flatfield()

    scanner = Scanner(ctrl=controller.ctrl, log=controller.log, flatfield=flatfield)
    success = scanner.beam_shift_scan_line(**kwargs)

def beam_shift_scan_rectangle(controller, **kwargs):
    from instamatic.experiments import Scanner
    
    flatfield = controller.module_io.get_flatfield()

    scanner = Scanner(ctrl=controller.ctrl, log=controller.log, flatfield=flatfield)
    success = scanner.beam_shift_scan_rectangle(**kwargs)

def beam_precession(controller, **kwargs):
    from instamatic.experiments import Scanner
    
    flatfield = controller.module_io.get_flatfield()

    scanner = Scanner(ctrl=controller.ctrl, log=controller.log, flatfield=flatfield)
    success = scanner.beam_precession(**kwargs)

def beam_precession_scan_line(controller, **kwargs):
    from instamatic.experiments import Scanner
    
    flatfield = controller.module_io.get_flatfield()

    scanner = Scanner(ctrl=controller.ctrl, log=controller.log, flatfield=flatfield)
    success = scanner.beam_precession_scan_line(**kwargs)

def beam_precession_scan_rectangle(controller, **kwargs):
    from instamatic.experiments import Scanner
    
    flatfield = controller.module_io.get_flatfield()

    scanner = Scanner(ctrl=controller.ctrl, log=controller.log, flatfield=flatfield)
    success = scanner.beam_precession_scan_rectangle(**kwargs)

module = BaseModule(name='scan', display_name='Scan', tk_frame=ExperimentalScan, location='bottom')
commands = {'beam_shift_scan_line': beam_shift_scan_line, 'beam_shift_scan_rectangle': beam_shift_scan_rectangle, 'beam_precession': beam_precession, 
            'beam_precession_scan_line': beam_precession_scan_line, 'beam_precession_scan_rectangle':beam_precession_scan_rectangle}


if __name__ == '__main__':
    root = Tk()
    ExperimentalScan(root).pack(side='top', fill='both', expand=True)
    root.mainloop()
