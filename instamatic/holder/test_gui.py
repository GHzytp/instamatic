import threading
import time
from datetime import datetime
from tkinter import *
from tkinter.ttk import *
from numpy import pi

from .holder import get_instance
from instamatic.utils.widgets import Spinbox, Hoverbox

class HolderGUI(LabelFrame):
    """GUI panel for holder function testing."""

    def __init__(self, parent):
        LabelFrame.__init__(self, parent, text='Holder testing graphical interface')
        self.parent = parent

        self.init_vars()

        frame = Frame(self)

        self.ConnectButton = Button(frame, text='Connect Holder', command=self.connect, state=NORMAL)
        self.ConnectButton.grid(row=0, column=0, sticky='EW', padx=5)
        Hoverbox(self.ConnectButton, 'Connect to a holder, enable all the operations. Close the GUI to disconnect.')

        Label(frame, text='Holder ID:').grid(row=0, column=1, sticky='W')
        self.lb_holder_id = Label(frame, width=10, textvariable=self.var_holder_id)
        self.lb_holder_id.grid(row=0, column=2, sticky='EW', padx=5)

        Label(frame, text='Angle:').grid(row=0, column=3, sticky='W')
        self.lb_angle = Label(frame, width=5, text='0.0')
        self.lb_angle.grid(row=0, column=4, sticky='EW', padx=5)
        self.GetAngleButton = Button(frame, text='Get Angle', command=self.get_angle, state=DISABLED)
        self.GetAngleButton.grid(row=0, column=5, sticky='EW')
        Hoverbox(self.GetAngleButton, 'Read current angle, unit is degree.')
        Label(frame, text='Distance:').grid(row=0, column=6, sticky='W', padx=5)
        self.lb_distance = Label(frame, width=5, text='0.0')
        self.lb_distance.grid(row=0, column=7, sticky='EW')
        self.GetDistButton = Button(frame, text='Get Distance', command=self.get_distance, state=DISABLED)
        self.GetDistButton.grid(row=0, column=8, sticky='EW', padx=5)
        Hoverbox(self.GetDistButton, 'Read current distance, unit is mm.')

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)
        
        frame = Frame(self)

        Label(frame, text='Axis:').grid(row=1, column=0, sticky='W')
        self.e_axis = Spinbox(frame, width=8, textvariable=self.var_axis, from_=0, to=3, increment=1, state=DISABLED)
        self.e_axis.grid(row=1, column=1, sticky='EW', padx=5, pady=5)
        Hoverbox(self.e_axis, 'The axis to move: 0->x, 1->y, 2->z, 3->alpha')
        Label(frame, text='Pulse:').grid(row=1, column=2, sticky='W')
        self.e_pulse = Spinbox(frame, width=8, textvariable=self.var_pulse, from_=0, to=255, increment=1, state=DISABLED)
        self.e_pulse.grid(row=1, column=3, sticky='EW', padx=5, pady=5)
        Hoverbox(self.e_pulse, 'Number of pulses or steps. 255 is an exception. 255 will make the holder rotate forever.')
        Label(frame, text='Speed:').grid(row=1, column=4, sticky='W')
        self.e_speed = Spinbox(frame, width=8, textvariable=self.var_speed, from_=0, increment=1, state=DISABLED)
        self.e_speed.grid(row=1, column=5, sticky='EW', padx=5, pady=5)
        Hoverbox(self.e_speed, 'Pulse length, unit is Hz')
        Label(frame, text='Amp:').grid(row=1, column=6, sticky='W')
        self.e_amp = Spinbox(frame, width=8, textvariable=self.var_amp, from_=-25122, to=25122, increment=1, state=DISABLED)
        self.e_amp.grid(row=1, column=7, sticky='EW', padx=5, pady=5)
        Hoverbox(self.e_amp, 'Voltage applied to drive the holder, unit is (150/32767V). '
                             'The largeest volage that the driver box can output is 115V. '
                             'When the value is negative, the holder will move to the opposite direction.')
        Label(frame, text='Angle:').grid(row=1, column=8, sticky='W')
        self.e_angle = Spinbox(frame, width=8, textvariable=self.var_angle, from_=-180.0, to=180.0, increment=0.01, state=DISABLED)
        self.e_angle.grid(row=1, column=9, sticky='EW', padx=5, pady=5)
        Hoverbox(self.e_angle, 'Target angle, unit degree')

        self.CoarseMoveButton = Button(frame, text='Coarse Move', command=self.coarse_move, state=DISABLED)
        self.CoarseMoveButton.grid(row=2, column=0, columnspan=2, sticky='EW')
        Hoverbox(self.CoarseMoveButton, 'Holder coarse move. Need to fill in axis, pulses, speed and amp.')
        self.StopCoarseMoveButton = Button(frame, text='Stop', command=self.stop_coarse_move, state=DISABLED)
        self.StopCoarseMoveButton.grid(row=2, column=2, columnspan=2, sticky='EW', padx=5)
        self.FineMoveButton = Button(frame, text='Fine Move', command=self.fine_move, state=DISABLED)
        self.FineMoveButton.grid(row=2, column=4, columnspan=2, sticky='EW')
        Hoverbox(self.FineMoveButton, 'Holder fine move. Need to fill in axis and amp')
        self.RotateToButton = Button(frame, text='Rotate To', command=self.rotate_to, state=DISABLED)
        self.RotateToButton.grid(row=2, column=6, columnspan=2, sticky='EW', padx=5)
        Hoverbox(self.RotateToButton, 'Holder rotation move. Need to fill in angle and amp.')

        self.RotateRecordButton = Button(frame, text='Rotate&Record', command=self.rotate_record, state=DISABLED)
        self.RotateRecordButton.grid(row=3, column=0, columnspan=2, sticky='EW')
        Hoverbox(self.RotateRecordButton, 'Holder rotate and record angles. Need to fill in angle and amp.')
        self.StopRecordButton = Button(frame, text='Stop Record', command=self.stop_record, state=DISABLED)
        self.StopRecordButton.grid(row=3, column=2, columnspan=2, sticky='EW', padx=5)
        Hoverbox(self.StopRecordButton, 'Stop recording angles')

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

        frame = Frame(self)

        Label(frame, text='Compensation Coefficients:').grid(row=1, column=0, columnspan=3, sticky='W')
        vcmd = (self.parent.register(self.validate),
                '%d', '%i', '%P', '%s', '%S', '%v', '%V', '%W')
        self.coff_0 = Entry(frame, textvariable=self.var_coff_0, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_0.focus()
        self.coff_0.grid(row=1, column=3, sticky='EW', padx=5)
        Hoverbox(self.coff_0, 'Compensation Coefficient 0')
        self.coff_1 = Entry(frame, textvariable=self.var_coff_1, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_1.focus()
        self.coff_1.grid(row=1, column=4, sticky='EW')
        Hoverbox(self.coff_1, 'Compensation Coefficient 1')
        self.coff_2 = Entry(frame, textvariable=self.var_coff_2, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_2.focus()
        self.coff_2.grid(row=1, column=5, sticky='EW', padx=5)
        Hoverbox(self.coff_2, 'Compensation Coefficient 2')
        self.coff_3 = Entry(frame, textvariable=self.var_coff_3, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_3.focus()
        self.coff_3.grid(row=1, column=6, sticky='EW')
        Hoverbox(self.coff_3, 'Compensation Coefficient 3')
        self.coff_4 = Entry(frame, textvariable=self.var_coff_4, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_4.focus()
        self.coff_4.grid(row=1, column=7, sticky='EW', padx=5)
        Hoverbox(self.coff_4, 'Compensation Coefficient 4')
        self.coff_5 = Entry(frame, textvariable=self.var_coff_5, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_5.focus()
        self.coff_5.grid(row=1, column=8, sticky='EW')
        Hoverbox(self.coff_5, 'Compensation Coefficient 5')

        self.coff_6 = Entry(frame, textvariable=self.var_coff_6, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_6.focus()
        self.coff_6.grid(row=2, column=0, sticky='EW')
        Hoverbox(self.coff_6, 'Compensation Coefficient 6')
        self.coff_7 = Entry(frame, textvariable=self.var_coff_7, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_7.focus()
        self.coff_7.grid(row=2, column=1, sticky='EW', padx=5)
        Hoverbox(self.coff_7, 'Compensation Coefficient 7')
        self.coff_8 = Entry(frame, textvariable=self.var_coff_8, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_8.focus()
        self.coff_8.grid(row=2, column=2, sticky='EW')
        Hoverbox(self.coff_8, 'Compensation Coefficient 8')
        self.coff_9 = Entry(frame, textvariable=self.var_coff_9, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_9.focus()
        self.coff_9.grid(row=2, column=3, sticky='EW', padx=5)
        Hoverbox(self.coff_9, 'Compensation Coefficient 9')
        self.coff_10 = Entry(frame, textvariable=self.var_coff_10, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_10.focus()
        self.coff_10.grid(row=2, column=4, sticky='EW')
        Hoverbox(self.coff_10, 'Compensation Coefficient 10')
        self.coff_11 = Entry(frame, textvariable=self.var_coff_11, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_11.focus()
        self.coff_11.grid(row=2, column=5, sticky='EW', padx=5)
        Hoverbox(self.coff_11, 'Compensation Coefficient 11')
        self.coff_12 = Entry(frame, textvariable=self.var_coff_12, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_12.focus()
        self.coff_12.grid(row=2, column=6, sticky='EW')
        Hoverbox(self.coff_12, 'Compensation Coefficient 12')
        self.coff_13 = Entry(frame, textvariable=self.var_coff_13, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_13.focus()
        self.coff_13.grid(row=2, column=7, sticky='EW', padx=5)
        Hoverbox(self.coff_13, 'Compensation Coefficient 13')
        self.coff_14 = Entry(frame, textvariable=self.var_coff_14, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_14.focus()
        self.coff_14.grid(row=2, column=8, sticky='EW')
        Hoverbox(self.coff_14, 'Compensation Coefficient 14')

        self.coff_15 = Entry(frame, textvariable=self.var_coff_15, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_15.focus()
        self.coff_15.grid(row=3, column=0, sticky='EW')
        Hoverbox(self.coff_15, 'Compensation Coefficient 15')
        self.coff_16 = Entry(frame, textvariable=self.var_coff_16, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_16.focus()
        self.coff_16.grid(row=3, column=1, sticky='EW', padx=5)
        Hoverbox(self.coff_16, 'Compensation Coefficient 16')
        self.coff_17 = Entry(frame, textvariable=self.var_coff_17, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_17.focus()
        self.coff_17.grid(row=3, column=2, sticky='EW')
        Hoverbox(self.coff_17, 'Compensation Coefficient 17')
        self.coff_18 = Entry(frame, textvariable=self.var_coff_18, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_18.focus()
        self.coff_18.grid(row=3, column=3, sticky='EW', padx=5)
        Hoverbox(self.coff_18, 'Compensation Coefficient 18')
        self.coff_19 = Entry(frame, textvariable=self.var_coff_19, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_19.focus()
        self.coff_19.grid(row=3, column=4, sticky='EW')
        Hoverbox(self.coff_19, 'Compensation Coefficient 19')
        self.coff_20 = Entry(frame, textvariable=self.var_coff_20, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_20.focus()
        self.coff_20.grid(row=3, column=5, sticky='EW', padx=5)
        Hoverbox(self.coff_20, 'Compensation Coefficient 20')
        self.coff_21 = Entry(frame, textvariable=self.var_coff_21, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_21.focus()
        self.coff_21.grid(row=3, column=6, sticky='EW')
        Hoverbox(self.coff_21, 'Compensation Coefficient 21')
        self.coff_22 = Entry(frame, textvariable=self.var_coff_22, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_22.focus()
        self.coff_22.grid(row=3, column=7, sticky='EW', padx=5)
        Hoverbox(self.coff_22, 'Compensation Coefficient 22')
        self.coff_23 = Entry(frame, textvariable=self.var_coff_23, width=8, validate='key', validatecommand=vcmd, state=DISABLED)
        self.coff_23.focus()
        self.coff_23.grid(row=3, column=8, sticky='EW')
        Hoverbox(self.coff_23, 'Compensation Coefficient 23')

        self.GetCompCoeffButton =  Button(frame, text='Get Compensation', command=self.get_comp_coeff, state=DISABLED)
        self.GetCompCoeffButton.grid(row=4, column=1, columnspan=3, sticky='EW', padx=5)
        self.SetCompCoeffButton =  Button(frame, text='Set Compensation', command=self.set_comp_coeff, state=DISABLED)
        self.SetCompCoeffButton.grid(row=4, column=5, columnspan=3, sticky='EW', padx=5)

        frame.pack(side='top', fill='x', expand=False, padx=5, pady=5)

    def init_vars(self):
        self.ctrl = None
        self.var_holder_id = StringVar(value=0)
        self.var_angle = DoubleVar(value=0.0)
        self.var_axis = IntVar(value=0)
        self.var_pulse = IntVar(value=0)
        self.var_speed = IntVar(value=0)
        self.var_amp = IntVar(value=0)
        self.var_coff_0 = DoubleVar(value=0.0)
        self.var_coff_1 = DoubleVar(value=0.0)
        self.var_coff_2 = DoubleVar(value=0.0)
        self.var_coff_3 = DoubleVar(value=0.0)
        self.var_coff_4 = DoubleVar(value=0.0)
        self.var_coff_5 = DoubleVar(value=0.0)
        self.var_coff_6 = DoubleVar(value=0.0)
        self.var_coff_7 = DoubleVar(value=0.0)
        self.var_coff_8 = DoubleVar(value=0.0)
        self.var_coff_9 = DoubleVar(value=0.0)
        self.var_coff_10 = DoubleVar(value=0.0)
        self.var_coff_11 = DoubleVar(value=0.0)
        self.var_coff_12 = DoubleVar(value=0.0)
        self.var_coff_13 = DoubleVar(value=0.0)
        self.var_coff_14 = DoubleVar(value=0.0)
        self.var_coff_15 = DoubleVar(value=0.0)
        self.var_coff_16 = DoubleVar(value=0.0)
        self.var_coff_17 = DoubleVar(value=0.0)
        self.var_coff_18 = DoubleVar(value=0.0)
        self.var_coff_19 = DoubleVar(value=0.0)
        self.var_coff_20 = DoubleVar(value=0.0)
        self.var_coff_21 = DoubleVar(value=0.0)
        self.var_coff_22 = DoubleVar(value=0.0)
        self.var_coff_23 = DoubleVar(value=0.0)
        self.stopEvent = threading.Event()

    def connect(self):
        t = threading.Thread(target=self.wait_holder, args=(), daemon=True)
        t.start()
        self.ctrl = get_instance()

    def wait_holder(self):
        self.ConnectButton.config(state=DISABLED)
        for i in range(5):
            time.sleep(0.5)
            if self.ctrl.getHolderId() != 0:
                time.sleep(0.5)
                self.enable_operations()
                self.var_holder_id.set(hex(self.ctrl.getHolderId()))
                break
            print("Wait for XNano holder...")
        if i == 4:
            print("Please connect to a XNano holder.")
            self.ConnectButton.config(state=NORMAL)

    def validate(self, action, index, value_if_allowed, prior_value, text, validation_type, trigger_type, widget_name):
        if value_if_allowed:
            try:
                value = float(value_if_allowed)
                if value >= -1 and value <= 1:
                    return True
                else:
                    return False
            except ValueError:
                return False
        else:
            return False

    def get_angle(self):
        self.lb_angle.config(text=self.ctrl.getAngle()*180/pi) 

    def get_distance(self):
        self.lb_distance.config(text=self.ctrl.getDistance())

    def coarse_move(self):
        self.ctrl.holderMove(self.var_axis.get(), self.var_pulse.get(), self.var_speed.get(), self.var_amp.get())

    def stop_coarse_move(self):
        self.ctrl.holderStop()

    def fine_move(self):
        self.ctrl.holderFine(self.var_axis.get(), self.var_amp.get())

    def rotate_to(self):
        self.ctrl.holderRotateTo(self.var_angle.get()*pi/180, self.var_amp.get())

    def rotate_record(self):
        self.ctrl.holderRotateTo(self.var_angle.get()*pi/180, self.var_amp.get())
        t_record_angle = threading.Thread(target=self.record_angle, args=(), daemon=True)
        t_record_angle.start()

    def record_angle(self):
        self.stopEvent.clear()
        current_angle = self.ctrl.getAngle()*180/pi
        target_angle = self.var_angle.get()*180/pi
        angle_list = []
        while round(current_angle, 2) != round(target_angle, 2) and not self.stopEvent.is_set():
            current_angle = self.ctrl.getAngle()*180/pi
            angle_list.append(current_angle)
            time.sleep(0.01)
        print(angle_list)
        self.stopEvent.clear()

    def stop_record(self):
        self.stopEvent.set()

    def get_comp_coeff(self):
        table = self.ctrl.getCompCoef()
        self.var_coff_0.set(table[0])
        self.var_coff_1.set(table[1])
        self.var_coff_2.set(table[2])
        self.var_coff_3.set(table[3])
        self.var_coff_4.set(table[4])
        self.var_coff_5.set(table[5])
        self.var_coff_6.set(table[6])
        self.var_coff_7.set(table[7])
        self.var_coff_8.set(table[8])
        self.var_coff_9.set(table[9])
        self.var_coff_10.set(table[10])
        self.var_coff_11.set(table[11])
        self.var_coff_12.set(table[12])
        self.var_coff_13.set(table[13])
        self.var_coff_14.set(table[14])
        self.var_coff_15.set(table[15])
        self.var_coff_16.set(table[16])
        self.var_coff_17.set(table[17])
        self.var_coff_18.set(table[18])
        self.var_coff_19.set(table[19])
        self.var_coff_20.set(table[20])
        self.var_coff_21.set(table[21])
        self.var_coff_22.set(table[22])
        self.var_coff_23.set(table[23])

    def set_comp_coeff(self):
        table = self.ctrl.getCompCoef()
        table[0] = self.var_coff_0.get()
        table[1] = self.var_coff_1.get()
        table[2] = self.var_coff_2.get()
        table[3] = self.var_coff_3.get()
        table[4] = self.var_coff_4.get()
        table[5] = self.var_coff_5.get()
        table[6] = self.var_coff_6.get()
        table[7] = self.var_coff_7.get()
        table[8] = self.var_coff_8.get()
        table[9] = self.var_coff_9.get()
        table[10] = self.var_coff_10.get()
        table[11] = self.var_coff_11.get()
        table[12] = self.var_coff_12.get()
        table[13] = self.var_coff_13.get()
        table[14] = self.var_coff_14.get()
        table[15] = self.var_coff_15.get()
        table[16] = self.var_coff_16.get()
        table[17] = self.var_coff_17.get()
        table[18] = self.var_coff_18.get()
        table[19] = self.var_coff_19.get()
        table[20] = self.var_coff_20.get()
        table[21] = self.var_coff_21.get()
        table[22] = self.var_coff_22.get()
        table[23] = self.var_coff_23.get()
        self.ctrl.setCompCoef(table)

    def enable_operations(self):
        self.GetAngleButton.config(state=NORMAL)
        self.GetDistButton.config(state=NORMAL)
        self.e_amp.config(state=NORMAL)
        self.e_speed.config(state=NORMAL)
        self.e_pulse.config(state=NORMAL)
        self.e_axis.config(state=NORMAL)
        self.e_angle.config(state=NORMAL)
        self.CoarseMoveButton.config(state=NORMAL)
        self.StopCoarseMoveButton.config(state=NORMAL)
        self.FineMoveButton.config(state=NORMAL)
        self.RotateToButton.config(state=NORMAL)
        self.RotateRecordButton.config(state=NORMAL)
        self.StopRecordButton.config(state=NORMAL)
        self.coff_0.config(state=NORMAL)
        self.coff_1.config(state=NORMAL)
        self.coff_2.config(state=NORMAL)
        self.coff_3.config(state=NORMAL)
        self.coff_4.config(state=NORMAL)
        self.coff_5.config(state=NORMAL)
        self.coff_6.config(state=NORMAL)
        self.coff_7.config(state=NORMAL)
        self.coff_8.config(state=NORMAL)
        self.coff_9.config(state=NORMAL)
        self.coff_10.config(state=NORMAL)
        self.coff_11.config(state=NORMAL)
        self.coff_12.config(state=NORMAL)
        self.coff_13.config(state=NORMAL)
        self.coff_14.config(state=NORMAL)
        self.coff_15.config(state=NORMAL)
        self.coff_16.config(state=NORMAL)
        self.coff_17.config(state=NORMAL)
        self.coff_18.config(state=NORMAL)
        self.coff_19.config(state=NORMAL)
        self.coff_20.config(state=NORMAL)
        self.coff_21.config(state=NORMAL)
        self.coff_22.config(state=NORMAL)
        self.coff_23.config(state=NORMAL)
        self.SetCompCoeffButton.config(state=NORMAL)
        self.GetCompCoeffButton.config(state=NORMAL)


if __name__ == '__main__':
    root = Tk()
    HolderGUI(root).pack(side='top', fill='both', expand=True)
    root.mainloop()
