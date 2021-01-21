# Photon Nano Setup Instructions for MaskCam
This page provides step-by-step instructions for setting up the Jetson Nano on a Connect Tech Photon board with the CTI-L4T BSP (i.e., the "Photon Nano"). 

The following software versions are used for this setup:

* JetPack 4.4.1
* Connect Tech BSP [Nano-32.4.4 V003](https://connecttech.com/ftp/Drivers/L4T-Release-Notes/Jetson-Nano/Nano-32.4.4.pdf)
* CUDA 10.2
* Deepstream 5.0

### 1. Flash Jetson OS onto Nano SOM
Install the Jetson Nano SOM into the Photon carrier board. Follow [Connect Tech's instructions](https://connecttech.com/resource-center/kdb373/) to build a Jetson OS image on a host PC, install the Connect Tech Photon BSP on it, and flash it onto the Nano SOM over USB.

### 2. Boot up Jetson OS and remove unneeded software
Power cycle the Photon carrier board or hit the RESET button to reboot it. Work through the Ubuntu setup dialog. When the NVIDIA desktop is displayed, open a terminal and issue the following commands to remove LibreOffice, Thunderbird, and some other miscellaneous files.

```
sudo apt purge libreoffice*
sudo apt purge thunderbird*
sudo rm -rf /usr/share/example-content/Ubuntu_Free_Culture_Showcase/
sudo rm -rf /usr/share/backgrounds
```

This is necessary to free up about 400MB of storage space on the Nano. If this step is skipped, the Nano will be unable to boot after installing CUDA and Deepstream in Step 3, due to its storage space being completely full.

### 3. Install CUDA, Deepstream, and other JetPack components using SDK Manager
Plug an ethernet cable into both the host PC and the Photon Nano. Open SDK Manager on the host PC. Select Jetson Nano (not the developer kit version) from the hardware target dropdown menu, then click "CONTINUE". De-select the Jetson OS box and select the SDK Components box, as shown in the image below. Click "FLASH".

*Insert image here :)*

A window will open asking to enter the IP address, username, and password for the Photon Nano. You can check the Nano's IP address by opening a terminal on the Photon Nano and issuing `ifconfig`. (The default IP address is 192.168.1.119.) Enter the IP address, username, and password, then click "Flash". This will install the selected SDK Components over an SSH connection. The process takes about 30 minutes. Reboot the Photon Nano after it's finished.

This leaves the Nano with very little storage space left. Free up more storage space by removing samples directories for Deepstream, CUDA, and other packages. On the Photon Nano, issue:

```
sudo rm -rf /opt/nvidia/deepstream/deepstream-5.0/samples
sudo rm -rf /usr/local/cuda-10.2/samples
sudo rm -rf ~/VisionWorks-SFM-0.90-Samples

```

### 4. Update NVIDIA apt sources list and install pip3
Open the NVIDIA apt sources list using `sudo gedit /etc/apt/sources.list.d/nvidia-l4t-apt-source.list` . Remove the "#" in front of each line so it looks like this:

```
deb https://repo.download.nvidia.com/jetson/common r32.4 main
deb https://repo.download.nvidia.com/jetson/<platform> r32.4 main
```

Save and exit the file. Then, issue `sudo apt update` to update the package list. Install pip3 using:
```
sudo apt get python3-pip
```

### 5. Mount SD card-based drive
There still isn't quite enough storage space to set up MaskCam on the Nano's 16GB eMMC chip. Insert a blank SD card (at least 8GB) into the SD card slot on the Photon carrier board. Use Ubuntu's Disks application to format the card as EXT4 and mount it as a storage device.  This SD card will be used to hold the MaskCam program files, as well as all Python libraries that are needed for MaskCam.

(Note: A USB flash drive is not used because there is only one USB hub on the Photon Carrier board. If other devices are plugged and unplugged from this USB hub while the mounted USB flash drive is plugged in, it will be unmounted and stop working.)

Take note of the mount location for the drive. For example, I named my SD card partition "MaskCam-SD". The path to the mounted device is /media/evan/MaskCam-SD. I will refer to location for the rest of the setup instructions.



### 6.  Create symlink to Python site-packages directory and install Python libraries
Since there is limited storage space on the Nano, the Python libraries need to be installed on the SD card. First, install a dummy Python library (imutils) using:

```
pip3 install imutils
```

This creates a local site-packages folder at /home/*username*/.local/lib/python3.6/site-packages. Move the folder to the SD card and create a symbolic link to it using:

```
mv ~/.local/lib/python3.6/site-packages /media/evan/MaskCam-SD/site-packages-local
ln -s /media/evan/MaskCam-SD/site-packages-local ~/.local/lib/python3.6/site-packages
```

Now, all user Python libraries that are added with the `pip3` command will be installed to the site-packages-local folder on the SD card.

Install the Python libraries required for MaskCam using:
```
pip3 install black flake8 ipython ipdb Cython numpy scipy PyYAML rich paho-mqtt
```

There may be errors from installing scipy, but these can be ignored.

### 7. Set up MaskCam directory
On the Photon Nano, create a MaskCam folder inside the mounted SD card and cd into it.

```
mkdir /media/evan/MaskCam-SD
cd /media/evan/MaskCam-SD/MaskCam
```

Clone this bdti-jetson repository, the [norfair repository](https://github.com/tryolabs/norfair), and the [filterpy](https://github.com/rlabbe/filterpy) repository from GitHub using the following commands. To clone these repositories, SSH keys will need to be set up on the Photon Nano (see [these instructions](https://docs.github.com/en/github/authenticating-to-github/connecting-to-github-with-ssh)).

```
git clone git@github.com:tryolabs/bdti-jetson.git
git clone git@github.com:tryolabs/norfair.git
git clone git@github.com:rlabbe/filterpy.git
```

Add filterpy and norfair to PYTHONPATH using:
```
export PYTHONPATH=/media/evan/MaskCam-SD/MaskCam/filterpy:/media/evan/MaskCam-SD/MaskCam/norfair
```

### 8. Install GStreamer Python bindings



