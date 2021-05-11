# https://github.com/alandmoore/cpython/blob/53046dcf91481f3e69ddbc97e5d8d0d921c1d09f/Lib/tkinter/ttk.py
# https://gist.github.com/novel-yet-trivial/49fa18828cddca44a2befae84cfd67ad

from itertools import cycle
import tkinter as tk
import tkinter.font as tkFont
from tkinter import *
from tkinter.ttk import *

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


class MultiListbox(tk.Frame):
    def __init__(self, master=None, columns=2, data=[], row_select=True, **kwargs):
        '''makes a multicolumn listbox by combining a bunch of single listboxes
        with a single scrollbar
        :columns:
          (int) the number of columns
          OR (1D list or strings) the column headers
        :data:
          (1D iterable) auto add some data
        :row_select:
          (boolean) When True, clicking a cell selects the entire row
        All other kwargs are passed to the Listboxes'''
        tk.Frame.__init__(self, master, borderwidth=1, highlightthickness=1, relief=tk.SUNKEN)
        self.rowconfigure(1, weight=1)
        self.columns = columns
        if isinstance(self.columns, (list, tuple)):
            for col, text in enumerate(self.columns):
                tk.Label(self, text=text).grid(row=0, column=col)
            self.columns = len(self.columns)

        self.boxes = []
        for col in range(self.columns):
            box = tk.Listbox(self, exportselection=not row_select, **kwargs)
            if row_select:
                box.bind('<<ListboxSelect>>', self.selected)
            box.grid(row=1, column=col, sticky='nsew')
            self.columnconfigure(col, weight=1)
            self.boxes.append(box)
        vsb = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.multiple(*[box.yview for box in self.boxes]))
        vsb.grid(row=1, column=col+1, sticky='ns')
        for box in self.boxes:
            box.config(yscrollcommand=self.scroll_to_view(vsb.set, *[b.yview for b in self.boxes if b is not box]))
        self.add_data(data)

    def multiple(self, *func_list):
        '''run multiple functions as one'''
        # I can't decide if this is ugly or pretty
        return lambda *args, **kw: [func(*args, **kw) for func in func_list]; None

    def scroll_to_view(self, scroll_set, *view_funcs):
        ''' Allows one widget to control the scroll bar and other widgets
            scroll set: the scrollbar set function
            view_funcs: other widget's view functions'''
        def closure(start, end):
            scroll_set(start, end)
            for func in view_funcs:
                func('moveto', start)
        return closure

    def selected(self, event=None):
        row = event.widget.curselection()[0]
        for lbox in self.boxes:
            lbox.select_clear(0, tk.END)
            lbox.select_set(row)

    def add_data(self, data=[]):
        '''takes a 1D list of data and adds it row-wise
        If there is not enough data to fill the row, then the row is
        filled with empty strings
        these will not be back filled; every new call starts at column 0'''
        # it is essential that the listboxes all have the same length.
        # because the scroll works on "percent" ...
        # and 100% must mean the same in all cases
        boxes = cycle(self.boxes)
        idx = -1
        for idx, (item, box) in enumerate(zip(data, boxes)):
            box.insert(tk.END, item)
        for _ in range(self.columns - idx%self.columns - 1):
            next(boxes).insert(tk.END, '')
          
    def __getitem__(self, index):
        '''get a row'''
        return [box.get(index) for box in self.boxes]

    def __delitem__(self, index):
        '''delete a row'''
        [box.delete(index) for box in self.boxes]

    def curselection(self):
        '''get the currently selected row'''
        selection = self.boxes[0].curselection()
        return selection[0] if selection else None 


class Spinbox(Entry):
    """Ttk Spinbox is an Entry with increment and decrement arrows It is
    commonly used for number entry or to select from a list of string
    values."""

    def __init__(self, master=None, **kw):
        """Construct a Ttk Spinbox widget with the parent master.

        STANDARD OPTIONS: class, cursor, style, takefocus, validate,
        validatecommand, xscrollcommand, invalidcommand

        WIDGET-SPECIFIC OPTIONS: to, from_, increment, values, wrap, format, command
        """
        Entry.__init__(self, master, 'ttk::spinbox', **kw)

    def set(self, value):
        """Sets the value of the Spinbox to value."""
        self.tk.call(self._w, 'set', value)

class Hoverbox:
    """
    create a tooltip for a given widget
    """
    def __init__(self, widget, text='widget info'):
        self.waittime = 500     #miliseconds
        self.wraplength = 180   #pixels
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = tk.Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#ffffff", relief='solid', borderwidth=1,
                       wraplength = self.wraplength)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw= None
        if tw:
            tw.destroy()

class ShowMatplotlibFig(tk.Toplevel):
    """Simple class to load a matplotlib figure in a new top level panel."""

    def __init__(self, parent, fig, title='figure'):
        tk.Toplevel.__init__(self, parent)
        self.grab_set()
        self.title(title)
        button = Button(self, text='Dismiss', command=self.close)
        button.pack(side=BOTTOM)
        self.canvas = canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.draw()
        canvas.get_tk_widget().pack(side=TOP, fill=BOTH, expand=True)
        # canvas._tkcanvas.pack(side=self, fill=BOTH, expand=True)
        self.toolbar = NavigationToolbar2Tk(canvas, self)
        self.toolbar.update()
        self.wm_protocol('WM_DELETE_WINDOW', self.close)
        self.focus_set()
        self.wait_window(self)

    def close(self, event=None):
        self.canvas.get_tk_widget().destroy()
        self.destroy()    # this is necessary on Windows to prevent
        # Fatal Python Error: PyEval_RestoreThread: NULL tstate
        plt.close('all')

class popupWindow(tk.Toplevel):
    def __init__(self, parent, title, text):
        tk.Toplevel.__init__(self, parent)
        self.grab_set()
        self.title(title)
        self.value = None

        self.l = Label(self, text=text)
        self.l.pack()
        self.e = Entry(self)
        self.e.pack()
        self.b = Button(self, text='OK', command=self.close)
        self.b.pack()
        self.wm_protocol('WM_DELETE_WINDOW', self.close)
        self.focus_set()

    def close(self):
        self.value = self.e.get()
        self.destroy()

    def get_value(self):
        self.wait_window(self)
        return self.value