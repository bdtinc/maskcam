import cv2
import numpy as np

from norfair.drawing import Color


class YoloAdaptor:
    def __init__(self, config):
        self.detection_threshold = config["detection_threshold"]
        self.distance_threshold = config["distance_threshold"]

    def classify_people(self, tracked_people):
        p_masks = []
        for d in tracked_people:
            meta = d.last_detection.data
            if meta["label"] == "mask":
                p_mask = float(meta["p"])
            elif meta["label"] == "no_mask" or meta["label"] == "misplaced":
                p_mask = 1 - float(meta["p"])
            elif meta["label"] == "not_visible":
                p_mask = 0.5
            else:
                raise  # Unknown label
            p_masks.append(p_mask)
        return p_masks

    def keypoints_distance(self, detected_pose, tracked_pose):
        detected_points = detected_pose.points
        estimated_pose = tracked_pose.estimate
        min_box_size = min(
            max(
                detected_points[1][0] - detected_points[0][0],  # x2 - x1
                detected_points[1][1] - detected_points[0][1],  # y2 - y1
                1,
            ),
            max(
                estimated_pose[1][0] - estimated_pose[0][0],  # x2 - x1
                estimated_pose[1][1] - estimated_pose[0][1],  # y2 - y1
                1,
            ),
        )
        mean_distance_normalized = (
            np.mean(np.linalg.norm(detected_points - estimated_pose, axis=1)) / min_box_size
        )
        return mean_distance_normalized

    def person_has_face(self, person):
        return person.last_detection.data["label"] != "not_visible"

    def get_person_head(self, person):
        if person.live_points.sum() < 2:
            return None
        p1, p2 = person.estimate.astype(int)
        return (tuple(p1), tuple(p2))

    def draw_raw_detections(self, frame, detections):
        for d in detections:
            p1, p2 = d.points.astype(int)
            bbox = (tuple(p1), tuple(p2))
            label = d.data["label"]
            p = float(d.data["p"])
            color = (
                Color.green
                if label == "mask"
                else (
                    Color.red
                    if label == "no_mask"
                    else (Color.yellow if label == "misplaced" else Color.white)
                )
            )
            cv2.rectangle(frame, bbox[0], bbox[1], color, 1)
            cv2.putText(
                frame,
                f"{label}: {p:.2f}",
                (bbox[0][0], bbox[0][1] - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )
            # # Draw debugging info
            # cv2.putText(
            #     frame,
            #     f"width: {bbox[1][0] - bbox[0][0]}",
            #     (bbox[1][0], bbox[1][1] + 10),
            #     cv2.FONT_HERSHEY_SIMPLEX,
            #     0.5,
            #     color,
            #     1,
            #     cv2.LINE_AA,
            # )


