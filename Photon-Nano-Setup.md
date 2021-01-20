# Photon Nano Setup Instructions for MaskCam
This page provides step-by-step instructions for setting up the Jetson Nano on a Connect Tech Photon board with the CTI-L4T BSP (i.e., the "Photon Nano"). 

The following software versions are used for this setup:

* JetPack 4.4.1
* Connect Tech BSP [Nano-32.4.4 V003](https://connecttech.com/ftp/Drivers/L4T-Release-Notes/Jetson-Nano/Nano-32.4.4.pdf)
* CUDA 10.2
* Deepstream 5.0

## 1. Flash Jetson OS onto Nano SOM
Install the Jetson Nano SOM into the Photon carrier board. Follow [Connect Tech's instructions](https://connecttech.com/resource-center/kdb373/) to build a Jetson OS image on a host PC, install the Connect Tech Photon BSP on it, and flash it onto the Nano SOM over USB.

## 2. Boot up Jetson OS and remove unneeded software
Power cycle the Photon carrier board or hit the RESET button to reboot it. Work through the Ubuntu setup dialog. When the NVIDIA desktop is displayed, open a terminal and issue the following commands to remove LibreOffice and Thunderbird.

```
sudo apt purge libreoffice*
sudo apt purge thunderbird*
```

This is necessary to free up about 400MB of storage space on the Nano. If this step is skipped, the Nano will be unable to boot after installing CUDA and Deepstream in Step 3, due to its storage space being completely full.

## 3. Install CUDA, Deepstream, and other JetPack components using SDK Manager
Plug an ethernet cable into both the host PC and the Photon Nano. Open SDK Manager on the host PC. Select Jetson Nano (not the developer kit version) from the hardware target dropdown menu, then click "CONTINUE". De-select the Jetson OS box and select the SDK Components box, as shown in the image below. Click "FLASH".

*Insert image here :)*

A window will open asking to enter the IP address, username, and password for the Photon Nano. You can check the Nano's IP address by opening a terminal on the Photon Nano and issuing `ifconfig`. (The default IP address is 192.168.1.119.) Enter the IP address, username, and password, then click "Flash". This will install the selected SDK Components over an SSH connection. The process takes about 30 minutes. Reboot the Photon Nano after it's finished.

This leaves the Nano with very little storage space left. Free up more storage space by removing the Deepstream and CUDA sample directories. On the Photon Nano, issue:

```
sudo rm -rf /opt/nvidia/deepstream/deepstream-5.0/samples
sudo rm -rf /usr/local/cuda-10.2/samples
```

## 4. Set up MaskCam directory
On the Photon Nano, create a MaskCam folder inside the home directory (/home/<username>) and cd into it using

```
mkdir ~/MaskCam
cd ~/MaskCam
```

Clone this repository, the [norfair repository](https://github.com/tryolabs/norfair), and the [filterpy](https://github.com/rlabbe/filterpy) repository from GitHub using the following commands. To clone these repositories, SSH keys will need to be set up on the Photon Nano (see [these instructions](https://docs.github.com/en/github/authenticating-to-github/connecting-to-github-with-ssh)).

```
git clone git@github.com:tryolabs/bdti-jetson.git
git clone git@github.com:tryolabs/norfair.git
git clone git@github.com:rlabbe/filterpy.git
```

## 5. Update NVIDIA apt sources list
Open the NVIDIA apt sources list using `sudo gedit /etc/apt/sources.list.d/nvidia-l4t-apt-source.list` . Make sure it contains the following lines:

```
deb https://repo.download.nvidia.com/jetson/common r32.4 main
deb https://repo.download.nvidia.com/jetson/<platform> r32.4 main
```

Save and exit the file. Then, issue "sudo apt update" to update the package list.

