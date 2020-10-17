import numpy as np
import time
from tkinter import *
from tkinter.ttk import *

from .base_module import BaseModule
from instamatic import config
from instamatic.utils.spinbox import Spinbox

class ConfigFrame(LabelFrame):
    """GUI frame for common TEM configuration, ie: sample holder, camera configuration..."""
    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Configuration')

if __name__ == '__main__':
    root = Tk()
    ConfigFrame(root).pack(side='top', fill='both', expand=True)
    root.mainloop()