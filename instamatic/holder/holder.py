import logging
from instamatic import config

logger = logging.getLogger(__name__)

default_holder_interface = config.microscope.interface

__all__ = ['Holder', 'get_holder']

_holder = None  # store reference of ctrl so it can be accessed without re-initializing

default_holder = config.holder.name

def initialize(holder_name: str = default_holder):
    """"""
    print(f"Holder: {holder_name}")

    global _holder
    holder = _holder = Holder(holder_name)

    return holder

def get_instance():
    """Gets the current `ctrl` instance if it has been initialized, otherwise 
    initialize it using default parameters."""

    global _holder

    if _holder:
        holder = _holder
    else:
        holder = _holder = initialize()

    return holder

def get_holder(interface: str):
    """Grab holder class with the specific 'interface'."""

    if interface == 'xnano':
        from .XNano import XNanoHolder as cls
    else:
        raise ValueError(f'No such holder interface: `{interface}`')

    return cls


def Holder(name: str = None):
    """Generic class to load holder interface class.

    name: str
        Specify which holder to use

    returns: Holder interface class
    """

    if name is None:
        interface = default_holder_interface
        name = interface
    elif name != config.settings.holder:
        config.load_holder_config(holder_name=name)
        interface = config.holder.interface
    else:
        interface = config.holder.interface

    cls = get_holder(interface)
    holder = cls(name=name)

    return holder

def main_entry():
    import argparse
    description = """Program to control external holders."""

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-x', '--position_x', dest='position_x', type=float, nargs=1, metavar='X', default=0.0,
                        help=('Specify the target x position'))

    parser.add_argument('-y', '--position_y', dest='position_y', type=float, nargs=1, metavar='Y', default=0.0,
                        help=('Specify the target y position'))

    parser.add_argument('-z', '--position_z', dest='position_z', type=float, nargs=1, metavar='Z', default=0.0,
                        help=('Specify the target z height'))

    parser.add_argument('-a', '--angle', dest='angle', nargs=1, type=float, metavar='A', default=0.0,
                        help=('Specify the target rotation angle'))

    options = parser.parse_args()
    position_x = options.position_x
    position_y = options.position_y
    position_z = options.position_z
    angle = options.angle


if __name__ == '__main__':
    from IPython import embed
    ctrl = get_instance()
    
    embed(banner1='')
