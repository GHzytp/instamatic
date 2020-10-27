import time
import multiprocessing
from multiprocessing.sharedctypes import RawArray
import threading
import queue
import decimal
import ctypes
import numpy as np
import numexpr as ne
from abc import ABC, abstractmethod

from instamatic.tools import printer
from instamatic.formats import read_tiff
from instamatic import config
from .camera_dm import CameraDM

frame_buffer = multiprocessing.Queue(2)
stream_buffer_proc = multiprocessing.Queue(1024)
stream_buffer_thread = queue.Queue(1024)

image_size = config.camera.dimensions
sharedMem = RawArray(np.ctypeslib.ctypes.c_uint16, image_size[0]*image_size[1])
writeEvent = multiprocessing.Event()
writeEvent.clear()
readEvent = multiprocessing.Event()
readEvent.set()

def start_streaming():
    data_stream = None
    image_stream = None

    if ctypes.windll.user32.MessageBoxW(0, "Please make sure Digital Micrograph is not acquiring images.", "Confirmation", 1) == 1:
        data_stream = CameraDataStream(cam=config.camera.name, frametime=config.settings.default_frame_time)
        data_stream.start_loop()
        if config.settings.buffer_stream_use_thread:
            image_stream = StreamBufferThread(exposure=config.settings.default_frame_time, frametime=config.settings.default_frame_time)
            image_stream.start_loop()
        else:
            image_stream = StreamBufferProc(exposure=config.settings.default_frame_time, frametime=config.settings.default_frame_time)
            image_stream.start_loop()
    # time.sleep(8)
    return data_stream, image_stream

class DataStreamError(RuntimeError):
    pass

class StreamBufferError(RuntimeError):
    pass

class CameraDataStream:
    """
    Start a new process and continuously call getImage to obtain image data from Gatan cameras
    """
    def __init__(self, cam, frametime):
        self.cam = CameraDM(cam, frametime=frametime)
        self.stopProcEvent = multiprocessing.Event()

    def run(self, queue, read_event, write_event, shared_mem):
        #i = 0
        try:
            self.cam.init()
            self.cam.startAcquisition()
            time.sleep(0.5)

            if self.cam.subframetime is None:
                arr = self.cam.getImage(frametime=self.cam.frametime)
                if image_size[0] != arr.shape[0] or image_size[1] != arr.shape[1]:
                    print("Please adjust the dimension in the configuration file.")
                    self.stop()

                while not self.stopProcEvent.is_set():
                    arr = self.cam.getImage(frametime=self.cam.frametime)
                    arr[ne.evaluate('arr < 0')] = 0
                    arr = arr.astype(np.uint16)
                    self.put_arr(queue, arr, read_event, write_event, shared_mem)
                    #if i%10 == 0:
                        #print(f"Number of images produced: {i}")
                    #i = i + 1
            else:
                if self.cam.frametime < self.cam.subframetime:
                    raise ValueError('Frame time should be larger or equal to subframe time.')

                n = decimal.Decimal(str(self.cam.frametime)) / decimal.Decimal(str(self.cam.subframetime))
                if n != int(n):
                    raise ValueError('Frame time should be an integer times of sub frame time')

                arr = self.cam.getImage(frametime=self.cam.subframetime)
                if image_size[0] != arr.shape[0] or image_size[1] != arr.shape[1]:
                    print("Please adjust the dimension in the configuration file.")
                    self.stop()

                if config.camera.processing == 1:
                    try:
                        dark_ref, _ = read_tiff(config.settings.dark_reference)
                        gain_norm, _ = read_tiff(config.settings.gain_normalize) * config.settings.multiplier
                    except:
                        dark_ref = None
                        gain_norm = None

                while not self.stopProcEvent.is_set():
                    tmp_store = np.empty(self.cam.dimensions, dtype=np.float32)
                    for j in range(int(n)):
                        if dark_ref and gain_norm:
                            arr = self.cam.getImage(frametime=self.cam.subframetime)
                            arr = ne.evaluate('(arr - dark_ref) * gain_norm') # 1ms 4ms
                            tmp_store += arr # 0.8ms cost 3.25ms for 1k by 1k image(float64+uint16) 1.87ms(float32+uint16) 
                        else:
                            arr = self.cam.getImage(frametime=self.cam.subframetime)
                            tmp_store += arr
                    tmp_store /= j + 1 # 0.22ms cost 2.56ms for 1k by 1k image(float64) 1.28ms(float32)
                    tmp_store[ne.evaluate('tmp_store < 0')] = 0 # 0.7ms cost 0.97ms for 1k by 1k image(float64) 0.8ms(float32)
                    arr = tmp_store.astype(np.uint16)
                    self.put_arr(queue, arr, read_event, write_event, shared_mem)
                    #if i%10 == 0:
                        #print(f"Number of images produced: {i}")
                    #i = i + 1
        except:
            raise DataStreamError(f'CameraDataStream encountered en error!')
        finally:
            self.cam.stopAcquisition()

    def put_arr(self, queue, arr, read_event, write_event, shared_mem):
        '''Put an array into a queue or a shared memory space'''
        if queue is None:
            arr = arr.reshape(-1)
            read_event.wait()
            memoryview(shared_mem).cast('B').cast('H')[:] = arr[:]
            write_event.set()
            read_event.clear()
        else:
            queue.put(arr)

    def start_loop(self):
        self.stopProcEvent.clear()
        self.proc = multiprocessing.Process(target=self.run, args=(None,readEvent,writeEvent,sharedMem), daemon=True)
        self.proc.start()

    def stop(self):
        if not self.stopProcEvent.is_set():
            self.stopProcEvent.set()
            time.sleep(0.5)
            printer('Stopping the data stream.')
            print()


