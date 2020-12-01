# %%
import os
import sys
import yaml
import time

from norfair.video import Video
from norfair.tracker import Tracker
from norfair.drawing import draw_tracked_objects, draw_debug_metrics, Color

from face_mask_detector import FaceMaskDetector

from integrations.yolo.yolo_adaptor import YoloAdaptor


# %%
def preprocess_frame(frame, config):
    offset_left = config["input_left"]
    offset_top = config["input_top"]
    width = config["input_width"]
    height = config["input_height"]
    if not width:
        width = frame.shape[1] - offset_left
    if not height:
        height = frame.shape[0] - offset_top
    return frame[offset_top : offset_top + height, offset_left : offset_left + width]


with open("config.yml", "r") as stream:
    # Not using Loader=yaml.FullLoader since it doesn't work on jetson PyYAML version
    config = yaml.load(stream)

# Pick YOLO detector implementation to use
yolo_variant = config["yolo_generic"]["yolo_variant"]
yolo_config = {**config[yolo_variant], **config["yolo_generic"]}
print(f"Loading yolo variant: {yolo_variant}")

prefix_trt = "yolo_trt"  # yolo_trt and yolo_trt_tiny
if yolo_variant[: len(prefix_trt)] == prefix_trt:  # Fastest implementation
    # Requires python tensorrt, usually compiled for python 3.6 at system level
    from integrations.yolo.detector_trt import DetectorYoloTRT  # noqa

    detector = DetectorYoloTRT(yolo_config)
elif yolo_variant == "yolo_pytorch":
    from integrations.yolo.detector_pytorch import DetectorYoloPytorch  # noqa

    detector = DetectorYoloPytorch(yolo_config)
else:
    from integrations.yolo.detector_darknet import DetectorDarknet  # noqa

    detector = DetectorDarknet(yolo_config)

# Converter functions from Yolo -> Tracker + FaceMaskDetector
pose_adaptor = YoloAdaptor(config["yolo_generic"])

# In Norfair we trust
tracker = Tracker(
    distance_function=pose_adaptor.keypoints_distance,
    detection_threshold=pose_adaptor.detection_threshold,
    distance_threshold=pose_adaptor.distance_threshold,
    point_transience=8,
    hit_inertia_min=20,
    hit_inertia_max=40,
)

# Video handler (Norfair)
output_codec = (  # Jetson: use VIDEO_CODEC=avc1
    os.environ["VIDEO_CODEC"] if "VIDEO_CODEC" in os.environ else None
)
video = Video(
    input_path=sys.argv[1],
    output_path=config["general"]["output_folder"],
    codec_fourcc=output_codec,
)

# Face masks stuff (classification voting/face extraction/margins/drawing)
face_mask_detector = FaceMaskDetector(
    config=config["face_mask_detector"],
    fn_get_person_head=pose_adaptor.get_person_head,
    fn_person_has_face=pose_adaptor.person_has_face,
    fn_classify_people=pose_adaptor.classify_people,
)

timer_yolo = 0.0  # Reset to 0.0 after first frame to avoid counting model loading
timer_tracker = 0.0
timer_facemask = 0.0
timer_drawing = 0.0
timer_write = 0.0
timer_read = 0.0

# High level components
tracker_enabled = config["debug"]["tracker_enabled"]
facemask_enabled = config["debug"]["facemask_enabled"]
detector_output = config["debug"]["output_detector_resolution"]

