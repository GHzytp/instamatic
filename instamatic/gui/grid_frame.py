import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import *
from tkinter.ttk import *

import numpy as np
import pandas as pd

from PIL import Image, ImageEnhance, ImageTk

from .base_module import BaseModule
from .modules import MODULES
from instamatic import config
from instamatic.formats import read_tiff, write_tiff
from instamatic.utils.widgets import Hoverbox, Spinbox
from instamatic.processing.find_holes import find_square

class GridFrame(LabelFrame):
    """Load a GUi to show the grid map and label suitable crystals."""

    def __init__(self, parent, init_dir=None):
        LabelFrame.__init__(self, parent, text='Grid Map')
        self.init_dir = init_dir
        self.canvas = None
        self.point_list = pd.DataFrame(columns=['pos_x', 'pos_y', 'cross_1', 'cross_2'])
        self.map = None
        self.map_info = None
        self.map_path = None
        self.image = None
        self.image_scaled = None
        self.last_scale = 1
        self.counter = 0
        self.select_flag = 0
        self._drag_data = {"x": 0, "y": 0}
        self.saved_tv_items = None
        self.software_binsize = config.settings.software_binsize
        self.cryo_frame = None
        self.map_on_canvas = None
        self.last_selected_position = None

        self.init_vars()
        
        frame = Frame(self)

        self.OpenMapButton = Button(frame, text='Open Map', width=12, command=self.open_map, state=NORMAL)
        self.OpenMapButton.grid(row=0, column=0, sticky='EW')
        self.lbl_open_map = Label(frame, text="", width=13)
        self.lbl_open_map.grid(row=0, column=1, columnspan=3, sticky='EW', padx=5)

        self.AddPosButton = Button(frame, text='Add Position', width=12, command=self.add_position, state=NORMAL)
        self.AddPosButton.grid(row=1, column=0, sticky='EW')
        self.DeletePosButton = Button(frame, text='Del Position', width=12, command=self.delete_position, state=NORMAL)
        self.DeletePosButton.grid(row=1, column=1, sticky='EW', padx=5)
        self.MoveMapButton = Button(frame, text='Move Map', width=12, command=self.move_map, state=NORMAL)
        self.MoveMapButton.grid(row=1, column=2, sticky='EW')
        self.UnbindAllButton = Button(frame, text='Unbind All', width=12, command=self.unbind_all, state=NORMAL)
        self.UnbindAllButton.grid(row=1, column=3, sticky='EW', padx=5)
        self.ClearAllButton = Button(frame, text='Clear All', width=12, command=self.clear_all, state=NORMAL)
        self.ClearAllButton.grid(row=1, column=4, sticky='EW')

        self.e_tolerance = Spinbox(frame, width=8, textvariable=self.var_tolerance, from_=0.01, to=2, increment=0.01)
        self.e_tolerance.grid(row=2, column=0, stick='EW')
        self.FindSquareButton = Button(frame, text='Find Squares', width=12, command=self.find_squares, state=NORMAL)
        self.FindSquareButton.grid(row=2, column=1, sticky='EW', padx=5)
        
        self.zoom_slider = tk.Scale(frame, variable=self.var_zoom, from_=0.02, to=1, resolution=0.01, showvalue=1, orient=HORIZONTAL, command=self.set_zoom)
        self.zoom_slider.grid(row=3, column=0, columnspan=3, sticky='EW')
        self.e_zoom_level = Spinbox(frame, width=8, textvariable=self.var_zoom, from_=0.02, to=1, increment=0.01)
        self.e_zoom_level.grid(row=3, column=3, stick='EW', padx=5)
        self.ZoomButton = Button(frame, text='Set Zoom', command=self.set_zoom, state=NORMAL)
        self.ZoomButton.grid(row=3, column=4, sticky='EW')

        self.DeleteItemButton = Button(frame, text='Delete All', width=11, command=self.delete_all, state=NORMAL)
        self.DeleteItemButton.grid(row=0, column=4, sticky='EW')
        self.DeleteItemButton = Button(frame, text='Delete', width=11, command=self.delete_item, state=NORMAL)
        self.DeleteItemButton.grid(row=0, column=5, sticky='EW')
        self.SendItemsButton = Button(frame, text='Send', width=11, command=self.send_items, state=NORMAL)
        self.SendItemsButton.grid(row=0, column=6, sticky='EW')
        self.tv_positions = Treeview(frame, height=3, selectmode='browse')
        self.tv_positions["columns"] = ("1", "2")
        self.tv_positions['show'] = 'headings'
        self.tv_positions.column("1", width=13, anchor='c')
        self.tv_positions.column("2", width=13, anchor='c')
        self.tv_positions.heading("1", text="Pos_x")
        self.tv_positions.heading("2", text="Pos_y")
        self.tv_positions.grid(row=1, column=5, rowspan=5, columnspan=2, sticky='EW')
        self.scroll_tv = ttk.Scrollbar(frame, orient="vertical", command=self.tv_positions.yview)
        self.scroll_tv.grid(row=1, column=7, rowspan=5, sticky='NS')
        self.tv_positions.configure(yscrollcommand=self.scroll_tv.set)
        self.tv_positions.bind("<Double-1>", self.update_tv)
        self.tv_positions.bind("<Button-2>", self.update_tv)
        self.tv_positions.bind("<Button-3>", self.update_tv)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        if self.software_binsize is None:
            canvas_shape = np.array(config.camera.dimensions) * 0.95
        else:
            canvas_shape = np.array(config.camera.dimensions) / self.software_binsize * 0.95
        self.canvas = Canvas(frame, width=canvas_shape[1], height=canvas_shape[0])
        self.canvas.grid(row=0, column=0)
        self.scroll_x = tk.Scrollbar(frame, orient="horizontal", command=self.canvas.xview)
        self.scroll_x.grid(row=1, column=0, sticky="ew")
        self.scroll_y = tk.Scrollbar(frame, orient="vertical", command=self.canvas.yview)
        self.scroll_y.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)
        
    def init_vars(self):
        self.var_zoom = DoubleVar(value=1.0)
        self.var_tolerance = DoubleVar(value=0.1)

    def clear_all(self):
        self.canvas.delete('all')
        self.tv_positions.delete(*self.tv_positions.get_children())
        self.point_list = pd.DataFrame(columns=['pos_x', 'pos_y', 'cross_1', 'cross_2'])
        self.map = None
        self.map_info = None
        self.image = None
        self.image_scaled = None
        self.last_scale = 1
        self.counter = 0
        self.saved_tv_items = None
        self.var_zoom.set(1.0)
        self.lbl_open_map.config(text="")
        self.map_on_canvas = None
        self.select_flag = 0
        self.last_selected_position = None

    def open_map(self):
        if self.init_dir is None:
            self.map_path = filedialog.askopenfilename(initialdir=config.locations['work'], title='Select an image', 
                            filetypes=(('tiff files', '*.tiff'), ('tif files', '*.tif'), ('all files', '*.*')))
        else:
            self.map_path = filedialog.askopenfilename(initialdir=self.init_dir, title='Select an image', 
                            filetypes=(('tiff files', '*.tiff'), ('tif files', '*.tif'), ('all files', '*.*')))
        if self.map_path != '':
            self.clear_all()
            self.lbl_open_map.config(text=self.map_path.split("/")[-1])
            suffix = self.map_path.split('.')[-1]
            if suffix in ('tiff', 'tif'):
                self.map, self.map_info = read_tiff(self.map_path)
            if self.map is not None:
                tmp = self.map - np.min(self.map[::8, ::8])
                tmp = self.map * (256.0 / (1 + np.percentile(self.map[::8, ::8], 99.5))) 
                self.image_scaled = self.image = Image.fromarray(tmp)
                self.image_tk = ImageTk.PhotoImage(image=self.image)
                self.map_on_canvas = self.canvas.create_image(0, 0, anchor=NW, image=self.image_tk, state=DISABLED)
                self.canvas.configure(scrollregion=self.canvas.bbox("all")) # coordinate for the whole image

    def open_from_frame(self):
        if self.map_path != '' and self.map_path is not None:
            self.clear_all()
            self.lbl_open_map.config(text=self.map_path.split("/")[-1])
            suffix = self.map_path.split('.')[-1]
            if suffix in ('tiff', 'tif'):
                self.map, self.map_info = read_tiff(self.map_path)
            if self.map is not None:
                tmp = self.map - np.min(self.map[::8, ::8])
                tmp = self.map * (256.0 / (1 + np.percentile(self.map[::8, ::8], 99.5))) 
                self.image_scaled = self.image = Image.fromarray(tmp)
                self.image_tk = ImageTk.PhotoImage(image=self.image)
                self.map_on_canvas = self.canvas.create_image(0, 0, anchor=NW, image=self.image_tk, state=DISABLED)
                self.canvas.configure(scrollregion=self.canvas.bbox("all")) # coordinate for the whole image

    def save_positions(self):
        files = (('csv files', '*.csv'), ('all files', '*.*'))
        filename = filedialog.asksaveasfile(initialdir=config.locations['work'], title='Save selected positions', 
                             filetypes=files, defaultextension=files)
        if filename != '':
            self.point_list.to_csv(filename, index=False)

    def load_positions(self):
        filename = filedialog.askopenfilename(initialdir=config.locations['work'], title='Load selected positions', 
                             filetypes=(('csv files', '*.csv'), ('all files', '*.*')))
        if filename != '':
            self.point_list = pd.read_csv(filename)
            self.canvas.delete('cross')
            self.counter = 0
            self.tv_positions.delete(*self.tv_positions.get_children())
            for index in range(len(self.point_list)):
                cent_x = self.point_list.loc[index, 'pos_x']
                cent_y = self.point_list.loc[index, 'pos_y']
                self.tv_positions.insert("",'end', text="Item"+str(self.counter), values=(cent_x,cent_y))
                self.counter += 1
                cent_x = cent_x * self.last_scale
                cent_y = cent_y * self.last_scale
                self.point_list.loc[index, 'cross_1'] = self.canvas.create_line(cent_x-5, cent_y, cent_x+6, cent_y, tags='cross', width=3, fill='red')
                self.point_list.loc[index, 'cross_2'] = self.canvas.create_line(cent_x, cent_y-5, cent_x, cent_y+6, tags='cross', width=3, fill='red')
            self.saved_tv_items = self.tv_positions.get_children()

    def find_squares(self):
        if 'grid' in Path(self.map_path).name:
            coords = find_square(self.map, tolerance=self.var_tolerance.get())
            coords = coords.T
            print(coords)
            self.point_list = pd.DataFrame(columns=['pos_x', 'pos_y', 'cross_1', 'cross_2'])
            self.point_list['pos_x'] = coords[1]
            self.point_list['pos_y'] = coords[0]
            """
            self.seg = Image.fromarray(seg)
            self.seg_tk = ImageTk.PhotoImage(image=self.seg)
            self.seg_on_canvas = self.canvas.create_image(0, 0, anchor=NW, image=self.seg_tk, state=DISABLED)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            """
            self.load_positions_from_frame()
        else:
            print('Can only find squares on grid level')

    def load_positions_from_frame(self):
        self.canvas.delete('cross')
        self.counter = 0
        self.tv_positions.delete(*self.tv_positions.get_children())
        for index in range(len(self.point_list)):
            cent_x = self.point_list.loc[index, 'pos_x']
            cent_y = self.point_list.loc[index, 'pos_y']
            self.tv_positions.insert("",'end', text="Item"+str(self.counter), values=(cent_x,cent_y))
            self.counter += 1
            cent_x = cent_x * self.last_scale
            cent_y = cent_y * self.last_scale
            self.point_list.loc[index, 'cross_1'] = self.canvas.create_line(cent_x-5, cent_y, cent_x+6, cent_y, tags='cross', width=3, fill='red')
            self.point_list.loc[index, 'cross_2'] = self.canvas.create_line(cent_x, cent_y-5, cent_x, cent_y+6, tags='cross', width=3, fill='red')
        self.saved_tv_items = self.tv_positions.get_children()

    def update_tv(self, event):
        selected_item = self.tv_positions.selection()[0]
        selected_position = self.saved_tv_items.index(selected_item)
        selected_cross = (self.point_list.loc[selected_position, 'cross_1'], self.point_list.loc[selected_position, 'cross_2'])
        print(selected_position)
        print(selected_cross)
        print(self.last_selected_position)
        if self.last_selected_position is None:
            self.last_selected_position = selected_position
            self.canvas.itemconfig(int(selected_cross[0]), fill='blue')
            self.canvas.itemconfig(int(selected_cross[1]), fill='blue')
            self.select_flag = 1
        else:
            if selected_position == self.last_selected_position:
                if self.select_flag == 0:
                    self.canvas.itemconfig(int(selected_cross[0]), fill='blue')
                    self.canvas.itemconfig(int(selected_cross[1]), fill='blue')
                    self.select_flag = 1
                elif self.select_flag == 1:
                    self.canvas.itemconfig(int(selected_cross[0]), fill='red')
                    self.canvas.itemconfig(int(selected_cross[1]), fill='red')
                    self.select_flag = 0
            else:
                try:
                    last_selected_cross = (self.point_list.loc[self.last_selected_position, 'cross_1'], self.point_list.loc[self.last_selected_position, 'cross_2'])
                    self.canvas.itemconfig(int(last_selected_cross[0]), fill='red')
                    self.canvas.itemconfig(int(last_selected_cross[1]), fill='red')
                except KeyError:
                    pass
                self.last_selected_position = selected_position
                self.canvas.itemconfig(int(selected_cross[0]), fill='blue')
                self.canvas.itemconfig(int(selected_cross[1]), fill='blue')
                self.select_flag = 1

    def add_position(self):
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.bind("<ButtonPress-1>", self._mouse_clicked_add)

    def delete_position(self):
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.bind("<ButtonPress-1>", self._mouse_clicked_delete)

    def move_map(self):
        self.canvas.unbind("<ButtonPress-1>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.bind('<ButtonPress-1>', self._mouse_move_start)
        self.canvas.bind('<ButtonRelease-1>', self._mouse_move_end)
        self.canvas.bind("<B1-Motion>", self._mouse_move)

    def unbind_all(self):
        self.canvas.unbind("<ButtonPress-1>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<B1-Motion>")

    def set_zoom(self, event=None):
        if self.image is not None:
            time.sleep(0.03)
            scale = self.var_zoom.get()
            self.image_scaled = self.image.resize((int(self.image.size[0]*scale), int(self.image.size[1]*scale)))
            self.image_tk = ImageTk.PhotoImage(image=self.image_scaled)
            self.canvas.itemconfig(self.map_on_canvas, image=self.image_tk)
            for index, point in self.point_list.iterrows():
                self.canvas.move(int(point['cross_1']), point['pos_x']*scale-point['pos_x']*self.last_scale, point['pos_y']*scale-point['pos_y']*self.last_scale)
                self.canvas.move(int(point['cross_2']), point['pos_x']*scale-point['pos_x']*self.last_scale, point['pos_y']*scale-point['pos_y']*self.last_scale)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self.last_scale = scale

    def _mouse_clicked_add(self, event):
        if self.image_scaled is not None:
            self.draw_cross(event.x, event.y)

    def _mouse_clicked_delete(self, event):
        if self.image_scaled is not None:
            self.delete_cross(event.x, event.y)

    def _mouse_move_start(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _mouse_move_end(self, event):
        self._drag_data["x"] = 0
        self._drag_data["y"] = 0

    def _mouse_move(self, event):
        delta_x = event.x - self._drag_data["x"]
        delta_y = event.y - self._drag_data["y"]

        if delta_x > 0:
            self.canvas.xview_scroll(1, UNITS)
        else:
            self.canvas.xview_scroll(-1, UNITS)

        if delta_y > 0:
            self.canvas.yview_scroll(1, UNITS)
        else:
            self.canvas.yview_scroll(-1, UNITS)

        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def draw_cross(self, cent_x, cent_y):
        point = {}
        size = self.image_scaled.size
        cent_x = cent_x + self.scroll_x.get()[0] * size[0]
        cent_y = cent_y +  self.scroll_y.get()[0] * size[1]
        point['cross_1'] = self.canvas.create_line(cent_x-5, cent_y, cent_x+6, cent_y, tags='cross', width=3, fill='red')
        point['cross_2'] = self.canvas.create_line(cent_x, cent_y-5, cent_x, cent_y+6, tags='cross', width=3, fill='red')
        cent_x = cent_x
        point['pos_x'] = cent_x / self.last_scale
        point['pos_y'] = cent_y / self.last_scale
        self.tv_positions.insert("",'end', text="Item_"+str(self.counter), values=(point['pos_x'],point['pos_y']))
        self.saved_tv_items = self.tv_positions.get_children()
        self.counter += 1
        self.point_list = self.point_list.append(point, ignore_index=True)

    def delete_cross(self, cent_x, cent_y):
        size = self.image_scaled.size
        cent_x = (cent_x + self.scroll_x.get()[0] * size[0]) / self.last_scale
        cent_y = (cent_y +  self.scroll_y.get()[0] * size[1]) / self.last_scale
        delete_condition = (self.point_list['pos_x'] - cent_x) ** 2 + (self.point_list['pos_y'] - cent_y) ** 2 <= 50 / self.last_scale**2
        for index, condition in delete_condition.iteritems():
            if condition == True:
                self.canvas.delete(int(self.point_list.loc[index, 'cross_1']))
                self.canvas.delete(int(self.point_list.loc[index, 'cross_2']))
                self.tv_positions.delete(self.saved_tv_items[index])
        self.saved_tv_items = self.tv_positions.get_children()
        self.point_list = self.point_list[-delete_condition]
        self.point_list = self.point_list.reset_index().drop(['index'], axis=1)
        print(self.point_list)

    def delete_item(self):
        selected_item = self.tv_positions.selection()
        if len(selected_item) != 0:
            selected_item = selected_item[0]
            index = self.saved_tv_items.index(selected_item)
            delete_condition = [False] * len(self.saved_tv_items)
            delete_condition[index] = True
            delete_condition = pd.Series(delete_condition)
            for index, condition in delete_condition.iteritems():
                if condition == True:
                    self.canvas.delete(int(self.point_list.loc[index, 'cross_1']))
                    self.canvas.delete(int(self.point_list.loc[index, 'cross_2']))
            self.tv_positions.delete(selected_item)
            self.saved_tv_items = self.tv_positions.get_children()
            self.point_list = self.point_list[-delete_condition]
            self.point_list = self.point_list.reset_index().drop(['index'], axis=1)

    def delete_all(self):
        self.tv_positions.delete(*self.tv_positions.get_children())
        self.canvas.delete('cross')
        self.point_list = pd.DataFrame(columns=['pos_x', 'pos_y', 'cross_1', 'cross_2'])
        self.counter = 0
        self.saved_tv_items = None
        self.select_flag = 0
        self.last_selected_position = None

    def _generate_stage_position(self):
        if self.map_info is not None:
            pixel_center = np.array(self.map_info['ImageResolution'][::-1])/2
            stage_pos = self.point_list[['pos_x', 'pos_y']].to_numpy() # pixel coordination (relative to (0,0))
            stage_pos -= pixel_center
            stage_matrix = np.array(self.map_info['stage_matrix'])
            # this is done because the x and y axis definition of numpy (Y,X) and tkinter canvas (X,Y) is different
            stage_matrix = stage_matrix[::-1] 
            stage_pos = stage_pos @ stage_matrix # stage coordination (include pixelsize already)
            stage_pos += np.array(self.map_info['center_pos'])
            stage_pos = np.round(stage_pos)
            stage_pos_df = pd.DataFrame({'x':self.point_list['pos_x'], 'y':self.point_list['pos_y'], 'pos_x':stage_pos[:,0], 'pos_y':stage_pos[:,1]})
            path = Path(self.map_path).parent
            return stage_pos_df, path
        else:
            return None, None

    def send_items(self):
        if self.cryo_frame is None:
            self.cryo_frame = [module for module in MODULES if module.name == 'cryo'][0].frame

        stage_pos_df, path = self._generate_stage_position()

        level = self.cryo_frame.var_level.get()
        if stage_pos_df is not None:
            name = Path(self.map_path).name
            if level == 'Whole':
                if name.split('_')[0] != 'grid':
                    messagebox.showerror(title='Error', message='Please use grid level image!')
                    return
                last_num_grid = len(self.cryo_frame.df_grid)
                self.cryo_frame.df_grid = self.cryo_frame.df_grid.append(stage_pos_df, ignore_index=True)
                for index in range(len(stage_pos_df)):
                    self.cryo_frame.tv_whole_grid.insert("",'end', text="Item_"+str(last_num_grid+index), 
                                        values=(last_num_grid+index, stage_pos_df.loc[index,'pos_x'],stage_pos_df.loc[index,'pos_y']))
                    self.cryo_frame.df_grid.loc[last_num_grid+index, 'grid'] = last_num_grid + index
                self.cryo_frame.grid_dir = Path(path)
                print(self.cryo_frame.df_grid)
            elif level == 'Square':
                z = self.cryo_frame.ctrl.stage.z
                if self.cryo_frame.df_grid is None:
                    raise RuntimeError('Please collect whole grid map first!')
                else:
                    try:
                        grid_num = self.cryo_frame.tv_whole_grid.get_children().index(self.cryo_frame.tv_whole_grid.selection()[0])
                    except IndexError: 
                        raise RuntimeError('Please select a grid position before get positions in square level')

                    if name.split('_')[0] != 'square':
                        messagebox.showerror(title='Error', message='Please use square level image!')
                        return

                    last_num_square = len(self.cryo_frame.df_square)
                    existing_num_square = len(self.cryo_frame.df_square[self.cryo_frame.df_square['grid'] == grid_num])
                    existing_square_in_tv = len(self.cryo_frame.tv_grid_square.get_children())
                    self.cryo_frame.df_square = self.cryo_frame.df_square.append(stage_pos_df, ignore_index=True)
                    for index in range(len(stage_pos_df)):
                        self.cryo_frame.tv_grid_square.insert("",'end', text="Item_"+str(last_num_square+index), 
                                        values=(existing_square_in_tv+index, stage_pos_df.loc[index,'pos_x'],stage_pos_df.loc[index,'pos_y'],z))
                        self.cryo_frame.df_square.loc[last_num_square+index, 'grid'] = grid_num
                        self.cryo_frame.df_square.loc[last_num_square+index, 'square'] = existing_num_square + index
                        self.cryo_frame.df_square.loc[last_num_square+index, 'pos_z'] = z
                    self.cryo_frame.square_dir = Path(path)
                    self.cryo_frame.grid_dir = Path(path).parent
                    print(self.cryo_frame.df_square)
            elif level == 'Target':
                z = self.cryo_frame.ctrl.stage.z
                if self.cryo_frame.df_square is None:
                    raise RuntimeError('Please collect grid square map first!')
                else:
                    try:
                        grid_num = self.cryo_frame.tv_whole_grid.get_children().index(self.cryo_frame.tv_whole_grid.selection()[0])
                        square_num = self.cryo_frame.tv_grid_square.get_children().index(self.cryo_frame.tv_grid_square.selection()[0])
                    except IndexError:
                        raise RuntimeError('Please select a grid and square before get positions in target level')

                    if name.split('_')[0] != 'target':
                        messagebox.showerror(title='Error', message='Please use target level image!')
                        return
                    last_num_target = len(self.cryo_frame.df_target)
                    existing_num_targets = len(self.cryo_frame.df_target[(self.cryo_frame.df_target['grid'] == grid_num) & (self.cryo_frame.df_target['square'] == square_num)])
                    existing_target_in_tv = len(self.cryo_frame.tv_target.get_children())
                    self.cryo_frame.df_target = self.cryo_frame.df_target.append(stage_pos_df, ignore_index=True)
                    for index in range(len(stage_pos_df)):
                        self.cryo_frame.tv_target.insert("",'end', text="Item_"+str(last_num_target+index), 
                                        values=(existing_target_in_tv+index, stage_pos_df.loc[index,'pos_x'],stage_pos_df.loc[index,'pos_y'],z))
                        self.cryo_frame.df_target.loc[last_num_target+index, 'grid'] = grid_num
                        self.cryo_frame.df_target.loc[last_num_target+index, 'square'] = square_num
                        self.cryo_frame.df_target.loc[last_num_target+index, 'target'] = existing_num_targets+index
                        self.cryo_frame.df_target.loc[last_num_target+index, 'pos_z'] = z
                    self.cryo_frame.square_dir = Path(path).parent
                    self.cryo_frame.target_dir = Path(path)
                    print(self.cryo_frame.df_target)

module = BaseModule(name='grid', display_name='GridMap', tk_frame=GridFrame, location='left')
commands = {}

if __name__ == '__main__':
    root = Tk()
    GridFrame(root).pack(side='top', fill='both', expand=True)
    root.mainloop()