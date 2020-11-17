# %%
import sys
import yaml
import time

from norfair.video import Video
from norfair.tracker import Tracker
from norfair.drawing import draw_tracked_objects, draw_points, draw_debug_metrics, Color

from face_mask_detector import FaceMaskDetector

# from integrations.yolo.detector_darknet import DetectorDarknet

# from integrations.yolo.detector_pytorch import DetectorYoloPytorch

# Required python tensorrt, usually compiled for python 3.6 at system level
from integrations.yolo.detector_trt import DetectorYoloTRT

from integrations.yolo.yolo_adaptor import YoloAdaptor


# %%
with open("config.yml", "r") as stream:
    # Not using Loader=yaml.FullLoader since it doesn't work on jetson PyYAML version
    config = yaml.load(stream)

# Yolo implementation to use
# detector = DetectorDarknet({**config["yolo_darknet"], **config["yolo_generic"]})

# detector = DetectorYoloPytorch({**config["yolo_pytorch"], **config["yolo_generic"]})

detector = DetectorYoloTRT({**config["yolo_trt"], **config["yolo_generic"]})

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
video = Video(
    input_path=sys.argv[1],
    output_path=config["general"]["output_folder"],  # , codec_fourcc="avc1")
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
timer_logic = 0.0
timer_drawing = 0.0
for k, frame in enumerate(video):

    tick = time.time()

    # Filter parts to track, and also keep detected pose tracked_scores for later use
    detections_tracker, frame_preprocessed = detector.detect(frame, rescale_detections=True)
    timer_yolo += time.time() - tick

    # Tracker update
    tick = time.time()
    tracked_people = tracker.update(
        detections_tracker, period=config["general"]["inference_period"]
    )
    timer_tracker += time.time() - tick

    # Detect and classify faces from tracked poses
    tick = time.time()
    boxes_face_ok, boxes_face_fail = face_mask_detector.detect_face_masks(frame, tracked_people)
    timer_logic += time.time() - tick

    # Drawing functions
    tick = time.time()
    face_mask_detector.draw_margins(frame)
    if config["general"]["draw_classification"]:
        face_mask_detector.draw_classification(frame, tracked_people)
    if config["debug"]["draw_detections"]:  # Using yolo detections
        # draw_points(frame, detections_tracker)
        pose_adaptor.draw_raw_detections(frame, detections_tracker)
    if config["debug"]["draw_face_boxes"]:  # Using tracker
        face_mask_detector.draw_face_boxes(frame, boxes_face_ok, boxes_face_fail)
    if config["debug"]["draw_predictions"]:
        draw_tracked_objects(frame, tracked_people, id_size=0)
    if config["debug"]["draw_tracking_ids"]:
        draw_tracked_objects(
            frame, tracked_people, draw_points=False, id_thickness=1, color=Color.white
        )
    if config["debug"]["draw_tracking_debug"]:
        draw_debug_metrics(frame, tracked_people)

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

    video.write(frame)
    timer_drawing += time.time() - tick

    # Reset counters after first frame to avoid counting model loading
    if k == 0:
        timer_yolo = 0.0
        timer_tracker = 0.0
        timer_logic = 0.0
        timer_drawing = 0.0

if config["debug"]["profiler"]:
    # No need to divide between (k+1) - counters reset on k==0
    timer_total = timer_yolo + timer_tracker + timer_logic + timer_drawing
    print(f"Avg total time/frame:\t{timer_total / k:.4f}s\t| FPS: {k / timer_total:.1f}")
    print(f"Avg yolo time/frame:\t{timer_yolo / k:.4f}s\t| FPS: {k / timer_yolo:.1f}")
    print(f"Avg logic time/frame:\t{timer_logic / k:.4f}s\t| FPS: {k / timer_logic:.1f}")
    print(f"Avg tracker time/frame:\t{timer_tracker / k:.4f}s\t| FPS: {k / timer_tracker:.1f}")
    print(f"Avg drawing time/frame:\t{timer_drawing / k:.4f}s\t| FPS: {k / timer_drawing:.1f}")
