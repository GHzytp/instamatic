import logging
import os
import pickle
import sys

import matplotlib.pyplot as plt
import numpy as np
from skimage.registration import phase_cross_correlation

from .filenames import *
from instamatic.utils.fit import fit_affine_transformation
from instamatic import config
from instamatic.image_utils import autoscale
from instamatic.image_utils import imgscale
from instamatic.processing.find_holes import find_holes
from instamatic.tools import find_beam_center
from instamatic.tools import printer
from instamatic.formats import read_image

logger = logging.getLogger(__name__)


class CalibBeamTilt:
    """Simple class to hold the methods to perform transformations from one
    setting to another based on calibration results."""

    def __init__(self, transform, reference_tilt, reference_pixel):
        super().__init__()
        self.transform = transform
        self.reference_tilt = reference_tilt
        self.reference_pixel = reference_pixel
        self.has_data = False

    def __repr__(self):
        return f'CalibBeamTilt(transform=\n{self.transform},\n   reference_tilt=\n{self.reference_tilt},\n   reference_pixel=\n{self.reference_pixel})'

    def beamtilt_to_pixelcoord(self, beamtilt):
        """Converts from beamtilt x,y to pixel coordinates."""
        r_i = np.linalg.inv(self.transform)
        pixelcoord = np.dot(self.reference_tilt - beamtilt, r_i) + self.reference_pixel
        return pixelcoord

    def pixelcoord_to_beamtilt(self, pixelcoord):
        """Converts from pixel coordinates to beamtilt x,y."""
        r = self.transform
        beamtilt = self.reference_tilt - np.dot(pixelcoord - self.reference_pixel, r)
        return beamtilt.astype(int)

    @classmethod
    def from_data(cls, tilts, beampos, reference_tilt, reference_pixel, header=None):
        fit_result = fit_affine_transformation(tilts, beampos)
        r = fit_result.r
        t = fit_result.t

        c = cls(transform=r, reference_tilt=reference_tilt, reference_pixel=reference_pixel)
        c.data_tilts = tilts
        c.data_beampos = beampos
        c.has_data = True
        c.header = header

        return c

    @classmethod
    def from_file(cls, fn=CALIB_BEAMSHIFT):
        """Read calibration from file."""
        import pickle
        try:
            return pickle.load(open(fn, 'rb'))
        except OSError as e:
            prog = 'instamatic.calibrate_beamtilt'
            raise OSError(f'{e.strerror}: {fn}. Please run {prog} first.')

    @classmethod
    def live(cls, ctrl, outdir='.'):
        while True:
            c = calibrate_beamtilt(ctrl=ctrl, save_images=True, outdir=outdir)
            if input(' >> Accept? [y/n] ') == 'y':
                return c

    def to_file(self, fn=CALIB_BEAMSHIFT, outdir='.'):
        """Save calibration to file."""
        fout = os.path.join(outdir, fn)
        pickle.dump(self, open(fout, 'wb'))

    def plot(self, to_file=None, outdir=''):
        if not self.has_data:
            return

        if to_file:
            to_file = f'calib_{beamtilt}.png'

        beampos = self.data_beampos
        tilts = self.data_tilts

        r_i = np.linalg.inv(self.transform)
        beampos_ = np.dot(beampos, r_i)

        plt.scatter(*tilts.T, marker='>', label='Observed pixel tilts')
        plt.scatter(*beampos_.T, marker='<', label='Positions in pixel coords')
        plt.legend()
        plt.title('BeamTilt vs. Direct beam position (Imaging)')
        if to_file:
            plt.savefig(os.path.join(outdir, to_file))
            plt.close()
        else:
            plt.show()

    def center(self, ctrl):
        """Return beamtilt values to center the beam in the frame."""
        pixel_center = [val / 2.0 for val in ctrl.cam.getImageDimensions()]

        beamtilt = self.pixelcoord_to_beamtilt(pixel_center)
        if ctrl:
            ctrl.beamtilt.set(*beamtilt)
        else:
            return beamtilt


