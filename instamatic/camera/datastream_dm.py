import time
import multiprocessing
from multiprocessing.sharedctypes import RawArray
import threading
import queue
import decimal
import ctypes
import numpy as np
import numexpr as ne
from skimage.measure import block_reduce
from abc import ABC, abstractmethod

from instamatic.tools import printer
from instamatic.formats import read_tiff
from instamatic import config
from .camera_dm import CameraDM

frame_buffer = multiprocessing.Queue(2)
stream_buffer_proc = multiprocessing.Queue(1024)
stream_buffer_thread = queue.Queue(1024)

image_size = config.camera.dimensions
scale = config.settings.software_binsize
if scale is not None:
    software_binned_image_size = (round(image_size[0]/scale), round(image_size[1]/scale))
    sharedMem = RawArray(np.ctypeslib.ctypes.c_uint16, software_binned_image_size[0]*software_binned_image_size[1])
else:
    software_binned_image_size = None
    sharedMem = RawArray(np.ctypeslib.ctypes.c_uint16, round(image_size[0]*image_size[1]))
sharedMem_processing = RawArray(np.ctypeslib.ctypes.c_uint16, image_size[0]*image_size[1])
writeEvent_processing = multiprocessing.Event()
writeEvent_processing.clear()
readEvent_processing = multiprocessing.Event()
readEvent_processing.set()
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
        processing_stream = ProcessingStream()
        processing_stream.start_loop()
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
            else:
                arr = self.cam.getImage(frametime=self.cam.subframetime)
            if image_size[0] != arr.shape[0] or image_size[1] != arr.shape[1]:
                print("Please adjust the dimension in the configuration file.")
                self.stop()

            while not self.stopProcEvent.is_set():
                if self.cam.subframetime is None:
                    arr = self.cam.getImage(frametime=self.cam.frametime)
                else:
                    arr = self.cam.getImage(frametime=self.cam.subframetime)
                if config.camera.processing != 1:
                    arr[ne.evaluate('arr < 0')] = 0
                    arr = arr.astype(np.uint16)
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
            read_event.clear()
            memoryview(shared_mem).cast('B').cast('H')[:] = arr[:]
            write_event.set()
        else:
            queue.put(arr)

    def start_loop(self):
        self.stopProcEvent.clear()
        self.proc = multiprocessing.Process(target=self.run, args=(None,readEvent_processing,writeEvent_processing,
            sharedMem_processing), daemon=True)
        self.proc.start()

    def stop(self):
        if not self.stopProcEvent.is_set():
            self.stopProcEvent.set()
            time.sleep(0.5)
            printer('Stopping the data stream.')
            print()

