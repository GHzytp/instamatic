import shutil
from math import sin
from pathlib import Path

from instamatic import config
from instamatic.config.utils import yaml
from instamatic.tools import relativistic_wavelength


def get_tvips_calibs(ctrl, rng: list, mode: str, wavelength: float) -> dict:
    """Loop over magnification ranges and return calibrations from EMMENU."""

    if mode == 'diff':
        print('Warning: Pixelsize can be a factor 10 off in diff mode (bug in EMMENU)')

    calib_range = {}

    binning = ctrl.cam.getBinning()

    ctrl.mode.set(mode)

    for i, mag in enumerate(rng):
        ctrl.magnification.index = i
        d = ctrl.cam.getCurrentCameraInfo()

        img = ctrl.get_image(exposure=10)  # set to minimum allowed value
        index = ctrl.cam.get_image_index()
        v = ctrl.cam.getEMVectorByIndex(index)

        PixelSizeX = v['fImgDistX']
        PixelSizeY = v['fImgDistY']

        assert PixelSizeX == PixelSizeY, 'Pixelsizes differ in X and Y direction?! (X: {PixelSizeX} | Y: {PixelSizeY})'

        if mode == 'diff':
            pixelsize = sin(PixelSizeX / 1_000_000) / wavelength  # µrad/px -> rad/px -> px/Å
        else:
            pixelsize = PixelSizeX

        calib_range[mag] = pixelsize

        # print("mode", mode, "mag", mag, "pixelsize", pixelsize)

    return calib_range


def choice_prompt(choices: list = [], default=None, question: str = 'Which one?'):
    """Simple cli to prompt for a list of choices."""
    print()

    try:
        default_choice = choices.index(default)
        suffix = f' [{default}]'
    except ValueError:
        default_choice = 0
        suffix = f''

    for i, choice in enumerate(choices):
        print(f'{i+1: 2d}: {choice}')

    q = input(f'\n{question}{suffix} >> ')
    if not q:
        q = default_choice
    else:
        q = int(q) - 1

    picked = choices[q]

    # print(choices, picked)
    print(picked)

    return picked


