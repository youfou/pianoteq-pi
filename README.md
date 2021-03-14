# pianoteq-pi

> Install Pianoteq and tweak your system on Raspberry Pi in one line ⚡️

[Pianoteq](https://pianoteq.com/) is probably the only top-notch virtual piano in the world that can be installed on Raspberry Pi. 
And `pianoteq-pi` might be the fastest way to install Pianoteq onto your Raspberry Pi.

> This is an early version, only tested on Raspberry Pi 4B + Raspberry Pi OS 64bit + Pianoteq 7 Stage & Standard edition. Use at your own risk.

## How to use

1. Install [Raspberry Pi OS (64 bit)](https://downloads.raspberrypi.org/raspios_arm64/images/) on your Raspberry Pi.
2. Download Pianoteq from [the official website](https://pianoteq.com/), and put the 7z/zip package you got into your Raspberry Pi.
   - Or download directly on your Raspberry Pi.
3. Run the following command in the same folder of the 7z/zip package:
```shell
wget -O setup.py https://github.com/youfou/pianoteq-pi/raw/main/setup.py && sudo python3 setup.py
```
Simple as that.

![](https://raw.githubusercontent.com/youfou/pianoteq-pi/main/screenshot.png)

After installed in this way, Pianoteq will run headlessly (No GUI, to get better performance) on every system boot.
If you want to adjust something on it, just double click the desktop icon to open GUI.

## What this script actually does?

1. Installs dependencies:
   - `p7zip-full` - to extract the Pianoteq 7z/zip package
   - `cpufrequtils` - to improve CPU performance while running Pianoteq
2. Extracts the Pianoteq 7z/zip package to `/home/pi/`
3. Creates a `start.sh` script under the Pianoteq folder, and it:
   - sets CPUs to "Performance" mode while running Pianoteq
   - runs Pianoteq as a GUI program or headlessly for better performance 
   - sets CPUs to "On Demand" mode when quit Pianoteq
4. Creates a desktop entry for Pianoteq, so you can open it easily by clicking the icon
5. Creates a system service to run Pianoteq headlessly every time the system startups
6. Overclocks the CPU to 2000 MHz at the 6th voltage level to get better performance as well
7. Disables smsc95xx.turbo_mode as Pianoteq officially advised
8. Modifies the "account limits" as Pianoteq officially advised
9. Checks if you have already installed Pianoteq and can re-install or uninstall it if you want

## FAQ

1. `Q` Why use the Beta version of Raspberry Pi OS (64 bit) instead of the stable 32 bit version, or Ubuntu Mate (64 bit)?
    - `A` 64 bit allows for better performance, and Raspberry Pi OS comes with VNC Server, which saves a lot of work.
2. `Q` Is Pianoteq playable on it?
    - `A` Sure it is. I get a Performance Index of 32 on it. The internal sample rate set to 24000 Hz, and max polyphony is set to 128. No crackles or dropouts. Playing is quite enjoyable.
3. `Q` Can I try this on other machines / OS version?
    - `A` Not recommended. I haven't tested it on other machines or OS versions.
