import sys
import cv2
import torch
import numpy as np
from integrations.yolo.utils_pytorch import load_class_names, post_processing

from norfair.tracker import Detection


class DetectorYoloPytorch:
    """ Adaptor for the pytorch Yolo implementation (Tianxiaomo/pytorch-YOLOv4) """

    def __init__(self, config):
        sys.path.append(config["repo_path"])
        from tool.darknet2pytorch import Darknet  # noqa

        self.model = Darknet(config["config_file"])
        self.detection_threshold = config["detection_threshold"]
        self.nms_threshold = config["nms_threshold"]

        self.model.print_network()
        self.model.load_weights(config["weights_file"])
        print("Loading weights from %s... Done!" % (config["weights_file"]))
        self.use_cuda = config["use_cuda"]
        if self.use_cuda:
            self.model.cuda()
        self.class_names = load_class_names(config["names_file"])

    def detect(self, frame, rescale_detections=True, recolor=False):
        orig_height, orig_width = frame.shape[:2]
        frame = cv2.resize(frame, (self.model.width, self.model.height))
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        detections = self._do_detect(frame)
        width = orig_width if rescale_detections else self.model.width
        height = orig_height if rescale_detections else self.model.height
        dets = []
        for k, d in enumerate(detections[0]):
            d[0] *= width
            d[1] *= height
            d[2] *= width
            d[3] *= height
            p = d[4]
            label = self.class_names[d[6]]
            dets.append(Detection(np.array((d[0:2], d[2:4])), data={"label": label, "p": p},))
        if recolor:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return dets, frame

    def _do_detect(self, img):
        """ Adapted from torch_utils.py -> do_detect() """
        self.model.eval()

        if type(img) == np.ndarray and len(img.shape) == 3:  # cv2 image
            img = torch.from_numpy(img.transpose(2, 0, 1)).float().div(255.0).unsqueeze(0)
        elif type(img) == np.ndarray and len(img.shape) == 4:
            img = torch.from_numpy(img.transpose(0, 3, 1, 2)).float().div(255.0)
        else:
            print("unknow image type")
            exit(-1)

        if self.use_cuda:
            img = img.cuda()
        img = torch.autograd.Variable(img)
        output = self.model(img)
        return post_processing(img, self.detection_threshold, self.nms_threshold, output)
