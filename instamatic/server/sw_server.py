import datetime
import json
import logging
import pickle
import queue
import socket
import threading
import traceback

from .serializer import dumper
from .serializer import loader
from instamatic import config
from instamatic.TEMController import Software

condition = threading.Condition()
box = []

HOST = config.settings.tem_server_host
PORT_SW = config.settings.sw_server_port
MAX_IMAGE_SIZE = 4096
BUFSIZE = MAX_IMAGE_SIZE * MAX_IMAGE_SIZE * 4 #1024

default_software = config.settings.software

class SWServer(threading.Thread):
    """TIA communcation server.

    Takes a logger object `log`, command queue `q`, and name of the
    microscope `name` that is used to initialize the connection to the
    microscope. Start the server using `TemServer.run` which will wait
    for items to appear on `q` and execute them on the specified
    microscope instance.
    """

    def __init__(self, log=None, q=None, software_name=None):
        super().__init__()

        self.log = log
        self.q = q

        # self.name is a reserved parameter for threads
        self._software_name = software_name

        self.verbose = False

    def run(self):
        """Start the server thread."""
        self.sw = Software(name=self._software_name, use_server=False)
        if self.sw is not None:
            print(f'Initialized connection to software: {self.sw.name}')

        while True:
            now = datetime.datetime.now().strftime('%H:%M:%S.%f')

            cmd = self.q.get()

            with condition:
                func_name = cmd['func_name']
                args = cmd.get('args', ())
                kwargs = cmd.get('kwargs', {})

                try:
                    ret = self.evaluate(func_name, args, kwargs)
                    status = 200
                except Exception as e:
                    traceback.print_exc()
                    if self.log:
                        self.log.exception(e)
                    ret = (e.__class__.__name__, e.args)
                    status = 500

                box.append((status, ret))
                condition.notify()
                if self.verbose:
                    print(f'{now} | {status} {func_name}: {ret}')

    def evaluate(self, func_name: str, args: list, kwargs: dict):
        """Evaluate the function `func_name` on `self.tem` and call it with
        `args` and `kwargs`."""
        # print(func_name, args, kwargs)
        if hasattr(self.sw, func_name):
            f = getattr(self.sw, func_name)
        ret = f(*args, **kwargs)
        return ret


def handle(conn, q):
    """Handle incoming connection, put command on the Queue `q`, which is then
    handled by TEMServer."""
    with conn:
        while True:
            data = conn.recv(BUFSIZE)
            if not data:
                break

            data = loader(data)

            if data == 'exit':
                break

            if data == 'kill':
                break

            with condition:
                q.put(data)
                condition.wait()
                response = box.pop()
                conn.send(dumper(response))


def main():
    '''
    if config.settings.tem_require_admin:
        from instamatic import admin
        if not admin.is_admin():
            admin.run_as_admin()
    '''

    import argparse

    description = f"""
Connects to the TEM and starts a server for microscope communication. Opens a socket on port {HOST}:{PORT_SW}.

This program initializes a connection to the TEM as defined in the config. On some setups it must be run in admin mode in order to establish a connection (on JEOL TEMs, wait for the beep!). The purpose of this program is to isolate the microscope connection in a separate process for improved stability of the interface in case instamatic crashes or is started and stopped frequently. For running the GUI, the temserver is required. Another reason is that it allows for remote connections from different PCs. The connection goes over a TCP socket.

The host and port are defined in `config/settings.yaml`.

The data sent over the socket is a serialized dictionary with the following elements:

- `func_name`: Name of the function to call (str)
- `args`: (Optional) List of arguments for the function (list)
- `kwargs`: (Optiona) Dictionary of keyword arguments for the function (dict)

The response is returned as a serialized object.
"""

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-s', '--software', action='store', dest='software',
                        help="""Override software to use.""")
    parser.set_defaults(software=default_software)

    options = parser.parse_args()
    software = options.software

    date = datetime.datetime.now().strftime('%Y-%m-%d')
    logfile = config.locations['logs'] / f'instamatic_TEMServer_{date}.log'
    logging.basicConfig(format='%(asctime)s | %(module)s:%(lineno)s | %(levelname)s | %(message)s',
                        filename=logfile,
                        level=logging.DEBUG)
    logging.captureWarnings(True)
    log = logging.getLogger(__name__)

    q = queue.Queue(maxsize=100)

    tem_reader = SWServer(software_name=software, log=log, q=q)
    tem_reader.start()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT_SW))
    s.listen(5)

    log.info(f'Software server listening on {HOST}:{PORT_SW}')
    print(f'Software server listening on {HOST}:{PORT_SW}')

    with s:
        while True:
            conn, addr = s.accept()
            log.info('Connected by %s', addr)
            print('Connected by', addr)
            threading.Thread(target=handle, args=(conn, q)).start()


if __name__ == '__main__':
    main()