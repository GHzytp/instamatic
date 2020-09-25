import atexit
import time
import threading
    
import numpy as np
from .experiment import VIRTUALIMGBUF

class GrabbingError(RuntimeError):
    pass

class ImageGrabber:
    """Continuously read out the camera for continuous acquisition.

    When the continousCollectionEvent is set, the camera will set the exposure to `frametime`, otherwise, the default camera exposure is used.

    The callback function is used to send the frame back to the parent routine.
    """

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

        self.frame = None
        self.thread = None

        self.lock = threading.Lock()

        self.stopEvent = threading.Event()
        self.acquireInitiateEvent = threading.Event()
        self.acquireCompleteEvent = threading.Event()
        self.continuousCollectionEvent = threading.Event()

    def run(self):
        try:
            while not self.stopEvent.is_set():
                if self.acquireInitiateEvent.is_set():
                    self.acquireInitiateEvent.clear()
                    frame = VIRTUALIMGBUF.get()
                    self.callback(frame, acquire=True)
                elif not self.continuousCollectionEvent.is_set():
                    frame = VIRTUALIMGBUF.get()
                    self.callback(frame)
        except:
            raise GrabbingError(f'ImageGrabber encountered en error!')

    def start_loop(self):
        """Obtaining frames from stream_buffer (after processing)"""
        self.thread = threading.Thread(target=self.run, args=(), daemon=True)
        self.thread.start()

    def stop(self):
        self.stopEvent.set()


class VideoStream:
    """Handle the continuous stream of incoming data from the ImageGrabber."""

    def __init__(self):
        threading.Thread.__init__(self)

        self.frame = np.zeros((4, 4))

        self.grabber = self.setup_grabber()

        self.start()

    def start(self):
        self.grabber.start_loop()

    def send_frame(self, frame, acquire=False):
        if acquire:
            self.grabber.lock.acquire(True)
            self.acquired_frame = self.frame = frame
            self.grabber.lock.release()
            self.grabber.acquireCompleteEvent.set()
        else:
            self.grabber.lock.acquire(True)
            self.frame = frame
            self.grabber.lock.release()

    def setup_grabber(self):
        grabber = ImageGrabber(callback=self.send_frame)
        atexit.register(grabber.stop)
        return grabber

    def getImage(self):
        self.grabber.acquireInitiateEvent.set()

        self.grabber.acquireCompleteEvent.wait()

        self.grabber.lock.acquire(True)
        frame = self.acquired_frame
        self.grabber.lock.release()

        self.grabber.acquireCompleteEvent.clear()

        return frame

    def close(self):
        self.grabber.stop()

    def block(self):
        self.grabber.continuousCollectionEvent.set()

    def unblock(self):
        self.grabber.continuousCollectionEvent.clear()


