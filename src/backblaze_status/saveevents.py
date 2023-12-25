#!/Users/xev/opt/anaconda3/envs/backblaze_tools/bin/python

import os
import sys
import datetime
import shutil
import argparse
import math
import time
from flask import Flask, request, Response
import json
import threading

root_dir = "/Volumes/CameraCache"
dest_dir = "/Volumes/CameraHDD/SecuritySpy"
logfile = "/Volumes/CameraHDD/logfile"

port = 9842
IP = "192.168.86.250"
SERVER = True

one_minute = 60
one_hour = one_minute * 60
one_day = one_hour * 24
one_week = one_day * 7
one_month = one_day * 30

now = datetime.datetime.now()
copy_time = one_day

total_file_size = 0
total_files_copied = 0
total_files = 0

room_list = {
    "Bedroom": [
        "Bedroom Stuff Closet",
        "Bedroom Closet",
        "Bedroom Foot",
        "Bedroom Wall",
        "Bedroom Head",
        "Bedroom Overhead",
    ],
    "Patio": ["Patio Wall", "Patio Over", "Patio Screen"],
    "Living Room": ["LR Cam 1", "LR Cam 2", "LR Cam 3"],
    "Playroom": ["Playroom Cam 1", "Playroom Cam 2"],
}


class Timestamp:
    def __init__(self, timestamp):
        self.timestamp = timestamp
        self.year = timestamp[0:4]
        self.month = timestamp[4:6]
        self.day = timestamp[6:8]
        self.hour = timestamp[8:10]
        if len(timestamp) > 10:
            self.minute = timestamp[10:12]
        else:
            self.minute = "00"

        if len(timestamp) > 12:
            self.second = timestamp[12:14]
        else:
            self.second = "00"

        self.date = datetime.datetime(
            int(self.year),
            int(self.month),
            int(self.day),
            int(self.hour),
            int(self.minute),
            int(self.second),
        )


class CopyEvent(threading.Thread):
    def __init__(self):
        super(CopyEvent, self).__init__()
        self.data = {}

    def run(self):
        from_time = convert_date(self.data["q4_from"])
        to_time = convert_date(self.data["q9_to"])
        event_name = self.data["q7_eventName"]
        location = self.data["q6_location"]
        cameras = self.data["q8_cameras"]
        if cameras == "":
            cameras = None
        save_events(
            self.data["slug"],
            event_name,
            from_time,
            to_time,
            cameras,
            location,
        )


def output(id_num, data):
    print(data, end="", flush=True)
    if SERVER:
        log = open(logfile, "a")
        log.write(f"{datetime.datetime.now()}: {id_num}: {data}")
        log.flush()
        log.close()


def copy_file(src, dest, id_num, file_number, file_total):
    global total_file_size
    global total_files_copied
    global total_files

    total_files = total_files + 1
    try:
        pre_copy_time = time.perf_counter()
        stat = os.stat(src)
        total_file_size = total_file_size + stat.st_size
        file_size_gb = stat.st_size / 1000000000
        output(
            id_num,
            f"Copying ({file_number} of {file_total}) {src} -> {dest} ({file_size_gb:.2f} GB) ...",
        )
        shutil.copy2(src, dest)
        post_copy_time = time.perf_counter()
        time_diff = str(
            datetime.timedelta(seconds=post_copy_time - pre_copy_time)
        ).split(".")[0]
        output(id_num, f" in {time_diff}\n")
        total_files_copied = total_files_copied + 1

    except Exception as exp:
        output(id_num, f"Failed to copy {exp}\n")  # {src}: {exp=} {type(exp)=} {exp}')


def convert_date(data):
    if data["ampm"] != "PM":
        if int(data["hour"]) == 12:
            hour = 0
        else:
            hour = int(data["hour"])
    else:
        hour = int(data["hour"]) + 12
        if hour == 24:
            hour = 12
    date = datetime.datetime(
        year=int(data["year"]),
        month=int(data["month"]),
        day=int(data["day"]),
        hour=hour,
        minute=int(data["min"]),
    )
    return date


