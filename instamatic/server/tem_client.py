from instamatic import config
from instamatic.TEMController.microscope_client import MicroscopeClient, SoftwareClient

microscope_name= config.microscope.name
software_name = config.settings.software


if __name__ == '__main__':
    # Usage:
    # First run tem_server.py (or `instamatic.temserver.exe`)
    # Second, run tem_client.py

    tem = MicroscopeClient(microscope_name)
    if software_name is not None:
        sw = SoftwareClient(software_name)

    from IPython import embed
    embed()