class StreamBuffer(ABC):
    """
    Base class for StreamBufferProc and StreamBufferThread
    """
    def __init__(self, exposure, frametime):
        self.stopEvent = None

        self.exposure = exposure
        self.frametime = frametime

    @abstractmethod
    def run(self, queue_in, queue_out, read_event, write_event, shared_mem):        
        pass

    def get_arr(self, queue, read_event, write_event, shared_mem):
        '''Get an array from a queue or a shared memory space'''
        if queue is None:
            arr = np.empty(image_size[0]*image_size[1])
            write_event.wait()
            arr[:] = memoryview(shared_mem)[:]
            read_event.set()
            write_event.clear()
            return arr.reshape((image_size[0],image_size[1]))
        else:
            return queue.get()

    @abstractmethod
    def start_loop(self):
        pass

    def stop(self):
        if not self.stopEvent.is_set():
            self.stopEvent.set()
            time.sleep(0.1)
            printer('Stopping the buffer stream.')
            print()

class StreamBufferProc(StreamBuffer):
    """
    Start a new process to buffer and process data stream from camera
    Later it can be used to do more computational entensive online processing, such as drift correction
    However, you need restart the process before you can change the exposure parameter
    """
    def __init__(self, exposure, frametime):
        super().__init__(exposure, frametime)
        self.stopEvent = multiprocessing.Event()

    def run(self, queue_in, queue_out, read_event, write_event, shared_mem):        
        #i = 0
        try:
            self.stopEvent.clear()

            while not self.stopEvent.is_set():
                n = decimal.Decimal(str(self.exposure)) / decimal.Decimal(str(self.frametime))
                if n != int(n):
                    print(f"Exposure should be integer times of frametime.")
                    self.stop()
                    break

                arr = np.empty((image_size[0], image_size[1]), dtype=np.float32)
                t0 = time.perf_counter()
                for j in range(int(n)):
                    if not self.stopEvent.is_set():
                        tmp = self.get_arr(queue_in, read_event, write_event, shared_mem)
                        arr += tmp
                    else:
                        break
                dt = time.perf_counter() - t0
                arr /= (j + 1)
                queue_out.put_nowait(arr.astype(np.uint16))
                #if i%2 == 0:
                    #print(f"Number of images processed: {i} {n}")
                if queue_in is None:
                    print(f"Stream Buffer: {queue_out.qsize()}, Actual time: {dt}")
                else:
                    print(f"Frame Buffer: {queue_in.qsize()}, Stream Buffer: {queue_out.qsize()}, Actual time: {dt}")
                #i = i + 1
        except:
            raise StreamBufferError(f"StreamBuffer encountered en error!")

    def start_loop(self):
        self.proc = multiprocessing.Process(target=self.run, args=(frame_buffer,stream_buffer_proc,readEvent,writeEvent,sharedMem), daemon=True)
        self.proc.start()

class StreamBufferThread(StreamBuffer):
    """
    Start a new thread to buffer and process data stream from camera
    Later it can be used to do more processing, such as drift correction, but not so computational entensive because it will
    slow the response for the main program
    The good thing is you can easily change the exposure time and stop the stream.
    """
    def __init__(self, exposure, frametime):
        super().__init__(exposure, frametime)
        self.stopEvent = threading.Event()
        self.collectEvent = threading.Event()

    def run(self, queue_in, queue_out, read_event, write_event, shared_mem):        
        i = 0
        try:
            self.stopEvent.clear()
            self.collectEvent.set()

            while not self.stopEvent.is_set():
                n = decimal.Decimal(str(self.exposure)) / decimal.Decimal(str(self.frametime))
                if n != int(n):
                    print(f"Exposure should be integer times of frametime.")
                    self.stop()
                    break

                arr = np.empty((image_size[0], image_size[1]), dtype=np.float32)
                t0 = time.perf_counter()
                for j in range(int(n)):
                    if not self.stopEvent.is_set():
                        self.collectEvent.wait()
                        tmp = self.get_arr(queue_in, read_event, write_event, shared_mem)
                        arr += tmp
                    else:
                        break
                dt = time.perf_counter() - t0
                arr /= (j + 1)
                queue_out.put_nowait(arr.astype(np.uint16))
                if i%10 == 0:
                    if queue_in is None:
                        print(f"Stream Buffer: {queue_out.qsize()}, Actual time: {dt}")
                    else:
                        print(f"Frame Buffer: {queue_in.qsize()}, Stream Buffer: {queue_out.qsize()}, Actual time: {dt}")
                i = i + 1
        except:
            raise StreamBufferError(f"StreamBuffer encountered en error!")

    def start_loop(self):
        self.thread = threading.Thread(target=self.run, args=(None,stream_buffer_thread,readEvent,writeEvent,sharedMem), daemon=True)
        self.thread.start()

    def pause_streaming(self):
        self.collectEvent.clear()

    def continue_streaming(self):
        self.collectEvent.set()


if __name__ == '__main__':
    from instamatic import config
    data_stream = CameraDataStream(cam=config.camera.name, frametime=0.3)
    data_stream.start_loop()
    image_stream = StreamBufferThread(exposure=0.6, frametime=0.3)
    image_stream.start_loop()
    from IPython import embed
    embed()
