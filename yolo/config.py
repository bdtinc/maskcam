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

import yaml


class Config:
    def __init__(self, config_file_path):
        # Load config file
        with open(config_file_path, "r") as stream:
            self._config = yaml.load(stream, Loader=yaml.FullLoader)

        # Define colors to be used internally through the app, and also externally if wanted
        self.colors = {
            "green": (0, 128, 0),
            "white": (255, 255, 255),
            "olive": (0, 128, 128),
            "black": (0, 0, 0),
            "navy": (128, 0, 0),
            "red": (0, 0, 255),
            "pink": (128, 128, 255),
            "maroon": (0, 0, 128),
            "grey": (128, 128, 128),
            "purple": (128, 0, 128),
            "yellow": (0, 255, 255),
            "lime": (0, 255, 0),
            "fuchsia": (255, 0, 255),
            "aqua": (255, 255, 0),
            "blue": (255, 0, 0),
            "teal": (128, 128, 0),
            "silver": (192, 192, 192),
        }

    def __getitem__(self, name):
        return self._config[name]
