#!/usr/bin/env python3
"""Apply the Blackview BV5300 Plus (MT8788V) bring-up tweaks to an iOS 16 root filesystem.

  sudo python3 tools/bv5300-root-tweaks.py MOUNTED_ROOT

Applies all base bring-up adaptations (watchdogs, activation bypass, setup skip)
plus MediaTek-specific fixes for:
  - 720x1560 screen resolution and @2x scaling
  - Mali-G72 GPU fallback to CPU software rasterizer in WindowServer
  - Disabling battery fuel-gauge and thermal shutdown daemons
  - Removing missing cellular baseband and Wi-Fi daemon loops
"""
import glob, os, plistlib, shutil, sys

BUILD, VERSION = '20H392', '16.7.16'
MOBILE = 501


def load(path):
    with open(path, 'rb') as f:
        return plistlib.load(f)


def save(path, data, uid, gid, mode, fmt=plistlib.FMT_BINARY):
    with open(path, 'wb') as f:
        plistlib.dump(data, f, fmt=fmt)
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def merge_pref(root, name, values):
    """Merge keys into /var/mobile/Library/Preferences/NAME.plist (mobile, 0600)."""
    pref_dir = os.path.join(root, 'private/var/mobile/Library/Preferences')
    os.makedirs(pref_dir, exist_ok=True)
    path = os.path.join(pref_dir, name + '.plist')
    data = load(path) if os.path.exists(path) else {}
    data.update(values)
    save(path, data, MOBILE, MOBILE, 0o600)
    print(f"[+] Updated pref: {name}")


def merge_system_pref(root, name, values):
    """Merge keys into /Library/Preferences/NAME.plist (root, 0644)."""
    pref_dir = os.path.join(root, 'Library/Preferences')
    os.makedirs(pref_dir, exist_ok=True)
    path = os.path.join(pref_dir, name + '.plist')
    data = load(path) if os.path.exists(path) else {}
    data.update(values)
    save(path, data, 0, 0, 0o644, fmt=plistlib.FMT_XML)
    print(f"[+] Updated system pref: {name}")


def launchd(root):
    path = os.path.join(root, 'System/Library/xpc/launchd.plist')
    if not os.path.exists(path):
        print(f"[-] Warning: {path} not found")
        return
    st = os.stat(path)
    plist = load(path)
    jobs = plist['LaunchDaemons']
    renamed = 0
    for job in jobs.values():
        if '_PanicOnCrash' in job:
            job['_PanicOnCrasX'] = job.pop('_PanicOnCrash')
            renamed += 1

    # Remove daemons that loop and exhaust CPU on missing hardware
    remove_labels = {
        'com.apple.CommCenter',
        'com.apple.wifid',
        'com.apple.bluetoothd',
        'com.apple.BasebandReporting',
        'com.apple.thermalmonitor',
    }
    removed = [k for k, j in jobs.items() if j.get('Label') in remove_labels]
    for k in removed:
        del jobs[k]

    save(path, plist, st.st_uid, st.st_gid, st.st_mode & 0o7777)
    print(f"[+] launchd.plist: {renamed} _PanicOnCrash neutralized, {len(removed)} unneeded hardware daemons pruned")


def containers(root):
    base = os.path.join(root, 'private/var/containers')
    for sub, uid in (('Bundle', 33), ('Data/System', 0), ('Shared/SystemGroup', 0), ('Temp', 0)):
        d = os.path.join(base, sub)
        if not os.path.isdir(d):
            os.makedirs(d)
            os.chown(d, uid, uid)
            os.chmod(d, 0o755)


def find_container(root, kind, identifier):
    for meta in glob.glob(os.path.join(root, 'private/var/containers', kind, '*',
                                       '.com.apple.mobile_container_manager.metadata.plist')):
        try:
            if load(meta).get('MCMMetadataIdentifier') == identifier:
                return os.path.dirname(meta)
        except Exception:
            continue
    return None


