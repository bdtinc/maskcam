# Custom Container Development
The MaskCam code in this repository can be used as a starting point for developing your own smart camera application. If you'd like to develop a custom application (for example, a dog detector that counts how many dogs walk past your house and reports the count to a server), you can build your own container that has the custom code, files, and packages used for your unique application. This page gives instructions on how to build a custom container, rather than downloading our pre-built container from Docker. 

This page is split in to two sections:
- [How to Build Your Own Container from Source on the Jetson Nano](#how-to-build-your-own-container-from-source-on-the-jetson-nano)
- [How to Use Your Own Detection Model](#how-to-use-your-own-detection-model)

## How to Build Your Own Container from Source on the Jetson Nano
The easiest way to get Maskcam running or set up for development purposes, is by using a container like the one provided in the main [Dockerfile](Dockerfile), which provides the right versions of the OS (Ubuntu 18.04 / Bionic Beaver) and all the system level packages required (mainly NVIDIA L4T packages, GStreamer and DeepStream among others).

For development, you could make modifications to the code or the container definition, and then rebuild locally using:
```
docker build . -t maskcam_custom
```

The above building step could be executed in the target Jetson Nano device (easier), or in another development environment (i.e: pushing the result to [Docker Hub](https://hub.docker.com/) and then pulling from device).

Either way, once the image is ready on the device, remember to run the container using the `--runtime nvidia` and `--privileged` flags (to access the camera device), and mapping the used ports (MQTT -1883-, static file serving -8080- and streaming -8554-, as defined in [maskcam_config.txt](maskcam_config.txt)):
```
docker run --runtime nvidia --privileged --rm -it -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam_custom
```

If you still want to better understand some of the [Dockerfile](Dockerfile) steps, or you need to run without a container and are willing to deal with version conflicts, please see the dependencies manual installation and building instructions at [docs/Manual-Dependency-Installation.md](docs/Manual-Dependencies-Installation.md)

## How to Use Your Own Detection Model
As mentioned above, MaskCam is a reference design for smart camera applications that need to perform computer vision tasks on the edge. Specifically, those involving **Object Detection** (for which you'll need a TensorRT engine) and **Tracking** (for which we use [Norfair](https://github.com/tryolabs/norfair)).

Depending on the degree of similarity with this particular use case, you might need to just change the configuration file or some parts of the source code.

### Changing the DeepStream model
If you train a new model that is compatible with DeepStream, and has exactly the same (or a subset of the) object classes that are used in this project (`mask`, `no_mask`, `not_visible`, `misplaced`), then you only need to edit the configuration file.

In particular, you should change only the corresponding parts of the [maskcam_config.txt](maskcam_config.txt) file, which are under the `[property]` section, and make them match your app's configuration parameters (usually under a file `config_infer_primary.txt` in NVIDIA sample apps). You should not need to change any of the `[face-processor]`, `[mqtt]` or `[maskcam]` sections of the config file, in order to use a new compatible model. Also, note that the `interval` parameter of that section will be ignored when `inference-interval-auto` is enabled.

As an example, you'll find there's commented code showing how to use a `Detectnet_v2` model like the one trained using the [NVIDIA facemask app](https://github.com/NVIDIA-AI-IOT/face-mask-detection), but after converting the label names as mentioned above.

Check the [DeepStream docs](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_using_custom_model.html) for more information about how to convert a model in order to use it with DeepStream (in particular, the `nvinfer` GStreamer plugin).

Remember to include your new model engine file in the [Dockerfile](Dockerfile) before building the container!

### Changing the object labels
If your custom model does not have exactly the same label names, you should edit the [maskcam_inference.py](maskcam/maskcam_inference.py) file, and change the constants `LABEL_MASK`, `LABEL_NO_MASK`, `LABEL_MISPLACED` and `LABEL_NOT_VISIBLE`, to match your needs.

If your application has nothing to do with detecting face masks, then you'll probably need to change many other parts of the source code for this application, but a good place to start is the `FaceMaskProcessor` class definition, used in the same inference file, which contains all the code related to the DeepStream pipeline.