def save_events(
    id_num,
    event_name,
    save_start_time,
    save_end_time,
    camera_list,
    location,
):
    save_app_start_time = time.perf_counter()

    global total_files_copied

    save_total_file_size = 0
    total_files_copied = 0
    save_total_files = 0

    copy_root = root_dir

    # Figure out how many hours of video to save

    if save_end_time <= save_start_time:
        output(
            id_num,
            f"Start time {save_start_time} must be before end time {save_end_time}",
        )
        return

    time_diff = save_end_time - save_start_time
    hours = math.ceil(time_diff.total_seconds() / 60 / 60)
    if hours > 23:
        output(id_num, "Current code cannot handle more than 23 hours of video\n")
        return

    start_hour = save_start_time.hour
    end_hour = save_end_time.hour

    if end_hour >= start_hour:
        hours = end_hour - start_hour + 1
    else:
        hours = end_hour + (24 - start_hour) + 1

    output(id_num, f"Saving {hours} hours of video per camera\n")
    today = []
    tomorrow = []

    # Get the hours to save, including tomorrows if it goes over.
    for i in range(hours):
        hour = save_start_time.hour + i
        if hour > 23:
            tomorrow.append(hour - 24)
        else:
            today.append(hour)

    # Go through the cameras and save the dates
    cameras = []
    if camera_list is not None and camera_list != "":
        cameras = camera_list

    if location is not None:
        try:
            cams = room_list[location]
        except KeyError:
            output(id_num, f'No location "{location}"\n')
            return

        for i in cams:
            cameras.append(i)

    if len(cameras) == 0:
        output(id_num, "No cameras specified\n")
        return

    file_total = len(cameras) * hours
    current_file = 0

    output(
        id_num, f"Saving video for cameras: {cameras} ({file_total} files projected)\n"
    )

    dest_base = f"{dest_dir}/Saved/{event_name}"
    try:
        os.mkdir(dest_base)
    except FileExistsError:
        pass

    tag = open(f"{dest_base}/eventinfo.txt", "w")
    tag.write(f'{"Event Name:":>23} {event_name}\n')
    tag.write(
        f'{"Start Time:":>23} {save_start_time.strftime("%A %B %d %Y %I:%M %p")}\n'
    )
    tag.write(f'{"Start Time:":>23} {save_end_time.strftime("%A %B %d %Y %I:%M %p")}\n')
    tag.write(f'{"Hours per camera:":>23} {hours}\n')
    tag.write(f'{"Cameras:":>23} \n')
    for i in cameras:
        tag.write(f'{" ":>23} {i}\n')
    tag.write(f'{"Total Hours:":>23} {len(cameras) * hours}\n')
    tag.flush()
    tag.close()

    for camera in cameras:
        src_base = f'{copy_root}/{camera}/{save_start_time.strftime("%Y-%m-%d")}/{save_start_time.strftime("%Y-%m-%d")}'

        for hour in today:
            src_name = f"{src_base} {hour:02d} C {camera}.m4v"
            current_file = current_file + 1
            copy_file(src_name, dest_base, id_num, current_file, file_total)

        if len(tomorrow) > 0:
            src_base = f'{copy_root}/{camera}/{save_end_time.strftime("%Y-%m-%d")}/{save_end_time.strftime("%Y-%m-%d")}'

            for hour in tomorrow:
                src_name = f"{src_base} {hour:02d} C {camera}.m4v"

                current_file = current_file + 1
                copy_file(src_name, dest_base, id_num, current_file, file_total)

    total_time = str(
        datetime.timedelta(seconds=time.perf_counter() - save_app_start_time)
    ).split(".")[0]
    output(
        id_num,
        f"Copied {total_files_copied} files (out of {save_total_files} attempted)"
        f" with {save_total_file_size / 1000000000:.2f} GB in {total_time}\n",
    )
    tag = open(f"{dest_base}/eventinfo.txt", "a")
    tag.write(f'{"Total Files Copied:":>23} {total_files_copied}\n')
    tag.write(f'{"Total Files Attempted:":>23} {save_total_files}\n')
    tag.write(f'{"Total File Size:":>23} {save_total_file_size / 1000000000:.2f} GB\n')
    tag.write(f'{"Total Time Spent:":>23} {total_time}\n')
    tag.close()


app = Flask(__name__)


@app.route("/webhook", methods=["POST"])
def webhook():
    if request.method == "POST":
        data = json.loads(request.form["rawRequest"])
        new_thread = CopyEvent()
        new_thread.data = data
        new_thread.start()

        print("Data received from Webhook is: ", data)
        return Response(status=200)


if len(sys.argv) > 1 and sys.argv[1] == "-s":
    app.run(host="192.168.86.250", port=9842)
    exit(0)

app_start_time = time.perf_counter()

# Parse the command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="Turn on verbose mode", action="store_true")
parser.add_argument("EventName", type=str, help="The name of the event", action="store")
parser.add_argument(
    "StartTime",
    type=str,
    help="The start time in the format YYYYMMDDHHMM",
    action="store",
)
parser.add_argument(
    "EndTime", type=str, help="The end time in the format YYYYMMDDHHMM", action="store"
)
parser.add_argument(
    "-l",
    "--location",
    type=str,
    help="The room the event took place in",
    action="store",
)
parser.add_argument(
    "-c", "--camera", type=str, help="An individual camera or cameras", action="append"
)

# args = parser.parse_args(["-c", "Playroom Cam 1", "-c", "Playroom Cam 2", 'Fun Times', '2023020114', '2023020205'])
# args = parser.parse_args(["-l", "Playroom", 'Fun Times', '2023020114', '2023020205'])
args = parser.parse_args(
    [
        "-b",
        "-l",
        "Bedroom",
        "20230205 - Test Case",
        "202310302340",
        "202310310030",
    ]
)
# args = parser.parse_args()

# Get the start and end dates
start_time = Timestamp(args.StartTime).date
end_time = Timestamp(args.EndTime).date

save_events(
    args.EventName,
    args.EventName,
    start_time,
    end_time,
    args.camera,
    args.location,
)