def main():
    import argparse

    description = """
This tool will help to set up the configuration files for `instamatic`.
It establishes a connection to the microscope and reads out the camera lengths and magnification ranges.
"""

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    options = parser.parse_args()

    # Connect to microscope

    tem_name = input('Input the name of the TEM (manufacturer_model_institution): ')

    tem_interface_name = choice_prompt(choices='jeol fei simulate'.split(),
                             default='simulate',
                             question='Which microscope interface can I connect to?')

    # Connect to camera
    # Fetch camera config

    drc = Path(__file__).parent
    choices = list(drc.glob('camera/*.yaml'))
    choices_name = list(map(lambda x: x.name.split('.')[0], choices))
    choices_name.append(None)
    choices.append(None)

    cam_name = choice_prompt(choices=choices_name,
                               default=None,
                               question='Which camera type do you want to use (select closest one and modify if needed)?')

    cam_config = choices[choices_name.index(cam_name)]

    cam_interface_name = choice_prompt(choices=[None, 'DM', 'gatan', 'tvips', 'simulate'],
                             default='simulate',
                             question='Which camera can I connect to?')

    
    # Instantiate microscope / camera connection

    from instamatic.TEMController.microscope import get_tem
    from instamatic.camera.camera import get_cam
    from instamatic.TEMController.TEMController import TEMController

    cam = get_cam(cam_interface_name)(cam_name) if cam_interface_name else None
    tem = get_tem(tem_interface_name)()

    ctrl = TEMController(tem=tem, cam=cam)

    try:
        ranges = ctrl.magnification.get_ranges()
    except BaseException:
        print('Warning: Cannot access magnification ranges')
        ranges = {}

    ht = ctrl.high_tension  # in V

    wavelength = relativistic_wavelength(ht)

    tem_config = {}
    tem_config['interface'] = tem_interface_name
    tem_config['wavelength'] = wavelength
    if tem_interface_name == 'jeol':
        try:
            neutral_obj_ranges = ctrl.tem.getNeutralObjRanges()
        except BaseException:
            print('Warning: Cannot access objective lense or magnification')
            neutral_obj_ranges = {}

        tem_config['neutral'] = {}
        tem_config['neutral']['objective'] = {}
        tem_config['neutral']['objective']['mag1'] = neutral_obj_ranges
    elif tem_interface_name == 'fei':
        holder_name = input('Holder name: ')
        if holder_name != '':
            x_limit = input('Stage limit x (xmin xmax): ')
            x = [int(x_limit.split(' ')[0]), int(x_limit.split(' ')[-1])]
            y_limit = input('Stage limit y (ymin ymax): ')
            y = [int(y_limit.split(' ')[0]), int(y_limit.split(' ')[-1])]
            z_limit = input('Stage limit z (zmin zmax): ')
            z = [int(z_limit.split(' ')[0]), int(z_limit.split(' ')[-1])]
            a_limit = input('Stage limit a (amin amax): ')
            a = [int(a_limit.split(' ')[0]), int(a_limit.split(' ')[-1])]
            b_limit = input('Stage limit b (bmin bmax): ')
            if len(b_limit) != 0:
                b = [int(b_limit.split(' ')[0]), int(b_limit.split(' ')[-1])]
            else:
                b = None
            tem_config['holder'] = holder_name
            tem_config[holder_name] = {}
            tem_config[holder_name]['stageLimit'] = {}
            tem_config[holder_name]['stageLimit']['x'] = x
            tem_config[holder_name]['stageLimit']['y'] = y
            tem_config[holder_name]['stageLimit']['z'] = z
            tem_config[holder_name]['stageLimit']['a'] = a
            tem_config[holder_name]['stageLimit']['b'] = b

        tem_config['SpeedTable'] = {1.00: 21.14,
                                    0.90: 19.61,
                                    0.80: 18.34,
                                    0.70: 16.90,
                                    0.60: 14.85,
                                    0.50: 12.69,
                                    0.40: 10.62,
                                    0.30: 8.20,
                                    0.20: 5.66,
                                    0.10: 2.91,
                                    0.05: 1.48,
                                    0.04: 1.18,
                                    0.03: 0.888,
                                    0.02: 0.593,
                                    0.01: 0.297}

    for mode, rng in ranges.items():
        try:
            tem_config['ranges'][mode] = rng
        except KeyError:
            tem_config['ranges'] = {}
            tem_config['ranges'][mode] = rng

    calib_config = {}
    calib_config['interface'] = f'{tem_name}'
    calib_config['mode'] = 'tem'
    calib_config['camera_rotation_vs_stage_xy'] = 0
    calib_config['stretch_amplitude'] = 0
    calib_config['stretch_azimuth'] = 0
    calib_config['beam_shift_matrix'] = [1, 0, 0, 1]
    calib_config['beam_tilt_matrix_D'] = [1, 0, 0, 1]
    calib_config['beam_tilt_matrix_img'] = [1, 0, 0, 1]
    calib_config['stage_matrix_angle'] = [1, 0, 0, 1]
    calib_config['image_shift1_matrix'] = [1, 0, 0, 1]
    calib_config['image_shift2_matrix'] = [1, 0, 0, 1]
    calib_config['diffraction_shift_matrix'] = [1, 0, 0, 1]
    # Find magnification ranges

    for mode, rng in ranges.items():
        calib_config[mode] = {}

        if cam_interface_name == 'tvips':
            pixelsizes = get_tvips_calibs(ctrl=ctrl, rng=rng, mode=mode, wavelength=wavelength)
        else:
            pixelsizes = {r: 1.0 for r in rng}
        calib_config[mode]['pixelsize'] = pixelsizes

        stagematrices = {r: [1, 0, 0, 1] for r in rng}

        calib_config[mode]['stagematrix'] = stagematrices

    # Write/copy configs

    tem_config_fn = f'{tem_name}_tem.yaml'
    calib_config_fn = f'{tem_name}_{cam_name}_calib.yaml'
    if cam_config:
        cam_config_fn = f'{cam_name}_cam.yaml'
        shutil.copyfile(cam_config, cam_config_fn)

    yaml.dump(tem_config, open(tem_config_fn, 'w'), sort_keys=False)
    yaml.dump(calib_config, open(calib_config_fn, 'w'), sort_keys=False)

    microscope_drc = config.locations['microscope']
    camera_drc = config.locations['camera']
    calibration_drc = config.locations['calibration']
    settings_yaml = config.locations['settings']

    print()
    print('Next step:')
    print(f'1. Wrote files config files:')
    print(f'    Copy {tem_config_fn} -> `{microscope_drc}`')
    print(f'    Copy {calib_config_fn} -> `{calibration_drc}`')
    if cam_config:
        print(f'    Copy {cam_config_fn} -> `{camera_drc}`')
    print()
    print(f'2. In `{settings_yaml}`, change:')
    print(f'    microscope: {tem_name}_tem')
    print(f'    calibration: {tem_name}_calib')
    if cam_config:
        print(f'    camera: {cam_name}_cam')
    print()
    print(f'3. Todo: Check and update the pixelsizes in `{calib_config_fn}`')
    print('    In real space, pixelsize in nm/pixel')
    print('    In reciprocal space, pixelsize in Angstrom^(-1)/pixel')
    print()


if __name__ == '__main__':
    main()
