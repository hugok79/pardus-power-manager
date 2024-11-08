import os
from util import writefile, readfile, listdir
from backends.cpu import list_cpu, list_big_cpu, list_little_cpu,  change_cpu_status
from backends.backlight import set_brightness
from common import *


_cur_mode = None

def set_mode(mode):
    global _cur_mode
    if _cur_mode == mode:
        return
    backlight="%100"
    if mode == "performance":
        _performance()
        backlight = get("backlight-performance","%100","modes")
    elif mode == "powersave":
        _powersave()
        backlight = get("backlight-powersave","%50","modes")
    _cur_mode = mode
    set_brightness("all", backlight)
    log("New mode: {}".format(mode))

def get_mode():
    return _cur_mode


# https://wiki.debian.org/SimplePowerSave
@asynchronous
def _powersave():
    if get("governor",True,"power"):
        # cpu governor
        cpu_path="/sys/devices/system/cpu/"
        for dir in listdir(cpu_path):
            if dir.startswith("cpu"):
                writefile("{}/{}/cpufreq/scaling_governor".format(cpu_path,dir),"powersave")

    if get("cpufreq",True,"power"):
        # decrease max cpu freq
        ratio = float(get("freq-ratio",0.5,"powersave"))
        if ratio > 1.0:
            ratio = 1.0
        cpu_path="/sys/devices/system/cpu/"
        for dir in listdir(cpu_path):
            if not dir.startswith("cpu"):
                continue
            freq_file = "{}/{}/cpufreq/scaling_available_frequencies".format(cpu_path,dir)
            if os.path.exists(freq_file):
                freqs = readfile(freq_file).split(" ")
                if len(freqs) > 0 and freqs[0] != '':
                    new_freq = freqs[int((len(freqs) -1) * ratio)]
                    writefile("{}/{}/cpufreq/scaling_max_freq".format(cpu_path,dir),int(new_freq))
            else:
                min_freq=readfile("{}/{}/cpufreq/cpuinfo_min_freq".format(cpu_path,dir))
                max_freq=readfile("{}/{}/cpufreq/cpuinfo_max_freq".format(cpu_path,dir))
                if min_freq != "" and max_freq != "":
                    new_freq = int(max_freq) * ratio
                    writefile("{}/{}/cpufreq/scaling_max_freq".format(cpu_path,dir),int(new_freq))

    if get("core",True,"power"):
        # disable cpu core
        def cpu_disable_event(cpus, min):
            dnum = len(cpus) * float(get("core-ratio",0.5,"powersave"))
            if len(cpus) <= min:
                dnum = 0
            elif len(cpus) - dnum < min:
                dnum = min
            for cpu in range(len(cpus) - int(dnum), len(cpus)):
                change_cpu_status(cpu,False)
        cpu_disable_event(list_big_cpu(), 4)
        cpu_disable_event(list_little_cpu(), 0)

    if not is_acpi_supported() and not get("unstable", False, "service"):
        return

    # laptop mode
    writefile("/proc/sys/vm/laptop_mode",5)

    # NMI watchdog
    writefile("/proc/sys/kernel/nmi_watchdog",0)

    # platform profile
    writefile("/sys/firmware/acpi/platform_profile","low-power")

    # intel pstate
    freq_path="/sys/devices/system/cpu/cpufreq/"
    for dir in listdir(freq_path):
        if dir.startswith("policy"):
            epath="energy_performance_preference"
            writefile("{}/{}/{}".format(freq_path, dir, epath), "power")

    # less disk activity
    writefile("/proc/sys/vm/dirty_writeback_centisecs",1500)
    writefile("/proc/sys/vm/dirty_expire_centisecs",3000)
    writefile("/proc/sys/vm/dirty_ratio", "10")
    writefile("/proc/sys/vm/dirty_background_ratio", "5")

    # vfs cache pressure
    writefile("/proc/sys/vm/vfs_cache_pressure", "50")

    # disable THP
    writefile("/sys/kernel/mm/transparent_hugepage/enabled", "never")

    if get("scsi",True,"power"):
        # sata channel
        scsi_host_path="/sys/class/scsi_host/"
        for dir in listdir(scsi_host_path):
            if dir.startswith("host"):
                writefile("{}/{}/link_power_management_policy".format(scsi_host_path,dir),"min_power")


    if get("usb",True,"power"):
        # usb auto suspend
        usb_path="/sys/bus/usb/devices/"
        for dir in listdir(usb_path):
            # ignore if interface type is HID or HUB
            if os.path.isfile("{}/{}/bInterfaceClass".format(usb_path,dir)):
                if readfile("{}/{}/bInterfaceClass".format(usb_path,dir)) in ["03","09"]:
                    continue
            writefile("{}/{}/power/control".format(usb_path,dir),"auto")
            writefile("{}/{}/power/autosuspend_delay_ms".format(usb_path,dir),get("suspend_delay", "60000", "power"))

    if get("block",True,"power"):
        # block auto suspend
        block_path="/sys/block/"
        for dir in listdir(block_path):
            writefile("{}/{}/device/power/control".format(block_path,dir),"auto")

    if get("pci",True,"power"):
        # pci auto suspend
        pci_path="/sys/bus/pci/devices/"
        for dir in listdir(pci_path):
            writefile("{}/{}/power/control".format(pci_path,dir),"auto")
            writefile("{}/{}/power/autosuspend_delay_ms".format(pci_path,dir),get("suspend_delay", "60000", "power"))
        writefile("/sys/module/pcie_aspm/parameters/policy", "powersave")


    if get("i2c",True,"power"):
        # i2c auto suspend
        i2c_path="/sys/bus/i2c/devices/"
        for dir in listdir(i2c_path):
            writefile("{}/{}/power/control".format(i2c_path,dir),"auto")
            writefile("{}/{}/device/power/control".format(i2c_path,dir),"auto")

    if get("audio",True,"power"):
        # audio card
        writefile("/sys/module/snd_hda_intel/parameters/power_save",1)
        writefile("/sys/module/snd_hda_intel/parameters/power_save_controller","Y")


    if get("turbo",True,"power"):
        # turbo boost
        writefile("/sys/devices/system/cpu/intel_pstate/no_turbo",1)
        writefile("/sys/devices/system/cpu/cpufreq/boost",0)

    if get("gpu",True,"power"):
        # gpu powersave boost
        dri_path="/sys/class/drm/"
        for card in listdir(dri_path):
            if card.startswith("card") and card[4:].isnumeric():
                writefile("{}/{}/device/power_dpm_force_performance_level".format(dri_path, card), "low")
                writefile("{}/{}/device/power_dpm_state".format(dri_path, card), "battery")
                writefile("{}/{}/device/power/control".format(dri_path, card), "auto")

    if get("network",True,"power"):
        # network
        net_path="/sys/class/net/"
        for dir in listdir(net_path):
            writefile("{}/{}/device/power/control".format(net_path,dir),"auto")

    if get("bluetooth",True,"power"):
        # bluetooth
        net_path="/sys/class/bluetooth/"
        for dir in listdir(net_path):
            writefile("{}/{}/power/control".format(net_path,dir),"auto")

    if get("nvme",True,"power"):
        # nvme
        net_path="/sys/class/nvme/"
        for dir in listdir(net_path):
            writefile("{}/{}/power/control".format(net_path,dir),"auto")

