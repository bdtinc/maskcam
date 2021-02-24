################################################################################
# Copyright (c) 2020-2021, Berkeley Design Technology, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
################################################################################

CODEC_MP4 = "MP4"
CODEC_H265 = "H265"
CODEC_H264 = "H264"
USBCAM_PROTOCOL = "v4l2://"  # Invented by us since there's no URI for this
RASPICAM_PROTOCOL = "argus://"  # Invented by us since there's no URI for this
CONFIG_FILE = "maskcam_config.txt"  # Also used in nvinfer element

# Available commands (to send internally, between processes or via MQTT)
CMD_FILE_SAVE = "save_file"
CMD_STREAMING_START = "streaming_start"
CMD_STREAMING_STOP = "streaming_stop"
CMD_INFERENCE_RESTART = "inference_restart"
CMD_FILESERVER_RESTART = "fileserver_restart"
CMD_STATUS_REQUEST = "status_request"