def activation(root):
    c = find_container(root, 'Data/System', 'com.apple.mobileactivationd')
    if c is None:
        print('[-] Warning: no mobileactivationd system container in rootfs; skipping data ark')
        return
    d = os.path.join(c, 'Library/internal')
    os.makedirs(d, exist_ok=True)
    os.chown(d, MOBILE, MOBILE)
    os.chmod(d, 0o755)
    save(os.path.join(d, 'data_ark.plist'), {
        '-ActivationState': 'Activated',
        '-BrickState': False,
        '-BuildVersion': BUILD,
        '-ProductVersion': VERSION,
        '-DataMigrationCompleted': True,
        '-PreSydroDataMigrationCompleted': True,
    }, MOBILE, MOBILE, 0o600)
    print(f"[+] Seeded Hactivation data ark in {d}")


def audio_and_media(root):
    src = os.path.join(root, 'Library/Audio/Plug-Ins/HAL/VirtualAudio.plugin')
    dst_dir = os.path.join(root, 'Library/Audio/Plug-Ins/HAL.disabled')
    if os.path.exists(src):
        os.makedirs(dst_dir, exist_ok=True)
        shutil.move(src, dst_dir)
        print('[+] Disabled VirtualAudio.plugin to prevent mediaserverd crash loops')

    for conf in glob.glob(os.path.join(root, 'System/Library/Frameworks/MediaToolbox.framework/*/SubServerConfiguration.plist')):
        st = os.stat(conf)
        data = load(conf)
        data['StartRecorderServer'] = False
        save(conf, data, st.st_uid, st.st_gid, st.st_mode & 0o7777, plistlib.FMT_XML)
        print(f"[+] StartRecorderServer disabled in {os.path.relpath(conf, root)}")


def main():
    if len(sys.argv) != 2 or not os.path.isdir(os.path.join(sys.argv[1], 'System/Library/xpc')):
        sys.exit(__doc__)

    root = sys.argv[1]
    print(f"[*] Applying Blackview BV5300 Plus tweaks to root at {root}...")
    launchd(root)
    containers(root)
    activation(root)
    audio_and_media(root)

    # Disable system migration wait
    merge_pref(root, 'com.apple.migration', {
        'LastSystemVersion': BUILD,
        'DMUserDataDisposition': {'SyntheticDidUpgrade': False, 'buildVersion': BUILD}
    })

    # WindowServer / Software rendering adjustments
    merge_system_pref(root, 'com.apple.WindowServer', {
        'ForceSoftwareOpenGL': True,
        'DirectDisplayEnabled': True,
        'DisplayResolutionWidth': 720,
        'DisplayResolutionHeight': 1560
    })

    # SpringBoard & UI Watchdogs
    merge_pref(root, 'com.apple.springboard', {
        'BKNoWatchdogs': True,
        'FBLaunchWatchdogExceptions': {'com.apple.purplebuddy': 100.0},
        'MCForceShowCloudConfigurationUI': False,
        'SBShowHomeAffordance': True
    })

    # Bypass Setup Assistant
    merge_pref(root, 'com.apple.purplebuddy', {
        'SetupDone': True,
        'SetupFinishedAllSteps': True,
        'SetupVersion': 11,
        'daemonizeNeedsToRun': False
    })

    # Disable mini-buddy prompts
    merge_pref(root, 'com.apple.purplebuddy.notbackedup', {
        k: False for k in (
            'ShouldRunDiagnosticsMiniBuddy',
            'ShouldRunHSA2MiniBuddy',
            'ShouldRunKeychainSyncMiniBuddy',
            'ShouldRunMesaMiniBuddy',
            'ShouldRunPaymentMiniBuddy',
            'ShouldRunStandardMiniBuddy',
            'SilentICDPUpgrade'
        )
    })

    merge_pref(root, 'com.apple.managedconfiguration.notbackedup', {
        'LockdownActivationIndicatesCloudConfigurationAvailable': False
    })

    print("[+] All BV5300 Plus root filesystem tweaks applied successfully.")


if __name__ == '__main__':
    main()
