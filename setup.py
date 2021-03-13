#!/usr/bin/env python3
# coding: utf-8

import os
import re
import stat
import subprocess
import sys

script_dir, script_filename = os.path.split(__file__)


def hl(text, style=1, margin=False):
    # style: https://misc.flogisoft.com/bash/tip_colors_and_formatting
    nl = '\n' if margin else ''
    return f'{nl}\033[{style}m{text}{nl}\033[0m'


def notice(text):
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
    security_limits_path = '/etc/security/limits.conf'

    def __init__(self):
        self.issue_date = None
        self.arch = None
        self._get_issue_date()
        self._get_arch()

    def _get_issue_date(self):
        rpi_issue = run('cat', '/etc/rpi-issue', interact=False)
        m = re.search(r'[\d\-]{10}', rpi_issue)
        if not m:
            raise EnvironmentError('Please run on Raspberry Pi OS')
        self.issue_date = m.group()

    def _get_arch(self):
        self.arch = run('uname', '-m', interact=False)

    def disable_smsc95xx_turbo_mode(self):
        notice('Disabling smsc95xx.turbo_mode ...')
        with open(self.cmdline_path) as fp:
            cmdline = fp.read().strip()
        regexp = re.compile(r'smsc95xx\.turbo_mode\S*')
        param = 'smsc95xx.turbo_mode=N'
        if regexp.search(cmdline):
            cmdline = regexp.sub(param, cmdline)
        else:
            cmdline += f' {param}'
        with open(self.cmdline_path, 'w') as fp:
            fp.write(cmdline)

    def modify_account_limits(self):
        notice('Modifying account limits ...')
        with open(self.security_limits_path) as fp:
            conf = fp.read()
        conf = conf.split('\n')
        limits = dict(rtprio=90, nice=-10, memlock=500000)
        regexp = re.compile(r'^@audio\s+-\s+(' + '|'.join(limits.keys()) + r')\s+[\d\-]+')
        to_remove = list()
        for i, line in enumerate(conf):
            if regexp.search(line):
                to_remove.append(i)
        for i in to_remove[::-1]:
            conf.pop(i)
        for k, v in limits.items():
            conf.append(f'@audio - {k} {v}')
        conf = '\n'.join(conf)
        with open(self.security_limits_path, 'w') as fp:
            fp.write(conf)


rp = RPOS()


class Pianoteq:
    desktop_entry_path = '/home/pi/Desktop/pianoteq.desktop'
    service_path = '/lib/systemd/system/pianoteq.service'
    all_arch_bits = ['arm-64bit', 'arm-32bit', 'x86-64bit']

    def __init__(self, parent_dir='/home/pi/'):
        self.parent_dir = parent_dir
        self.pianoteq_dir = None
        self.edition_suffix = None
        try:
            self.arch_bit = dict(aarch64='arm-64bit', armv7l='arm-32bit', x86_64='x86-64bit')[rp.arch]
        except KeyError:
            raise EnvironmentError(f'Unknown arch: {rp.arch}')
        self.find_existing_installation()

    def find_existing_installation(self):
        for root, folders, files in os.walk(self.parent_dir):
            for folder in folders:
                m = re.search(r'^Pianoteq 7( \w+)?$', folder)
                if m:
                    path = os.path.join(root, folder)
                    if self.arch_bit in os.listdir(path) and os.path.isdir(os.path.join(path, self.arch_bit)):
                        self.edition_suffix = m.group(1) or ''
                        self.pianoteq_dir = path
                        return self.pianoteq_dir
            break

    @staticmethod
    def install_dependencies():
        notice('Installing dependencies ...')
        run('apt', 'update')
        run('apt', 'install', 'cpufrequtils', 'p7zip-full', '-y')

    @staticmethod
    def _find_installer_package():
        for fn in os.listdir(os.curdir):
            if re.search(r'^pianoteq\w*_linux_v?\d*\.(7z|zip)$', fn) and os.path.isfile(fn):
                return fn
        else:
            raise LookupError('Unable to find installer package.')

    def extract_package(self):
        package_path = self._find_installer_package()
        notice(f'Extracting package {package_path} ...')
        content_list = run('7za', 'l', '-slt', package_path, interact=False)
        root_dir = re.search(r'^-{5,}\n^Path = (.+)$', content_list, re.M).group(1).split('/')[0]
        m = re.search(r'^Pianoteq \d+( \w+)?$', root_dir)
        self.edition_suffix = m.group(1) or ''
        exclusion = self.all_arch_bits[:]
        exclusion.remove(self.arch_bit)
        exclusion = ['-xr!' + e for e in exclusion]
        run('7za', 'x', package_path, '-o' + self.parent_dir, '-aoa', *exclusion)
        self.pianoteq_dir = os.path.join(self.parent_dir, root_dir)
        return self.pianoteq_dir

    @property
    def start_sh_path(self):
        return os.path.join(self.pianoteq_dir, 'start.sh')

    def create_start_sh(self):
        notice('Creating start.sh for Pianoteq ...')
        start_sh_content = f"""#!/bin/bash

exec_path="{self.pianoteq_dir}/{self.arch_bit}/Pianoteq 7{self.edition_suffix}"
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
        notice('Creating service for Pianoteq ...')
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
        notice('Creating desktop entry for Pianoteq ...')
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

    def chown(self, ):
        run('chown', '-R', 'pi:pi', self.pianoteq_dir)

    def install(self):
        notice(f'Installing Pianoteq to {self.parent_dir} ...')
        rp.disable_smsc95xx_turbo_mode()
        rp.modify_account_limits()
        self.install_dependencies()
        try:
            self.extract_package()
        except LookupError:
            sys.exit(
                'Please download Pianoteq from Modartt website and put the 7z/zip package here.\n'
                'Download: https://www.modartt.com/user_area#downloads'
            )
        self.create_start_sh()
        self.create_desktop_entry()
        self.create_service()
        self.chown()
        notice('Pianoteq has been installed or updated.')

    def uninstall(self):
        notice(f'Uninstalling Pianoteq from {self.parent_dir} ...')
        run('systemctl', 'stop', 'pianoteq')
        run('systemctl', 'disable', 'pianoteq')
        run('rm', self.service_path)
        run('systemctl', 'daemon-reload')
        run('rm', self.desktop_entry_path)
        run('rm', '-rf', self.pianoteq_dir)
        self.pianoteq_dir = None
        self.edition_suffix = None
        notice('Pianoteq has been uninstalled.')


if __name__ == '__main__':
    pt = Pianoteq('/home/pi')
    notice('System version:')
    print(f'Raspberry Pi OS {pt.arch_bit} v{rp.issue_date}')
    if pt.pianoteq_dir:
        notice('You have already installed Pianoteq. What would you like to do?')
        print(
            '1. Re-install / Update\n'
            '2. Uninstall'
        )
        while True:
            choice = input('Enter a number or "q" to quit: ').strip()
            if choice.lower().startswith('q'):
                sys.exit(0)
            elif choice == '1':
                pt.install()
                break
            elif choice == '2':
                pt.uninstall()
                break
    else:
        pt.install()