def calibrate_beamtilt_live(ctrl, gridsize=None, stepsize=None, save_images=False, outdir='.', **kwargs):
    """Calibrate pixel->beamtilt coordinates live on the microscope.

    ctrl: instance of `TEMController`
        contains tem + cam interface
    gridsize: `int` or None
        Number of grid points to take, gridsize=5 results in 25 points
    stepsize: `float` or None
        Size of steps for beamtilt along x and y
        Defined at a magnification of 2500, scales stepsize down for other mags.
    exposure: `float` or None
        exposure time
    binsize: `int` or None

    In case paramers are not defined, camera specific default parameters are retrieved

    return:
        instance of Calibration class with conversion methods
    """

    exposure = kwargs.get('exposure', ctrl.cam.default_exposure)
    binsize = kwargs.get('binsize', ctrl.cam.default_binsize)

    if not gridsize:
        gridsize = config.camera.calib_beamtilt.get('gridsize', 5)
    if not stepsize:
        stepsize = config.camera.calib_beamtilt.get('stepsize', 250)

    img_cent, h_cent = ctrl.get_image(exposure=exposure, binsize=binsize, comment='Beam in center of image')
    x_cent, y_cent = beamtilt_cent = np.array(h_cent['BeamTilt'])

    magnification = h_cent['Magnification']
    stepsize = 2500.0 / magnification * stepsize

    print(f'Gridsize: {gridsize} | Stepsize: {stepsize:.2f}')

    img_cent, scale = autoscale(img_cent)

    outfile = os.path.join(outdir, 'calib_beamcenter') if save_images else None

    pixel_cent = find_beam_center(img_cent) * binsize / scale

    print('Beamtilt: x={} | y={}'.format(*beamtilt_cent))
    print('Pixel: x={} | y={}'.format(*pixel_cent))

    tilts = []
    beampos = []

    n = int((gridsize - 1) / 2)  # number of points = n*(n+1)
    x_grid, y_grid = np.meshgrid(np.arange(-n, n + 1) * stepsize, np.arange(-n, n + 1) * stepsize)
    tot = gridsize * gridsize

    i = 0
    for dx, dy in np.stack([x_grid, y_grid]).reshape(2, -1).T:
        ctrl.beamtilt.set(x=x_cent + dx, y=y_cent + dy)

        printer('Position: {}/{}: {}'.format(i + 1, tot, ctrl.beamtilt))

        outfile = os.path.join(outdir, 'calib_beamtilt_{i:04d}') if save_images else None

        comment = f'Calib image {i}: dx={dx} - dy={dy}'
        img, h = ctrl.get_image(exposure=exposure, binsize=binsize, out=outfile, comment=comment, header_keys='BeamTilt')
        img = imgscale(img, scale)

        tilt, error, phasediff = phase_cross_correlation(img_cent, img, upsample_factor=10)

        beamtilt = np.array(h['BeamTilt'])
        beampos.append(beamtilt)
        tilts.append(tilt)

        i += 1

    print('')
    # print "\nReset to center"

    ctrl.beamtilt.set(*beamtilt_cent)

    # correct for binsize, store in binsize=1
    tilts = np.array(tilts) * binsize / scale
    beampos = np.array(beampos) - np.array(beamtilt_cent)

    c = CalibBeamTilt.from_data(tilts, beampos, reference_tilt=beamtilt_cent, reference_pixel=pixel_cent, header=h_cent)

    # Calling c.plot with videostream crashes program
    # if not hasattr(ctrl.cam, "VideoLoop"):
    #     c.plot()

    return c


def calibrate_beamtilt_from_image_fn(center_fn, other_fn):
    """Calibrate pixel->beamtilt coordinates from a set of images.

    center_fn: `str`
        Reference image with the beam at the center of the image
    other_fn: `tuple` of `str`
        Set of images to cross correlate to the first reference image

    return:
        instance of Calibration class with conversion methods
    """
    print()
    print('Center:', center_fn)

    img_cent, h_cent = read_image(center_fn)
    beamtilt_cent = np.array(h_cent['BeamTilt'])

    img_cent, scale = autoscale(img_cent, maxdim=512)

    binsize = h_cent['ImageBinsize']

    holes = find_holes(img_cent, plot=False, verbose=False, max_eccentricity=0.8)
    pixel_cent = np.array(holes[0].centroid) * binsize / scale

    print('Beamtilt: x={} | y={}'.format(*beamtilt_cent))
    print('Pixel: x={:.2f} | y={:.2f}'.format(*pixel_cent))

    tilts = []
    beampos = []

    for fn in other_fn:
        img, h = read_image(fn)
        img = imgscale(img, scale)

        beamtilt = np.array(h['BeamTilt'])
        print()
        print('Image:', fn)
        print('Beamtilt: x={} | y={}'.format(*beamtilt))

        tilt, error, phasediff = phase_cross_correlation(img_cent, img, upsample_factor=10)

        beampos.append(beamtilt)
        tilts.append(tilt)

    # correct for binsize, store as binsize=1
    tilts = np.array(tilts) * binsize / scale
    beampos = np.array(beampos) - beamtilt_cent

    c = CalibBeamTilt.from_data(tilts, beampos, reference_tilt=beamtilt_cent, reference_pixel=pixel_cent, header=h_cent)
    c.plot()

    return c


def calibrate_beamtilt(center_fn=None, other_fn=None, ctrl=None, save_images=True, outdir='.', confirm=True):
    if not (center_fn or other_fn):
        if confirm:
            ctrl.store('calib_beamtilt')
            while True:
                inp = input("""
Calibrate beamtilt
-------------------
 1. Go to desired magnification (e.g. 2500x)
 2. Select desired beam size (BRIGHTNESS)
 3. Center the beam with beamtilt

 >> Press <ENTER> to start >> \n""")
                if inp == 'x':
                    ctrl.restore()
                    ctrl.close()
                    sys.exit()
                elif inp == 'r':
                    ctrl.restore('calib_beamtilt')
                elif inp == 'go':
                    break
                elif not inp:
                    break
        calib = calibrate_beamtilt_live(ctrl, save_images=save_images, outdir=outdir)
    else:
        calib = calibrate_beamtilt_from_image_fn(center_fn, other_fn)

    logger.debug(calib)

    calib.to_file(outdir=outdir)
    # calib.plot(to_file=True, outdir=outdir)  # FIXME: this causes a freeze

    return calib


def main_entry():
    import argparse
    description = """Program to calibrate the beamtilt of the microscope (Deprecated)."""

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('args',
                        type=str, nargs='*', metavar='IMG',
                        help='Perform calibration using pre-collected images. The first image must be the center image used as the reference position. The other images are cross-correlated to this image to calibrate the translations. If no arguments are given, run the live calibration routine.')

    options = parser.parse_args()
    args = options.args

    if not args:
        from instamatic import TEMController
        ctrl = TEMController.initialize()
        calibrate_beamtilt(ctrl=ctrl, save_images=True)
    else:
        center_fn = args[0]
        other_fn = args[1:]
        calibrate_beamtilt(center_fn=center_fn, other_fn=other_fn)


if __name__ == '__main__':
    main_entry()
