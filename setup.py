#!/usr/bin/env python3
# coding: utf-8

import dbm
import os
import re
import stat
import subprocess
import sys

DEFAULT_INSTALL_LOCATION = '/home/pi/'
CONFIG_PATH = '/home/pi/.config/pianoteq-pi.dbm'
script_dir, script_filename = os.path.split(__file__)


def hl(text, style=1, margin=False):
    # style: https://misc.flogisoft.com/bash/tip_colors_and_formatting
    nl = '\n' if margin else ''
    return f'{nl}\033[{style}m{text}{nl}\033[0m'


def notify(text):
    print(hl(text, style=7, margin=True))


def run(*args, interact=True, **kwargs):
    if interact:
        print(hl('# ', 2) + hl(' '.join([f'"{a}"' if ' ' in a else a for a in args])))
        kwargs.update(stdout=sys.stdout, stderr=sys.stderr)
    else:
        kwargs.update(capture_output=True)
    result = subprocess.run(args, check=True, text=True, **kwargs).stdout
    if result:
        return result.strip()
    else:
        return ''


if os.getuid():
    # exit if non-root
    sys.exit(f'Please run as root like this:\n{hl("$", 2)} ' + hl(f'sudo python3 {script_filename}'))


class RPOS:
    cmdline_path = '/boot/cmdline.txt'
    config_path = '/boot/config.txt'
    security_limits_path = '/etc/security/limits.conf'

    def __init__(self):
        self.issue_date = None
        self.arch = None
        self._get_issue_date()
        self._get_arch()
        try:
            self.arch_bit = dict(aarch64='arm-64bit', armv7l='arm-32bit', x86_64='x86-64bit')[self.arch]
        except KeyError:
            raise EnvironmentError(f'Unknown arch: {self.arch}')
        self.reboot_required = False

    def _get_issue_date(self):
        rpi_issue = run('cat', '/etc/rpi-issue', interact=False)
        m = re.search(r'[\d\-]{10}', rpi_issue)
        if not m:
            raise EnvironmentError('Please run on Raspberry Pi OS')
        self.issue_date = m.group()

    def _get_arch(self):
        self.arch = run('uname', '-m', interact=False)

    def _config_modifier(self, path, rp_to_remove: re.Pattern, new_items: list, sep='\n'):
        with open(path) as fp:
            old_config = fp.read()
        new_config = [line for line in old_config.strip().split(sep) if not rp_to_remove.search(line)]
        new_config = sep.join(new_config).strip(sep)
        new_config += sep + sep.join(new_items) + sep
        if new_config != old_config:
            with open(path, 'w') as fp:
                fp.write(new_config)
            self.reboot_required = True
            return new_config

    def set_default_resolution(self):
        notify('Setting default resolution ...')
        self._config_modifier(
            path=self.config_path,
            rp_to_remove=re.compile(r'^\s*(hdmi_force_hotplug|hdmi_group|hdmi_mode)\b'),
            new_items=['hdmi_force_hotplug=1', 'hdmi_group=2', 'hdmi_mode=4'],
        )

    def overclock_cpu(self, freq=None, voltage=None):
        notify(f'Overclocking CPU: freq={freq} voltage={voltage} ...')
        self._config_modifier(
            path=self.config_path,
            rp_to_remove=re.compile(r'^\s*(arm_freq|over_voltage)\b'),
            new_items=[f'arm_freq={freq or 2000}', f'over_voltage={voltage or 6}'] if freq else [],
        )

    def disable_smsc95xx_turbo_mode(self):
        notify('Disabling smsc95xx.turbo_mode ...')
        self._config_modifier(
            path=self.cmdline_path,
            rp_to_remove=re.compile(r'^\s*smsc95xx\.turbo_mode\b'),
            new_items=['smsc95xx.turbo_mode=N'],
            sep=' '
        )

    def modify_account_limits(self):
        notify('Modifying account limits ...')
        self._config_modifier(
            path=self.security_limits_path,
            rp_to_remove=re.compile(r'^\s*^@audio\s*-\s*(rtprio|nice|memlock)\s+'),
            new_items=[
                '@audio - rtprio 90',
                '@audio - nice -10',
                '@audio - memlock 500000'
            ]
        )


rp = RPOS()