@asynchronous
def _performance():
    if get("governor",True,"power"):
        # cpu governor
        cpu_path="/sys/devices/system/cpu/"
        for dir in listdir(cpu_path):
            if dir.startswith("cpu"):
                writefile("{}/{}/cpufreq/scaling_governor".format(cpu_path,dir),"performance")

    if get("core",True,"power"):
        # enable cpu core
        cpus = list_cpu()
        print(cpus)
        for cpu in range(0, len(cpus)):
            change_cpu_status(cpu,True)

    if get("cpufreq",True,"power"):
        # increase max cpu freq
        cpu_path="/sys/devices/system/cpu/"
        for dir in listdir(cpu_path):
            if not dir.startswith("cpu"):
                continue
            max_freq=readfile("{}/{}/cpufreq/cpuinfo_max_freq".format(cpu_path,dir))
            if max_freq != "":
                writefile("{}/{}/cpufreq/scaling_max_freq".format(cpu_path,dir),max_freq)

    if not is_acpi_supported() and not get("unstable", False, "service"):
        return

    # laptop mode
    writefile("/proc/sys/vm/laptop_mode",0)

    # NMI watchdog
    writefile("/proc/sys/kernel/nmi_watchdog",0)

    # platform profile
    writefile("/sys/firmware/acpi/platform_profile","performance")

    # intel pstate
    freq_path="/sys/devices/system/cpu/cpufreq/"
    for dir in listdir(freq_path):
        if dir.startswith("policy"):
            epath="energy_performance_preference"
            writefile("{}/{}/{}".format(freq_path, dir, epath), "performance")


    # more disk activity
    writefile("/proc/sys/vm/dirty_writeback_centisecs",500)
    writefile("/proc/sys/vm/dirty_expire_centisecs",500)
    writefile("/proc/sys/vm/dirty_ratio", "20")
    writefile("/proc/sys/vm/dirty_background_ratio", "10")

    # vfs cache pressure
    writefile("/proc/sys/vm/vfs_cache_pressure", "100")

    # enable THP
    writefile("/sys/kernel/mm/transparent_hugepage/enabled", "madvise")

    if get("scsi",True,"power"):
        # sata channel
        scsi_host_path="/sys/class/scsi_host/"
        for dir in listdir(scsi_host_path):
            if dir.startswith("host"):
                writefile("{}/{}/link_power_management_policy".format(scsi_host_path,dir),"max_performance")


    if get("block",True,"power"):
        # block auto suspend
        block_path="/sys/block/"
        for dir in listdir(block_path):
            writefile("{}/{}/device/power/control".format(block_path,dir),"on")

    if get("usb",True,"power"):
        # usb auto suspend
        usb_path="/sys/bus/usb/devices/"
        for dir in listdir(usb_path):
            # ignore if interface type is HID or HUB
            if os.path.isfile("{}/{}/bInterfaceClass".format(usb_path,dir)):
                if readfile("{}/{}/bInterfaceClass".format(usb_path,dir)) in ["03","09"]:
                    continue
            writefile("{}/{}/power/control".format(usb_path,dir),"on")
            writefile("{}/{}/power/autosuspend_delay_ms".format(usb_path,dir),get("suspend_delay", "60000", "power"))

    if get("pci",True,"power"):
        # pci auto suspend
        pci_path="/sys/bus/pci/devices/"
        for dir in listdir(pci_path):
            writefile("{}/{}/power/control".format(pci_path,dir),"on")
            writefile("{}/{}/power/autosuspend_delay_ms".format(pci_path,dir),get("suspend_delay", "60000", "power"))
        writefile("/sys/module/pcie_aspm/parameters/policy", "performance")


    if get("i2c",True,"power"):
        # i2c auto suspend
        i2c_path="/sys/bus/i2c/devices/"
        for dir in listdir(i2c_path):
            writefile("{}/{}/power/control".format(i2c_path,dir),"on")
            writefile("{}/{}/device/power/control".format(i2c_path,dir),"on")

    if get("audio",True,"power"):
        # audio card
        writefile("/sys/module/snd_hda_intel/parameters/power_save",0)
        writefile("/sys/module/snd_hda_intel/parameters/power_save_controller","N")

    if get("turbo",True,"power"):
        # turbo boost
        writefile("/sys/devices/system/cpu/intel_pstate/no_turbo",0)
        writefile("/sys/devices/system/cpu/cpufreq/boost",1)

    if get("gpu",True,"power"):
        # gpu powersave boost
        dri_path="/sys/class/drm/"
        for card in listdir(dri_path):
            if card.startswith("card") and card[4:].isnumeric():
                writefile("{}/{}/device/power_dpm_force_performance_level".format(dri_path, card), "auto")
                writefile("{}/{}/device/power_dpm_state".format(dri_path, card), "performance")
                writefile("{}/{}/device/power/control".format(dri_path, card), "on")

    if get("network",True,"power"):
        # network
        net_path="/sys/class/net/"
        for dir in listdir(net_path):
            writefile("{}/{}/device/power/control".format(net_path,dir),"on")

    if get("bluetooth",True,"power"):
        # bluetooth
        net_path="/sys/class/bluetooth/"
        for dir in listdir(net_path):
            writefile("{}/{}/power/control".format(net_path,dir),"on")

    if get("nvme",True,"power"):
        # nvme
        net_path="/sys/class/nvme/"
        for dir in listdir(net_path):
            writefile("{}/{}/power/control".format(net_path,dir),"on")

