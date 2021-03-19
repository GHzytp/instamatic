import threading
import time
from pathlib import Path
from datetime import datetime
from tkinter import filedialog, messagebox
from tkinter import *
from tkinter.ttk import *
from tqdm import tqdm

import numpy as np
import pandas as pd

from .base_module import BaseModule
from .modules import MODULES
from instamatic import config
from instamatic import TEMController
from instamatic.formats import write_tiff
from instamatic.utils import suppress_stderr
from instamatic.gui.grid_window import GridWindow
from instamatic.utils.widgets import MultiListbox, Hoverbox

from pyserialem.navigation import sort_nav_items_by_shortest_path

class CryoEDFrame(LabelFrame):
    """GUI panel for Cryo electron diffraction data collection protocol."""

    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Cryo electron diffraction protocol')
        self.parent = parent
        self.df_grid = pd.DataFrame(columns=['grid', 'x', 'y', 'pos_x', 'pos_y', 'img_location'])
        self.df_square = pd.DataFrame(columns=['grid', 'square', 'x', 'y', 'pos_x', 'pos_y', 'pos_z', 'img_location'])
        self.df_target = pd.DataFrame(columns=['grid', 'square', 'target', 'x', 'y', 'pos_x', 'pos_y', 'pos_z', 'diff_location'])
        self.grid_dir = None
        self.square_dir = None
        self.last_grid = None
        self.last_square = None
        self.grid_montage_path = None
        self.ctrl = TEMController.get_instance()
        self.dimension = self.ctrl.cam.dimension
        self.binsize = self.ctrl.cam.default_binsize
        self.software_binsize = config.settings.software_binsize
        self.indexing_frame = [module for module in MODULES if module.name == 'indexing'][0].frame
        try:
            self.grid_frame = [module for module in MODULES if module.name == 'grid'][0].frame
        except IndexError:
            self.grid_frame = None

        self.init_vars()

        frame = Frame(self)

        self.e_level = OptionMenu(frame, self.var_level, 'Whole', 'Whole', 'Square', 'Target')
        self.e_level.config(width=7)
        self.e_level.grid(row=0, column=0, sticky='EW')
        Label(frame, text='Radius(um):', anchor="center").grid(row=0, column=1, sticky='EW')
        self.e_radius = Spinbox(frame, textvariable=self.var_radius, width=6, from_=0.0, to=500.0, increment=1)
        self.e_radius.grid(row=0, column=2, sticky='EW', padx=5)
        Label(frame, text='Exp Name:', anchor="center").grid(row=0, column=3, sticky='EW')
        self.e_name = Entry(frame, textvariable=self.var_name, width=8)
        self.e_name.grid(row=0, column=4, sticky='EW', padx=5)
        Label(frame, text='Exposure:', anchor="center").grid(row=0, column=5, sticky='EW')
        self.e_radius = Spinbox(frame, textvariable=self.var_exposure, width=6, from_=self.ctrl.cam.default_exposure*2, to=30, increment=self.ctrl.cam.default_exposure)
        self.e_radius.grid(row=0, column=6, sticky='EW', padx=5)
        
        self.CollectMapButton = Button(frame, text='Collect Montage or Image', width=11, command=self.collect_map, state=NORMAL)
        self.CollectMapButton.grid(row=1, column=1, columnspan=2, sticky='EW')
        self.OpenMapButton = Button(frame, text='Get Stage Positions', width=11, command=self.get_pos, state=NORMAL)
        self.OpenMapButton.grid(row=1, column=3, columnspan=2, sticky='EW', padx=5)
        self.RetakeImgButton = Button(frame, text='Retake IMG', width=6, command=self.retake_image, state=NORMAL)
        self.RetakeImgButton.grid(row=1, column=5, sticky='EW')
        self.GetDiffButton = Button(frame, text='Get DIFF', width=6, command=self.get_diff, state=NORMAL)
        self.GetDiffButton.grid(row=1, column=6, sticky='EW', padx=5)

        self.lb_coll1 = Label(frame, text='')
        self.lb_coll1.grid(row=3, column=0, columnspan=7, sticky='EW', pady=5)
        

        self.DelGridButton = Button(frame, text='Del Grid', width=11, command=self.del_grid, state=NORMAL)
        self.DelGridButton.grid(row=4, column=0, sticky='EW')
        self.DelSquareButton = Button(frame, text='Del Square', width=11, command=self.del_square, state=NORMAL)
        self.DelSquareButton.grid(row=4, column=1, sticky='EW', padx=5)
        self.DelTargetButton = Button(frame, text='Del Target', width=11, command=self.del_target, state=NORMAL)
        self.DelTargetButton.grid(row=4, column=2, sticky='EW')
        self.SaveGridButton = Button(frame, text='Change Grid', width=11, command=self.change_grid, state=NORMAL)
        self.SaveGridButton.grid(row=4, column=4, sticky='EW')
        self.SaveGridButton = Button(frame, text='Save Grid', width=11, command=self.save_grid, state=NORMAL)
        self.SaveGridButton.grid(row=4, column=5, sticky='EW', padx=5)
        self.LoadGridButton = Button(frame, text='Load Grid', width=11, command=self.load_grid, state=NORMAL)
        self.LoadGridButton.grid(row=4, column=6, sticky='EW')
        

        self.UpdateZButton = Button(frame, text='Z Square', width=11, command=self.update_z_square, state=NORMAL)
        self.UpdateZButton.grid(row=5, column=0, sticky='EW')
        self.UpdateZButton = Button(frame, text='Z Target', width=11, command=self.update_z_target, state=NORMAL)
        self.UpdateZButton.grid(row=5, column=1, sticky='EW', padx=5)
        self.GoXYButton = Button(frame, text='Go to XY', width=11, command=self.go_xy, state=NORMAL)
        self.GoXYButton.grid(row=5, column=2, sticky='EW')
        self.GoXYZButton = Button(frame, text='Go to XYZ', width=11, command=self.go_xyz, state=NORMAL)
        self.GoXYZButton.grid(row=5, column=3, sticky='EW', padx=5)
        self.ShowGridButton = Button(frame, text='Show Mont', width=11, command=self.show_grid_montage, state=NORMAL)
        self.ShowGridButton.grid(row=5, column=4, sticky='EW')
        self.ShowGridButton = Button(frame, text='Show Grid', width=11, command=self.show_grid, state=NORMAL)
        self.ShowGridButton.grid(row=5, column=5, sticky='EW', padx=5)
        self.ShowSquareButton = Button(frame, text='ShowSquare', width=11, command=self.show_square, state=NORMAL)
        self.ShowSquareButton.grid(row=5, column=6, sticky='EW')

        self.ShowTargetButton = Button(frame, text='Show Target', width=11, command=self.show_target, state=NORMAL)
        self.ShowTargetButton.grid(row=6, column=0, sticky='EW')
        self.RunTargetButton = Button(frame, text='Run Target', width=11, command=self.run_target, state=NORMAL)
        self.RunTargetButton.grid(row=6, column=1, sticky='EW', padx=5)
        

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Label(frame, width=20, text='Whole Grid Level', anchor="center").grid(row=0, column=0, sticky='EW')
        Label(frame, width=28, text='Grid Square Level', anchor="center").grid(row=0, column=2, sticky='EW')
        Label(frame, width=28, text='Individual target Level', anchor="center").grid(row=0, column=4, sticky='EW')

        self.tv_whole_grid = Treeview(frame, height=12, selectmode='browse')
        self.tv_whole_grid["columns"] = ("1", "2", "3")
        self.tv_whole_grid['show'] = 'headings'
        self.tv_whole_grid.column("1", width=8, anchor='c')
        self.tv_whole_grid.column("2", width=12, anchor='c')
        self.tv_whole_grid.column("3", width=12, anchor='c')
        self.tv_whole_grid.heading("1", text="IDX")
        self.tv_whole_grid.heading("2", text="Pos_x")
        self.tv_whole_grid.heading("3", text="Pos_y")
        self.tv_whole_grid.grid(row=1, column=0, sticky='EW')
        self.tv_whole_grid.bind("<Double-1>", self.update_grid)
        self.tv_whole_grid.bind("<Button-2>", self.update_grid)
        self.tv_whole_grid.bind("<Button-3>", self.update_grid)
        self.scroll_tv_grid = ttk.Scrollbar(frame, orient="vertical", command=self.tv_whole_grid.yview)
        self.scroll_tv_grid.grid(row=1, column=1, sticky='NS')
        self.tv_whole_grid.configure(yscrollcommand=self.scroll_tv_grid.set)

        self.tv_grid_square = Treeview(frame, height=12, selectmode='browse')
        self.tv_grid_square["columns"] = ("1", "2", "3", "4")
        self.tv_grid_square['show'] = 'headings'
        self.tv_grid_square.column("1", width=8, anchor='c')
        self.tv_grid_square.column("2", width=12, anchor='c')
        self.tv_grid_square.column("3", width=12, anchor='c')
        self.tv_grid_square.column("4", width=12, anchor='c')
        self.tv_grid_square.heading("1", text="IDX")
        self.tv_grid_square.heading("2", text="Pos_x")
        self.tv_grid_square.heading("3", text="Pos_y")
        self.tv_grid_square.heading("4", text="Pos_z")
        self.tv_grid_square.grid(row=1, column=2, sticky='EW')
        self.tv_grid_square.bind("<Double-1>", self.update_square)
        self.tv_grid_square.bind("<Button-2>", self.update_square)
        self.tv_grid_square.bind("<Button-3>", self.update_square)
        self.scroll_tv_square = ttk.Scrollbar(frame, orient="vertical", command=self.tv_grid_square.yview)
        self.scroll_tv_square.grid(row=1, column=3, sticky='NS')
        self.tv_grid_square.configure(yscrollcommand=self.scroll_tv_square.set)

        self.tv_target = Treeview(frame, height=12, selectmode='browse')
        self.tv_target["columns"] = ("1", "2", "3", "4")
        self.tv_target['show'] = 'headings'
        self.tv_target.column("1", width=8, anchor='c')
        self.tv_target.column("2", width=12, anchor='c')
        self.tv_target.column("3", width=12, anchor='c')
        self.tv_target.column("4", width=12, anchor='c')
        self.tv_target.heading("1", text="IDX")
        self.tv_target.heading("2", text="Pos_x")
        self.tv_target.heading("3", text="Pos_y")
        self.tv_target.heading("4", text="Pos_z")
        self.tv_target.grid(row=1, column=4, sticky='EW')
        self.scroll_tv_target = ttk.Scrollbar(frame, orient="vertical", command=self.tv_target.yview)
        self.scroll_tv_target.grid(row=1, column=5, sticky='NS')
        self.tv_target.configure(yscrollcommand=self.scroll_tv_target.set)
        
        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

    def init_vars(self):
        self.var_radius = IntVar(value=200)
        self.var_name = StringVar(value="")
        self.var_level = StringVar(value='Whole')
        self.var_exposure = DoubleVar(value=round(round(1.5/self.ctrl.cam.default_exposure)*self.ctrl.cam.default_exposure, 1))

    def run_target(self):
        pass

    def show_grid_montage(self):
        self.grid_frame.map_path = str(self.grid_montage_path)
        self.grid_frame.open_from_frame()
        self.grid_frame.point_list = pd.DataFrame(columns=['pos_x', 'pos_y', 'cross_1', 'cross_2'])
        self.grid_frame.point_list['pos_x'] = self.df_grid['x']
        self.grid_frame.point_list['pos_y'] = self.df_grid['y']
        self.grid_frame.point_list = self.grid_frame.point_list.reset_index().drop(['index'], axis=1)
        self.grid_frame.load_positions_from_frame()

    def show_grid(self):
        try:
            selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
            self.grid_frame.map_path = str(self.grid_dir/self.df_grid.loc[self.df_grid['grid']==selected_grid, 'img_location'].values[0])
            self.grid_frame.open_from_frame()
            self.grid_frame.point_list = pd.DataFrame(columns=['pos_x', 'pos_y', 'cross_1', 'cross_2'])
            self.grid_frame.point_list['pos_x'] = self.df_square.loc[self.df_square['grid']==selected_grid, 'x']
            self.grid_frame.point_list['pos_y'] = self.df_square.loc[self.df_square['grid']==selected_grid, 'y']
            self.grid_frame.point_list = self.grid_frame.point_list.reset_index().drop(['index'], axis=1)
            self.grid_frame.load_positions_from_frame()
        except IndexError:
            raise RuntimeError('Please choose grid')

    def show_square(self):
        try:
            selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
            selected_square = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
            self.grid_frame.map_path = str(self.grid_dir/self.df_square.loc[(self.df_square['grid']==selected_grid) & (self.df_square['square']==selected_square), 'img_location'].values[0])
            self.grid_frame.open_from_frame()
            self.grid_frame.point_list = pd.DataFrame(columns=['pos_x', 'pos_y', 'cross_1', 'cross_2'])
            self.grid_frame.point_list['pos_x'] = self.df_target.loc[(self.df_target['grid']==selected_grid) & (self.df_target['square']==selected_square), 'x']
            self.grid_frame.point_list['pos_y'] = self.df_target.loc[(self.df_target['grid']==selected_grid) & (self.df_target['square']==selected_square), 'y']
            self.grid_frame.point_list = self.grid_frame.point_list.reset_index().drop(['index'], axis=1)
            self.grid_frame.load_positions_from_frame()
        except IndexError:
            raise RuntimeError('Please choose grid and square')

    def show_target(self):
        try:
            selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
            selected_square = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
            selected_target = self.tv_target.get_children().index(self.tv_target.selection()[0])
            self.indexing_frame.img_path = str(self.grid_dir/self.df_target.loc[(self.df_target['grid']==selected_grid) & (self.df_target['square']==selected_square) & (self.df_target['target']==selected_target), 'diff_location'].values[0])
            self.indexing_frame.open_from_frame()
        except IndexError:
            raise RuntimeError('Please choose grid, square and target')

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
        self.state = self.ctrl.mode.state
        if self.state in ('D', 'LAD', 'diff'):
            raise RuntimeError('Cannot collect map in diffraction mode')

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

        level = self.var_level.get()
        if level == 'Whole':
            if self.state not in ('LM', 'lowmag'):
                print('Recommend in low mag mode to collect whole grid map')

            confirm  = messagebox.askquestion('Collect whole grid map', 'Confirm proper conditions (low mag) were setted')
            if confirm == 'yes':
                self.mag = self.ctrl.magnification.get()
                if self.software_binsize is None:
                    self.image_scale = config.calibration[self.state]['pixelsize'][self.mag] / 1000 * self.binsize #nm->um
                else:
                    self.image_scale = config.calibration[self.state]['pixelsize'][self.mag] / 1000 * self.binsize * self.software_binsize
                img_physical_area = self.dimension[0] * self.dimension[1] * self.image_scale**2 
                num_img = min(max(int(np.sqrt(np.pi * self.var_radius.get()**2 / img_physical_area)), 1), 5)
                self.var_radius.set(num_img * self.image_scale * (self.dimension[0] + self.dimension[1]) / 4)
                t = threading.Thread(target=self.collect_montage, args=(num_img,self.grid_dir/f'grid_{self.var_name.get()}.tiff'), daemon=True)
                t.start()
                self.grid_montage_path = self.grid_dir/f'grid_{self.var_name.get()}.tiff'
                
        elif level == 'Square':
            if self.grid_dir is None:
                raise RuntimeError('Please first collect a whole grid map')
            
            if self.state not in ('SA', 'mag1', 'mag2', 'samag'):
                print('Recommend to use intermediate maginifcation to collect grid square map')

            confirm  = messagebox.askquestion('Collect grid square map', 'Confirm proper conditions (medium mag) were setted')
            if confirm == 'yes':
                try:
                    selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
                    num = 1
                    self.square_dir = self.grid_dir / f'Sqaure_{num}'
                    success = False
                    while not success:
                        try:
                            self.square_dir.mkdir(parents=True)
                            success = True
                        except OSError:
                            num += 1
                            self.square_dir = self.grid_dir / f'Square_{num}'
                    self.mag = self.ctrl.magnification.get()
                    if self.software_binsize is None:
                        self.image_scale = config.calibration[self.state]['pixelsize'][self.mag] / 1000 * self.binsize #nm->um
                    else:
                        self.image_scale = config.calibration[self.state]['pixelsize'][self.mag] / 1000 * self.binsize * self.software_binsize
                    
                    self.var_radius.set(self.image_scale * (self.dimension[0] + self.dimension[1]) / 4)
                    t = threading.Thread(target=self.collect_image, args=(self.var_exposure.get(),level,self.square_dir/f'square_{self.var_name.get()}.tiff'), daemon=True)
                    t.start()
                    self.df_grid.loc[self.df_grid['grid']==selected_grid, 'img_location'] = Path(self.square_dir.name)/f'square_{self.var_name.get()}.tiff'
                except IndexError:
                    raise RuntimeError('Please choose grid')

        elif level == 'Target':
            if self.square_dir is None:
                raise RuntimeError('Please first collect a grid square map')
            
            confirm  = messagebox.askquestion('Collect targets', 'Confirm proper conditions (high mag) were setted')
            if confirm == 'yes':
                try:
                    selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
                    selected_square = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
                    num = 1
                    self.target_dir = self.square_dir / f'Target_{num}'
                    success = False
                    while not success:
                        try:
                            self.target_dir.mkdir(parents=True)
                            success = True
                        except OSError:
                            num += 1
                            self.target_dir = self.square_dir / f'Target_{num}'
                    self.mag = self.ctrl.magnification.get()
                    if self.software_binsize is None:
                        self.image_scale = config.calibration[self.state]['pixelsize'][self.mag] / 1000 * self.binsize #nm->um
                    else:
                        self.image_scale = config.calibration[self.state]['pixelsize'][self.mag] / 1000 * self.binsize * self.software_binsize
                    
                    self.var_radius.set(self.image_scale * (self.dimension[0] + self.dimension[1]) / 4)
                    t = threading.Thread(target=self.collect_image, args=(self.var_exposure.get(),level,self.target_dir/f'target_{self.var_name.get()}.tiff'), daemon=True)
                    t.start()
                    self.df_square.loc[(self.df_square['grid']==selected_grid) & (self.df_square['square']==selected_square), 'img_location'] = Path(self.target_dir.parent.name)/self.target_dir.name/f'target_{self.var_name.get()}.tiff'
                except IndexError:
                    raise RuntimeError('Please choose grid and square')

    def retake_image(self):
        level = self.var_level.get()
        if level == 'Square':
            if self.square_dir is None:
                raise RuntimeError('Please first collect a grid square map')
            t = threading.Thread(target=self.collect_image, args=(self.var_exposure.get(),level,self.square_dir/f'square_{self.var_name.get()}.tiff'), daemon=True)
            t.start()
        elif level == 'Target':
            if self.target_dir is None:
                raise RuntimeError('Please first collect a target map')
            t = threading.Thread(target=self.collect_image, args=(self.var_exposure.get(),level,self.target_dir/f'target_{self.var_name.get()}.tiff'), daemon=True)
            t.start()

    def get_diff(self):
        self.state = self.ctrl.mode.state
        if self.state in ('D', 'diff', 'LAD'):
            try:
                selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
                selected_square = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
                selected_target = self.tv_target.get_children().index(self.tv_target.selection()[0])
                self.cam_len = self.ctrl.magnification.get()
                target_path = self.grid_dir/self.df_square.loc[(self.df_square['grid']==selected_grid) & (self.df_square['square']==selected_square), 'img_location'].parent
                existing_tiff = len(list(self.target_path.glob('*.tiff')))
                t = threading.Thread(target=self.collect_image, args=(self.var_exposure.get(),'Target diffcation',target_path/f'target_diff_{self.var_name.get()}_{existing_tiff:03}.tiff'), daemon=True)
                t.start()
                self.df_target.loc[(self.df_target['grid']==selected_grid) & (self.df_target['square']==selected_square) & (self.df_target['target']==selected_target), 'img_location'] = Path(self.target_dir.parent.name)/self.target_dir.name/f'target_diff_{self.var_name.get()}_{existing_tiff:03}.tiff'
            except IndexError:
                raise RuntimeError('Please choose grid, square and target')

    def collect_montage(self, num_img, filepath):
        ctrl = self.ctrl
        gm = self.ctrl.grid_montage()
        current_pos = self.ctrl.stage.xy
        pos, px_center, stage_center = gm.setup(nx=num_img, ny=num_img, stage_shift=current_pos)
        self.lb_coll1.config(text='Collecting montage, please wait for a moment...')
        gm.start()
        m = gm.to_montage()
        m.calculate_montage_coords()
        #m.optimize_montage_coords()
        stitched = m.stitch()
        h = {}
        h['is_montage'] = True
        h['center_pos'] = current_pos
        h['mode'] = self.state
        h['magnification'] = self.mag
        h['ImageResolution'] = stitched.shape
        h['stage_matrix'] = self.ctrl.get_stagematrix() # normalized need to multiple pixelsize
        h['ImagePixelsize'] = self.image_scale * 1000 #um -> nm
        write_tiff(filepath, stitched, header=h)
        self.ctrl.stage.xy = current_pos
        self.lb_coll1.config(text=f'Montage completed. Saved dir: {filepath.parent}')

    def collect_image(self, exposure, level, filepath):
        current_pos = self.ctrl.stage.xy
        self.lb_coll1.config(text=f'Collecting {level} image, please wait for a moment...')
        arr, h = self.ctrl.get_image(exposure=exposure)
        h['is_montage'] = False
        h['center_pos'] = current_pos
        h['mode'] = self.state
        h['magnification'] = self.mag
        h['ImageResolution'] = arr.shape
        h['stage_matrix'] = self.ctrl.get_stagematrix() # normalized need to multiple pixelsize
        write_tiff(filepath, arr, header=h)
        self.ctrl.stage.xy = current_pos
        self.lb_coll1.config(text=f'{level} completed. Saved dir: {filepath.parent}')

    def get_pos(self):
        level = self.var_level.get()
        self.position_list, path = GridWindow(self).get_selected_positions()

        if self.position_list is not None:
            z = self.ctrl.stage.z
            if level == 'Whole':
                last_num_grid = len(self.df_grid)
                self.df_grid = self.df_grid.append(self.position_list, ignore_index=True)
                for index in range(len(self.position_list)):
                    self.tv_whole_grid.insert("",'end', text="Item_"+str(last_num_grid+index), 
                                        values=(last_num_grid+index, self.position_list.loc[index,'pos_x'],self.position_list.loc[index,'pos_y']))
                    self.df_grid.loc[last_num_grid+index, 'grid'] = last_num_grid + index
                self.grid_dir = Path(path)
                print(self.df_grid)
            elif level == 'Square':
                if self.df_grid is None:
                    raise RuntimeError('Please collect whole grid map first!')
                else:
                    try:
                        grid_num = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
                    except IndexError: 
                        raise RuntimeError('Please select a grid position before get positions in square level')

                    last_num_square = len(self.df_square)
                    existing_num_square = len(self.df_square[self.df_square['grid'] == grid_num])
                    existing_square_in_tv = len(self.tv_grid_square.get_children())
                    self.df_square = self.df_square.append(self.position_list, ignore_index=True)
                    for index in range(len(self.position_list)):
                        self.tv_grid_square.insert("",'end', text="Item_"+str(last_num_square+index), 
                                        values=(existing_square_in_tv+index, self.position_list.loc[index,'pos_x'],self.position_list.loc[index,'pos_y'],z))
                        self.df_square.loc[last_num_square+index, 'grid'] = grid_num
                        self.df_square.loc[last_num_square+index, 'square'] = existing_num_square + index
                        self.df_square.loc[last_num_square+index, 'pos_z'] = z
                    self.square_dir = Path(path)
                    self.grid_dir = Path(path).parent
                    print(self.df_square)

            elif level == 'Target':
                if self.df_square is None:
                    raise RuntimeError('Please collect grid square map first!')
                else:
                    try:
                        grid_num = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
                        square_num = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
                    except IndexError:
                        raise RuntimeError('Please select a grid and square before get positions in target level')

                    last_num_target = len(self.df_target)
                    existing_num_targets = len(self.df_target[(self.df_target['grid'] == grid_num) & (self.df_target['square'] == square_num)])
                    existing_target_in_tv = len(self.tv_target.get_children())
                    self.df_target = self.df_target.append(self.position_list, ignore_index=True)
                    for index in range(len(self.position_list)):
                        self.tv_target.insert("",'end', text="Item_"+str(last_num_target+index), 
                                        values=(existing_target_in_tv+index, self.position_list.loc[index,'pos_x'],self.position_list.loc[index,'pos_y'],z))
                        self.df_target.loc[last_num_target+index, 'grid'] = grid_num
                        self.df_target.loc[last_num_target+index, 'square'] = square_num
                        self.df_target.loc[last_num_target+index, 'target'] = existing_num_targets+index
                        self.df_target.loc[last_num_target+index, 'pos_z'] = z
                    self.square_dir = Path(path).parent
                    self.target_dir = Path(path)
                    print(self.df_target)

    def change_grid(self):
        self.df_grid = pd.DataFrame(columns=['grid', 'x', 'y', 'pos_x', 'pos_y', 'img_location'])
        self.df_square = pd.DataFrame(columns=['grid', 'square', 'x', 'y', 'pos_x', 'pos_y', 'pos_z', 'img_location'])
        self.df_target = pd.DataFrame(columns=['grid', 'square', 'target', 'x', 'y', 'pos_x', 'pos_y', 'pos_z', 'diff_location'])
        self.tv_whole_grid.delete(*self.tv_whole_grid.get_children())
        self.tv_grid_square.delete(*self.tv_grid_square.get_children())
        self.tv_target.delete(*self.tv_target.get_children())
        self.grid_montage_path = None
        self.grid_dir = None
        self.target_dir = None
        self.square_dir = None
        self.last_grid = None
        self.last_square = None

    def update_grid(self, event):
        selected = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
        if self.last_grid != selected:
            self.last_grid = selected
            self.tv_grid_square.delete(*self.tv_grid_square.get_children())
            self.tv_target.delete(*self.tv_target.get_children())
            selected_square_df = self.df_square[self.df_square['grid'] == selected].reset_index().drop(['index'], axis=1)
            for index in range(len(selected_square_df)):
                self.tv_grid_square.insert("",'end', text="Item_"+str(index), values=(index, selected_square_df.loc[index,'pos_x'],selected_square_df.loc[index,'pos_y'],selected_square_df.loc[index,'pos_z']))

    def update_square(self, event):
        selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
        selected_square = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
        if self.last_square != selected_square or self.last_grid != selected_grid:
            self.last_square = selected_square
            self.last_grid = selected_grid
            self.tv_target.delete(*self.tv_target.get_children())
            selected_target_df = self.df_target[(self.df_target['grid']==selected_grid) & (self.df_target['square']==selected_square)].reset_index().drop(['index'], axis=1)
            for index in range(len(selected_target_df)):
                self.tv_target.insert("",'end', text="Item_"+str(index), values=(index, selected_target_df.loc[index,'pos_x'],selected_target_df.loc[index,'pos_y'],selected_target_df.loc[index,'pos_z']))

    def update_z_square(self):
        selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
        selected_square = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
        z = self.ctrl.stage.z
        self.df_square.loc[(self.df_square['grid']==selected_grid) & (self.df_square['square']==selected_square), 'pos_z'] = z

    def update_z_target(self):
        selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
        selected_square = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
        selected_target = self.tv_target.get_children().index(self.tv_target.selection()[0])
        z = self.ctrl.stage.z
        self.df_target.loc[(self.df_target['grid']==selected_grid) & (self.df_target['square']==selected_square) & 
                            (self.df_target['target']==selected_target), 'pos_z'] = z

    def go_xy(self):
        level = self.var_level.get()
        if level == 'Whole':
            try:
                selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
                selected_df = self.df_grid[(self.df_grid['grid']==selected_grid)]
                self.ctrl.stage.xy = (selected_df['pos_x'].values[0], selected_df['pos_y'].values[0])
            except IndexError:
                raise RuntimeError('Please select a grid position')
        elif level == 'Square':
            try:
                selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
                selected_square = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
                selected_df = self.df_square[(self.df_square['grid']==selected_grid) & (self.df_square['square']==selected_square)]
                self.ctrl.stage.xy = (selected_df['pos_x'].values[0], selected_df['pos_y'].values[0])
            except IndexError:
                raise RuntimeError('Please select a grid and a square position')
        elif level == 'Target':
            try:
                selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
                selected_square = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
                selected_target = self.tv_target.get_children().index(self.tv_target.selection()[0])
                selected_df = self.df_target[(self.df_target['grid']==selected_grid) & (self.df_target['square']==selected_square) & (self.df_target['target']==selected_target)]
                self.ctrl.stage.xy =  (selected_df['pos_x'].values[0], selected_df['pos_y'].values[0])
            except IndexError:
                raise RuntimeError('Please select a grid, a square and a target position')

    def go_xyz(self):
        level = self.var_level.get()
        if level == 'Whole':
            try:
                selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
                selected_df = self.df_grid[(self.df_grid['grid']==selected_grid)]
                self.ctrl.stage.xy = (selected_df['pos_x'].values[0], selected_df['pos_y'].values[0])
            except IndexError:
                raise RuntimeError('Please select a grid position')
        elif level == 'Square':
            try:
                selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
                selected_square = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
                selected_df = self.df_square[(self.df_square['grid']==selected_grid) & (self.df_square['square']==selected_square)]
                self.ctrl.stage.xy = (selected_df['pos_x'].values[0], selected_df['pos_y'].values[0])
                self.ctrl.stage.z = selected_df['pos_z'].values[0]
            except IndexError:
                raise RuntimeError('Please select a grid and a square position')
        elif level == 'Target':
            try:
                selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
                selected_square = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
                selected_target = self.tv_target.get_children().index(self.tv_target.selection()[0])
                selected_df = self.df_target[(self.df_target['grid']==selected_grid) & (self.df_target['square']==selected_square) & (self.df_target['target']==selected_target)]
                self.ctrl.stage.xy =  (selected_df['pos_x'].values[0], selected_df['pos_y'].values[0])
                self.ctrl.stage.z = selected_df['pos_z'].values[0]
            except IndexError:
                raise RuntimeError('Please select a grid, a square and a target position')

    def del_target(self):
        try:
            selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
            selected_square = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
            selected_target = self.tv_target.get_children().index(self.tv_target.selection()[0])
            existing_targets = self.tv_target.get_children()
        except IndexError:
            raise RuntimeError('Please select grid, square and target level.')

        self.tv_target.delete(existing_targets[selected_target])
        existing_targets = self.tv_target.get_children()
        self.df_target = self.df_target[(self.df_target['grid']!=selected_grid) | 
                                        (self.df_target['square']!=selected_square) |
                                         self.df_target['target']!=selected_target].reset_index().drop(['index'], axis=1)
        num = 0
        for index, _ in self.df_target[(self.df_target['grid']==selected_grid) & (self.df_target['square']==selected_square)].iterrows():
            self.df_target.loc[index, 'target'] = num
            self.tv_target.set(existing_targets[num], 0, value=num)
            num += 1

    def del_square(self):
        try:
            selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
            selected_square = self.tv_grid_square.get_children().index(self.tv_grid_square.selection()[0])
            existing_square = self.tv_grid_square.get_children()
        except IndexError:
            raise RuntimeError('Please select grid and square level.')

        self.tv_target.delete(*self.tv_target.get_children())
        self.tv_grid_square.delete(existing_square[selected_square])
        existing_square = self.tv_grid_square.get_children()
        self.df_square_org_index = self.df_square[(self.df_square['grid']==selected_grid) & (self.df_square['square']!=selected_square)]
        self.df_square = self.df_square[(self.df_square['grid']!=selected_grid) | (self.df_square['square']!=selected_square)].reset_index().drop(['index'], axis=1)
        self.df_target = self.df_target[(self.df_target['grid']!=selected_grid) | (self.df_target['square']!=selected_square)].reset_index().drop(['index'], axis=1)

        num = 0
        for index, _ in self.df_square[self.df_square['grid']==selected_grid].iterrows():
            self.df_square.loc[index, 'square'] = num
            self.tv_grid_square.set(existing_square[num], 0, value=num)
            num+=1

        num = 0
        for index, _ in self.df_square_org_index.iterrows():
            self.df_target.loc[self.df_target['square']==index, 'square'] = num
            num+=1

    def del_grid(self):
        try:
            selected_grid = self.tv_whole_grid.get_children().index(self.tv_whole_grid.selection()[0])
            existing_grid = self.tv_whole_grid.get_children()
        except IndexError:
            raise RuntimeError('Please select grid level.')

        self.tv_grid_square.delete(*self.tv_grid_square.get_children())
        self.tv_target.delete(*self.tv_target.get_children())
        self.tv_whole_grid.delete(existing_grid[selected_grid])
        existing_grid = self.tv_whole_grid.get_children()
        self.df_grid_org_index = self.df_grid[(self.df_grid['grid']!=selected_grid)]
        self.df_grid = self.df_grid[(self.df_grid['grid']!=selected_grid)].reset_index().drop(['index'], axis=1)
        self.df_square = self.df_square[(self.df_square['grid']!=selected_grid)].reset_index().drop(['index'], axis=1)
        self.df_target = self.df_target[(self.df_target['grid']!=selected_grid)].reset_index().drop(['index'], axis=1)

        num = 0
        for index, _ in self.df_grid.iterrows():
            self.df_grid.loc[index, 'grid'] = num
            self.tv_whole_grid.set(existing_grid[index], 0, value=num)
            num += 1

        num = 0
        for index, _ in self.df_grid_org_index.iterrows():
            self.df_square.loc[self.df_square['grid']==index, 'grid'] = num
            self.df_target.loc[self.df_target['grid']==index, 'grid'] = num
            num += 1
        
    def save_grid(self):
        # grid g_x g_y 
        # grid square s_x_sy 
        # square target t_x t_y
        if self.grid_dir is not None:
            dir_name = filedialog.askdirectory(initialdir=self.grid_dir, title='Save Whole Grid')
            sample_name = self.var_name.get()
            self.df_grid.to_csv(Path(dir_name)/f'grid_{sample_name}.csv', index=False)
            self.df_square.to_csv(Path(dir_name)/f'square_{sample_name}.csv', index=False)
            self.df_target.to_csv(Path(dir_name)/f'target_{sample_name}.csv', index=False)

    def load_grid(self):
        dir_name = filedialog.askdirectory(initialdir=self.grid_dir, title='Load Whole Grid')
        if dir_name != '':
            self.tv_grid_square.delete(*self.tv_grid_square.get_children())
            self.tv_target.delete(*self.tv_target.get_children())
            self.tv_whole_grid.delete(*self.tv_whole_grid.get_children())
            dir_name = Path(dir_name)
            self.grid_dir = dir_name
            files = dir_name.glob('*.csv')
            for file in files:
                if 'grid' in str(file):
                    self.df_grid = pd.read_csv(file)
                elif 'square' in str(file):
                    self.df_square = pd.read_csv(file)
                elif 'target' in str(file):
                    self.df_target = pd.read_csv(file)
            imgs = dir_name.glob('*.tiff')
            counter = 0
            for img in imgs:
                if 'grid' in str(img):
                    self.grid_montage_path = img
                    counter += 1
                if counter > 1:
                    raise RuntimeError('Only one grid montage allow for one grid')

            for index in range(len(self.df_grid)):
                self.tv_whole_grid.insert("",'end', text="Item_"+str(index), values=(index, self.df_grid.loc[index,'pos_x'],self.df_grid.loc[index,'pos_y']))


module = BaseModule(name='cryo', display_name='CryoED', tk_frame=CryoEDFrame, location='bottom')
commands = {}

if __name__ == '__main__':
    root = Tk()
    CryoEDFrame(root).pack(side='top', fill='both', expand=True)
    root.mainloop()