class Pianoteq:
    desktop_entry_path = '/home/pi/Desktop/pianoteq.desktop'
    service_path = '/lib/systemd/system/pianoteq.service'
    all_arch_bits = ['arm-64bit', 'arm-32bit', 'x86-64bit']

    def __init__(self, parent_dir=None):
        self.parent_dir = parent_dir or DEFAULT_INSTALL_LOCATION
        self.pianoteq_dir = None
        self.edition_suffix = None
        self.find_existing_installation()

    def find_existing_installation(self):
        for root, folders, files in os.walk(self.parent_dir):
            for folder in folders:
                m = re.search(r'^Pianoteq 7( \w+)?$', folder)
                if m:
                    path = os.path.join(root, folder)
                    if rp.arch_bit in os.listdir(path) and os.path.isdir(os.path.join(path, rp.arch_bit)):
                        self.edition_suffix = m.group(1) or ''
                        self.pianoteq_dir = path
                        return self.pianoteq_dir
            break

    @staticmethod
    def install_dependencies():
        def which_cmd(cmd):
            try:
                return run('which', cmd, interact=False)
            except subprocess.CalledProcessError as e:
                if e.returncode == 1:
                    return False

        if which_cmd('7za') and which_cmd('cpufreq-set'):
            return
        notify('Installing dependencies ...')
        run('apt', 'update')
        run('apt', 'install', 'p7zip-full', 'cpufrequtils', '-y')

    @staticmethod
    def _find_installer_package():
        for fn in os.listdir(os.curdir):
            if re.search(r'^pianoteq\w*_linux_v?\d*\.(7z|zip)$', fn) and os.path.isfile(fn):
                return fn
        else:
            raise LookupError('Unable to find installer package.')

    def extract_package(self):
        package_path = self._find_installer_package()
        notify(f'Extracting package {package_path} ...')
        content_list = run('7za', 'l', '-slt', package_path, interact=False)
        root_dir = re.search(r'^-{5,}\n^Path = (.+)$', content_list, re.M).group(1).split('/')[0]
        m = re.search(r'^Pianoteq \d+( \w+)?$', root_dir)
        self.edition_suffix = m.group(1) or ''
        exclusion = self.all_arch_bits[:]
        exclusion.remove(rp.arch_bit)
        exclusion = ['-xr!' + e for e in exclusion]
        run('7za', 'x', package_path, '-o' + self.parent_dir, '-aoa', *exclusion)
        self.pianoteq_dir = os.path.join(self.parent_dir, root_dir)
        return self.pianoteq_dir

    @property
    def start_sh_path(self):
        return os.path.join(self.pianoteq_dir, 'start.sh')

    def create_start_sh(self):
        notify('Creating start.sh for Pianoteq ...')
        start_sh_content = f"""#!/bin/bash

exec_path="{self.pianoteq_dir}/{rp.arch_bit}/Pianoteq 7{self.edition_suffix}"
base_args="--multicore max --do-not-block-screensaver --midimapping TouchOSC"

base_cmd=("${{exec_path}}" $base_args)

sudo cpufreq-set -r -g performance

if [ "$#" -eq 0 ] ; then
    # open directly
    sudo systemctl stop pianoteq
    "${{base_cmd[@]}}"
    sudo systemctl start pianoteq
else
    # run from systemctl
    "${{base_cmd[@]}}" "$@"
fi

sudo cpufreq-set -r -g ondemand
"""
        with open(self.start_sh_path, 'w') as fp:
            fp.write(start_sh_content)
        os.chmod(self.start_sh_path, os.stat(self.start_sh_path).st_mode | stat.S_IEXEC)

    def create_service(self):
        notify('Creating service for Pianoteq ...')
        service_content = f"""[Unit]
Description=Start Pianoteq 7{self.edition_suffix}
After=graphical.target

[Service]
User=pi
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/pi/.Xauthority
ExecStart='{self.pianoteq_dir}/start.sh' --headless
Restart=on-failure
RestartSec=2s
KillMode=control-group
TimeoutSec=infinity

[Install]
WantedBy=graphical.target
"""
        with open(self.service_path, 'w') as fp:
            fp.write(service_content)
        run('systemctl', 'daemon-reload')
        run('sudo', 'systemctl', 'enable', 'pianoteq')

    def create_desktop_entry(self):
        notify('Creating desktop entry for Pianoteq ...')
        desktop_entry_content = f"""[Desktop Entry]
Name=Pianoteq 7
Exec="{self.pianoteq_dir}/start.sh"
Type=Application
Icon={self.pianoteq_dir}/icon.png
Comment=Fourth Generation Piano Instrument
Terminal=false
"""
        run(
            'wget',
            'https://raw.githubusercontent.com/youfou/pianoteq-pi/main/icon.png',
            '-O', f'{os.path.join(self.pianoteq_dir, "icon.png")}'
        )

        with open(self.desktop_entry_path, 'w') as fp:
            fp.write(desktop_entry_content)
        run('desktop-file-validate', self.desktop_entry_path)

    def install(self):
        notify(f'Installing Pianoteq to {self.parent_dir} ...')
        self.install_dependencies()
        try:
            self.extract_package()
        except LookupError:
            notify('Pianoteq 7z/zip package not found')
            sys.exit(
                'Please download Pianoteq from Modartt website and put the 7z/zip package under the same folder.\n'
                'Download: https://www.modartt.com/user_area#downloads'
            )
        self.create_start_sh()
        self.create_desktop_entry()
        self.create_service()
        run('chown', '-R', 'pi:pi', self.pianoteq_dir)
        rp.set_default_resolution()
        rp.overclock_cpu()
        rp.disable_smsc95xx_turbo_mode()
        rp.modify_account_limits()
        run('systemctl', 'start', 'pianoteq')
        notify('Pianoteq has been installed/updated.')

    def uninstall(self):
        notify(f'Uninstalling Pianoteq from {self.parent_dir} ...')
        run('systemctl', 'stop', 'pianoteq')
        run('systemctl', 'disable', 'pianoteq')
        run('rm', self.service_path)
        run('systemctl', 'daemon-reload')
        run('rm', self.desktop_entry_path)
        run('rm', '-rf', self.pianoteq_dir)
        self.pianoteq_dir = None
        self.edition_suffix = None
        notify('Pianoteq has been uninstalled.')


