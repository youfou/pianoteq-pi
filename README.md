# pianoteq-pi

> Install Pianoteq on your Raspberry Pi in one line ⚡️

[Pianoteq](https://pianoteq.com/) is probably the only top-notch virtual piano in the world that can be installed on Raspberry Pi. 
And `pianoteq-pi` might be the fastest way to install Pianoteq onto your Raspberry Pi.

> This is an early version, only tested on Raspberry Pi 4B + Raspberry Pi OS 64bit + Pianoteq 7 Stage & Standard edition. Use at your own risk.

## How to

1. Install [Raspberry Pi OS (64 bit)](https://downloads.raspberrypi.org/raspios_arm64/images/) on your Raspberry Pi
2. Download Pianoteq from [the official website](https://pianoteq.com/), and put the 7z/zip package you got in any folder on the Raspberry Pi.
3. Run the following command in the same folder on the Raspberry Pi:
```shell
wget -O setup.py https://github.com/youfou/pianoteq-pi/raw/main/setup.py && sudo python3 setup.py
```
Simple as that.

![](https://raw.githubusercontent.com/youfou/pianoteq-pi/main/screenshot.png)

When installed in this way, Pianoteq will run heedlessly (No GUI, to get the best performance) on every startup.
If you want to adjust something on it, just double click the desktop icon to open GUI.


## FAQ

1. [Q] Why use the Beta version of Raspberry Pi OS (64 bit) instead of the stable 32 bit version, or Ubuntu Mate (64 bit)?
    - [A] 64 bit allows for better performance, and Raspberry Pi OS comes with VNC Server, which saves a lot of work.
2. [Q] Is Pianoteq playable on it?
    - [A] Sure it is. I get a Performance Index of 32 on it. The internal sample rate set to 24000 Hz, and max polyphony is set to 128. No crackles or dropouts. Playing is quite enjoyable.
3. [Q] Can I try this on other machines / OS version?
    - [A] Not recommended. I haven't tested it on other machines or OS versions.
