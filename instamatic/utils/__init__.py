import ctypes
import os

from functools import wraps
from contextlib import redirect_stderr, redirect_stdout

def is_admin():
    """Check if the current python instance has admin rights."""
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

    return is_admin

def suppress_stderr(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with open(os.devnull, 'w') as devnull:
            with redirect_stderr(devnull):
                func(*args, **kwargs)
    return wrapper

def suppress_stdout(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with open(os.devnull, 'w') as devnull:
            with redirect_stdout(devnull):
                func(*args, **kwargs)
    return wrapper