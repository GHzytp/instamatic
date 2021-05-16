# TEM Image Analysis (TIA) software controller interface using TIA API from Pascal Hogan (pascal.hogan@gmail.com)

import numpy as np
import re

from .microscope import Software


def automatic_naming(name, dico):
    if name in [key for key in dico.keys()]:
        print("There is already an object named '{}'.".format(name))

        # Check for digits already present at the end of the name, remove those digits
        numerals = re.findall(r"(\d+)$", name)
        if numerals:
            length_of_numerals = len(numerals[0])
            name = name[:-(length_of_numerals)]

        # Look through existing names what is the highest digit, increase this digit and return the new name
        existing_names = [
            int(i)
            for i in [
                re.findall(r"{}(\d+)".format(name), j)[0]
                for j in [key for key in dico.keys()]
                if re.findall(r"{}(\d+)".format(name), j)
            ]
        ]
        if existing_names:
            suffix = max(existing_names) + 1
        else:
            suffix = 1
        name = name + str(suffix)
        print("Automatic naming: '{}'.".format(name))

    return name


def flatten(obj, parent_key="", sep="/"):
    dico = {}
    if "__dict__" in dir(obj):
        for key, value in obj.__dict__.items():
            if isinstance(value, dict):
                new_key = parent_key
                dico.update(flatten(value, new_key))
    elif isinstance(obj, dict):
        for key, value in obj.items():
            new_key = parent_key + sep + key if parent_key else key
            dico[new_key] = value
            dico.update(flatten(value, new_key))
    return dico


class Interface:
    def __init__(self, use_server=False):

        self.tia = Software("TIA", use_server)

        self.windows = {}
        self.components = {}
        self.updateComponents()

    def __str__(self, level=0):
        ret = "\t" * level + "Interface \n"
        for window_name, window in self.windows.items():
            ret += window.__str__(level + 1)
        return ret

    def openWindows(self, name=None, n=1):
        for i in range(n):
            self.openWindow(name)

    def openWindow(self, name=None):
        if name:
            name = automatic_naming(name, self.windows)
        window = Window.fromInterface(name, self.tia)
        self.windows[window.name] = window

    def closeWindow(self, name):
        if name in [key for key in self.windows.keys()]:
            self.tia.CloseDisplayWindow(name)
            del self.windows[name]
        else:
            print("There is no window named '{}'.".format(name))

    def closeAllWindows(self):
        windows_name = [key for key in self.windows.keys()]
        for window_name in windows_name:
            self.closeWindow(window_name)

    def updateWindows(self):
        self.windows = {
            wn: Window(wn, self.tia) for wn in self.tia.DisplayWindowNames()
        }

    def updateComponents(self):
        self.updateWindows()
        self.components = flatten(self.windows)

        workspace = self.tia.showWorkspace()
        for varname, vartype in workspace.items():
            front_object = None
            variable = self.tia.getVariable(varname)
            if vartype == "Calibration2D":
                front_object = Calibration2D(varname, self.tia, **variable)
            elif vartype == "Range2D":
                front_object = Range2D(varname, self.tia, **variable)
            elif vartype == "Range1D":
                front_object = Range1D(varname, self.tia, **variable)
            elif vartype == "Position2D":
                front_object = Position2D(varname, self.tia, variable)
            elif vartype == "PositionCollection":
                front_object = PositionCollection(varname, self.tia, **variable)
            """elif vartype == 'SpatialUnit':
                return self._getSpatialUnit(variable['object'])"""

            if front_object:
                self.components[varname] = front_object

    def activateWindow(self, name):
        if name in list(self.windows.keys()):
            self.tia.ActivateDisplayWindow(name)
        else:
            print("Window '{}' does not exist".format(name))

    def getActiveWindow(self):
        return self.tia.ActiveDisplayWindowName()

    def addCalibration2D(self, varname, offsetX, offsetY, deltaX, deltaY, calIndexX=0, calIndexY=0):
        calib = Calibration2D.fromInterface(
            varname,
            self.tia,
            offsetX,
            offsetY,
            deltaX,
            deltaY,
            calIndexX=0,
            calIndexY=0,
        )
        self.components[varname] = calib
        return calib

    def addRange2D(self, varname, startX, startY, endX, endY):
        range2d = Range2D.fromInterface(varname, self.tia, startX, startY, endX, endY)
        self.components[varname] = range2d
        return range2d

    def addRange1D(self, varname, start, end):
        range1d = Range1D.fromInterface(varname, self.tia, start, end)
        self.components[varname] = range1d
        return range1d

    def addPosition2D(self, varname, x, y):
        pos2d = Position2D.fromInterface(varname, self.tia, x, y)
        self.components[varname] = pos2d
        return pos2d

    def addPositionCollection(self, varname):
        poscoll = PositionCollection.fromInterface(varname, self.tia)
        self.components[varname] = poscoll
        return poscoll

    def addSpatialUnit(self, varname, unit_string):
        unit = SpatialUnit.fromInterface(varname, self.tia, unit_string)
        self.components[varname] = unit
        return unit


