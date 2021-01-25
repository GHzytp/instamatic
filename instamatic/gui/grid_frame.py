import threading
import time
from datetime import datetime
from tkinter import *
from tkinter.ttk import *

import numpy as np

from PIL import Image
from PIL import ImageEnhance
from PIL import ImageTk

from instamatic import config
from instamatic.formats import read_tiff
from instamatic.formats import write_tiff

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class GridFrame(Toplevel):
    """Load a GUi to show the grid map and label suitable crystals."""

    def __init__(self, parent, fig=None, title='figure'):
        Toplevel.__init__(self, parent)
        self.grab_set()
        self.title(title)
        button = Button(self, text='Dismiss', command=self.close)
        button.pack(side=BOTTOM)
        fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.draw()
        canvas.get_tk_widget().pack(side=TOP, fill=BOTH, expand=True)

        self.wm_protocol('WM_DELETE_WINDOW', self.close)
        self.focus_set()
        self.wait_window(self)

    def close(self, event=None):
        self.canvas.get_tk_widget().destroy()
        self.destroy()    # this is necessary on Windows to prevent
        # Fatal Python Error: PyEval_RestoreThread: NULL tstate
        plt.clf()
        plt.close('all')

if __name__ == '__main__':
    root = Tk()
    GridFrame(root)
    root.mainloop()