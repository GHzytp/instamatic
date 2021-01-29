import threading
import time
from pathlib import Path
from datetime import datetime
from tkinter import filedialog
from tkinter import *
from tkinter.ttk import *
from tqdm import tqdm

import numpy as np
import pandas as pd

from instamatic import config
from instamatic import TEMController
from instamatic.utils import suppress_stderr
from instamatic.gui.grid_frame import GridFrame
from instamatic.utils.widgets import MultiListbox, Hoverbox

class CryoED(LabelFrame):
    """GUI panel for Cryo electron diffraction data collection protocol."""

    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Cryo electron diffraction protocol')
        self.parent = parent
        self.crystal_list = None
        self.df_grid = pd.DataFrame(columns=['grid', 'pos_x', 'pos_y'])
        self.df_sqaure = pd.DataFrame(columns=['grid', 'square', 'pos_x', 'pos_y'])
        self.df_target = pd.DataFrame(columns=['sqaure', 'target', 'pos_x', 'pos_y'])
        self.grid_dir = None
        # self.ctrl = TEMController.get_instance()

        self.init_vars()

        frame = Frame(self)

        Label(frame, text='Area(um):').grid(row=0, column=0, sticky='EW')
        self.e_radius = Spinbox(frame, textvariable=self.var_radius, width=8, from_=0.0, to=500.0, increment=1)
        self.e_radius.grid(row=0, column=1, sticky='EW', padx=5)
        Label(frame, text='Name').grid(row=0, column=2, sticky='EW')
        self.e_name = Entry(frame, textvariable=self.var_name, width=8)
        self.e_name.grid(row=0, column=3, sticky='EW', padx=5)
        self.e_level = OptionMenu(frame, self.var_level, 'Whole', 'Whole', 'Sqaure', 'Target')
        self.e_level.config(width=7)
        self.e_level.grid(row=0, column=4, sticky='EW')

        self.CollectMapButton = Button(frame, text='Collect Map', width=11, command=self.collect_map, state=NORMAL)
        self.CollectMapButton.grid(row=1, column=0, sticky='EW')
        self.OpenMapButton = Button(frame, text='Get Pos', width=11, command=self.get_pos, state=NORMAL)
        self.OpenMapButton.grid(row=1, column=1, sticky='EW', padx=5)
        self.SaveGridButton = Button(frame, text='Change Grid', width=11, command=self.change_grid, state=NORMAL)
        self.SaveGridButton.grid(row=1, column=2, sticky='EW')
        self.SaveGridButton = Button(frame, text='Save Grid', width=11, command=self.save_grid, state=NORMAL)
        self.SaveGridButton.grid(row=1, column=3, sticky='EW')
        self.LoadGridButton = Button(frame, text='Load Grid', width=11, command=self.load_grid, state=NORMAL)
        self.LoadGridButton.grid(row=1, column=4, sticky='EW', padx=5)

        self.lb_coll1 = Label(frame, text='')
        self.lb_coll1.grid(row=2, column=0, columnspan=5, sticky='EW')
        

        self.AddPosButton = Button(frame, text='Add Pos', width=11, command=self.add_pos, state=NORMAL)
        self.AddPosButton.grid(row=3, column=0, sticky='EW')
        self.DelPosButton = Button(frame, text='Del Pos', width=11, command=self.del_pos, state=NORMAL)
        self.DelPosButton.grid(row=3, column=1, sticky='EW', padx=5)
        self.UpdateZButton = Button(frame, text='Update Z', width=11, command=self.update_z, state=NORMAL)
        self.UpdateZButton.grid(row=3, column=2, sticky='EW')
        self.GoXYButton = Button(frame, text='Go to XY', width=11, command=self.go_xy, state=NORMAL)
        self.GoXYButton.grid(row=3, column=3, sticky='EW', padx=5)
        self.GoXYZButton = Button(frame, text='Go to XYZ', width=11, command=self.go_xyz, state=NORMAL)
        self.GoXYZButton.grid(row=3, column=4, sticky='EW')

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Label(frame, width=16, text='Whole Grid Level', anchor="center").grid(row=0, column=0, sticky='EW')
        Label(frame, width=24, text='Grid Sqaure Level', anchor="center").grid(row=0, column=1, sticky='EW')
        Label(frame, width=24, text='Individual target Level', anchor="center").grid(row=0, column=2, sticky='EW')

        self.tv_whole_grid = Treeview(frame, height=15, selectmode='browse')
        self.tv_whole_grid["columns"] = ("1", "2")
        self.tv_whole_grid['show'] = 'headings'
        self.tv_whole_grid.column("1", width=12, anchor='c')
        self.tv_whole_grid.column("2", width=12, anchor='c')
        self.tv_whole_grid.heading("1", text="Pos_x")
        self.tv_whole_grid.heading("2", text="Pos_y")
        self.tv_whole_grid.grid(row=1, column=0, sticky='EW')

        self.tv_grid_square = Treeview(frame, height=15, selectmode='browse')
        self.tv_grid_square["columns"] = ("1", "2", "3")
        self.tv_grid_square['show'] = 'headings'
        self.tv_grid_square.column("1", width=12, anchor='c')
        self.tv_grid_square.column("2", width=12, anchor='c')
        self.tv_grid_square.column("3", width=12, anchor='c')
        self.tv_grid_square.heading("1", text="Pos_x")
        self.tv_grid_square.heading("2", text="Pos_y")
        self.tv_grid_square.heading("3", text="Pos_z")
        self.tv_grid_square.grid(row=1, column=1, sticky='EW')

        self.tv_target = Treeview(frame, height=15, selectmode='browse')
        self.tv_target["columns"] = ("1", "2", "3")
        self.tv_target['show'] = 'headings'
        self.tv_target.column("1", width=12, anchor='c')
        self.tv_target.column("2", width=12, anchor='c')
        self.tv_target.column("3", width=12, anchor='c')
        self.tv_target.heading("1", text="Pos_x")
        self.tv_target.heading("2", text="Pos_y")
        self.tv_target.heading("3", text="Pos_z")
        self.tv_target.grid(row=1, column=2, sticky='EW')
        
        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

    def init_vars(self):
        self.var_radius = IntVar(value=200)
        self.var_name = StringVar(value="")
        self.var_level = StringVar(value='Whole')

    @suppress_stderr
    def show_progress(self, n):
        tot = 50
        interval = tot / n
        with tqdm(total=100, ncols=60, bar_format='{l_bar}{bar}') as pbar:
            for i in range(n):
                self.lb_coll1.config(text=str(pbar))
                time.sleep(interval)
                pbar.update(100/n)
            self.lb_coll1.config(text=str(pbar))

    def collect_map(self):
        if self.grid_dir is None:
            num = 1
            self.grid_dir = config.locations['work'] / f'Grid_{num}'
            success = False
            while not success:
                try:
                    self.grid_dir.mkdir(parents=True)
                    success = True
                except OSError:
                    num += 1
                    self.grid_dir = config.locations['work'] / f'Grid_{num}'



    def get_pos(self):
        self.position_list = GridFrame(self).get_selected_positions()
        level = self.var_level.get()
        if len(self.position_list) != 0:
            if level == 'Whole':
                self.df_grid = self.position_list
                for index in range(len(self.df_grid)):

            elif level == 'Sqaure':
                if self.df_grid is None:
                    raise RuntimeError('Please collect whole grid map first!')
                else:
                    self.df_sqaure = self.df_sqaure.append(self.position_list, ignore_index=True)
                    for index in range(len(self.position_list)):

            elif level == 'Target':
                if self.df_sqaure is None:
                    raise RuntimeError('Please collect grid square map first!')
                else:
                    self.df_target = df_target.append(self.position_list, ignore_index=True)
                    for index in range(len(self.position_list)):

    def change_grid(self):
        self.df_grid = None
        self.df_sqaure = None
        self.df_target = None
        self.tv_whole_grid.delete(*self.tv_whole_grid.get_children())
        self.tv_grid_square.delete(*self.tv_grid_square.get_children())
        self.tv_target.delete(*self.tv_target.get_children())

    def update_z(self):
        pass

    def go_xy(self):
        pass

    def go_xyz(self):
        pass

    def add_pos(self):
        pass

    def del_pos(self):
        pass

    def save_grid(self):
        # grid g_x g_y 
        # grid sqaure s_x_sy 
        # sqaure target t_x t_y
        if self.grid_dir is not None:
            dir_name = filedialog.askdirectory(initialdir=self.grid_dir, title='Save Whole Grid')
            dir_name = Path(dir_name)
            sample_name = self.var_name.get()
            self.df_grid.to_csv(dir_name/f'grid_{sample_name}.csv', index=False)
            self.df_sqaure.to_csv(dir_name/f'square_{sample_name}.csv', index=False)
            self.df_target.to_csv(dir_name/f'target_{sample_name}.csv', index=False)

    def load_grid(self):
        if self.grid_dir is not None:
            dir_name = filedialog.askdirectory(initialdir=self.grid_dir, title='Load Whole Grid')
            dir_name = Path(dir_name)
            files = dir_name.glob('*.csv')
            for file in files:
                if 'grid' in file:
                    self.df_grid = pd.read_csv(file)
                elif 'square' in file:
                    self.df_sqaure = pd.read_csv(file)
                elif 'target' in file:
                    self.df_target = pd.read_csv(file)
                             

if __name__ == '__main__':
    root = Tk()
    CryoED(root).pack(side='top', fill='both', expand=True)
    root.mainloop()