class Window:
    def __init__(self, name, tia_handle):
        self.handle = tia_handle
        self.name = name

        self.displays = {}
        self.updateDisplays()

    def __str__(self, level=0):
        ret = "\t" * level + self.name + " \n"
        for display_name, display in self.displays.items():
            ret += display.__str__(level + 1)
        return ret

    @classmethod
    def fromInterface(cls, name, tia_handle):
        tia_handle.AddDisplayWindow(name)
        return cls(name, tia_handle)

    def addDisplays(self, name, n=1):
        for i in range(n):
            self.addDisplay(name)

    def addDisplay(
        self,
        display_name,
        display_type=0,
        display_subtype=0,
        splitdirection=0,
        newsplitportion=None,
    ):
        display_name = automatic_naming(display_name, self.displays)
        n_display = len(self.displays)
        if newsplitportion is None:
            newsplitportion = 1 / (n_display + 1)
        display = Display.fromWindow(
            self,
            display_name,
            display_type,
            display_subtype,
            splitdirection,
            newsplitportion,
        )
        self.displays[display.name] = display

    def addImagesToDisplays(self, name, sizeX, sizeY, calibration_name):
        for display_name, display in self.displays.items():
            display.addImage(name, sizeX, sizeY, calibration_name)

    def updateDisplays(self):
        self.displays = {
            dn: Display(dn, self.handle, self.name)
            for dn in self.handle.DisplayNames(self.name)
        }

    def deleteDisplay(self, display_name):
        if display_name in [key for key in self.displays.keys()]:
            self.handle.DeleteDisplay(self.name, display_name)
            del self.displays[display_name]
        else:
            print("There is no display named '{}'.".format(display_name))

    def deleteAllDisplays(self):
        displays_name = [key for key in self.displays.keys()]
        for display_name in displays_name:
            self.deleteDisplay(display_name)


class Display:
    def __init__(self, name, tia_handle, parent_window_name):
        self.handle = tia_handle
        self.name = name
        self.parent = parent_window_name

        self.images = {}
        self.updateImages()

        self.positionMarkers = {}
        self.updatePositionMarkers()

    def __str__(self, level=0):
        ret = "\t" * level + self.name + " \n"
        for image_name, image in self.images.items():
            ret += image.__str__(level + 1)
        return ret

    @classmethod
    def fromWindow(
        cls,
        parent_window,
        display_name,
        display_type,
        display_subtype,
        splitdirection,
        newsplitportion,
    ):
        parent_window.handle.AddDisplay(
            parent_window.name,
            display_name,
            display_type,
            display_subtype,
            splitdirection,
            newsplitportion,
        )
        return cls(display_name, parent_window.handle, parent_window.name)

    def addImage(self, name, size_x, size_y, calibration_varname):
        name = automatic_naming(name, self.images)
        image = Image.fromDisplay(self, name, size_x, size_y, calibration_varname)
        self.images[image.name] = image

    def updateImages(self):
        self.images = {
            on: Image(on, self.handle, self.parent, self.name)
            for on in self.handle.ObjectNames(self.parent, self.name)["Images"]
        }

    def updatePositionMarkers(self):
        self.positionMarkers = self.handle.getPositionMarkers(
            self.parent,
            self.name,
            self.handle.ObjectNames(self.parent, self.name)["Position Markers"],
        )

    def deleteImage(self, name):
        if name in [key for key in self.images.keys()]:
            self.handle.DeleteObject(self.parent, self.name, name)
            del self.images[name]
        else:
            print("There is no image named '{}'.".format(name))

    def deleteAllImages(self):
        images_name = [key for key in self.images.keys()]
        for image_name in images_name:
            self.deleteImage(image_name)


