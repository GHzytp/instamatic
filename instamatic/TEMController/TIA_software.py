# TEM Image Analysis (TIA) software control API from Pascal Hogan (pascal.hogan@gmail.com)

import numpy as np
import comtypes.client


class TIASoftware:
    def __init__(self, name="TIA", tia=None):
        self.name = name
        self.tia = tia
        self.cte = None

        self.workspace = {}

    def connect(self):
        try:
            comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
        except WindowsError:
            comtypes.CoInitialize()

        print("Initializing connection to TIA...")
        self.tia = comtypes.client.CreateObject(
            "ESVision.Application"
        )  # , comtypes.CLSCTX_ALL)
        # self.cte = comtypes.client.Constants(self.tia)

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
        return self._getData2DArray(image.Data)

    def _getData2DArray(self, data_object):
        return np.array(data_object.Array)

    def getPositionMarkers(self, window_name, display_name, position_marker_namelist):
        window = self._FindDisplayWindow(window_name)
        display = window.FindDisplay(display_name)
        return {
            "{}".format(pmn): np.array(
                [display.FindObject(pmn).Position.X, display.FindObject(pmn).Position.Y]
            )
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

    def Selection(
        self, varname, source_position_collection_name, index_start, index_stop
    ):
        self.workspace[varname] = self.workspace[source_position_collection_name]
        self.workspace[varname]["object"] = self.workspace[
            source_position_collection_name
        ]["object"].Selection(index_start, index_stop)

    def RemoveAll(self, position_collection_name):
        self.workspace[position_collection_name]["object"].RemoveAll()

    def SpatialUnit(self, varname, unit_string):
        spatial_unit = self.tia.SpatialUnit(unit_string)
        self.addVariable(varname, spatial_unit, "SpatialUnit")

    def _getSpatialUnit(self, spatial_unit_object):
        return spatial_unit_object.UnitString

    ### Acquisition manager functions ###

    def AcquisitionManager(self, varname):
        acq = self.tia.AcquisitionManager()
        self.addVariable(varname, acq, "AcquisitionManager")

    def IsAcquiring(self):
        return self.tia.AcquisitionManager().IsAcquiring

    def CanStart(self):
        return self.tia.AcquisitionManager().CanStart

    def CanStop(self):
        return self.tia.AcquisitionManager().CanStop

    def Start(self):
        self.tia.AcquisitionManager().Start()

    def Stop(self):
        self.tia.AcquisitionManager().Stop()

    def Acquire(self):
        self.tia.AcquisitionManager().Acquire()

    def AcquireSet(self, position_collection_name, dwelltime):
        self.tia.AcquisitionManager().AcquireSet(
            self.workspace[position_collection_name]["object"], dwelltime
        )

    def IsCurrentSetup(self):
        return self.tia.AcquisitionManager().IsCurrentSetup

    def DoesSetupExist(self, setup_name):
        return self.tia.AcquisitionManager().DoesSetupExist(setup_name)

    def CurrentSetup(self):
        return self.tia.AcquisitionManager().CurrentSetup

    def SelectSetup(self, setup_name):
        self.tia.AcquisitionManager().SelectSetup(setup_name)

    def AddSetup(self, setup_name):
        self.tia.AcquisitionManager().AddSetup(setup_name)

    def DeleteSetup(self, setup_name):
        self.tia.AcquisitionManager().DeleteSetup(setup_name)

    def LinkSignal(self, signal_name, window_name, display_name, image_name):
        window = self._FindDisplayWindow(window_name)
        display = window.FindDisplay(display_name)
        image = display.FindObject(image_name)
        self.tia.AcquisitionManager().LinkSignal(signal_name, image)

    def UnlinkSignal(self, signal_name):
        self.tia.AcquisitionManager().UnlinkSignal(signal_name)

    def UnlinkAllSignals(self):
        self.tia.AcquisitionManager().UnlinkAllSignals()

    def SignalNames(self):
        return [sn for sn in self.tia.AcquisitionManager().SignalNames]

    def EnabledSignalNames(self):
        return [esn for esn in self.tia.AcquisitionManager().EnabledSignalNames]

    def TypedSignalNames(self, signal_type):
        return [
            tsn for tsn in self.tia.AcquisitionManager().TypedSignalNames(signal_type)
        ]

    ### Scanning server functions ###

    def ScanningServer(self, varname):
        scan = self.tia.ScanningServer()
        self.addVariable(varname, scan, "ScanningServer")

    def getScanningServer(self):
        scan = self.tia.ScanningServer()
        return {
            "AcquireMode": scan.AcquireMode,
            "FrameWidth": scan.FrameWidth,
            "FrameHeight": scan.FrameHeight,
            "DwellTime": scan.DwellTime,
            "ScanResolution": scan.ScanResolution,
            "ScanMode": scan.ScanMode,
            "ForceExternalScan": scan.ForceExternalScan,
            "ReferencePosition": self._getPosition2D(scan.ReferencePosition),
            "BeamPosition": self._getPosition2D(scan.BeamPosition),
            "DriftRateX": scan.DriftRateX,
            "DriftRateY": scan.DriftRateY,
            "ScanRange": self._getRange2D(scan.ScanRange),
            "SeriesSize": scan.SeriesSize,
            "DwellTimeRange": self._getRange1D(scan.GetDwellTimeRange),
            "TotalScanRange": self._getRange2D(scan.GetTotalScanRange),
            "ScanResolutionRange": (
                self._getRange1D(scan.GetScanResolutionRange)
                if scan.ScanMode != 0
                else None
            ),
        }

    def setScanningServer(self, kwargs: dict):
        scan = self.tia.ScanningServer()
        for key, val in kwargs.items():
            setattr(scan, key, val)

    def setBeamPosition(self, position2d_name):
        scan = self.tia.ScanningServer()
        scan.BeamPosition = self.workspace[position2d_name]["object"]

    def setScanRange(self, range2d_name):
        scan = self.tia.ScanningServer()
        scan.ScanRange = self.workspace[range2d_name]["object"]

    def MagnificationNames(self, mode):
        scan = self.tia.ScanningServer()
        return [mn for mn in scan.MagnificationNames(mode)]

    ### CCD server functions ###

    def CCDServer(self, varname):
        ccd = self.tia.CCDServer()
        self.addVariable(varname, ccd, "CCDServer")

    def getCCDServer(self):
        ccd = self.tia.CCDServer()
        return {
            "AcquireMode": ccd.AcquireMode,
            "Camera": ccd.Camera,
            "CameraInserted": ccd.CameraInserted,
            "IntegrationTime": ccd.IntegrationTime,
            "ReadoutRange": self._getRange2D(ccd.ReadoutRange),
            "PixelReadoutRange": self._getRange2D(ccd.PixelReadoutRange),
            "Binning": ccd.Binning,
            "ReferencePosition": self._getPosition2D(ccd.ReferencePosition),
            "ReadoutRate": ccd.ReadoutRate,
            "DriftRateX": ccd.DriftRateX,
            "DriftRateY": ccd.DriftRateY,
            "BiasCorrection": ccd.BiasCorrection,
            "GainCorrection": ccd.GainCorrection,
            "SeriesSize": ccd.SeriesSize,
            "IntegrationTimeRange": self._getRange1D(ccd.GetIntegrationTimeRange),
            "TotalReadoutRange": self._getRange2D(ccd.GetTotalReadoutRange),
            "TotalPixelReadoutRange": self._getRange2D(ccd.GetTotalPixelReadoutRange),
        }

    def setCCDServer(self, kwargs: dict):
        ccd = self.tia.CCDServer()
        for key, val in kwargs.items():
            setattr(ccd, key, val)

    def setReadoutRange(self, range2d_name):
        ccd = self.tia.CCDServer()
        ccd.ReadoutRange = self.workspace[range2d_name]["object"]

    def setPixelReadoutRange(self, range2d_name):
        ccd = self.tia.CCDServer()
        ccd.PixelReadoutRange = self.workspace[range2d_name]["object"]

    ### Scanning and CCD server ###

    def setReferencePosition(self, position2d_name, server="scan"):
        if server == "scan":
            scan = self.tia.ScanningServer()
            scan.ReferencePosition = self.workspace[position2d_name]["object"]
        elif server == "ccd":
            ccd = self.tia.CCDServer()
            ccd.ReferencePosition = self.workspace[position2d_name]["object"]

    ### Beam control functions ###

    def BeamControl(self, varname):
        beam_control = self.tia.BeamControl()
        self.addVariable(varname, beam_control, "Beam Control")

    def getBeamControl(self):
        beam = self.tia.BeamControl()
        return {
            "DwellTime": beam.DwellTime,
            "PositionCalibrated": beam.PositionCalibrated,
        }

    def setBeamControl(self, kwargs: dict):
        beam = self.tia.BeamControl()
        for key, val in kwargs.items():
            setattr(beam, key, val)

    def StartBeamControl(self):
        self.tia.BeamControl().Start()

    def StopBeamControl(self):
        self.tia.BeamControl().Stop()

    def ResetBeamControl(self):
        self.tia.BeamControl().Reset()

    def SetSingleScan(self):
        self.tia.BeamControl().SetSingleScan()

    def SetContinuousScan(self):
        self.tia.BeamControl().SetContinuousScan()

    def LoadPositions(self, position_collection_name):
        self.tia.BeamControl().LoadPositions(
            self.workspace[position_collection_name]["object"]
        )

    def SetLineScan(self, start_position_name, end_position_name):
        self.tia.BeamControl().SetLineScan(
            self.workspace[start_position_name]["object"],
            self.workspace[start_position_name]["object"],
        )

    def SetFrameScan(self, range_name, nX, nY):
        self.tia.BeamControl().SetFrameScan(
            self.workspace[range_name]["object"], nX, nY
        )

    def MoveBeam(self, X, Y):
        self.tia.BeamControl().MoveBeam(X, Y)

    def CanStartBeamControl(self):
        return self.tia.BeamControl().CanStart

    def IsScanning(self):
        return self.tia.BeamControl().IsScanning
