# %%
import json
import sys


# %%
def merge_2_into_1(json1, json2):
    # TODO: Remap category IDs according to their name
    # ID offsets to put annotations and images from json2 into json1
    annotations1 = json1["annotations"]
    new_id_ann = 1 + max(*[ann["id"] for ann in annotations1])

    images1 = json1["images"]
    new_id_im = 1 + max(*[im["id"] for im in images1])

    annotations2 = json2["annotations"]
    images2 = json2["images"]

    # Append images2 to images1 and build a map from old to new IDs
    img_ids_1 = {im1["file_name"]: im1["id"] for im1 in images1}
    map_im2_to_im1 = {}
    for im2 in images2:
        if im2["file_name"] in img_ids_1:  # im2 was already in JSON 1
            map_im2_to_im1[im2["id"]] = img_ids_1[im2["file_name"]]
        else:
            map_im2_to_im1[im2["id"]] = new_id_im
            im2["id"] = new_id_im
            images1.append(im2)  # Add to JSON 1
            new_id_im += 1

    for annotation2 in annotations2:
        annotation2["image_id"] = map_im2_to_im1[annotation2["image_id"]]
        annotation2["id"] = new_id_ann
        annotations1.append(annotation2)
        new_id_ann += 1


def print_coco(js):
    print(
        f"Images: {len(js['images'])} "
        f"| Annotations: {len(js['annotations'])} "
        f"| Categories: {len(js['categories'])}"
    )


def open_coco(file_name):
    with open(file_name, "r") as f:
        js = json.load(f)
        print(f"Loaded JSON file: {file_name}")
        print_coco(js)
    return js


# %%
file1 = sys.argv[1]
images_to_remove = sys.argv[2:]

json1 = open_coco(file1)

images = json1["images"]
annotations = json1["annotations"]
new_images = []
new_annotations = []
img_ids_to_keep = set()

# Append images2 to images1 and build a map from old to new IDs
for im in images:
    if im["file_name"] not in images_to_remove:
        img_ids_to_keep.add(im["id"])
        new_images.append(im)

for ann in annotations:
    if ann["image_id"] in img_ids_to_keep:
        new_annotations.append(ann)

json1["images"] = new_images
json1["annotations"] = new_annotations

output_filename = "clean_result.json"
with open(output_filename, "w") as output_file:
    json.dump(json1, output_file)
    print(f"Saved {output_filename}")
    print_coco(json1)