class Image:
    def __init__(self, name, tia_handle, parent_window_name, parent_display_name):
        self.name = name
        self.handle = tia_handle
        self.parent = (parent_window_name, parent_display_name)

        self.data = Data2D()
        self.updateData()

    @classmethod
    def fromDisplay(
        cls, parent_display, image_name, size_x, size_y, calibration_varname
    ):
        parent_display.handle.AddImage(
            parent_display.parent,
            parent_display.name,
            image_name,
            size_x,
            size_y,
            calibration_varname,
        )
        return cls(
            image_name,
            parent_display.handle,
            parent_display.parent,
            parent_display.name,
        )

    def __str__(self, level=0):
        ret = "\t" * level + self.name + " \n"
        return ret

    def updateData(self):
        self.data.value = self.handle.getImageArray(
            self.parent[0], self.parent[1], self.name
        )

        metadata = self.handle.getImage(self.parent[0], self.parent[1], self.name)

        self.data.calibration = Calibration2D(
            "{}_calibration".format(self.name), self.handle, **metadata["Calibration"]
        )
        self.data.sizeX = metadata["PixelsX"]
        self.data.sizeY = metadata["PixelsY"]
        self.data.range = Range2D(
            "{}_range2d".format(self.name), self.handle, **metadata["Range"]
        )
        self.data.pixelPosition = self.getPixelPosition()

    def getPixelPosition(self):
        """
        Pixel position in spatial unit (m).
        In TIA, the index goes from bottom to top in y and from left to right in x. The index of pixel is correspond to the coordinates of the bottom left corner.
        The data imported in python is rotated, such that the index of the top left corner matters. That means that 'x,y' in TIA corresponds to 'row,column' in python,
        instead of 'column,row' like in a regular plot.
        """
        pixel_left_boundary_x = np.arange(
            self.data.range.startX, self.data.range.endX, self.data.calibration.deltaX
        )
        # pixel_right_boundary_x = pixel_left_boundary_x + self.calibration.deltaX
        pixel_bottom_boundary_y = np.arange(
            self.data.range.startY, self.data.range.endY, self.data.calibration.deltaY
        )
        # pixel_top_boundary_y = pixel_bottom_boundary_y + self.calibration.deltaY

        Y, X = np.meshgrid(
            pixel_left_boundary_x, pixel_bottom_boundary_y
        )  # X and Y are inverted in TIA with respect to python
        pixelPosition = np.vstack((X[np.newaxis, :, :], Y[np.newaxis, :, :]))

        return pixelPosition


class Data2D:
    def __init__(
        self,
        value=None,
        pixelPosition=None,
        calibration=None,
        sizeX=None,
        sizeY=None,
        range2d=None,
    ):
        self.value = value
        self.pixelPosition = pixelPosition
        self.calibration = calibration
        self.sizeX = sizeX
        self.sizeY = sizeY
        self.range = range2d


class Calibration2D:
    def __init__(
        self,
        varname,
        tia_handle,
        OffsetX,
        OffsetY,
        DeltaX,
        DeltaY,
        CalIndexX=0,
        CalIndexY=0,
    ):
        self.name = varname
        self.handle = tia_handle
        self.offsetX = OffsetX
        self.offsetY = OffsetY
        self.deltaX = DeltaX
        self.deltaY = DeltaY
        self.calIndexX = CalIndexX
        self.calIndexY = CalIndexY

    @classmethod
    def fromInterface(
        cls,
        varname,
        tia_handle,
        offsetX,
        offsetY,
        deltaX,
        deltaY,
        calIndexX=0,
        calIndexY=0,
    ):
        tia_handle.Calibration2D(
            varname, offsetX, offsetY, deltaX, deltaY, calIndexX, calIndexY
        )
        calib = tia_handle.getVariable(varname)
        return cls(varname, tia_handle, **calib)


class Range2D:
    def __init__(self, varname, tia_handle, StartX, StartY, EndX, EndY, SizeX, SizeY, Center):
        self.name = varname
        self.handle = tia_handle
        self.startX = StartX
        self.startY = StartY
        self.endX = EndX
        self.endY = EndY
        self.sizeX = SizeX
        self.sizeY = SizeY
        self.center = Center

    @classmethod
    def fromInterface(cls, varname, tia_handle, startX, startY, endX, endY):
        tia_handle.Range2D(varname, startX, startY, endX, endY)
        range2d = tia_handle.getVariable(varname)
        return cls(varname, tia_handle, **range2d)

    def __dict__(self):
        return {
            "StartX": self.startX,
            "EndX": self.endX,
            "StartY": self.startY,
            "EndY": self.endY,
            "SizeX": self.sizeX,
            "SizeY": self.sizeY,
            "Center": self.center,
        }


class Range1D:
    def __init__(self, varname, tia_handle, Start, End, Size, Center):
        self.name = varname
        self.handle = tia_handle
        self.start = Start
        self.end = End
        self.size = Size
        self.center = Center

    @classmethod
    def fromInterface(cls, varname, tia_handle, start, end):
        tia_handle.Range1D(varname, start, end)
        range1d = tia_handle.getVariable(varname)
        return cls(varname, tia_handle, **range1d)

    def __dict__(self):
        return {
            "Start": self.start,
            "End": self.end,
            "Size": self.size,
            "Center": self.center,
        }


