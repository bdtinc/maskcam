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

A window will open asking to enter the IP address, username, and password for the Photon Nano. You can check the Nano's IP address by opening a terminal on the Photon Nano and issuing `ifconfig`. (The default IP address is 192.168.1.119.) Enter the IP address, username, and password, then click "Flash". This will install the selected SDK Components over an SSH connection. The process takes about 30 minutes.