t_frame_end = time.time()
for k, frame in enumerate(video):

    tick = time.time()
    timer_read = tick - t_frame_end

    # Crop parts of the frame
    frame = preprocess_frame(frame, config["video"])

    tick = time.time()
    # YOLO object detection (outputs: norfair.tracker.Detection)
    if (
        detector_output
    ):  # Only for debugging purposes: use resized frame in video output
        detections_tracker, frames_resized = detector.detect(
            [frame], rescale_detections=False
        )
        frame = frames_resized[0]
    else:
        detections_tracker, _ = detector.detect([frame], rescale_detections=True)
    detections_tracker = detections_tracker[0]  # Remove batch dimension
    timer_yolo += time.time() - tick

    # Tracker update
    tick = time.time()
    if tracker_enabled:
        tracked_people = tracker.update(
            detections_tracker, period=config["general"]["inference_period"]
        )
    timer_tracker += time.time() - tick

    # Detect and classify faces from tracked poses
    tick = time.time()
    if facemask_enabled and tracker_enabled:
        boxes_face_ok, boxes_face_fail = face_mask_detector.detect_face_masks(
            frame, tracked_people
        )
    timer_facemask += time.time() - tick

    # Drawing functions
    tick = time.time()
    if config["debug"]["draw_detections"]:  # Raw yolo detections
        pose_adaptor.draw_raw_detections(frame, detections_tracker)

    if tracker_enabled:
        if config["debug"]["draw_predictions"]:
            draw_tracked_objects(frame, tracked_people, id_size=0)
        if config["debug"]["draw_tracking_ids"]:
            draw_tracked_objects(
                frame,
                tracked_people,
                draw_points=False,
                id_thickness=1,
                color=Color.white,
            )
        if config["debug"]["draw_tracking_debug"]:
            draw_debug_metrics(frame, tracked_people)

    if facemask_enabled and tracker_enabled:
        face_mask_detector.draw_margins(frame)
        if config["general"]["draw_classification"] and facemask_enabled:
            face_mask_detector.draw_classification(frame, tracked_people)
        if config["debug"]["draw_face_boxes"]:  # Using tracker
            face_mask_detector.draw_face_boxes(frame, boxes_face_ok, boxes_face_fail)

        # Side panel
        panel_faces = config["general"]["draw_panel_faces"]
        panel_text = config["general"]["draw_statistics_text"]
        panel_graph = config["general"]["draw_statistics_graphics"]
        if panel_faces or panel_text or panel_graph:
            face_mask_detector.draw_panel_background(frame)
            if panel_faces:
                face_mask_detector.draw_panel_faces(frame, tracked_people)
            if panel_text:
                face_mask_detector.draw_statistics_text(frame)
            if panel_graph:
                face_mask_detector.draw_statistics_graphics(frame)
    timer_drawing += time.time() - tick

    tick = time.time()
    video.write(frame)
    t_frame_end = time.time()
    timer_write += t_frame_end - tick

    # Reset counters after first frame to avoid counting model loading
    if k == 0:
        timer_yolo = 0.0
        timer_tracker = 0.0
        timer_facemask = 0.0
        timer_drawing = 0.0
        timer_write = 0.0
        timer_read = 0.0

if config["debug"]["profiler"]:
    # No need to divide between (k+1) - counters reset on k==0
    timer_total = (
        timer_yolo
        + timer_tracker
        + timer_facemask
        + timer_drawing
        + timer_write
        + timer_read
    )
    print(f"Frames processed: {k}")
    print(
        f"Avg total time/frame:\t{timer_total / k:.4f}s\t| FPS: {k / timer_total:.1f}"
    )
    print(f"Frames processed: {k}")
    print(
        f"Avg total time/frame:\t{timer_total / k:.4f}s\t| FPS: {k / timer_total:.1f}"
    )
    print(f"Avg yolo time/frame:\t{timer_yolo / k:.4f}s\t| FPS: {k / timer_yolo:.1f}")

    print(
        f"Avg logic time/frame:\t{timer_facemask / k:.4f}s\t| FPS: {k / timer_facemask:.1f}"
    )
    print(
        f"Avg tracker time/frame:\t{timer_tracker / k:.4f}s\t| FPS: {k / timer_tracker:.1f}"
    )
    print(
        f"Avg drawing time/frame:\t{timer_drawing / k:.4f}s\t| FPS: {k / timer_drawing:.1f}"
    )
    print(
        f"Avg reading time/frame:\t{timer_read / k:.4f}s\t| FPS: {k / timer_read:.1f}"
    )
    print(
        f"Avg writing time/frame:\t{timer_write / k:.4f}s\t| FPS: {k / timer_write:.1f}"
    )
    detector.print_profiler()