class Acquisition:
    def __init__(self, use_server=False):

        self.tia = Software("TIA", use_server)

        self.acq = self.tia.AcquisitionManager("acq")
        self.signals = self.getSignalsByType()

        self.ccd = CCDServer.fromAcquisition("ccd", self.tia)
        self.scan = ScanningServer.fromAcquisition("scan", self.tia)
        self.beam = self.beamControl("beam")
        self.beam.updateBeamControl()

        if self.doesCurrentSetupExist():
            self.setup = self.currentSetupName
        else:
            self.setup = None

    def isAcquiring(self):
        return self.tia.IsAcquiring()

    def canStart(self):
        return self.tia.CanStart()

    def canStop(self):
        return self.tia.CanStop()

    def startAcquisition(self):
        self.tia.Start()

    def stopAcquisition(self):
        self.tia.Stop()

    def acquireSingle(self):
        """
        Starts acquisition with the currently selected acquisition setup. The setup must be in single frame mode (Scanning Mode) or Add Mode (Spot Mode).
        This method acquires data synchronously. This means that program flow continues only after the acquisition invoked with the Acquire method has finished completely.
        """
        self.tia.Acquire()

    def acquireSet(self, position_collection_name, dwell_time):
        """Starts acquisition with the currently selected acquisition setup. The setup must be spot Mode. Acquisition is repeated at a specified set of beam positions and at a specified dwell time.
        This method acquires data synchronously. This means that program flow continues only after the acquisition invoked with the AcquireSet method has finished completely. How data is acquired at each beam position is completely determined by the current acquisition setup.
        The method Acquire used in a loop can implement the same functionaliy as AcquireSet. However, experiments implemented with the Acquire method have performance limitations. The AcquireSet method is specifically provided for dwell times smaller than 0.5-1 s."""
        self.tia.AcquireSet(position_collection_name, dwell_time)

    def doesCurrentSetupExist(self):
        return self.tia.IsCurrentSetup

    def doesSetupExist(self, setup_name):
        return self.tia.DoesSetupExist(setup_name)

    def currentSetupName(self):
        return self.tia.CurrentSetup()

    def selectSetup(self, setup_name):
        self.tia.SelectSetup(setup_name)

    def addSetup(self, setup_name):
        self.tia.AddSetup(setup_name)

    def deleteSetup(self, setup_name):
        self.tia.DeleteSetup(setup_name)

    def linkSignal(self, signal_name, image_object):
        self.tia.LinkSignal(
            signal_name,
            image_object.parent[0],
            image_object.parent[1],
            image_object.name,
        )

    def unlinkSignal(self, signal_name):
        self.tia.UnlinkSignal(signal_name)

    def unlinkAllSignals(self):
        self.tia.UnlinkAllSignals()

    def getAvailableSignalNames(self):
        return self.tia.SignalNames()

    def getEnabledSignalNames(self):
        return self.tia.EnabledSignalNames()

    def getSignalsByType(self):
        return {
            "Detectors": self.tia.TypedSignalNames(0),
            "CCDs": self.tia.TypedSignalNames(6),
        }

    def beamControl(self, varname):
        return BeamControl.fromAcquisition(varname, self.tia)


