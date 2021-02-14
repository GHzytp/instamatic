import threading
import time
from pathlib import Path
from datetime import datetime
from tkinter import filedialog, messagebox
from tkinter import *
from tkinter.ttk import *

import numpy as np
import pandas as pd

from .base_module import BaseModule
from instamatic import config

class IndexFrame(LabelFrame):
    """GUI panel for indexing diffraction patterns and powder patterns. In addition, calibrate the stretching of the powder ring."""

    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Indexing diffraction patterns and powder patterns')
        self.parent = parent

        self.init_vars()

        frame = Frame(self)



        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

    def init_vars(self):
        pass

module = BaseModule(name='indexing', display_name='Indexing', tk_frame=IndexFrame, location='left')
commands = {}

if __name__ == '__main__':
    root = Tk()
    CryoEDFrame(root).pack(side='top', fill='both', expand=True)
    root.mainloop()