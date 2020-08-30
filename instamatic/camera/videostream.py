import atexit
import time
import threading
from queue import Empty as Empty

from .camera import Camera
from instamatic import config

# can add a configuration to hide when buffers are not needed
if config.settings.camera[:2]=="DM":
    from .datastream_dm import frame_buffer
    if config.settings.buffer_stream_use_thread:
        from .datastream_dm import stream_buffer_thread as stream_buffer
    else:
        from .datastream_dm import stream_buffer_proc as stream_buffer
    

class GrabbingError(RuntimeError):
    pass

class ImageGrabber:
    """Continuously read out the camera for continuous acquisition.

    When the continousCollectionEvent is set, the camera will set the exposure to `frametime`, otherwise, the default camera exposure is used.

    The callback function is used to send the frame back to the parent routine.
    """

    def __init__(self, cam, callback, frametime: float = 0.05):
        super().__init__()

        self.callback = callback
        self.cam = cam

        self.name = self.cam.name

        self.frame = None
        self.thread = None
        self.stopEvent = None

        self.stash = None

        self.frametime = frametime
        self.exposure = self.frametime
        self.binsize = self.cam.default_binsize

        self.lock = threading.Lock()

        self.stopEvent = threading.Event()
        self.acquireInitiateEvent = threading.Event()
        self.acquireCompleteEvent = threading.Event()
        self.continuousCollectionEvent = threading.Event()

    def run(self, queue):
        #i = 0
        if queue is not None:
            while queue.empty():
                time.sleep(0.1)

        try:
            while not self.stopEvent.is_set():
                if self.acquireInitiateEvent.is_set():
                    self.acquireInitiateEvent.clear()
                    if self.name[:2]=="DM":
                        frame = self.cam.get_from_buffer(queue, exposure=self.exposure, multiple=True, align=False)
                    else:
                        frame = self.cam.getImage(exposure=self.exposure, binsize=self.binsize)
                    self.callback(frame, acquire=True)
                elif not self.continuousCollectionEvent.is_set():
                    if self.name[:2]=="DM":
                        #print(f"frametime: {self.frametime}")
                        frame = self.cam.get_from_buffer(queue, exposure=self.frametime)
                    else:
                        frame = self.cam.getImage(exposure=self.frametime, binsize=self.binsize)
                    self.callback(frame)
                #if i%10 == 0:
                #    print(f"Number of images consumed: {i}")
                #i = i + 1
        except:
            raise GrabbingError(f'ImageGrabber encountered en error!')

    def start_loop(self):
        """Obtaining frames from stream_buffer (after processing)"""
        if not config.settings.simulate and self.name[:2]=="DM":
            self.thread = threading.Thread(target=self.run, args=(stream_buffer,), daemon=True)
        else:
            self.thread = threading.Thread(target=self.run, args=(None,), daemon=True)
        self.thread.start()

    def stop(self):
        self.stopEvent.set()
        #self.thread.join() Cannot use this join in here. Otherwise the closing of the program may not responsive


class VideoStream(threading.Thread):
    """Handle the continuous stream of incoming data from the ImageGrabber."""

    def __init__(self, cam='simulate'):
        threading.Thread.__init__(self)

        if isinstance(cam, str):
            self.cam = Camera(name=cam)
        else:
            self.cam = cam

        self.lock = threading.Lock()

        self.name = self.cam.name
        
        self.frametime = 0.1
        self.grabber = self.setup_grabber()


        self.streamable = self.cam.streamable

        self.start()

    def __getattr__(self, attrname):
        """Pass attribute lookups to self.cam to prevent AttributeError."""
        try:
            return object.__getattribute__(self, attrname)
        except AttributeError as e:
            reraise_on_fail = e
            try:
                return getattr(self.cam, attrname)
            except AttributeError:
                raise reraise_on_fail

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
        grabber = ImageGrabber(self.cam, callback=self.send_frame, frametime=self.frametime)
        atexit.register(grabber.stop)
        return grabber

    def getImage(self, exposure=None, binsize=None):
        current_frametime = self.grabber.frametime

        # set to 0 to prevent it lagging data acquisition
        self.grabber.frametime = 0
        if exposure:
            self.grabber.exposure = exposure
        if binsize:
            self.grabber.binsize = binsize

        self.grabber.acquireInitiateEvent.set()

        self.grabber.acquireCompleteEvent.wait()

        self.grabber.lock.acquire(True)
        frame = self.acquired_frame
        self.grabber.lock.release()

        self.grabber.acquireCompleteEvent.clear()
        self.grabber.frametime = current_frametime
        return frame

    def update_frametime(self, frametime):
        self.frametime = frametime
        self.grabber.frametime = frametime

    def close(self):
        self.grabber.stop()

    def block(self):
        self.grabber.continuousCollectionEvent.set()

    def unblock(self):
        self.grabber.continuousCollectionEvent.clear()

    def continuous_collection(self, exposure=0.1, n=100, callback=None):
        """Function to continuously collect data Blocks the videostream while
        collecting data, and only shows collected images.

        exposure: float
            exposure time
        n: int
            number of frames to collect
            if defined, returns a list of collected frames
        callback: function
            This function is called on every iteration with the image as first argument
            Should return True or False if data collection is to continue
        """
        buffer = []

        go_on = True
        i = 0

        self.block()
        while go_on:
            i += 1

            img = self.getImage(exposure=exposure)

            if callback:
                go_on = callback(img)
            else:
                buffer.append(img)
                go_on = i < n

        self.unblock()

        if not callback:
            return buffer

    def show_stream(self):
        from instamatic.gui import videostream_frame
        t = threading.Thread(target=videostream_frame.start_gui, args=(self, ), daemon=True)
        t.start()


if __name__ == '__main__':
    from multiprocessing import Event
    from .datastream_dm import CameraDataStream

    camera = 'simulate'
    stream = VideoStream(cam=camera)
    #data_stream = CameraDataStream(cam=camera, frametime=0.1)
    #data_stream.start_loop()
    from IPython import embed
    print('test')
    embed()
    #data_stream.stop()
    stream.close()