class CCDServer:
    def __init__(self, name, tia_handle):
        self.handle = tia_handle
        self.name = name

        self.acquireMode = None
        self.camera = None
        self.cameraInserted = None
        self.integrationTime = None
        self.readoutRange = None
        self.pixelReadoutRange = None
        self.binning = None
        self.referencePosition = None
        self.readoutRate = None
        self.driftRateXY = (None, None)
        self.biasCorrection = None
        self.gainCorrection = None
        self.seriesSize = None

        self.allowedValueRange = {
            "Integration Time": None,
            "Readout Range": None,
            "Pixel Readout Range": None,
        }

    def updateCCDServer(self):

        ccd = self.handle.getCCDServer()

        self.acquireMode = self.getAcquireMode(ccd)
        self.camera = self.getCamera(ccd)
        self.cameraInserted = self.getCameraInserted(ccd)
        self.integrationTime = self.getIntegrationTime(ccd)
        self.readoutRange = self.getReadoutRange(ccd)
        self.pixelReadoutRange = self.getPixelReadoutRange(ccd)
        self.referencePosition = self.getReferencePosition(ccd)
        self.readoutRate = self.getReadoutRate(ccd)
        self.binning = self.getBinning(ccd)
        self.driftRateXY = self.getDriftRateXY(ccd)
        self.biasCorrection = self.getBiasCorrection(ccd)
        self.gainCorrection = self.getGainCorrection(ccd)
        self.seriesSize = self.getSeriesSize(ccd)

        self.allowedValueRange = {
            "Integration Time": self.getAllowedIntegrationTime(ccd),
            "Readout Range": self.getMaximumReadoutRange(ccd),
            "Pixel Readout Range": self.getMaximumPixelReadoutRange(ccd),
        }

    @classmethod
    def fromAcquisition(cls, name, tia_handle):
        tia_handle.CCDServer(name)
        return CCDServer(name, tia_handle)

    def setCCDServer(self, kwargs: dict):
        self.handle.setCCDServer(kwargs)
        self.updateCCDServer()

    def setAcquireMode(self, mode):
        if mode == "Continuous":
            val = 0
        elif mode == "Single":
            val = 1

        self.setCCDServer({"AcquireMode": val})
        self.acquireMode = mode

    def getAcquireMode(self, dico=None):
        if dico:
            mode = dico["AcquireMode"]
        else:
            mode = self.handle.getCCDServer()["AcquireMode"]

        if mode == 0:
            return "Continuous"
        elif mode == 1:
            return "Single"

    def setCamera(self, camera_name):
        self.setCCDServer({"Camera": camera_name})
        self.camera = camera_name

    def getCamera(self, dico=None):
        if dico:
            ccd = dico
        else:
            ccd = self.handle.getCCDServer()
        return ccd["Camera"]

    def setCameraInserted(self, camera_state):
        self.setCCDServer({"CameraInserted": camera_state})
        self.cameraInserted = camera_state

    def getCameraInserted(self, dico=None):
        if dico:
            ccd = dico
        else:
            ccd = self.handle.getCCDServer()
        return ccd["CameraInserted"]

    def setIntegrationTime(self, time):
        self.setCCDServer({"IntegrationTime": time})
        self.integrationTime = time

    def getIntegrationTime(self, dico=None):
        if dico:
            return dico["IntegrationTime"]
        else:
            return self.handle.getCCDServer()["IntegrationTime"]

    def setBinning(self, binning):
        self.setCCDServer({"Binning": binning})
        self.binning = binning

    def getBinning(self, dico=None):
        if dico:
            return dico["Binning"]
        else:
            return self.handle.getCCDServer()["Binning"]

    def setDriftRateXY(self, rateX=None, rateY=None):
        if rateX:
            self.setCCDServer({"DriftRateX": rateX})
        if rateY:
            self.setCCDServer({"DriftRateY": rateY})

        self.driftRateXY = (rateX, rateY)

    def getDriftRateXY(self, dico=None):
        if dico:
            ccd = dico
        else:
            ccd = self.handle.getCCDServer()

        DriftRateX = ccd["DriftRateX"]
        DriftRateY = ccd["DriftRateY"]
        return (DriftRateX, DriftRateY)

    def setBiasCorrection(self, bias):
        self.setCCDServer({"BiasCorrection": bias})
        self.biasCorrection = bias

    def getBiasCorrection(self, dico=None):
        if dico:
            return dico["BiasCorrection"]
        else:
            return self.handle.getCCDServer()["BiasCorrection"]

    def setGainCorrection(self, gain):
        self.setCCDServer({"GainCorrection": gain})
        self.gainCorrection = gain

    def getGainCorrection(self, dico=None):
        if dico:
            return dico["GainCorrection"]
        else:
            return self.handle.getCCDServer()["GainCorrection"]

    def setSeriesSize(self, size):
        self.setCCDServer({"SeriesSize": size})
        self.seriesSize = size

    def getSeriesSize(self, dico=None):
        if dico:
            return dico["SeriesSize"]
        else:
            return self.handle.getCCDServer()["SeriesSize"]

    def setReadoutRate(self, rate):
        self.setCCDServer({"ReadoutRate": rate})
        self.readoutRate = rate

    def getReadoutRate(self, dico=None):
        if dico:
            return dico["ReadoutRate"]
        else:
            return self.handle.getCCDServer()["ReadoutRate"]

    def setReferencePosition(self, position_object):
        self.handle.setReferencePosition(position_object.name, server="ccd")
        self.referencePosition = position_object

    def getReferencePosition(self, dico=None):
        if dico:
            xy = dico["ReferencePosition"]
        else:
            xy = self.handle.getCCDServer()["ReferencePosition"]
        return Position2D("{}_referencePosition".format(self.name), self.handle, xy)

    def setReadoutRange(self, range_object):
        self.handle.setReadoutRange(range_object.name)
        self.readoutRange = range_object

    def getReadoutRange(self, dico=None):
        if dico:
            range2d = dico["ReadoutRange"]
        else:
            range2d = self.handle.getScanningServer()["ReadoutRange"]
        return Range2D("{}_readoutRange".format(self.name), self.handle, **range2d)

    def setPixelReadoutRange(self, range_object):
        self.handle.setPixelReadoutRange(range_object.name)
        self.pixelreadoutRange = range_object

    def getPixelReadoutRange(self, dico=None):
        if dico:
            range2d = dico["PixelReadoutRange"]
        else:
            range2d = self.handle.getScanningServer()["PixelReadoutRange"]
        return Range2D("{}_pixelreadoutRange".format(self.name), self.handle, **range2d)

    def getAllowedIntegrationTime(self, dico=None):
        if dico:
            return dico["IntegrationTimeRange"]
        else:
            return self.handle.getCCDServer()["IntegrationTimeRange"]

    def getMaximumReadoutRange(self, dico=None):
        if dico:
            return dico["TotalReadoutRange"]
        else:
            return self.handle.getScanningServer()["TotalReadoutRange"]

    def getMaximumPixelReadoutRange(self, dico=None):
        if dico:
            return dico["TotalPixelReadoutRange"]
        else:
            return self.handle.getScanningServer()["TotalPixelReadoutRange"]


