# TEM Image Analysis (TIA) software control API from Pascal Hogan (pascal.hogan@gmail.com)

import numpy as np
import comtypes.client


class TIASoftware:
    def __init__(self, name="TIA"):
        self.name = name
        self.tia = None
        self.cte = None

        self.workspace = {}

    def connect(self):
        try:
            comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
        except WindowsError:
            comtypes.CoInitialize()

        print("Initializing connection to TIA...")
        self.tia = comtypes.client.CreateObject("ESVision.Application", comtypes.CLSCTX_ALL)
        self.cte = comtypes.client.Constants(self.tia)
        self.acq = self.tia.AcquisitionManager()
        self.beam_control = self.tia.BeamControl()
        self.ccd = self.tia.CCDServer()
        self.scan = self.tia.ScanningServer()

    def addVariable(self, varname, tia_object, tia_object_type):
        self.workspace[varname] = {}
        self.workspace[varname]["object"] = tia_object
        self.workspace[varname]["type"] = tia_object_type

    def showWorkspace(self):
        return {varname: var["type"] for varname, var in self.workspace.items()}

    def getVariable(self, varname):
        variable = self.workspace[varname]
        if variable["type"] == "Calibration2D":
            return self._getCalibration2D(variable["object"])
        elif variable["type"] == "Data2D":
            return self._getData2D(variable["object"])
        elif variable["type"] == "Range2D":
            return self._getRange2D(variable["object"])
        elif variable["type"] == "Range1D":
            return self._getRange1D(variable["object"])
        elif variable["type"] == "Position2D":
            return self._getPosition2D(variable["object"])
        elif variable["type"] == "PositionCollection":
            return self._getPositionCollection(variable["object"])
        elif variable["type"] == "SpatialUnit":
            return self._getSpatialUnit(variable["object"])

    def getFunc(self, varname: str, funcname: str, args: list = [], kwargs: dict = {}):
        f = getattr(self.workspace[varname]["object"], funcname)
        ret = f(*args, **kwargs)
        return ret

    def setFunc(self, varname: str, kwargs: dict):
        for key, val in kwargs.items():
            setattr(self.workspace[varname]["object"], key, val)

    ### Interface functions ####

    def CloseDisplayWindow(self, window_name):
        self.tia.CloseDisplayWindow(window_name)

    def DisplayWindowNames(self):
        return [wn for wn in self.tia.DisplayWindowNames()]

    def _FindDisplayWindow(self, window_name):
        return self.tia.FindDisplayWindow(window_name)

    def ActivateDisplayWindow(self, window_name):
        self.tia.ActivateDisplayWindow(window_name)

    def ActiveDisplayWindowName(self):
        return self.tia.ActiveDisplayWindow().Name

    def AddDisplayWindow(self, window_name=None):
        window = self.tia.AddDisplayWindow()
        if window_name:
            window.Name = window_name
            return window_name
        else:
            return window.Name

    def DisplayNames(self, window_name):
        window = self._FindDisplayWindow(window_name)
        return [dn for dn in window.DisplayNames]

    def _FindDisplay(self, window_name, display_name):
        window = self._FindDisplayWindow(window_name)
        return window.FindDisplay(display_name)

    def DeleteDisplay(self, window_name, display_name):
        window = self._FindDisplayWindow(window_name)
        display = self._FindDisplay(window_name, display_name)
        window.DeleteDisplay(display)

    def AddDisplay(
        self,
        window_name,
        display_name,
        display_type,
        display_subtype,
        splitdirection,
        newsplitportion,
    ):
        window = self._FindDisplayWindow(window_name)
        window.AddDisplay(
            display_name, display_type, display_subtype, splitdirection, newsplitportion
        )

    def ObjectNames(self, window_name, display_name):
        window = self._FindDisplayWindow(window_name)
        display = window.FindDisplay(display_name)
        object_handles = {
            "{}".format(on): display.FindObject(on) for on in display.ObjectNames
        }
        img_list = []
        position_marker_list = []
        for on, handle in object_handles.items():
            if handle.Type == 0:
                img_list.append(on)
            elif handle.Type == 1:  # Should be 4 according to help manual...
                position_marker_list.append(on)
        return {"Images": img_list, "Position Markers": position_marker_list}

    def _FindObject(self, window_name, display_name, object_name):
        window = self._FindDisplayWindow(window_name)
        display = window.FindDisplay(display_name)
        return display.FindObject(object_name)

    def DeleteObject(self, window_name, display_name, object_name):
        window = self._FindDisplayWindow(window_name)
        display = window.FindDisplay(display_name)
        display.DeleteObject(display.FindObject(object_name))

    def Calibration2D(
        self, varname, offsetX, offsetY, deltaX, deltaY, calIndexX=0, calIndexY=0
    ):
        calibration = self.tia.Calibration2D(
            offsetX, offsetY, deltaX, deltaY, calIndexX, calIndexY
        )
        self.addVariable(varname, calibration, "Calibration2D")

    def _getCalibration2D(self, calibration_object):
        return {
            "OffsetX": calibration_object.OffsetX,
            "OffsetY": calibration_object.OffsetY,
            "DeltaX": calibration_object.DeltaX,
            "DeltaY": calibration_object.DeltaY,
            "CalIndexX": calibration_object.CalIndexX,
            "CalIndexY": calibration_object.CalIndexY,
        }

    def AddImage(
        self, window_name, display_name, image_name, size_x, size_y, calibration_name
    ):
        window = self._FindDisplayWindow(window_name)
        display = window.FindDisplay(display_name)
        calibration = self.workspace[calibration_name]["object"]
        image = display.AddImage(image_name, size_x, size_y, calibration)

    def getImageInfo(self, window_name, display_name, image_name):
        window = self._FindDisplayWindow(window_name)
        display = window.FindDisplay(display_name)
        image = display.FindObject(image_name)
        return self._getData2D(image.Data)

    def _getData2D(self, data_object):
        return {
            "Calibration": self._getCalibration2D(data_object.Calibration),
            "Range": self._getRange2D(data_object.Range),
            "PixelsX": data_object.PixelsX,
            "PixelsY": data_object.PixelsY,
        }

    def getImageArray(self, window_name, display_name, image_name):
        window = self._FindDisplayWindow(window_name)
        display = window.FindDisplay(display_name)
        image = display.FindObject(image_name)
        return np.array(image.Data.Array, dtype=np.uint16)

    def getPositionMarkers(self, window_name, display_name, position_marker_namelist):
        window = self._FindDisplayWindow(window_name)
        display = window.FindDisplay(display_name)
        return {
            f"{pmn}": np.array([display.FindObject(pmn).Position.X, display.FindObject(pmn).Position.Y])
            for pmn in position_marker_namelist
        }

    ### Utility functions ###

    def Range2D(self, varname, startX, startY, stopX, stopY):
        range2d = self.tia.Range2D(startX, startY, stopX, stopY)
        self.addVariable(varname, range2d, "Range2D")

    def _getRange2D(self, range_object):
        return {
            "StartX": range_object.StartX,
            "StartY": range_object.StartY,
            "EndX": range_object.EndX,
            "EndY": range_object.EndY,
            "SizeX": range_object.SizeX,
            "SizeY": range_object.SizeY,
            "Center": (range_object.Center.X, range_object.center.Y),
        }

    def Range1D(self, varname, start, stop):
        range1d = self.tia.Range1D(start, stop)
        self.addVariable(varname, range1d, "Range1D")

    def _getRange1D(self, range_object):
        return {
            "Start": range_object.Start,
            "End": range_object.End,
            "Size": range_object.Size,
            "Center": range_object.Center,
        }

    def Position2D(self, varname, x, y):
        position2d = self.tia.Position2D(x, y)
        self.addVariable(varname, position2d, "Position2D")

    def _getPosition2D(self, position_object):
        return (position_object.X, position_object.Y)

    def PositionCollection(self, varname):
        position_collection = self.tia.PositionCollection()
        self.addVariable(varname, position_collection, "PositionCollection")

    def _getPositionCollection(self, position_collection_object):
        return {
            "Count": position_collection_object.Count,
            "Items": [
                (
                    position_collection_object.Item(i).X,
                    position_collection_object.Item(i).Y,
                )
                for i in range(position_collection_object.Count)
            ],
        }

    def AddPosition(self, position_collection_name, x, y):
        self.workspace[position_collection_name]["object"].Add(
            self.tia.Position2D(x, y)
        )

    def SetLinePattern(self, position_collection_name, x0, y0, x1, y1, npoints):
        p0 = self.tia.Position2D(x0, y0)
        p1 = self.tia.Position2D(x1, y1)
        self.workspace[position_collection_name]["object"].SetLinePattern(
            p0, p1, npoints
        )

    def SetGridPattern(self, position_collection_name, range_name, nX, nY):
        self.workspace[position_collection_name]["object"].SetGridPattern(
            self.workspace[range_name]["object"], nX, nY
        )

    def Selection(self, varname, source_position_collection_name, index_start, index_stop):
        self.workspace[varname] = self.workspace[source_position_collection_name]
        self.workspace[varname]["object"] = self.workspace[source_position_collection_name]["object"].Selection(index_start, index_stop)

    def RemoveAll(self, position_collection_name):
        self.workspace[position_collection_name]["object"].RemoveAll()

    def SpatialUnit(self, varname, unit_string):
        spatial_unit = self.tia.SpatialUnit(unit_string)
        self.addVariable(varname, spatial_unit, "SpatialUnit")

    def _getSpatialUnit(self, spatial_unit_object):
        return spatial_unit_object.UnitString

    ### Acquisition manager functions ###

    def AcquisitionManager(self, varname):
        self.addVariable(varname, self.acq, "AcquisitionManager")

    def IsAcquiring(self):
        return self.acq.IsAcquiring

    def CanStart(self):
        return self.acq.CanStart

    def CanStop(self):
        return self.acq.CanStop

    def Start(self):
        self.acq.Start()

    def Stop(self):
        self.acq.Stop()

    def Acquire(self):
        self.acq.Acquire()

    def AcquireSet(self, position_collection_name, dwelltime):
        self.acq.AcquireSet(self.workspace[position_collection_name]["object"], dwelltime)

    def IsCurrentSetup(self):
        return self.acq.IsCurrentSetup

    def DoesSetupExist(self, setup_name):
        return self.acq.DoesSetupExist(setup_name)

    def CurrentSetup(self):
        return self.acq.CurrentSetup

    def SelectSetup(self, setup_name):
        self.acq.SelectSetup(setup_name)

    def AddSetup(self, setup_name):
        self.acq.AddSetup(setup_name)

    def DeleteSetup(self, setup_name):
        self.acq.DeleteSetup(setup_name)

    def LinkSignal(self, signal_name, window_name, display_name, image_name):
        window = self._FindDisplayWindow(window_name)
        display = window.FindDisplay(display_name)
        image = display.FindObject(image_name)
        self.acq.LinkSignal(signal_name, image)

    def UnlinkSignal(self, signal_name):
        self.acq.UnlinkSignal(signal_name)

    def UnlinkAllSignals(self):
        self.acq.UnlinkAllSignals()

    def SignalNames(self):
        return [sn for sn in self.acq.SignalNames]

    def EnabledSignalNames(self):
        return [esn for esn in self.acq.EnabledSignalNames]

    def TypedSignalNames(self, signal_type):
        return [
            tsn for tsn in self.acq.TypedSignalNames(signal_type)
        ]

    ### Scanning server functions ###

    def ScanningServer(self, varname):
        self.addVariable(varname, self.scan, "ScanningServer")

    def getScanningServer(self):
        return {
            "AcquireMode": self.scan.AcquireMode,
            "FrameWidth": self.scan.FrameWidth,
            "FrameHeight": self.scan.FrameHeight,
            "DwellTime": self.scan.DwellTime,
            "ScanResolution": self.scan.ScanResolution,
            "ScanMode": self.scan.ScanMode,
            "ForceExternalScan": self.scan.ForceExternalScan,
            "ReferencePosition": self._getPosition2D(self.scan.ReferencePosition),
            "BeamPosition": self._getPosition2D(self.scan.BeamPosition),
            "DriftRateX": self.scan.DriftRateX,
            "DriftRateY": self.scan.DriftRateY,
            "ScanRange": self._getRange2D(self.scan.ScanRange),
            "SeriesSize": self.scan.SeriesSize,
            "DwellTimeRange": self._getRange1D(self.scan.GetDwellTimeRange),
            "TotalScanRange": self._getRange2D(self.scan.GetTotalScanRange),
            "ScanResolutionRange": (
                self._getRange1D(self.scan.GetScanResolutionRange)
                if self.scan.ScanMode != 0
                else None
            )
        }

    def setScanningServer(self, kwargs: dict):
        for key, val in kwargs.items():
            setattr(self.scan, key, val)

    def setBeamPosition(self, position2d_name):
        self.scan.BeamPosition = self.workspace[position2d_name]["object"]

    def setScanRange(self, range2d_name):
        self.scan.ScanRange = self.workspace[range2d_name]["object"]

    def MagnificationNames(self, mode):
        return [mn for mn in self.scan.MagnificationNames(mode)]

    ### CCD server functions ###

    def CCDServer(self, varname):
        self.addVariable(varname, self.ccd, "CCDServer")

    def getCCDServer(self):
        return {
            "AcquireMode": self.ccd.AcquireMode,
            "Camera": self.ccd.Camera,
            "CameraInserted": self.ccd.CameraInserted,
            "IntegrationTime": self.ccd.IntegrationTime,
            "ReadoutRange": self._getRange2D(self.ccd.ReadoutRange),
            "PixelReadoutRange": self._getRange2D(self.ccd.PixelReadoutRange),
            "Binning": self.ccd.Binning,
            "ReferencePosition": self._getPosition2D(self.ccd.ReferencePosition),
            "ReadoutRate": self.ccd.ReadoutRate,
            "DriftRateX": self.ccd.DriftRateX,
            "DriftRateY": self.ccd.DriftRateY,
            "BiasCorrection": self.ccd.BiasCorrection,
            "GainCorrection": self.ccd.GainCorrection,
            "SeriesSize": self.ccd.SeriesSize,
            "IntegrationTimeRange": self._getRange1D(self.ccd.GetIntegrationTimeRange),
            "TotalReadoutRange": self._getRange2D(self.ccd.GetTotalReadoutRange),
            "TotalPixelReadoutRange": self._getRange2D(self.ccd.GetTotalPixelReadoutRange),
        }

    def setCCDServer(self, kwargs: dict):
        for key, val in kwargs.items():
            setattr(self.ccd, key, val)

    def setReadoutRange(self, range2d_name):
        self.ccd.ReadoutRange = self.workspace[range2d_name]["object"]

    def setPixelReadoutRange(self, range2d_name):
        self.ccd.PixelReadoutRange = self.workspace[range2d_name]["object"]

    ### Scanning and CCD server ###

    def setReferencePosition(self, position2d_name, server="scan"):
        if server == "scan":
            self.scan.ReferencePosition = self.workspace[position2d_name]["object"]
        elif server == "ccd":
            self.ccd.ReferencePosition = self.workspace[position2d_name]["object"]

    ### Beam control functions ###

    def BeamControl(self, varname):
        self.addVariable(varname, self.beam_control, "Beam Control")

    def getBeamControl(self):
        return {
            "DwellTime": self.beam_control.DwellTime,
            "PositionCalibrated": self.beam_control.PositionCalibrated,
        }

    def setBeamControl(self, kwargs: dict):
        for key, val in kwargs.items():
            setattr(self.beam_control, key, val)

    def StartBeamControl(self):
        self.beam_control.Start()

    def StopBeamControl(self):
        self.beam_control.Stop()

    def ResetBeamControl(self):
        self.beam_control.Reset()

    def SetSingleScan(self):
        self.beam_control.SetSingleScan()

    def SetContinuousScan(self):
        self.beam_control.SetContinuousScan()

    def LoadPositions(self, position_collection_name):
        self.beam_control.LoadPositions(
            self.workspace[position_collection_name]["object"]
        )

    def SetLineScan(self, start_position_name, end_position_name):
        self.beam_control.SetLineScan(
            self.workspace[start_position_name]["object"],
            self.workspace[start_position_name]["object"],
        )

    def SetFrameScan(self, range_name, nX, nY):
        self.beam_control.SetFrameScan(
            self.workspace[range_name]["object"], nX, nY
        )

    def MoveBeam(self, X, Y):
        self.beam_control.MoveBeam(X, Y)

    def CanStartBeamControl(self):
        return self.beam_control.CanStart

    def IsScanning(self):
        return self.beam_control.IsScanning
