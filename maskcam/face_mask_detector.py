import cv2
import os
import numpy as np

from PIL import Image
from norfair.drawing import Color


class FaceMaskDetector:
    def __init__(
        self,
        config,
        fn_get_person_head,
        fn_person_has_face,
        fn_classify_people,
        files_prefix="",
    ):
        self.fn_get_person_head = fn_get_person_head
        self.fn_person_has_face = fn_person_has_face
        self.fn_classify_people = fn_classify_people

        self.face_min_size = config["face_min_size"]
        self.clf_th_vote = config["threshold_vote"]
        self.classification_voting = config["classification_voting"]
        self.box_no_mask = config["box_no_mask"]
        self.max_votes = config["classification_max_votes"]

        self.left_margin = config["left_margin"]
        self.right_margin = config["right_margin"]
        self.top_margin = config["top_margin"]
        self.bottom_margin = config["bottom_margin"]

        # Statistics panels
        self.stat_font_type = cv2.FONT_HERSHEY_SIMPLEX
        if config["resolution"] == "hd":
            # Bigger faces (HD videos with few people), up to 3 people simultaneusly
            self.stat_font_scale = 0.5
            stat_font_size, _ = cv2.getTextSize(
                text=" ",
                fontFace=self.stat_font_type,
                fontScale=self.stat_font_scale,
                thickness=1,
            )
            self.stat_font_h = stat_font_size[0]
            self.stat_font_w = stat_font_size[1]
            self.stat_margin = 20
            self.stat_face_size = 80
            self.stat_box_w = (
                3 * (self.stat_face_size + self.stat_margin) + self.stat_margin
            )
            self.stat_facebox_h = (
                1 * (self.stat_face_size + self.stat_margin)
                + self.stat_font_h
                + 3 * self.stat_margin
            )
        if config["resolution"] == "4k":
            # Big faces like HD videos, but also bigger margin and graphics
            self.stat_font_scale = 0.8
            stat_font_size, _ = cv2.getTextSize(
                text=" ",
                fontFace=self.stat_font_type,
                fontScale=self.stat_font_scale,
                thickness=1,
            )
            self.stat_font_h = stat_font_size[0]
            self.stat_font_w = stat_font_size[1]
            self.stat_margin = 20
            self.stat_face_size = 100
            self.stat_box_w = (
                5 * (self.stat_face_size + self.stat_margin) + self.stat_margin
            )
            self.stat_facebox_h = (
                1 * (self.stat_face_size + self.stat_margin)
                + self.stat_font_h
                + 3 * self.stat_margin
            )
        else:
            # Smaller faces in side panel, up to 10 people simultaneously in each category
            self.stat_font_scale = 0.5
            stat_font_size, _ = cv2.getTextSize(
                text=" ",
                fontFace=self.stat_font_type,
                fontScale=self.stat_font_scale,
                thickness=1,
            )
            self.stat_font_h = stat_font_size[0]
            self.stat_font_w = stat_font_size[1]
            self.stat_margin = 10
            self.stat_face_size = 30
            self.stat_box_w = (
                8 * (self.stat_face_size + self.stat_margin) + self.stat_margin
            )
            self.stat_facebox_h = (
                1 * (self.stat_face_size + self.stat_margin)
                + self.stat_font_h
                + 2 * self.stat_margin
            )
        self.stat_box_side = config["stat_box_side"]
        self.stat_box_h = (
            1 * (self.stat_face_size + self.stat_margin)
            + self.stat_font_h
            + 3 * self.stat_margin
        )

        self.color_mask = (128, 255, 128)
        self.color_no_mask = (128, 128, 255)
        self.color_unknown = Color.yellow
        self.color_stats = Color.white
        self.text_size = 4
        self.line_width = 2
        self.classifier_input_size = 64
        self.files_prefix = files_prefix
        self.step = 0
        self.people_face_votes_total = (
            dict()
        )  # id: total votes (only people w/face detected)
        self.people_face_votes_mask = (
            dict()
        )  # id: mask votes (only people w/face detected)
        self.people_votes = dict()  # id: classification results
        self.people_face_mask_p = (
            dict()
        )  # id: probability of person having a mask 0-1 (exp filter)
        self.people_detected = set()  # ids of people w/ face detected at least once

        self.has_mask_N = 5

    def init_frame(self):
        self.stat_current_y = 2 * self.stat_margin

    def _get_panel_horizontal_position(self, frame):
        return (
            0
            if self.stat_box_side == "left"
            else frame.shape[1] - self.stat_box_w - 2 * self.stat_margin
        )

    def _register_panel(self, frame, box_height, margin=0):
        """
        Statistics side panel: get the position for new panel box
        and update the current_y location so that the next
        one is placed below it.
        """
        new_pos_x = self._get_panel_horizontal_position(frame) + margin
        new_pos_y = min(
            self.stat_current_y + margin, frame.shape[0] - box_height - margin
        )
        self.stat_current_y = new_pos_y + box_height + margin
        # assert self.stat_current_y <= frame.shape[0]  # Check that box is inside the frame size
        return new_pos_x, new_pos_y

    def _validate_box_position(self, box, frame):
        """ Discard face boxes if some part is out of the scene """
        return not (
            box is None
            or box[0][0] < self.left_margin  # x1
            or box[0][1] < self.top_margin  # y1
            or box[1][0] >= frame.shape[1] - self.right_margin  # x2
            or box[1][1] >= frame.shape[0] - self.bottom_margin  # y2
        )

    def _validate_face_size(self, head_box):
        """ Faces too small for the classifier, but they're still drawn """
        return (head_box[1][0] - head_box[0][0]) >= self.face_min_size

    def detect_face_masks(self, frame, tracked_people):
        self.init_frame()  # This must be done before drawing any panel boxes

        boxes_face_detected = []
        boxes_face_invalid = []
        for person in tracked_people:
            person.last_head_box = None
            person.face_detected = False
            if not hasattr(person, "last_detected_head"):  # Don't empty if exists
                person.last_detected_head = None
            if self.classification_voting:
                if person.id not in self.people_face_votes_mask:
                    self.people_face_votes_mask[person.id] = 0
                    self.people_face_votes_total[person.id] = 0
                    self.people_votes[person.id] = []
                if person.id not in self.people_face_mask_p:
                    self.people_face_mask_p[person.id] = 0.5  # Initial probability

            head_box = self.fn_get_person_head(person)
            if self._validate_box_position(head_box, frame):
                person.last_head_box = head_box
                self.people_detected.add(person.id)

                if self._validate_face_size(head_box):
                    # Copy pixels: even if this is drawn in the end
                    # could be overwritten in async operations like save_faces
                    cropped_head = frame[
                        head_box[0][1] : head_box[1][1], head_box[0][0] : head_box[1][0]
                    ].copy()
                    person.last_detected_head = cropped_head
                    person.face_detected = self.fn_person_has_face(person)

                    if person.face_detected:
                        boxes_face_detected.append(head_box)
                    else:
                        boxes_face_invalid.append(head_box)

        self.classify_people(tracked_people)

        self.step += 1  # Run classify_people() before step > 0

        return boxes_face_detected, boxes_face_invalid

    def draw_classification(self, frame, predicted_people):
        for person in predicted_people:
            if person.last_head_box is not None:
                # Draw classifier label
                no_mask = False
                if self.classification_voting:
                    balance_votes = self.people_face_votes_mask[person.id]
                    total_votes = self.people_face_votes_total[person.id]
                    if balance_votes > 0 and total_votes > 3:
                        color = self.color_mask
                    elif balance_votes < 0 and total_votes > 3:
                        color = self.color_no_mask
                        no_mask = True
                    else:
                        color = self.color_unknown
                    text = f"{np.abs(balance_votes)}"
                else:
                    mask_p = self.people_face_mask_p[person.id]
                    if mask_p >= (1 - self.clf_th_vote):
                        color = self.color_mask
                    elif mask_p <= self.clf_th_vote:
                        color = self.color_no_mask
                        no_mask = True
                    else:
                        color = self.color_unknown
                    text = f"{100*mask_p:.0f}"

                last_headbox = person.last_head_box

                # Draw a box around non-masked people
                if no_mask and self.box_no_mask:
                    cv2.rectangle(frame, last_headbox[0], last_headbox[1], color, 2)

                startX, startY = last_headbox[0]
                endX, endY = last_headbox[1]
                center = ((startX + endX) // 2, startY - 20)
                radius = 5  # Could be related to log(abs(votes)) for example
                cv2.circle(frame, center, radius, color, -1)
                cv2.putText(
                    frame,
                    text,
                    (center[0] - 10, center[1] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    self.text_size / 6,
                    color,
                    self.line_width,
                    cv2.LINE_AA,
                )

    def draw_face_boxes(self, frame, boxes_face_detected, boxes_face_invalid):
        try:
            for head_box in boxes_face_detected:
                cv2.rectangle(frame, head_box[0], head_box[1], Color.white, 2)

            for head_box in boxes_face_invalid:
                cv2.rectangle(frame, head_box[0], head_box[1], Color.black, 2)
        except:
            import ipdb

            ipdb.set_trace()

    def draw_margins(self, frame):

        # Alternative to darker margins. Still slow.
        zones = [
            frame[: self.top_margin, :],
            frame[self.top_margin : -self.bottom_margin, : self.left_margin],
        ]
        # Indexings below don't work with margin = 0
        if self.bottom_margin > 0:
            zones.append(frame[-self.bottom_margin :, :])
        if self.right_margin > 0:
            zones.append(
                frame[self.top_margin : -self.bottom_margin, -self.right_margin :]
            )

        # Darken dividing each pixel by 2
        for zone in zones:
            zone[:, :, :] >>= 1

    def draw_panel_background(self, frame):
        x_start = self._get_panel_horizontal_position(frame)
        x_end = x_start + self.stat_box_w + 2 * self.stat_margin
        # Draw dark margin (divide pixels /2)
        frame[:, x_start:x_end, :] >>= 2

    def _get_statistics(self):
        total_classified = 0
        total_mask = 0
        if self.classification_voting:
            for person_id in self.people_face_votes_total:
                balance_votes = self.people_face_votes_mask[person_id]
                total_votes = self.people_face_votes_total[person_id]
                if total_votes >= 3 and balance_votes != 0:
                    total_classified += 1
                    if balance_votes > 0:
                        total_mask += 1
        else:
            for person_id in self.people_face_votes_total:
                mask_p = self.people_face_mask_p[person_id]
                if mask_p <= self.clf_th_vote:
                    total_classified += 1
                elif mask_p >= 1 - self.clf_th_vote:
                    total_classified += 1
                    total_mask += 1
        total_people = len(self.people_detected)
        return total_people, total_classified, total_mask

    def draw_statistics_text(self, frame):
        total_people, total_classified, total_mask = self._get_statistics()
        mask_percent = 100 * total_mask // total_classified if total_classified else 0
        visible_percent = 100 * total_classified // total_people if total_people else 0

        color = self.color_stats
        margin = self.stat_margin
        box_w = self.stat_box_w
        box_h = self.stat_box_h
        box_x, box_y = self._register_panel(frame, box_h, margin=margin)

        # Rectangle and text
        cv2.rectangle(
            frame, (box_x, box_y), (box_x + box_w, box_y + box_h), color, thickness=1
        )
        for position, text in enumerate(
            [
                "  - Accumulated results -  ",
                f"Total passed: {total_people}",
                f"Visible faces: {total_classified} [{visible_percent}%]",
                f"Wearing mask: {total_mask}  [{mask_percent}%]",
            ]
        ):
            cv2.putText(
                frame,
                text,
                (
                    box_x + margin,
                    box_y + self.stat_font_h * 2 * (position + 1) + margin,
                ),
                self.stat_font_type,
                self.stat_font_scale,
                color,
                1,
                cv2.LINE_AA,
            )

    def draw_statistics_graphics(self, frame):
        total_people, total_classified, total_mask = self._get_statistics()
        mask_fraction = total_mask / total_classified if total_classified else 0
        visible_fraction = total_classified / total_people if total_people else 0

        title_height = int(1.5 * self.stat_font_h + 3 * self.stat_margin)
        radius = (
            self.stat_box_w - self.stat_margin
        ) // 4  # Leave stat_margin between circles
        box_h = 2 * radius + title_height

        # Align from top
        # box_x, box_y = self._register_panel(frame, box_h, margin=0)
        # Align from bottom
        box_x = self._get_panel_horizontal_position(frame)
        box_y = frame.shape[0] - box_h - 2 * self.stat_margin

        cv2.putText(
            frame,
            "Accumulated results",
            (
                box_x + self.stat_margin,
                int(box_y + 2 * self.stat_margin + 1.5 * self.stat_font_h),
            ),
            self.stat_font_type,
            self.stat_font_scale,
            self.color_stats,
            1,
            cv2.LINE_AA,
        )

        # First circle: mask vs. no mask
        center = (box_x + self.stat_margin + radius, box_y + radius + title_height)
        # Counter-clockwise angles
        angle_mask = int(360 * mask_fraction)
        if angle_mask > 0:
            cv2.ellipse(
                frame,
                center,
                (radius, radius),
                270,
                0,
                angle_mask,
                self.color_mask,
                2,
                cv2.LINE_AA,
            )
        if angle_mask < 360:
            cv2.ellipse(
                frame,
                center,
                (radius, radius),
                270,
                angle_mask,
                360,
                self.color_no_mask,
                2,
                cv2.LINE_AA,
            )
        for n_line, text_line in enumerate(
            [
                "Wearing mask: ",
                f" {100*mask_fraction:.0f}%  [{total_mask}/{total_classified}]",
            ]
        ):
            cv2.putText(
                frame,
                text_line,
                (
                    int(center[0] - radius / 1.5),
                    center[1] + (n_line - 1) * (self.stat_font_h + self.stat_margin),
                ),
                self.stat_font_type,
                self.stat_font_scale / 1.5,
                self.color_stats,
                1,
                cv2.LINE_AA,
            )

        # Second circle: visible fraction
        center = (
            box_x + 2 * self.stat_margin + 3 * radius,
            box_y + radius + title_height,
        )
        angle_visible = int(360 * visible_fraction)
        # Non visible people arc
        if angle_visible > 0:
            cv2.ellipse(
                frame,
                center,
                (radius, radius),
                270,
                0,
                angle_visible,
                Color.white,
                2,
                cv2.LINE_AA,
            )
        if angle_visible < 360:
            # Visible people arc
            cv2.ellipse(
                frame,
                center,
                (radius, radius),
                270,
                angle_visible,
                360,
                Color.grey,
                1,
                cv2.LINE_AA,
            )
        for n_line, text_line in enumerate(
            [
                "Visible faces: ",
                f" {100*visible_fraction:.0f}%  [{total_classified}/{total_people}]",
            ]
        ):
            cv2.putText(
                frame,
                text_line,
                (
                    int(center[0] - radius / 1.5),
                    center[1] + (n_line - 1) * (self.stat_font_h + self.stat_margin),
                ),
                self.stat_font_type,
                self.stat_font_scale / 1.5,
                self.color_stats,
                1,
                cv2.LINE_AA,
            )

    def classify_people(self, tracked_people):
        batch_people = []
        if self.fn_classify_people is not None:
            people_with_faces = [
                person for person in tracked_people if person.face_detected
            ]
            batch_mask_scores = self.fn_classify_people(people_with_faces)
            batch_people = [person for person in people_with_faces]

        if batch_people:
            if self.classification_voting:
                self.classify_faces_voting(batch_mask_scores, batch_people)
            else:
                self.classify_faces_p(batch_mask_scores, batch_people)

    def classify_faces_voting(self, batch_mask_scores, batch_people):
        for k, person in enumerate(batch_people):
            self.people_face_votes_total[person.id] += 1
            if batch_mask_scores[k] >= (1 - self.clf_th_vote):
                self.people_face_votes_mask[person.id] += 1
            elif batch_mask_scores[k] <= self.clf_th_vote:
                self.people_face_votes_mask[person.id] -= 1

            # Clip range if max_votes is not null
            if self.max_votes:
                self.people_face_votes_mask[person.id] = np.clip(
                    self.people_face_votes_mask[person.id],
                    -self.max_votes,
                    self.max_votes,
                )

    def classify_faces_p(self, batch_mask_scores, batch_people):
        for k, person in enumerate(batch_people):
            # Exponential moving-average filter: new = (new + (N - 1)*old) / N
            self.people_face_mask_p[person.id] = (
                batch_mask_scores[k]
                + (self.has_mask_N - 1) * self.people_face_mask_p[person.id]
            ) / self.has_mask_N

    def draw_panel_faces(self, frame, tracked_people):
        people_mask = {}
        people_no_mask = {}
        people_unknown = {}
        for person in tracked_people:
            if self.people_face_votes_total[person.id] < 3:
                people_unknown[person.id] = person
                self.people_votes[person.id].append(0)
            elif self.people_face_votes_mask[person.id] > 0:
                people_mask[person.id] = person
                self.people_votes[person.id].append(1)
            else:
                people_no_mask[person.id] = person
                self.people_votes[person.id].append(-1)

        margin = self.stat_margin
        face_size = self.stat_face_size

        for title, people, color in (
            ("Currently no mask", people_no_mask, self.color_no_mask),
            ("Currently wearing mask", people_mask, self.color_mask),
            ("Currently unknown", people_unknown, self.color_unknown),
        ):
            box_x, box_y = self._register_panel(
                frame, self.stat_facebox_h, margin=margin
            )
            self._draw_debug_faces_pos(
                frame,
                people,
                (
                    box_x,
                    box_y,
                    self.stat_box_w,
                    self.stat_facebox_h,
                ),
                (face_size, face_size),
                title,
                color,
                margin,
            )

    def _draw_debug_faces_pos(
        self, frame, people, box_xywh, face_size, title, color, margin
    ):
        box_x, box_y, box_w, box_h = box_xywh
        cv2.putText(
            frame,
            title,
            (
                box_x + margin,
                box_y + self.stat_font_h + margin,
            ),
            self.stat_font_type,
            self.stat_font_scale,
            color,
            1,
            cv2.LINE_AA,
        )

        c_x = box_x + margin
        c_y = box_y + self.stat_font_h + 2 * margin
        for id in sorted(people.keys()):
            person = people[id]
            if person.last_detected_head is not None:
                head_box = person.last_detected_head
                head_box = cv2.resize(
                    head_box, face_size, interpolation=cv2.INTER_LINEAR
                )
                x_end = c_x + head_box.shape[0]
                if x_end > box_x + box_w:  # Enter
                    c_x = box_x + margin
                    x_end = c_x + head_box.shape[0]
                    row_height = margin + head_box.shape[1]
                    _, c_y = self._register_panel(frame, row_height)
                    box_h += row_height

                # Face box
                frame[c_y : c_y + head_box.shape[1], c_x:x_end] = head_box

                # Face votes
                v_x = c_x
                v_y = c_y + head_box.shape[0] + 3
                vote_spacing = 2  # Size in pixels
                vote_sampling = 5  # Sample 1 in 5 votes
                num_votes_span = vote_sampling * self.stat_face_size // vote_spacing
                for vote in self.people_votes[id][-num_votes_span::vote_sampling]:
                    if vote > 0:
                        dot_color = self.color_mask
                    elif vote < 0:
                        dot_color = self.color_no_mask
                    else:
                        dot_color = self.color_unknown
                    cv2.circle(
                        frame, (v_x, v_y), radius=1, color=dot_color, thickness=-1
                    )
                    v_x += vote_spacing

                c_x += head_box.shape[0] + margin

        # Draw box around faces after adding all needed rows
        cv2.rectangle(
            frame,
            (box_x, box_y),
            (box_x + box_w, box_y + box_h + margin),
            color,
            thickness=1,
        )

    def draw_image_into_panel(self, frame, image_path, bottom=True):
        # Read image and resize to fit panel width
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        dst_w = int(self.stat_box_w / 1.5)
        dst_h = (img.shape[0] * dst_w) // img.shape[1]  # keep aspect ratio
        img = cv2.resize(img, (dst_w, dst_h), cv2.INTER_AREA)

        # Overlay in the correct position
        if bottom:
            x = self._get_panel_horizontal_position(frame)
            y = frame.shape[0] - dst_h - 2 * self.stat_margin
        else:
            x, y = self._register_panel(frame, dst_h)
            # Align logo
            y += self.stat_margin
        x += (self.stat_box_w + 2 * self.stat_margin - dst_w) // 2
        self._overlay_png_image(frame[y : y + dst_h, x : x + dst_w], img)

    def _overlay_png_image(self, background, image):
        alpha = image[:, :, 3] / 255.0
        background[:, :, 0] = (1.0 - alpha) * background[:, :, 0] + alpha * image[
            :, :, 0
        ]
        background[:, :, 1] = (1.0 - alpha) * background[:, :, 1] + alpha * image[
            :, :, 1
        ]
        background[:, :, 2] = (1.0 - alpha) * background[:, :, 2] + alpha * image[
            :, :, 2
        ]