class ScanningServer:
    def __init__(self, name, tia_handle):

        self.handle = tia_handle
        self.name = name

        self.acquireMode = None
        self.frameShape = (None, None)
        self.dwellTime = None
        self.scanResolution = None
        self.scanMode = None
        self.externalScan = None
        self.referencePosition = None
        self.beamPosition = None
        self.driftRateXY = (None, None)
        self.scanRange = None
        self.seriesSize = None
        self.magnifications = None

        self.allowedValueRange = {
            "Dwell Time": None,
            "Scan Range": None,
            "Scan Resolution": None,
        }

        scan = self.handle.getVariable(self.name)
        self.updateScanningServer()

    def updateScanningServer(self):

        scan = self.handle.getScanningServer()

        self.acquireMode = self.getAcquireMode(scan)
        self.frameShape = self.getFrameShape(scan)
        self.dwellTime = self.getDwellTime(scan)
        self.scanResolution = self.getScanResolution(scan)
        self.scanMode = self.getScanMode(scan)
        self.externalScan = self.getExternalScanState(scan)
        self.referencePosition = self.getReferencePosition(scan)
        self.beamPosition = self.getBeamPosition(scan)
        self.driftRateXY = self.getDriftRateXY(scan)
        self.scanRange = self.getScanRange(scan)
        self.seriesScan = self.getSeriesSize(scan)
        self.magnifications = self.getMagnificationNames()

        self.allowedValueRange = {
            "Dwell Time": self.getAllowedDwellTime(scan),
            "Scan Range": self.getMaximumScanRange(scan),
            "Scan Resolution": self.getAllowedScanRes(scan),
        }

    @classmethod
    def fromAcquisition(cls, name, tia_handle):
        tia_handle.ScanningServer(name)
        return ScanningServer(name, tia_handle)

    def setScanningServer(self, kwargs: dict):
        self.handle.setScanningServer(kwargs)
        self.updateScanningServer()

    def setAcquireMode(self, mode):
        if mode == "Continuous":
            val = 0
        elif mode == "Single":
            val = 1

        self.setScanningServer({"AcquireMode": val})
        self.acquireMode = mode

    def getAcquireMode(self, dico=None):
        if dico:
            mode = dico["AcquireMode"]
        else:
            mode = self.handle.getScanningServer()["AcquireMode"]

        if mode == 0:
            return "Continuous"
        elif mode == 1:
            return "Single"

    def setFrameShape(self, width, height):
        self.setScanningServer({"FrameWidth": width, "FrameHeight": height})
        self.frameShape = (width, height)

    def getFrameShape(self, dico=None):
        if dico:
            scan = dico
        else:
            scan = self.handle.getScanningServer()
        width = scan["FrameWidth"]
        height = scan["FrameHeight"]
        return (width, height)

    def setDwellTime(self, time):
        self.setScanningServer({"DwellTime": time})
        self.dwellTime = time

    def getDwellTime(self, dico=None):
        if dico:
            return dico["DwellTime"]
        else:
            return self.handle.getScanningServer()["DwellTime"]

    def setScanResolution(self, res):
        self.setScanningServer({"ScanResolution": res})
        self.scanResolution = res

    def getScanResolution(self, dico=None):
        if dico:
            return dico["ScanResolution"]
        else:
            return self.handle.getScanningServer()["ScanResolution"]

    def setScanMode(self, mode):
        if mode == "Spot":
            val = 0
        elif mode == "Line":
            val = 1
        elif mode == "Frame":
            val = 2
        self.setScanningServer({"ScanMode": val})
        self.scanMode = mode

    def getScanMode(self, dico=None):
        if dico:
            value = dico["ScanMode"]
        else:
            value = self.handle.getScanningServer()["ScanMode"]

        if value == 0:
            mode = "Spot"
        elif value == 1:
            mode = "Line"
        elif value == 2:
            mode = "Frame"
        return mode

    def setExternalScanState(self, state):
        """
        If ForceExternalScan is true, then the computer controls the microscope scan in any circumstance (external scan is enabled). 
        The native microscope scanned image display (if available) is blanked when external scan is enabled.
        ForceExternalScan is normally false. Then the native microscope scanned image display (if available) is enabled when external scan is not used. 
        Typically, the native microscope scanned image display is enabled after acquiring an image. 
        Be advised that the native microscope scanned image display is disabled whenever TIA is in spot scan mode.
        """
        self.setScanningServer({"ForceExternalScan": state})
        self.externalScan = self.state

    def getExternalScanState(self, dico=None):
        if dico:
            return dico["ForceExternalScan"]
        else:
            return self.handle.getScanningServer()["ForceExternalScan"]

    def setReferencePosition(self, position_object):
        self.handle.setReferencePosition(position_object.name, server="scan")
        self.referencePosition = position_object

    def getReferencePosition(self, dico=None):
        if dico:
            xy = dico["ReferencePosition"]
        else:
            xy = self.handle.getScanningServer()["ReferencePosition"]
        return Position2D("{}_referencePosition".format(self.name), self.handle, xy)

    def setBeamPosition(self, position_object):
        self.handle.setBeamPosition(position_object.name)
        self.beamPosition = position_object

    def getBeamPosition(self, dico=None):
        if dico:
            xy = dico["BeamPosition"]
        else:
            xy = self.handle.getScanningServer()["BeamPosition"]
        return Position2D("{}_beamPosition".format(self.name), self.handle, xy)

    def setDriftRateXY(self, rateX=None, rateY=None):
        if rateX:
            self.setScanningServer({"DriftRateX": rateX})
        if rateY:
            self.setScanningServer({"DriftRateY": rateY})

        self.driftRateXY = (rateX, rateY)

    def getDriftRateXY(self, dico=None):
        if dico:
            scan = dico
        else:
            scan = self.handle.getScanningServer()

        DriftRateX = scan["DriftRateX"]
        DriftRateY = scan["DriftRateY"]
        return (DriftRateX, DriftRateY)

    def setScanRange(self, range_object):
        self.handle.setScanRange(range_object.name)
        self.scanRange = range_object

    def getScanRange(self, dico=None):
        if dico:
            range2d = dico["ScanRange"]
        else:
            range2d = self.handle.getScanningServer()["ScanRange"]
        return Range2D("{}_scanRange".format(self.name), self.handle, **range2d)

    def setSeriesSize(self, size):
        self.setScanningServer({"SeriesSize": size})
        self.seriesSize = size

    def getSeriesSize(self, dico=None):
        if dico:
            return dico["SeriesSize"]
        else:
            return self.handle.getScanningServer()["SeriesSize"]

    def getAllowedDwellTime(self, dico=None):
        if dico:
            return dico["DwellTimeRange"]
        else:
            return self.handle.getScanningServer()["DwellTimeRange"]

    def getMaximumScanRange(self, dico=None):
        if dico:
            return dico["TotalScanRange"]
        else:
            return self.handle.getScanningServer()["TotalScanRange"]

    def getAllowedScanRes(self, dico=None):
        if dico:
            return dico["ScanResolutionRange"]
        else:
            return self.handle.getScanningServer()["ScanResolutionRange"]

    def getMagnificationNames(self):
        return {
            "Imaging": self.handle.MagnificationNames(0),
            "Diffraction": self.handle.MagnificationNames(1),
        }

    """def createMagnification(self,magnification,image_range_object,mode):
        '''
        magnification: The microscope magnification for which to create the calibration.
        image_range_object: A Range2D object. The actual total total range of the imaging hardware at the given magnification.
        mode: The microscope mode for the magnification calibration. ("Imaging","Diffraction")
        '''
        if mode == 'Imaging':
            value = 0
        elif mode == 'Diffraction':
            value = 1
        self.handle.CreateMagnification(magnification,image_range_object.handle,value)
        self.magnifications = self.getMagnificationNames()
    
    def deleteMagnification(self,magnification,mode):
        if mode == 'Imaging':
            value = 0
        elif mode == 'Diffraction':
            value = 1
        self.handle.DeleteMagnification(magnification,value)
        self.magnifications = self.getMagnificationNames()"""