class ProcessingStream:
    """
    Start a new process to process the data from camera on the fly.
    """
    def __init__(self):
        self.stopProcEvent = multiprocessing.Event()
        self.subframetime = config.settings.default_subframe_time
        self.frametime = config.settings.default_frame_time

    def run(self, queue, read_event_processing, write_event_processing, read_event, write_event, shared_mem_processing, shared_mem):
        try:
            dark_ref = None
            gain_norm = None

            if config.camera.processing == 1:
                try:
                    dark_ref, _ = read_tiff(config.settings.dark_reference)
                    gain_norm, _ = read_tiff(config.settings.gain_normalize) 
                    gain_norm *= config.settings.multiplier
                except:
                    dark_ref = None
                    gain_norm = None

            arr_obtain = np.zeros(image_size[0]*image_size[1], dtype=np.uint16)

            if self.subframetime is None:
                if dark_ref is not None and gain_norm is not None:
                    while not self.stopProcEvent.is_set():
                        arr = self.get_arr(queue, arr_obtain, read_event_processing, write_event_processing, shared_mem_processing)
                        if scale is not None:
                            arr = block_reduce(arr, block_size=(scale,scale), func=np.mean, cval=0)
                        arr = ne.evaluate('(arr - dark_ref) * gain_norm')
                        #arr = ne.evaluate('(arr - dark_ref) ')
                        arr[ne.evaluate('arr < 0')] = 0
                        arr = arr.astype(np.uint16)
                        self.put_arr(queue, arr, read_event, write_event, shared_mem)
                else:
                    while not self.stopProcEvent.is_set():
                        arr = self.get_arr(queue, arr_obtain, read_event_processing, write_event_processing, shared_mem_processing)
                        if scale is not None:
                            arr = block_reduce(arr, block_size=(scale,scale), func=np.mean, cval=0)
                            arr = arr.astype(np.uint16)
                        self.put_arr(queue, arr, read_event, write_event, shared_mem)
            else:
                if self.frametime < self.subframetime:
                    raise ValueError('Frame time should be larger or equal to subframe time.')

                n = decimal.Decimal(str(self.frametime)) / decimal.Decimal(str(self.subframetime))
                if n != int(n):
                    raise ValueError('Frame time should be an integer times of sub frame time')
                arr = self.get_arr(queue, arr_obtain, read_event_processing, write_event_processing, shared_mem_processing)
                dimensions = arr.shape
                while not self.stopProcEvent.is_set():
                    tmp_store = np.zeros(dimensions, dtype=np.float32)
                    for j in range(int(n)):
                        if dark_ref is not None and gain_norm is not None:
                            arr = self.get_arr(queue, arr_obtain, read_event_processing, write_event_processing, shared_mem_processing)
                            if scale is not None:
                                arr = block_reduce(arr, block_size=(scale,scale), func=np.mean, cval=0)
                            arr = ne.evaluate('(arr - dark_ref) * gain_norm') # 1ms 4ms
                            tmp_store += arr # 0.8ms cost 3.25ms for 1k by 1k image(float64+uint16) 1.87ms(float32+uint16) 
                        else:
                            arr = self.get_arr(queue, arr_obtain, read_event_processing, write_event_processing, shared_mem_processing)
                            if scale is not None:
                                arr = block_reduce(arr, block_size=(scale,scale), func=np.mean, cval=0)
                            tmp_store += arr
                    tmp_store /= j + 1 # 0.22ms cost 2.56ms for 1k by 1k image(float64) 1.28ms(float32)
                    tmp_store[ne.evaluate('tmp_store < 0')] = 0 # 0.7ms cost 0.97ms for 1k by 1k image(float64) 0.8ms(float32)
                    arr = tmp_store.astype(np.uint16)
                    self.put_arr(queue, arr, read_event, write_event, shared_mem)
        except:
            raise DataStreamError(f'CameraDataStream processing encountered en error!')

    def put_arr(self, queue, arr, read_event, write_event, shared_mem):
        '''Put an array into a queue or a shared memory space'''
        if queue is None:
            arr = arr.reshape(-1)
            read_event.wait()
            read_event.clear()
            memoryview(shared_mem).cast('B').cast('H')[:] = arr[:]
            write_event.set()
        else:
            queue.put(arr)

    def get_arr(self, queue, arr, read_event, write_event, shared_mem):
        '''Get an array from a queue or a shared memory space'''
        if queue is None:
            write_event.wait()
            write_event.clear()
            arr[:] = memoryview(shared_mem)[:]
            read_event.set()
            return arr.reshape((image_size[0],image_size[1]))
        else:
            return queue.get()

    def start_loop(self):
        self.stopProcEvent.clear()
        self.proc = multiprocessing.Process(target=self.run, args=(None,readEvent_processing,writeEvent_processing,
            readEvent,writeEvent,sharedMem_processing,sharedMem), daemon=True)
        self.proc.start()

    def stop(self):
        if not self.stopProcEvent.is_set():
            self.stopProcEvent.set()
            time.sleep(0.5)
            printer('Stopping the processing stream.')
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

    def get_arr(self, queue, arr, read_event, write_event, shared_mem):
        '''Get an array from a queue or a shared memory space'''
        if queue is None:
            write_event.wait()
            write_event.clear()
            arr[:] = memoryview(shared_mem)[:]
            read_event.set()
            if software_binned_image_size is None:
                return arr.reshape((image_size[0], image_size[1]))
            else:
                return arr.reshape((software_binned_image_size[0], software_binned_image_size[1]))
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

                if software_binned_image_size is None:
                    arr = np.zeros((image_size[0], image_size[1]), dtype=np.float32)
                    arr_obtain = np.zeros(image_size[0]*image_size[1], dtype=np.uint16)
                else:
                    arr = np.zeros((software_binned_image_size[0], software_binned_image_size[1]), dtype=np.float32)
                    arr_obtain = np.zeros(software_binned_image_size[0]*software_binned_image_size[1], dtype=np.uint16)
                t0 = time.perf_counter()
                for j in range(int(n)):
                    if not self.stopEvent.is_set():
                        tmp = self.get_arr(queue_in, arr_obtain, read_event, write_event, shared_mem)
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

                if software_binned_image_size is None:
                    arr = np.zeros((image_size[0], image_size[1]), dtype=np.float32)
                    arr_obtain = np.zeros(image_size[0]*image_size[1], dtype=np.uint16)
                else:
                    arr = np.zeros((software_binned_image_size[0], software_binned_image_size[1]), dtype=np.float32)
                    arr_obtain = np.zeros(software_binned_image_size[0]*software_binned_image_size[1], dtype=np.uint16)
                t0 = time.perf_counter()
                for j in range(int(n)):
                    if not self.stopEvent.is_set():
                        self.collectEvent.wait()
                        tmp = self.get_arr(queue_in, arr_obtain, read_event, write_event, shared_mem)
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
