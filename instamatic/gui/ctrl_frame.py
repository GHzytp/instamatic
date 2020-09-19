import threading
from tkinter import *
from tkinter.ttk import *
import tkinter

from .base_module import BaseModule
from instamatic import config
from instamatic.utils.spinbox import Spinbox


class ExperimentalCtrl(LabelFrame):
    """This panel holds some frequently used functions to control the electron
    microscope."""

    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='TEM Control')

        from instamatic import TEMController
        self.ctrl = TEMController.get_instance()
        self.mode = self.ctrl.mode.state

        self.parent = parent

        self.init_vars()

        frame = Frame(self)

        Label(frame, text='Alpha Angle', width=15).grid(row=1, column=0, sticky='W')
        Label(frame, text='Wobbler (±)', width=15).grid(row=2, column=0, sticky='W')
        Label(frame, text='Stage(XYZ)', width=15).grid(row=3, column=0, sticky='W')

        e_alpha_angle = Spinbox(frame, width=10, textvariable=self.var_alpha_angle, from_=-90, to=90, increment=5)
        e_alpha_angle.grid(row=1, column=1, sticky='EW')
        b_alpha_angle = Button(frame, text='Set', command=self.set_alpha_angle)
        b_alpha_angle.grid(row=1, column=2, sticky='W')
        b_alpha_angle_get = Button(frame, text='Get', command=self.get_alpha_angle)
        b_alpha_angle_get.grid(row=1, column=3, sticky='W')

        b_find_eucentric_height = Button(frame, text='Eucentric', command=self.find_eucentric_height)
        b_find_eucentric_height.grid(row=1, column=4, sticky='EW', columnspan=1)

        if self.ctrl.tem.interface != "fei":
            b_stage_stop = Button(frame, text='Stop stage', command=self.stage_stop)
            b_stage_stop.grid(row=1, column=5, sticky='W')

        cb_nowait = Checkbutton(frame, text='Wait for stage', variable=self.var_stage_wait)
        cb_nowait.grid(row=1, column=6, sticky='W')

        e_alpha_wobbler = Spinbox(frame, width=10, textvariable=self.var_alpha_wobbler, from_=-90, to=90, increment=1)
        e_alpha_wobbler.grid(row=2, column=1, sticky='EW')
        self.b_start_wobble = Button(frame, text='Start', command=self.start_alpha_wobbler)
        self.b_start_wobble.grid(row=2, column=2, sticky='W')
        self.b_stop_wobble = Button(frame, text='Stop', command=self.stop_alpha_wobbler, state=DISABLED)
        self.b_stop_wobble.grid(row=2, column=3, sticky='W')

        Label(frame, text='Select TEM Mode:').grid(row=2, column=4, columnspan=2, sticky='E')
        
        if self.ctrl.tem.interface == "fei":
            self.o_mode = OptionMenu(frame, self.var_mode, self.mode, 'LM', 'Mi', 'SA', 'Mh', 'LAD', 'D', command=self.set_mode)
        else:
            self.o_mode = OptionMenu(frame, self.var_mode, self.mode, 'diff', 'mag1', 'mag2', 'lowmag', 'samag', command=self.set_mode)
        self.o_mode.grid(row=2, column=6, sticky='E', padx=10)

        e_stage_x = Entry(frame, width=10, textvariable=self.var_stage_x)
        e_stage_x.grid(row=3, column=1, sticky='EW')
        e_stage_y = Entry(frame, width=10, textvariable=self.var_stage_y)
        e_stage_y.grid(row=3, column=2, sticky='EW')
        e_stage_y = Entry(frame, width=10, textvariable=self.var_stage_z)
        e_stage_y.grid(row=3, column=3, sticky='EW')

        if config.settings.use_goniotool:
            Label(frame, text='Speed', width=15).grid(row=4, column=0, sticky='W')
            e_goniotool_tx = Spinbox(frame, width=10, textvariable=self.var_goniotool_tx, from_=1, to=12, increment=1)
            e_goniotool_tx.grid(row=4, column=1, sticky='EW')
            b_goniotool_set = Button(frame, text='Set', command=self.set_goniotool_tx)
            b_goniotool_set.grid(row=4, column=2, sticky='W')
            b_goniotool_default = Button(frame, text='Default', command=self.set_goniotool_tx_default)
            b_goniotool_default.grid(row=4, column=3, sticky='W')

        b_stage = Button(frame, text='Set', command=self.set_stage)
        b_stage.grid(row=3, column=4, sticky='W')
        b_stage_get = Button(frame, text='Get', command=self.get_stage)
        b_stage_get.grid(row=3, column=5, sticky='W')

        frame.pack(side='top', fill='x', padx=10, pady=10)
        frame = Frame(self)

        # defocus button
        Label(frame, text='Diff Defocus', width=15).grid(row=5, column=0, sticky='W')
        self.e_diff_defocus = Spinbox(frame, textvariable=self.var_diff_defocus, width=10, from_=-10000, to=10000, increment=100)
        self.e_diff_defocus.grid(row=5, column=1, sticky='EW')

        self.c_toggle_defocus = Checkbutton(frame, text='Toggle defocus ', variable=self.var_toggle_diff_defocus, command=self.toggle_diff_defocus)
        self.c_toggle_defocus.grid(row=5, column=2, sticky='E', columnspan=2)

        self.b_reset_defocus = Button(frame, text='Reset', command=self.reset_diff_defocus, state=DISABLED)
        self.b_reset_defocus.grid(row=5, column=4, sticky='EW')

        Label(frame, text='Diff Defocus', width=15).grid(row=6, column=0, sticky='W')
        self.e_difffocus = Entry(frame, width=12, textvariable=self.var_difffocus)
        self.e_difffocus.grid(row=6, column=1, sticky='W')

        self.b_difffocus = Button(frame, width=10, text='Set', command=self.set_difffocus)
        self.b_difffocus.grid(row=6, column=2, sticky='W')

        self.b_difffocus_get = Button(frame, width=10, text='Get', command=self.get_difffocus)
        self.b_difffocus_get.grid(row=6, column=3, sticky='W')

        if self.ctrl.tem.interface == 'fei':
            self.difffocus_slider = tkinter.Scale(frame, variable=self.var_difffocus, from_=-600000, to=600000, length=250, 
                showvalue=0, orient=HORIZONTAL, command=self.set_difffocus)
        else:
            self.difffocus_slider = tkinter.Scale(frame, variable=self.var_difffocus, from_=0, to=65535, length=250, 
                showvalue=0, orient=HORIZONTAL, command=self.set_difffocus)
        self.difffocus_slider.grid(row=6, column=4, columnspan=3, sticky='W')

        Label(frame, text='ObjFocus', width=15).grid(row=7, column=0, sticky='W')
        self.e_objfocus = Entry(frame, width=12, textvariable=self.var_objfocus)
        self.e_objfocus.grid(row=7, column=1, sticky='W')

        self.b_objfocus = Button(frame, width=10, text='Set', command=self.set_objfocus)
        self.b_objfocus.grid(row=7, column=2, sticky='W')

        self.b_objfocus_get = Button(frame, width=10, text='Get', command=self.get_objfocus)
        self.b_objfocus_get.grid(row=7, column=3, sticky='W')

        if self.ctrl.tem.interface == 'fei':
            self.objfocus_slider = tkinter.Scale(frame, variable=self.var_objfocus, from_=-600000, to=600000, length=250, 
                showvalue=0, orient=HORIZONTAL, command=self.set_objfocus)
        else:
            self.objfocus_slider = tkinter.Scale(frame, variable=self.var_objfocus, from_=0, to=65535, length=250, 
                showvalue=0, orient=HORIZONTAL, command=self.set_objfocus)
        self.objfocus_slider.grid(row=7, column=4, columnspan=3, sticky='W')

        self.set_gui_diffobj()

        Label(frame, text='Brightness', width=15).grid(row=8, column=0, sticky='W')
        e_brightness = Entry(frame, width=12, textvariable=self.var_brightness)
        e_brightness.grid(row=8, column=1, sticky='W')

        b_brightness = Button(frame, width=10, text='Set', command=self.set_brightness)
        b_brightness.grid(row=8, column=2, sticky='W')

        b_brightness_get = Button(frame, width=10, text='Get', command=self.get_brightness)
        b_brightness_get.grid(row=8, column=3, sticky='W')

        if self.ctrl.tem.interface == 'fei':
            slider = tkinter.Scale(frame, variable=self.var_brightness, from_=-1.0, to=1.0, resolution=0.001, length=250, 
                showvalue=0, orient=HORIZONTAL, command=self.set_brightness)
        else:
            slider = tkinter.Scale(frame, variable=self.var_brightness, from_=0, to=65535, length=250, orient=HORIZONTAL, 
                showvalue=0, command=self.set_brightness)
        slider.grid(row=8, column=4, columnspan=3, sticky='W')

        frame.pack(side='top', fill='x', padx=10, pady=10)

        frame = Frame(self)

        Label(frame, text='Beam Shift', width=15).grid(row=9, column=0, sticky='W')

        self.rb_beamshiftx = Radiobutton(frame, width=3, text='X', variable=self.var_beamshift_choose, 
                                        value=0, command=self.choose_beamshiftxy)
        self.rb_beamshiftx.grid(row=9, column=1, sticky='W')
        self.rb_beamshifty = Radiobutton(frame, width=3, text='Y', variable=self.var_beamshift_choose,
                                        value=1, command=self.choose_beamshiftxy)
        self.rb_beamshifty.grid(row=9, column=2, sticky='W')

        self.e_beamshift = Entry(frame, width=8, textvariable=self.var_beamshiftx)
        self.e_beamshift.grid(row=9, column=3, sticky='W')

        self.b_beamshift = Button(frame, width=5, text='Set', command=self.set_beamshift)
        self.b_beamshift.grid(row=9, column=4, sticky='W')

        self.b_beamshift_get = Button(frame, width=5, text='Get', command=self.get_beamshiftx)
        self.b_beamshift_get.grid(row=9, column=5, sticky='W')

        if self.ctrl.tem.interface == 'fei':
            self.beamshift_slider = tkinter.Scale(frame, variable=self.var_beamshiftx, from_=-1e8, to=1e8, length=250, 
                showvalue=0, orient=HORIZONTAL, command=self.set_beamshift)
        else:
            self.beamshift_slider = tkinter.Scale(frame, variable=self.var_beamshiftx, from_=0, to=65535, length=250, 
                showvalue=0, orient=HORIZONTAL, command=self.set_beamshift)
        self.beamshift_slider.grid(row=9, column=6, columnspan=3, sticky='W')

        Label(frame, text='Beam Tilt', width=15).grid(row=10, column=0, sticky='W')

        self.rb_beamtiltx = Radiobutton(frame, width=3, text='X', variable=self.var_beamtilt_choose, 
                                        value=0, command=self.choose_beamtiltxy)
        self.rb_beamtiltx.grid(row=10, column=1, sticky='W')
        self.rb_beamtilty = Radiobutton(frame, width=3, text='Y', variable=self.var_beamtilt_choose,
                                        value=1, command=self.choose_beamtiltxy)
        self.rb_beamtilty.grid(row=10, column=2, sticky='W')

        self.e_beamtilt = Entry(frame, width=8, textvariable=self.var_beamtiltx)
        self.e_beamtilt.grid(row=10, column=3, sticky='W')

        self.b_beamtilt = Button(frame, width=5, text='Set', command=self.set_beamtilt)
        self.b_beamtilt.grid(row=10, column=4, sticky='W')

        self.b_beamtilt_get = Button(frame, width=5, text='Get', command=self.get_beamtiltx)
        self.b_beamtilt_get.grid(row=10, column=5, sticky='W')

        if self.ctrl.tem.interface == 'fei':
            self.beamtilt_slider = tkinter.Scale(frame, variable=self.var_beamtiltx, from_=-9.0, to=9.0, resolution=0.01,
                length=250, showvalue=0, orient=HORIZONTAL, command=self.set_beamtilt)
        else:
            self.beamtilt_slider = tkinter.Scale(frame, variable=self.var_beamtiltx, from_=0, to=65535, length=250, 
                showvalue=0, orient=HORIZONTAL, command=self.set_beamtilt)
        self.beamtilt_slider.grid(row=10, column=6, columnspan=3, sticky='W')

        Label(frame, text='Image Shift 1', width=15).grid(row=11, column=0, sticky='W')
        self.rb_imageshift1x = Radiobutton(frame, width=3, text='X', variable=self.var_imageshift1_choose, 
                                        value=0, command=self.choose_imageshift1xy)
        self.rb_imageshift1x.grid(row=11, column=1, sticky='W')
        self.rb_imageshift1y = Radiobutton(frame, width=3, text='Y', variable=self.var_imageshift1_choose,
                                        value=1, command=self.choose_imageshift1xy)
        self.rb_imageshift1y.grid(row=11, column=2, sticky='W')

        self.e_imageshift1 = Entry(frame, width=8, textvariable=self.var_imageshift1x)
        self.e_imageshift1.grid(row=11, column=3, sticky='W')

        self.b_imageshift1 = Button(frame, width=5, text='Set', command=self.set_imageshift1)
        self.b_imageshift1.grid(row=11, column=4, sticky='W')

        self.b_imageshift1_get = Button(frame, width=5, text='Get', command=self.get_imageshift1x)
        self.b_imageshift1_get.grid(row=11, column=5, sticky='W')

        if self.ctrl.tem.interface == 'fei':
            self.imageshift1_slider = tkinter.Scale(frame, variable=self.var_imageshift1x, from_=-1.5e7, to=1.5e7, length=250, 
                showvalue=0, orient=HORIZONTAL, command=self.set_imageshift1)
        else:
            self.imageshift1_slider = tkinter.Scale(frame, variable=self.var_imageshift1x, from_=0, to=65535, length=250, 
                showvalue=0, orient=HORIZONTAL, command=self.set_imageshift1)
        self.imageshift1_slider.grid(row=11, column=6, columnspan=3, sticky='W')

        Label(frame, text='Image Shift 2', width=15).grid(row=12, column=0, sticky='W')
        self.rb_imageshift2x = Radiobutton(frame, width=3, text='X', variable=self.var_imageshift2_choose, 
                                        value=0, command=self.choose_imageshift2xy)
        self.rb_imageshift2x.grid(row=12, column=1, sticky='W')
        self.rb_imageshift2y = Radiobutton(frame, width=3, text='Y', variable=self.var_imageshift2_choose,
                                        value=1, command=self.choose_imageshift2xy)
        self.rb_imageshift2y.grid(row=12, column=2, sticky='W')

        self.e_imageshift2 = Entry(frame, width=8, textvariable=self.var_imageshift2x)
        self.e_imageshift2.grid(row=12, column=3, sticky='W')

        self.b_imageshift2 = Button(frame, width=5, text='Set', command=self.set_imageshift2)
        self.b_imageshift2.grid(row=12, column=4, sticky='W')

        self.b_imageshift2_get = Button(frame, width=5, text='Get', command=self.get_imageshift2x)
        self.b_imageshift2_get.grid(row=12, column=5, sticky='W')

        if self.ctrl.tem.interface == 'fei':
            self.imageshift2_slider = tkinter.Scale(frame, variable=self.var_imageshift2x, from_=-1.5e7, to=1.5e7, length=250, 
                showvalue=0, orient=HORIZONTAL, command=self.set_imageshift2)
        else:
            self.imageshift2_slider = tkinter.Scale(frame, variable=self.var_imageshift2x, from_=0, to=65535, length=250, 
                showvalue=0, orient=HORIZONTAL, command=self.set_imageshift2)
        self.imageshift2_slider.grid(row=12, column=6, columnspan=3, sticky='W')

        Label(frame, text='Diffraction Shift', width=15).grid(row=13, column=0, sticky='W')
        self.rb_diffshiftx = Radiobutton(frame, width=3, text='X', variable=self.var_diffshift_choose, 
                                        value=0, command=self.choose_diffshiftxy)
        self.rb_diffshiftx.grid(row=13, column=1, sticky='W')
        self.rb_diffshifty = Radiobutton(frame, width=3, text='Y', variable=self.var_diffshift_choose,
                                        value=1, command=self.choose_diffshiftxy)
        self.rb_diffshifty.grid(row=13, column=2, sticky='W')

        self.e_diffshift = Entry(frame, width=8, textvariable=self.var_diffshiftx)
        self.e_diffshift.grid(row=13, column=3, sticky='W')

        self.b_diffshift = Button(frame, width=5, text='Set', command=self.set_diffshift)
        self.b_diffshift.grid(row=13, column=4, sticky='W')

        self.b_diffshift_get = Button(frame, width=5, text='Get', command=self.get_diffshiftx)
        self.b_diffshift_get.grid(row=13, column=5, sticky='W')

        if self.ctrl.tem.interface == 'fei':
            self.diffshift_slider = tkinter.Scale(frame, variable=self.var_diffshiftx, from_=-28.7, to=28.7, resolution=0.01,
                length=250, showvalue=0, orient=HORIZONTAL, command=self.set_diffshift)
        else:
            self.diffshift_slider = tkinter.Scale(frame, variable=self.var_diffshiftx, from_=0, to=65535, length=250, 
                showvalue=0, orient=HORIZONTAL, command=self.set_diffshift)
        self.diffshift_slider.grid(row=13, column=6, columnspan=3, sticky='W')

        if self.ctrl.tem.interface == 'fei':

            Label(frame, text='Img Beam Tilt', width=15).grid(row=14, column=0, sticky='W')

            self.rb_imgbeamtiltx = Radiobutton(frame, width=3, text='X', variable=self.var_imgbeamtilt_choose, 
                                            value=0, command=self.choose_beamtiltxy)
            self.rb_imgbeamtiltx.grid(row=14, column=1, sticky='W')
            self.rb_imgbeamtilty = Radiobutton(frame, width=3, text='Y', variable=self.var_imgbeamtilt_choose,
                                            value=1, command=self.choose_beamtiltxy)
            self.rb_imgbeamtilty.grid(row=14, column=2, sticky='W')

            self.e_imgbeamtilt = Entry(frame, width=8, textvariable=self.var_imgbeamtiltx)
            self.e_imgbeamtilt.grid(row=14, column=3, sticky='W')

            self.b_imgbeamtilt = Button(frame, width=5, text='Set', command=self.set_imgbeamtilt)
            self.b_imgbeamtilt.grid(row=14, column=4, sticky='W')

            self.b_imgbeamtilt_get = Button(frame, width=5, text='Get', command=self.get_imgbeamtiltx)
            self.b_imgbeamtilt_get.grid(row=14, column=5, sticky='W')

            self.imgbeamtilt_slider = tkinter.Scale(frame, variable=self.var_imgbeamtiltx, from_=-9.0, to=9.0, resolution=0.01, 
                    length=250, showvalue=0, orient=HORIZONTAL, command=self.set_imgbeamtilt)

            self.imgbeamtilt_slider.grid(row=14, column=6, columnspan=3, sticky='W')

        frame.pack(side='top', fill='x', padx=10, pady=10)

    def init_vars(self):
        self.var_alpha_angle = DoubleVar(value=0.0)

        self.var_mode = StringVar(value=self.mode)

        self.var_alpha_wobbler = DoubleVar(value=5)

        self.var_stage_x = DoubleVar(value=0)
        self.var_stage_y = DoubleVar(value=0)
        self.var_stage_z = DoubleVar(value=0)

        self.var_goniotool_tx = IntVar(value=1)

        if self.ctrl.tem.interface == 'fei':
            self.var_brightness = DoubleVar(value=self.ctrl.brightness.value)
            if self.mode in ('D', 'LAD'):
                self.var_difffocus = IntVar(value=self.ctrl.difffocus.value)
                self.var_objfocus = IntVar(value=0)
            else:
                self.var_difffocus = IntVar(value=0)
                self.var_objfocus = IntVar(value=self.ctrl.objfocus.value)
            self.var_beamtiltx = DoubleVar(value=self.ctrl.beamtilt.x)
            self.var_beamtilty = DoubleVar(value=self.ctrl.beamtilt.y)
            self.var_diffshiftx = DoubleVar(value=self.ctrl.diffshift.x)
            self.var_diffshifty = DoubleVar(value=self.ctrl.diffshift.y)
            self.var_imgbeamtiltx = DoubleVar(value=self.ctrl.imgbeamtilt.x)
            self.var_imgbeamtilty = DoubleVar(value=self.ctrl.imgbeamtilt.y)
        else:
            self.var_brightness = IntVar(value=self.ctrl.brightness.value)
            if self.mode in ('diff'):
                self.var_difffocus = IntVar(value=self.ctrl.difffocus.value)
                self.var_objfocus = IntVar(value=0)
            else:
                self.var_difffocus = IntVar(value=0)
                self.var_objfocus = IntVar(value=self.ctrl.objfocus.value)
            self.var_beamtiltx = IntVar(value=self.ctrl.beamtilt.x)
            self.var_beamtilty = IntVar(value=self.ctrl.beamtilt.y)
            self.var_diffshiftx = IntVar(value=self.ctrl.diffshift.x)
            self.var_diffshifty = IntVar(value=self.ctrl.diffshift.y)
            self.var_imgbeamtiltx = IntVar(value=self.ctrl.imgbeamtilt.x)
            self.var_imgbeamtilty = IntVar(value=self.ctrl.imgbeamtilt.y)

        self.var_beamshiftx = IntVar(value=self.ctrl.beamshift.x)
        self.var_beamshifty = IntVar(value=self.ctrl.beamshift.y)
        self.var_imageshift1x = IntVar(value=self.ctrl.imageshift1.x)
        self.var_imageshift1y = IntVar(value=self.ctrl.imageshift1.y)
        self.var_imageshift2x = IntVar(value=self.ctrl.imageshift2.x)
        self.var_imageshift2y = IntVar(value=self.ctrl.imageshift2.y)

        self.var_beamshift_choose = IntVar(value=0)
        self.var_beamtilt_choose = IntVar(value=0)
        self.var_imageshift1_choose = IntVar(value=0)
        self.var_imageshift2_choose = IntVar(value=0)
        self.var_diffshift_choose = IntVar(value=0)
        self.var_imgbeamtilt_choose = IntVar(value=0)

        self.var_diff_defocus = IntVar(value=1500)
        self.var_toggle_diff_defocus = BooleanVar(value=False)

        self.var_stage_wait = BooleanVar(value=True)

    def GUI_DiffFocus(self):
        self.e_diff_defocus.config(state=NORMAL)
        self.c_toggle_defocus.config(state=NORMAL)
        self.b_reset_defocus.config(state=NORMAL)
        self.e_difffocus.config(state=NORMAL)
        self.b_difffocus.config(state=NORMAL)
        self.b_difffocus_get.config(state=NORMAL)
        self.difffocus_slider.config(state=NORMAL)
        self.e_objfocus.config(state=DISABLED)
        self.b_objfocus.config(state=DISABLED)
        self.b_objfocus_get.config(state=DISABLED)
        self.objfocus_slider.config(state=DISABLED)

    def GUI_ObjFocus(self):
        self.e_diff_defocus.config(state=DISABLED)
        self.c_toggle_defocus.config(state=DISABLED)
        self.b_reset_defocus.config(state=DISABLED)
        self.e_difffocus.config(state=DISABLED)
        self.b_difffocus.config(state=DISABLED)
        self.b_difffocus_get.config(state=DISABLED)
        self.difffocus_slider.config(state=DISABLED)
        self.e_objfocus.config(state=NORMAL)
        self.b_objfocus.config(state=NORMAL)
        self.b_objfocus_get.config(state=NORMAL)
        self.objfocus_slider.config(state=NORMAL)

    def set_gui_diffobj(self):
        if self.ctrl.tem.interface == 'fei':
            if self.ctrl.mode.state in ('D','LAD'):
                self.GUI_DiffFocus()
            else:
                self.GUI_ObjFocus()
        else:
            if self.ctrl.mode.state == 'diff':
                self.GUI_DiffFocus()
            else:
                self.GUI_ObjFocus()

    def set_trigger(self, trigger=None, q=None):
        self.triggerEvent = trigger
        self.q = q

    def set_mode(self, event=None):
        if self.ctrl.cam.interface == 'DM':
            if self.var_mode.get() in ('D', 'LAD'):
                self.ctrl.tem.setProjectionMode('diffraction')
                self.var_mode.set(self.ctrl.mode.state)
                self.q.put(('ctrl', {'task': 'in_diff_state'}))
                self.triggerEvent.set()
            else:
                self.ctrl.tem.setProjectionMode('imaging')
                self.var_mode.set(self.ctrl.mode.state)
                self.q.put(('ctrl', {'task': 'in_img_state'}))
                self.triggerEvent.set()
            self.set_gui_diffobj()
        else:
            self.ctrl.mode.set(self.var_mode.get())
            self.set_gui_diffobj()

    def set_brightness(self, event=None):
        self.q.put(('ctrl', {'task': 'brightness.set',
                             'value': self.var_brightness.get()}))
        self.triggerEvent.set()

    def get_brightness(self, event=None):
        self.var_brightness.set(self.ctrl.brightness.get())

    def set_difffocus(self, event=None):
        self.q.put(('ctrl', {'task': 'difffocus.set',
                             'value': self.var_difffocus.get()}))
        self.triggerEvent.set()

    def get_difffocus(self, event=None):
        self.var_difffocus.set(self.ctrl.difffocus.get())

    def set_objfocus(self, event=None):
        self.q.put(('ctrl', {'task': 'objfocus.set',
                             'value': self.var_objfocus.get()}))
        self.triggerEvent.set()

    def get_objfocus(self, event=None):
        self.var_objfocus.set(self.ctrl.objfocus.get())

    def choose_beamshiftxy(self):
        if self.var_beamshift_choose.get() == 0:
            self.e_beamshift.configure(textvariable=self.var_beamshiftx)
            self.b_beamshift_get.configure(command=self.get_beamshiftx)
            self.beamshift_slider.configure(variable=self.var_beamshiftx)
        else:
            self.e_beamshift.configure(textvariable=self.var_beamshifty)
            self.b_beamshift_get.configure(command=self.get_beamshifty)
            self.beamshift_slider.configure(variable=self.var_beamshifty)

    def choose_beamtiltxy(self):
        if self.var_beamtilt_choose.get() == 0:
            self.e_beamtilt.configure(textvariable=self.var_beamtiltx)
            self.b_beamtilt_get.configure(command=self.get_beamtiltx)
            self.beamtilt_slider.configure(variable=self.var_beamtiltx)
        else:
            self.e_beamtilt.configure(textvariable=self.var_beamtilty)
            self.b_beamtilt_get.configure(command=self.get_beamtilty)
            self.beamtilt_slider.configure(variable=self.var_beamtilty)

    def choose_imageshift1xy(self):
        if self.var_imageshift1_choose.get() == 0:
            self.e_imageshift1.configure(textvariable=self.var_imageshift1x)
            self.b_imageshift1_get.configure(command=self.get_imageshift1x)
            self.imageshift1_slider.configure(variable=self.var_imageshift1x)
        else:
            self.e_imageshift1.configure(textvariable=self.var_imageshift1y)
            self.b_imageshift1_get.configure(command=self.get_imageshift1y)
            self.imageshift1_slider.configure(variable=self.var_imageshift1y)

    def choose_imageshift2xy(self):
        if self.var_imageshift2_choose.get() == 0:
            self.e_imageshift2.configure(textvariable=self.var_imageshift2x)
            self.b_imageshift2_get.configure(command=self.get_imageshift2x)
            self.imageshift2_slider.configure(variable=self.var_imageshift2x)
        else:
            self.e_imageshift2.configure(textvariable=self.var_imageshift2y)
            self.b_imageshift2_get.configure(command=self.get_imageshift2y)
            self.imageshift2_slider.configure(variable=self.var_imageshift2y)

    def choose_diffshiftxy(self):
        if self.var_diffshift_choose.get() == 0:
            self.e_diffshift.configure(textvariable=self.var_diffshiftx)
            self.b_diffshift_get.configure(command=self.get_diffshiftx)
            self.diffshift_slider.configure(variable=self.var_diffshiftx)
        else:
            self.e_diffshift.configure(textvariable=self.var_diffshifty)
            self.b_diffshift_get.configure(command=self.get_diffshifty)
            self.diffshift_slider.configure(variable=self.var_diffshifty)

    def choose_imgbeamtiltxy(self):
        if self.var_imgbeamtilt_choose.get() == 0:
            self.e_imgbeamtilt.configure(textvariable=self.var_imgbeamtiltx)
            self.b_imgbeamtilt_get.configure(command=self.get_imgbeamtiltx)
            self.imgbeamtilt_slider.configure(variable=self.var_imgbeamtiltx)
        else:
            self.e_imgbeamtilt.configure(textvariable=self.var_imgbeamtilty)
            self.b_imgbeamtilt_get.configure(command=self.get_imgbeamtilty)
            self.imgbeamtilt_slider.configure(variable=self.var_imgbeamtilty)

    def get_beamshiftx(self, event=None):
        self.var_beamshiftx.set(self.ctrl.beamshift.x)

    def get_beamshifty(self, event=None):
        self.var_beamshifty.set(self.ctrl.beamshift.y)

    def get_beamtiltx(self, event=None):
        self.var_beamtiltx.set(self.ctrl.beamtilt.x)

    def get_beamtilty(self, event=None):
        self.var_beamtilty.set(self.ctrl.beamtilt.y)

    def get_imageshift1x(self, event=None):
        self.var_imageshift1x.set(self.ctrl.imageshift1.x)

    def get_imageshift1y(self, event=None):
        self.var_imageshift1y.set(self.ctrl.imageshift1.y)

    def get_imageshift2x(self, event=None):
        self.var_imageshift2x.set(self.ctrl.imageshift2.x)

    def get_imageshift2y(self, event=None):
        self.var_imageshift2y.set(self.ctrl.imageshift2.y)

    def get_diffshiftx(self, event=None):
        self.var_diffshiftx.set(self.ctrl.diffshift.x)

    def get_diffshifty(self, event=None):
        self.var_diffshifty.set(self.ctrl.diffshift.y)

    def get_imgbeamtiltx(self, event=None):
        self.var_imgbeamtiltx.set(self.ctrl.imgbeamtilt.x)

    def get_imgbeamtilty(self, event=None):
        self.var_imgbeamtilty.set(self.ctrl.imgbeamtilt.y)

    def set_beamshift(self, event=None):
        self.q.put(('ctrl', {'task': 'beamshift.set',
                             'x': self.var_beamshiftx.get(),
                             'y': self.var_beamshifty.get()}))
        self.triggerEvent.set()

    def set_beamtilt(self, event=None):
        self.q.put(('ctrl', {'task': 'beamtilt.set',
                             'x': self.var_beamtiltx.get(),
                             'y': self.var_beamtilty.get()}))
        self.triggerEvent.set()

    def set_imageshift1(self, event=None):
        self.q.put(('ctrl', {'task': 'imageshift1.set',
                             'x': self.var_imageshift1x.get(),
                             'y': self.var_imageshift1y.get()}))
        self.triggerEvent.set()

    def set_imageshift2(self, event=None):
        self.q.put(('ctrl', {'task': 'imageshift2.set',
                             'x': self.var_imageshift2x.get(),
                             'y': self.var_imageshift2y.get()}))
        self.triggerEvent.set()

    def set_diffshift(self, event=None):
        self.q.put(('ctrl', {'task': 'diffshift.set',
                             'x': self.var_diffshiftx.get(),
                             'y': self.var_diffshifty.get()}))
        self.triggerEvent.set()

    def set_imgbeamtilt(self, event=None):
        self.q.put(('ctrl', {'task': 'imgbeamtilt.set',
                             'x': self.var_imgbeamtiltx.get(),
                             'y': self.var_imgbeamtilty.get()}))
        self.triggerEvent.set()

    def get_alpha_angle(self):
        self.var_alpha_angle.set(self.ctrl.stage.a)

    def set_alpha_angle(self):
        self.q.put(('ctrl', {'task': 'stage.set',
                             'a': self.var_alpha_angle.get(),
                             'wait': self.var_stage_wait.get()}))
        self.triggerEvent.set()

    def set_goniotool_tx(self, event=None, value=None):
        if not value:
            value = self.var_goniotool_tx.get()
        self.ctrl.stage.set_rotation_speed(value)

    def set_goniotool_tx_default(self, event=None):
        value = 12
        self.set_goniotool_tx(value=value)

    def set_stage(self):
        self.q.put(('ctrl', {'task': 'stage.set',
                             'x': self.var_stage_x.get(),
                             'y': self.var_stage_y.get(),
                             'z': self.var_stage_z.get(),
                             'wait': self.var_stage_wait.get()}))
        self.triggerEvent.set()

    def get_stage(self, event=None):
        x, y, z, _, _ = self.ctrl.stage.get()
        self.var_stage_x.set(round(x,2))
        self.var_stage_y.set(round(y,2))
        self.var_stage_z.set(round(z,2))

    def start_alpha_wobbler(self):
        self.wobble_stop_event = threading.Event()

        self.b_stop_wobble.config(state=NORMAL)
        self.b_start_wobble.config(state=DISABLED)

        self.q.put(('ctrl', {'task': 'stage.alpha_wobbler',
                             'delta': self.var_alpha_wobbler.get(),
                             'event': self.wobble_stop_event}))
        self.triggerEvent.set()

    def stop_alpha_wobbler(self):
        self.wobble_stop_event.set()

        self.b_stop_wobble.config(state=DISABLED)
        self.b_start_wobble.config(state=NORMAL)

    def stage_stop(self):
        self.q.put(('ctrl', {'task': 'stage.stop'}))
        self.triggerEvent.set()

    def find_eucentric_height(self):
        self.q.put(('ctrl', {'task': 'find_eucentric_height'}))
        self.triggerEvent.set()

    def toggle_diff_defocus(self):
        toggle = self.var_toggle_diff_defocus.get()

        if toggle:
            offset = self.var_diff_defocus.get()
            self.ctrl.difffocus.defocus(offset=offset)
            self.b_reset_defocus.config(state=NORMAL)
        else:
            self.ctrl.difffocus.refocus()
            self.var_toggle_diff_defocus.set(False)

        self.get_difffocus()

    def reset_diff_defocus(self):
        self.ctrl.difffocus.refocus()
        self.var_toggle_diff_defocus.set(False)
        self.get_difffocus()


module = BaseModule(name='ctrl', display_name='control', tk_frame=ExperimentalCtrl, location='bottom')
commands = {}

def run(ctrl, trigger, q):
    from .modules import JOBS

    while True:
        trigger.wait()
        trigger.clear()

        job, kwargs = q.get()
        try:
            print(job)
            func = JOBS[job]
        except KeyError:
            print(f'Unknown job: {job}')
            print(f'Kwargs:\n{kwargs}')
            continue
        func(ctrl, **kwargs)


if __name__ == '__main__':
    import threading
    import queue
    
    root = Tk()
    trigger = threading.Event()
    q = queue.LifoQueue(maxsize=1)
    ctrl = ExperimentalCtrl(root)
    ctrl.pack(side='top', fill='both', expand=True)
    ctrl.set_trigger(trigger=trigger, q=q)

    p = threading.Thread(target=run, args=(ctrl,trigger,q,))
    p.start()

    root.mainloop()
    ctrl.ctrl.close()