class Position2D:
    def __init__(self, name, tia_handle, xy):
        self.handle = tia_handle
        self.name = name
        self.xy = xy

    @classmethod
    def fromInterface(cls, varname, tia_handle, x, y):
        tia_handle.Position2D(varname, x, y)
        return cls(varname, tia_handle, (x, y))


class PositionCollection:
    def __init__(self, name, tia_handle, Items=[], Count=0):
        self.handle = tia_handle
        self.name = name
        self.positions = Items
        self.npositions = Count

    def updatePositions(self):
        poscoll = self.handle.getVariable(self.name)
        self.positions = poscoll["Items"]
        self.npositions = poscoll["Count"]

    @classmethod
    def fromInterface(cls, varname, tia_handle):
        tia_handle.PositionCollection(varname)
        return cls(varname, tia_handle)

    def addPosition(self, x, y):
        self.handle.AddPosition(self.name, x, y)
        self.positions.append((x, y))
        self.npositions = len(self.positions)

    def setLinePattern(self, x0, y0, x1, y1, n):
        self.handle.SetLinePattern(self.name, x0, y0, x1, y1, n)
        # SetLinePattern clears the initial position collection
        self.updatePositions()

    def setGridPattern(self, range_object_name, nX, nY):
        self.handle.SetGridPattern(self.name, range_object_name, nX, nY)
        # SetGridPattern clears the initial position collection
        self.updatePositions()

    def subCollection(self, subColl_varname, index_start, index_stop):
        self.handle.Selection(subColl_varname, self.name, index_start, index_stop)
        subColl = self.__class__(self, subColl_varname, self.handle)
        subColl.updatePositions()
        return subColl_varname

    def clear(self):
        self.handle.RemoveAll(self.name)