def number_menu(callbacks: list):
    while True:
        for i, (prompt, _) in enumerate(callbacks):
            print(f'{i + 1}. {prompt}')
        choice = input('\nEnter a number or "q" to quit: ').strip()
        if choice.lower().startswith('q'):
            sys.exit(0)
        number = int(choice)
        if number <= len(callbacks):
            return callbacks[number - 1][1]()


def ask_to_overclock_cpu():
    oc_2000_6 = lambda: rp.overclock_cpu(2000, 6)
    oc_1750_2 = lambda: rp.overclock_cpu(1750, 2)
    cancel_oc = lambda: rp.overclock_cpu()
    notify('Would you like to overclock the CPU of your Raspberry Pi?')
    return number_menu([
        ('Overclock to 2000 MHz @ 6th voltage level', oc_2000_6),
        ('Overclock to 1750 MHz @ 2nd voltage level', oc_1750_2),
        ('Restore back to the stock CPU frequency and voltage', cancel_oc),
    ])


if __name__ == '__main__':
    notify('System version:')
    print(f'Raspberry Pi OS {rp.arch_bit} ({rp.issue_date})')
    notify('Specify install location for Pianoteq')
    with dbm.open(CONFIG_PATH, 'c') as db:
        install_location = db.setdefault('install_location', DEFAULT_INSTALL_LOCATION.encode()).decode()
        install_location = input(f'Install location (default: "{install_location}"): ').strip() or install_location
        if not os.path.exists(install_location):
            to_create = input(f'"{install_location}" does not exist. Would you like to create it now? (Y/n)')
            if to_create.strip().lower().startswith('y') or not to_create:
                os.makedirs(install_location)
                run('chown', 'pi:pi', install_location)
            else:
                sys.exit(0)
        db['install_location'] = install_location
        pt = Pianoteq(install_location)
    if pt.pianoteq_dir:
        notify('You have already installed Pianoteq. What would you like to do?')
        number_menu([
            ('Re-install / Update', pt.install),
            ('Uninstall', pt.uninstall),
            ('Overclock CPU or cancel overclocking', ask_to_overclock_cpu)
        ])

    else:
        pt.install()
        ask_to_overclock_cpu()
    if rp.reboot_required:
        reboot = input('Your system has been tweeted during the installation, reboot now? (Y/n): ')
        if reboot.strip().lower().startswith('y') or not reboot:
            run('reboot')
