mkdir -p backup
LD_LIBRARY_PATH=/usr/local/cuda-9.0/lib64/ ./darknet detector train data/obj.data facemask-yolov4-tiny.cfg yolov4-tiny.conv.29 -dont_show -mjpeg_port 8090 -map
