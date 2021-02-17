# BalenaOS Photon Nano Setup Instructions for MaskCam
This page provides step-by-step instructions for setting up the Connect Tech Photon-based Nano with balenaOS. BalenaOS is a barebones host operating system optimized for running Docker containers. It allows MaskCam to easily be installed as a container and remotely updated or configured. This is the configuration used for our production MaskCam device.

*Note (to be removed later): This document will basically be a copy of https://github.com/tryolabs/bdti-jetson/blob/main/docs/BalenaOS-DeveloperKit-Nano-Setup.md except there will be different instructions for flashing the eMMC chip and setting up the CTI-Photon DTB file*

## Setup Instructions

### 1. Create balena account
Evan or John can work on this part


### 2. Create new application and device on balena dashboard
Evan or John can work on this part. 

### 3. Flashing balenaOS onto Jetson Nano eMMC and configuring device tree
Evan can work on this part.
This part includes: 
1. Setting up the [jetson-flash](https://github.com/balena-os/jetson-flash) tool
2. Flashing the device image onto the Nano's eMMC chip using jetson-flash
3. Remotely connecting to Nano, downloading the CTI-Photon DTB file, and putting it in the right spot


### 3. Deploy MaskCam code to balena device
(John can work on this part... Evan doesn't know how it works yet :grimacing: )
This part also needs to show how to configure the device in balena dashboard so it points to the CTI-Photon DTB file


### 4. Running MaskCam on device
Instructions for connecting to device via balena dashboard or over SSH, and issuing commands to configure/run MaskCam.

### What else?