class SpatialUnit:
    def __init__(self, name, tia_handle, unit_string=None):
        self.handle = tia_handle
        self.name = name
        self.unit = unit_string

    @classmethod
    def fromInterface(cls, varname, tia_handle, unit_string):
        """
        Valid unit strings are: "m", "mm", "um", "nm", "A", "1/m", "1/mm", "1/um", "1/nm", "1/A"
        """
        tia_handle.SpatialUnit(varname, unit_string)
        return cls(varname, tia_handle, unit_string)

    def getUnit(self):
        return self.handle.getVariable(self.name)

    """def setUnit(self,unit_string):
        self.handle.UnitString = unit_string
        self.unit = self.getUnit() """


class BeamControl:
    def __init__(self, name, tia_handle, DwellTime=None, PositionCalibrated=None, ScanMode=None):
        self.handle = tia_handle
        self.name = name
        self.dwellTime = DwellTime
        #'PositionCalibrated':
        # True: positions in meter, False: positions as fraction (<=+-1) of max scan range
        self.positionCalibrated = PositionCalibrated
        self.scanMode = ScanMode

    def updateBeamControl(self):
        beamctrl = self.handle.getBeamControl()
        self.dwellTime = self.getDwellTime(beamctrl)
        self.positionCalibrated = self.isPositionCalibrated(beamctrl)

    def __dict__(self):
        return {
            "Dwell time": self.dwellTime,
            "Position calibratied": self.positionCalibrated,
            "Scan mode": self.scanMode,
        }

    @classmethod
    def fromAcquisition(cls, varname, tia_handle):
        tia_handle.BeamControl(varname)
        tia_handle.SetSingleScan()
        return cls(varname, tia_handle, ScanMode="Single")

    def setDwellTime(self, time):
        self.handle.setBeamControl({"DwellTime": time})
        self.dwellTime = time

    def getDwellTime(self, dico=None):
        if dico:
            return dico["DwellTime"]
        else:
            return self.handle.getBeamControl()["DwellTime"]

    def isPositionCalibrated(self, dico=None):
        if dico:
            return dico["PositionCalibrated"]
        else:
            return self.handle.getBeamControl()["PositionCalibrated"]

    def setPositionCalibrationState(self, state):
        self.handle.setBeamControl({"PositionCalibrated": state})
        self.positionCalibrated = state

    def startMoving(self):
        self.handle.StartBeamControl()

    def stopMoving(self):
        self.handle.StopBeamControl()

    def resetBeamPosition(self):
        self.handle.ResetBeamControl()

    def setSingleScan(self):
        self.handle.SetSingleScan()
        self.scanMode = "Single"

    def setContinuousScan(self):
        self.handle.SetContinuousScan()
        self.scanMode = "Continuous"

    def loadPositions(self, position_collection_name):
        self.handle.LoadPositions(position_collection_name)

    def setLineScan(self, start_position_name, end_position_name, n):
        self.handle.SetLineScan(start_position_name, end_position_name, n)

    def setFrameScan(self, range_name, nX, nY):
        """
        If the PositionCalibrated property is set to false, then all positions (X, Y) must satisfy the follwing conditions: -1 <= X <= 1 and -1 <= Y <= 1.
        """
        self.handle.SetFrameScan(range_name, nX, nY)

    def moveBeam(self, x, y):
        """
        X and Y must satisfy the following conditions: -1 <= X <= 1 and -1 <= Y <= 1 when (position calbrated is false)
        Modifies the value of the beam position in the scanning server object
        """
        self.handle.MoveBeam(x, y)

    def canStart(self):
        return self.handle.CanStart()

    def isScanning(self):
        return self.handle.IsScanning()
