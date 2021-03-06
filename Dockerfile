# Installs maskcam on a BalenaOS container (devkit or Photon)
FROM balenalib/jetson-nano-ubuntu:20210201

# Don't prompt with any configuration questions
ENV DEBIAN_FRONTEND noninteractive

# Switch the nvidia apt source repos and
# install some utilities

RUN \
    apt-get update && apt-get install -y \
    lbzip2 wget tar python3 git

ENV UDEV=1

# Download and install BSP binaries for L4T 32.4.2
# This is mostly from Balena's Alan Boris at:
# https://github.com/balena-io-playground/jetson-nano-sample-new/blob/master/CUDA/Dockerfile

RUN apt-get update && apt-get install -y wget tar python3 libegl1 && \
    wget https://developer.nvidia.com/embedded/L4T/r32_Release_v4.2/t210ref_release_aarch64/Tegra210_Linux_R32.4.2_aarch64.tbz2 && \
    tar xf Tegra210_Linux_R32.4.2_aarch64.tbz2 && \
    cd Linux_for_Tegra && \
    sed -i 's/config.tbz2\"/config.tbz2\" --exclude=etc\/hosts --exclude=etc\/hostname/g' apply_binaries.sh && \
    sed -i 's/install --owner=root --group=root \"${QEMU_BIN}\" \"${L4T_ROOTFS_DIR}\/usr\/bin\/\"/#install --owner=root --group=root \"${QEMU_BIN}\" \"${L4T_ROOTFS_DIR}\/usr\/bin\/\"/g' nv_tegra/nv-apply-debs.sh && \
    sed -i 's/LC_ALL=C chroot . mount -t proc none \/proc/ /g' nv_tegra/nv-apply-debs.sh && \
    sed -i 's/umount ${L4T_ROOTFS_DIR}\/proc/ /g' nv_tegra/nv-apply-debs.sh && \
    sed -i 's/chroot . \//  /g' nv_tegra/nv-apply-debs.sh && \
    ./apply_binaries.sh -r / --target-overlay && cd .. && \
    rm -rf Tegra210_Linux_R32.4.2_aarch64.tbz2 && \
    rm -rf Linux_for_Tegra && \
    echo "/usr/lib/aarch64-linux-gnu/tegra" > /etc/ld.so.conf.d/nvidia-tegra.conf && \
    echo "/usr/lib/aarch64-linux-gnu/tegra-egl" > /etc/ld.so.conf.d/nvidia-tegra-egl.conf && ldconfig

# Install GStreamer and remove unnecessary files
RUN apt-get install -y \
    libssl1.0.0 \
    libgstreamer1.0-0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    libgstrtspserver-1.0-0 \
    libjansson4=2.11-1 \
    cuda-toolkit-10-2 && \
    ldconfig
RUN \
  rm -rf /usr/src/nvidia/graphics_demos \
     /usr/local/cuda-10.2/samples \
     /usr/local/cuda-10.2/doc 

# Install DeepStream
RUN apt-get install -y deepstream-5.0 && \
  rm -rf /opt/nvidia/deepstream/deepstream-5.0/samples \
     /usr/lib/aarch64-linux-gnu/libcudnn_static_v8.a \
     /usr/lib/aarch64-linux-gnu/libcudnn_cnn_infer_static_v8.a \
     /usr/lib/aarch64-linux-gnu/libnvinfer_static.a \
     /usr/lib/aarch64-linux-gnu/libcudnn_adv_infer_static_v8.a \
     /usr/lib/aarch64-linux-gnu/libcublas_static.a \
     /usr/lib/aarch64-linux-gnu/libcudnn_adv_train_static_v8.a \
     /usr/lib/aarch64-linux-gnu/libcudnn_ops_infer_static_v8.a \
     /usr/lib/aarch64-linux-gnu/libcublasLt_static.a \
     /usr/lib/aarch64-linux-gnu/libcudnn_cnn_train_static_v8.a \
     /usr/lib/aarch64-linux-gnu/libcudnn_ops_train_static_v8.a \
     /usr/lib/aarch64-linux-gnu/libmyelin_compiler_static.a \
     /usr/lib/aarch64-linux-gnu/libmyelin_executor_static.a \
     /usr/lib/aarch64-linux-gnu/libnvinfer_plugin_static.a && \
     ldconfig

# Install system-level python3 packages
RUN apt-get update && apt-get install -y \
  gir1.2-gst-rtsp-server-1.0 \
  python3-pip \
  python3-opencv \
  python3-libnvinfer \
  python3-scipy \
  cython3 \
  python3-sklearn \
  python-gi-dev \
  unzip && ldconfig

# These system-level packages don't provide egg-info files, add them manually so that pip knows
COPY docker/opencv_python-3.2.0.egg-info /usr/lib/python3/dist-packages/
COPY docker/scikit-learn-0.19.1.egg-info /usr/lib/python3/dist-packages/

# Install gst-python (python bindings for GStreamer)
RUN \
   export GST_CFLAGS="-pthread -I/usr/include/gstreamer-1.0 -I/usr/include/glib-2.0 -I/usr/lib/x86_64-linux-gnu/glib-2.0/include" && \
   export GST_LIBS="-lgstreamer-1.0 -lgobject-2.0 -lglib-2.0" && \
   git clone https://github.com/GStreamer/gst-python.git && \
   cd gst-python && git checkout 1a8f48a && \
   ./autogen.sh PYTHON=python3 && \
   ./configure PYTHON=python3 && \
   make && make install

# Install pyds (python bindings for DeepStream)
RUN cd /opt/nvidia/deepstream/deepstream-5.0/lib && python3 setup.py install

# Upgrade here to avoid re-running on code changes
RUN pip3 install --upgrade pip

# ---- Below steps are run before copying full maskcam code to allow layer caching ----

# Compile YOLOv4 plugin for DeepStream
COPY deepstream_plugin_yolov4 /deepstream_plugin_yolov4
ENV CUDA_VER=10.2
RUN cd /deepstream_plugin_yolov4 && make

# Get TensorRT engine (pretrained YOLOv4-tiny)
# Model trained on smaller dataset
# RUN wget -P / https://maskcam.s3.us-east-2.amazonaws.com/facemask_y4tiny_1024_608_fp16.trt

# Model trained on bigger dataset, merged with MAFA, WiderFace, Kaggle Medical Masks and FDDB
RUN wget -P / https://maskcam.s3.us-east-2.amazonaws.com/maskcam_y4t_1024_608_fp16.trt
# RUN wget -P / https://maskcam.s3.us-east-2.amazonaws.com/maskcam_y4t_1120_640_fp16.trt

# Install requirements with pinned versions
COPY requirements.txt /maskcam_requirements.txt
RUN pip3 install -r /maskcam_requirements.txt

# ---- Note: all layers below this will be re-generated each time code changes ----
# Copy full maskcam code
COPY . /opt/maskcam_1.0/
WORKDIR /opt/maskcam_1.0

# Move pre-copied files to their maskcam location
# NOTE: Ignoring errors with `exit 0` to avoid breaking on balena livepush
RUN rm -r deepstream_plugin_yolov4 && mv /deepstream_plugin_yolov4 . ; exit 0
RUN mv /*.trt yolo/ ; exit 0

# Preload library to avoids Gst errors "cannot allocate memory in static TLS block"
ENV LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1

# Un-pinned versions of maskcam requirements (comment pip3 install above before this)
# RUN pip3 install -r requirements.in -c docker/constraints.docker

RUN chmod +x docker/start.sh
RUN chmod +x maskcam_run.py
CMD ["docker/start.sh"]
