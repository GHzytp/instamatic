import threading
from tkinter import *
from tkinter.ttk import *
import tkinter

from .base_module import BaseModule
from instamatic import config
from instamatic.utils.spinbox import Spinbox

class ExperimentalFourDSTEM(LabelFrame):
	def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='FourDSTEM')

        self.parent = parent

        self.init_vars()

        self.stopEvent = threading.Event()


    def init_vars(self):


    def set_trigger(self, trigger=None, q=None):
        self.triggerEvent = trigger
        self.q = q

    def start_collection(self):
    	params = self.get_params()
        self.q.put(('FourDSTEM', params))

    def stop_collection(self, event=None):
        self.stopEvent.set()

    def get_params(self):
        params = {'exposure_time': self.var_exposure_time.get(),
                  'exposure_time_image': self.var_exposure_time_image.get(),
                  'unblank_beam': self.var_unblank_beam.get(),
                  'enable_image_interval': self.var_enable_image_interval.get(),
                  'image_interval': self.var_image_interval.get(),
                  'diff_defocus': self.var_diff_defocus.get(),
                  'mode': self.mode,
                  'footfree_rotate_to': self.var_footfree_rotate_to.get(),
                  'rotation_speed': self.var_rotation_speed.get(),
                  'write_tiff': self.var_save_tiff.get(),
                  'write_xds': self.var_save_xds.get(),
                  'write_dials': self.var_save_dials.get(),
                  'write_red': self.var_save_red.get(),
                  'stop_event': self.stopEvent}
        return params

def acquire_data_FourDSTEM(controller, **kwargs):
    controller.log.info('Start FourDSTEM experiment')
    from instamatic.experiments import FourDSTEM

    from operator import attrgetter

    task = kwargs.pop('task')

    if task == 'None':
        pass
    else:
        f = attrgetter(task)(controller.ctrl)
        f(**kwargs)

module = BaseModule(name='FourDSTEM', display_name='FourDSTEM', tk_frame=ExperimentalFourDSTEM, location='bottom')
commands = {'FourDSTEM': acquire_data_FourDSTEM}

if __name__ == '__main__':
	root = Tk()
    ExperimentalFourDSTEM(root).pack(side='top', fill='both', expand=True)
    root.mainloop()