import os
def enable_usb_wakeups():
    if not os.path.isdir("/sys/bus/usb/devices"):
        return
    for dir in os.listdir("/sys/bus/usb/devices"):
        file = "/sys/bus/usb/devices/{}/power/wakeup".format(dir)
        if os.path.isfile(file):
            with open(file,"w") as f:
                f.write("enabled")
                f.flush()
