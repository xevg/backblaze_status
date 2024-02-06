#!/Users/Xev/anaconda3/bin/python3

import datetime
import logging
import os
import re
import signal
import smtplib
import ssl
import subprocess
import sys
import threading
import time
from datetime import timedelta

import xmltodict

from time_buffer import TimeBuffer
from build_number import VERSION, VERSION_TIME

# This program is called by
#   original_check_backup.py [large file directory]

PROGRAM_NAME = "original_check_backup.py"

# Enable showing the version number. While the program is running, use CTRL-T
print(f"Running {PROGRAM_NAME} version {VERSION} (from {VERSION_TIME})")


def show_version(signum, frame):
    print(f"\n{PROGRAM_NAME} version {VERSION} (from {VERSION_TIME})\n")


signal.signal(signal.SIGINFO, show_version)

script_directory = "/Users/Xev/Dropbox/PyProjects/BackBlaze"
default_file_size = 10 * 8  # 10485760 = 10 MB = 80 Mb
no_reset = True

# If I want additional logging, un comment out the next line
# logging.basicConfig(level=logging.DEBUG)

# The next controls the different debugging if I am in the debugger
gettrace = getattr(sys, "gettrace", None)

indebugger = False
if gettrace is None:
    print("No sys.gettrace")
elif gettrace():
    print("In Debugger")
    logging.basicConfig(level=logging.DEBUG)
    indebugger = True

# I use google for sending out email alerts. The port for SSL and the developer password for gmiail
port = 465  # For SSL
password = "waccwlalfmgbozog"
sender_email = "xev@gittler.com"
receiver_email = "xev@gittler.com"

slow_process_threshold = 20

# The drive BackBlaze uses to break down large files
LARGE_FILE_DRIVE = "Temp Backups"

# How long to sleep between iterations of the loop, for checking the logfile state
sleeptime = 1

# How long to sleep between printing report lines
large_sleeptime = 60

# The threshold of the number of files processed per second. Anything under this number counts as slow
slow_threshold = 30

# How many minutes before we send an alerts
threshold_count = 10

# The number of lines to do the header at
header_counter = 0
header_interval = 25

# The directory for the BackBlaze lasttransmitted file, and the actual log handle
#   This logfile logs the files that have been transmitted. I use this to
#   show progression between output lines
lastfilestransmitted_logdir = (
    "/Library/Backblaze.bzpkg/bzdata/bzlogs/bzreports_lastfilestransmitted"
)
lastfilestransmitted_log = None

# Set large file size
largefile_size = 0
# The directory for the BackBlaze bztransmit file, and the actual log handle
#   This logfile contains information about the current large file we are
#   processing
transmit_logdir = "/Library/Backblaze.bzpkg/bzdata/bzlogs/bztransmit"
transmit_log = None

# The path to the directory where BackBlaze breaks down large files
path = (
    sys.argv[1]
    if len(sys.argv) > 1
    else f"/Volumes/{LARGE_FILE_DRIVE}/.bzvol/bzscratch/bzcurrentlargefile/"
)

# Where the xmlfile with which file is being backed up is kept. This is mostly deprecated and
#  read from the logfile instead, but it is here for a fallback. I also set up some flags to
#  determine if the xml file has been deleted
xmlfilename = f"{path}/currentlargefile.xml"
xmlDeleted = False
firstXmlDeleted = True

# set up a rolling average for the last hour
rolling_buffer = datetime.timedelta(hours=1)

# Flags to indicate if the files have failed to open once
warned_of_failed_open_lastfiletransmitted_log = False
warned_of_failed_open_transmit_log = False

# Track the last position read in the log
oldlastfilestransmitted_logspot = 0

# How much data is remaining in the large file directory
total_file_size = 0

# Keeps track of how many passes we have gone through the main loop, so that
#   we can run the main part after a certain number
pass_counter = 0

# The day of the month for the current log file. I set it to zero initially
#   so that it definitely doesn't match an actual value, since legal values
#   are 1-31
oldlogday = 0
oldutclogday = 0

# The name of the large file
largefilename = None

# I don't know what this is
oldloglinesize = 0

# The list of the values of the number of files per second transmitted
slow_process = []

# The direction of the large file. Direction should be one:

GROWING = 0
STALLED = 1
PROCESSING = 2

direction = STALLED

# Don't rewrite headers on the first transition

first_transition = True


# The following class is to define the codes to manipulate the terminal, mostly setting color


class color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARKCYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"
    CLEAR = "\033[K"  # Delete everything till the end of the line
    REWIND = "\033[2K"  # Go to the beginning of the line


# def format_seconds(secs):
#   Takes a number of seconds and return a string in
#     days, hours, minutes and seconds


def format_seconds(secs):
    days, remainder = divmod(secs, 86400)  # 60 * 60 * 24 = 86400
    hours, remainder = divmod(remainder, 3600)  # 60 * 60 = 3600
    minutes, seconds = divmod(remainder, 60)
    hours, minutes, seconds = int(hours), int(minutes), int(seconds)

    if days > 1:
        return f"{int(days):d} days, {hours:02}:{minutes:02}:{seconds:02}"
    elif days > 0:
        return f"{int(days):d} day, {hours:02}:{minutes:02}:{seconds:02}"
    else:
        return f"{hours:02}:{minutes:02}:{seconds:02}"


# def parse_xml_file(oldFileInfo):
#   This parses the XML file to get the name of the current large file


def parseXMLFile(oldfileinfo):
    global workingfile
    global xmlDeleted
    global firstXmlDeleted

    # Set the timestamp
    parse_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Set the default value for if the file doesn't exist
    newfileinfo = {"basename": "Unknown"}

    # Try reading the xml file.  If it can be open, parse it and pull out
    #   the information in it. Hopefully the fields below are self-explanatory
    try:
        with open(xmlfilename) as fd:
            doc = xmltodict.parse(fd.read())

            firstXmlDeleted = True
            newfileinfo = {
                "filename": doc["contents"]["bzonelargefile"]["@bzfname"],
                "basename": os.path.basename(
                    doc["contents"]["bzonelargefile"]["@bzfname"]
                ),
                "size": doc["contents"]["largefileinfo"]["@numbytesinfile"],
                "created": doc["contents"]["largefileinfo"]["@filecreationtime"],
                "modified": doc["contents"]["largefileinfo"]["@filemodtime"],
                "started": doc["contents"]["otherinfo"]["@datetime_backup_started"],
                "gmt_started": doc["contents"]["otherinfo"][
                    "@millis_gmt_backup_started"
                ],
            }

            # After we get the file information, we save it as oldFileInfo, so
            #   that we can compare it. If it is the same, we are working on the
            #   same file. If not, we've changed files, so we need to reset all
            #   the statistics and inform that we have started on a new file

            if newfileinfo != oldfileinfo:
                # If we have a new file, reset the statistics
                reset_statistics()
                backup_started = datetime.datetime.strptime(
                    newfileinfo["started"], "%Y%m%d%H%M%S"
                )
                logging.debug(
                    "\n{}: Now backing up file {}. Backup started {}".format(
                        parse_timestamp, newfileinfo["filename"], backup_started
                    )
                )
                print(
                    "{}{}{} Discovered large filename: {} via XML".format(
                        color.REWIND,
                        color.CLEAR,
                        parse_timestamp,
                        newfileinfo["filename"],
                    )
                )

    # If we could not open the XML file, then its been deleted, meanimng we are
    #   not backing  up a large file, so reset the statistics and let us know.
    #   We compare newfileInfo and oldFileInfo to make sure they aren't both
    #   unknown.
    except FileNotFoundError:
        if newfileinfo != oldfileinfo:
            logging.debug(
                "{} XML file deleted ({} vs {})".format(
                    parse_timestamp, newfileinfo, oldfileinfo
                )
            )
            reset_statistics()
            xmlDeleted = True

    return newfileinfo


# def reset_last_files_transmit_log():
#     Backblaze used the day of the month as the filename for the log files.
#       If we've crossed over to a new day, we need to open the new logfile


def reset_lastfiletransmit_log():
    global lastfilestransmitted_log
    global lastfilestransmitted_logspot
    global warned_of_failed_open_lastfiletransmitted_log
    global header_counter

    # Get the day of the month
    # Apparently, this file doesn't use UTC date
    day = datetime.datetime.now().strftime("%d")

    # Open lastfilestransmitted_log
    logfile = f"{lastfilestransmitted_logdir}/{day}.log"

    reset_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        lastfilestransmitted_log = open(logfile, "r")
        print(f"{reset_timestamp} Opened logfile {logfile}")
        warned_of_failed_open_lastfiletransmitted_log = False

        # Reset header_counter so that a header gets printed
        # header_counter = 0

    # If there was an error opening the logfile, then warn about it,
    #    unless we already have
    except FileNotFoundError:
        if not warned_of_failed_open_lastfiletransmitted_log:
            print(f"{reset_timestamp} Cannot open logfile {logfile}")
            warned_of_failed_open_lastfiletransmitted_log = True
            lastfilestransmitted_log = None

            # Reset header_counter so that a header gets printed
            # header_counter = 0


# def reset_transmit_log():
#     Backblaze used the day of the month as the filename for the log files.
#       If we've crossed over to a new day, we need to open the new logfile


def reset_transmit_log():
    global transmit_log
    global transmit_logspot
    global warned_of_failed_open_transmit_log
    global header_counter

    # Get the day of the month
    day = datetime.datetime.utcnow().strftime("%d")

    # Open transmit_log
    logfile = f"{transmit_logdir}/bztransmit{day}.log"

    reset_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        transmit_log = open(logfile, "r")
        print(f"{reset_timestamp} Opened logfile {logfile}")
        warned_of_failed_open_transmit_log = False

        # Reset header_counter so that a header gets printed
        # header_counter = 0

    # If there was an error opening the logfile, then warn about it,
    #    unless we already have
    except FileNotFoundError:
        if not warned_of_failed_open_transmit_log:
            print(f"{reset_timestamp} Cannot open logfile {logfile}")
            warned_of_failed_open_transmit_log = True
            transmit_log = None

            # Reset header_counter so that a header gets printed
            # header_counter = 0


# def reset_statistics():
#   When we start working on a mew large file, we need to reset all the
#     statistics so they apply only to the new file
def reset_statistics():
    # The previous time
    global oldtime
    global files
    global oldfilecount
    global total_filecount
    global original_filecount
    global original_time
    global oldFileInfo
    global buffer
    global header_counter
    global highestnum
    global highestprocessed
    global previous_highestprocessed
    global total_dedups
    global direction

    #    global lastnum

    # Set the timestamp

    reset_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logging.debug(f"{reset_timestamp} Resetting statistics")
    print(f"{reset_timestamp} Resetting statistics")

    # The current time, which will be used as the previous time as well on
    #    this reset
    oldtime = datetime.datetime.now()

    # The current time, which will be saved as the original time that we reset
    original_time = oldtime

    # The list of files remaining in the large file directory
    files = os.listdir(path)

    # The previous number of files remaining in the large file directory
    oldfilecount = len(files)

    # The total files remaining in the large file directory
    total_filecount = len(files)

    # The original number of files remaining in the large file directory
    original_filecount = oldfilecount

    # Contents of the XML file. This is a default to be overridden
    oldFileInfo = {"error": "No file specified"}

    # The rotating buffer that contains the rolling values
    buffer = TimeBuffer(rolling_buffer)

    # The counter for how often we write out a header line in the output
    # header_counter = 0

    # A new file is neither growing nor processing
    direction = PROCESSING

    # What the highest number found in the logfile is for dedups
    highestnum = 0

    # What is the highest number chunk we have processed
    highestprocessed = 0

    # The last highestprocessed
    previous_highestprocessed = 0

    # The total number of dedups in the file
    total_dedups = 0


#    # The highest value of a file
#    lastnum = 0

#     print(f"""
# oldtime = {oldtime}
# files = {len(files):,d}
# oldfilecount = {oldfilecount:,d}
# total_filecount = {total_filecount:,d}
# original_filecount = {original_filecount:,d}
# original_time = {original_time}
# """)

# def slow_alert(slow_process):
#  Sometimes my internet slows down and I have to reset it. I know when this
#    happens because the number of files per second drops. If it drops under
#    the threshold, I send myself an email alert. This is the function
#    that sends out the email. The parameter is array of how many per minutes
#    over the last minute


def slow_alert(alert_slow_process):
    # Try and reset the wifi adapter
    try:
        wifiresult = subprocess.run(
            f"{script_directory}/resetwifi.sh",
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
        ).stdout.decode("utf-8")
    except:
        wifiresult = f"Error resetting wifi adapter ('{script_directory}/resetwifi.sh'): {sys.exc_info()[0]}"

    print(wifiresult)

    # We need to wait for the wifi to come back
    print("Sleeping until wifi comes back ...")
    time.sleep(10)

    message = f"""\
    Subject: Backblaze running slowly at {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    Attempt to reset wifi adapter: {wifiresult}

    Last items per minutes: {alert_slow_process}"""

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", port, context=context) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message)
    except:
        print(f"Could not email {wifiresult}:\n{alert_slow_process}")


# file_size_string():
#   This function returns a string with the file size in either GB or MB,
#   depending on the file size. < 1GB, use MB, otherwise use GB


def file_size_string(size):
    if size < 1073741824:
        return f"{size / 1024 / 1024:,.2f} MB"
    else:
        return f"{size / 1024 / 1024 / 1024:,.2f} GB"


# def precheck():
#   This function kicks off a few seconds before the reporting happens and
#     calculates the file sizes of the remaining files


def precheck():
    global total_file_size

    # Since this kicks off as a different thread, sometimes I want to track
    #    when it is running amd when it is done running

    #    logging.debug('Starting precheck')

    # Reset the total file size
    total_file_size = 0

    # Get the number of files in the directory
    check_files = os.listdir(path)def precheck():
    global total_file_size

    # Since this kicks off as a different thread, sometimes I want to track
    #    when it is running amd when it is done running

    #    logging.debug('Starting precheck')

    # Reset the total file size
    total_file_size = 0

    # Get the number of files in the directory
    check_files = os.listdir(path)

    # Go through and calculate the total size of the files remaining
    for f in check_files:
        fp = os.path.join(path, f)
        # skip if it is symbolic link
        try:
            if not os.path.islink(fp):
                # Right now, Backblaze has stopped working as expected, and instead of putting
                #  the file chunks in the directory, it is putting a small file with a pointer
                #  to it. So instead of looking at file sizes now, I am going to temporarily
                #  just add 100MB for each file.

                #                total_file_size += os.path.getsize(fp)
                total_file_size += 10485760  # The size of the chunk in bytes
        except:
            pass

    # Go through and calculate the total size of the files remaining
    for f in check_files:
        fp = os.path.join(path, f)
        # skip if it is symbolic link
        try:
            if not os.path.islink(fp):
                # Right now, Backblaze has stopped working as expected, and instead of putting
                #  the file chunks in the directory, it is putting a small file with a pointer
                #  to it. So instead of looking at file sizes now, I am going to temporarily
                #  just add 100MB for each file.

                #                total_file_size += os.path.getsize(fp)
                total_file_size += 10485760  # The size of the chunk in bytes
        except:
            pass


#   logging.debug('precheck done')


# Before we start the main loop, reset the statistics, which initializes
#   all the values
reset_statistics()

# Compile the filename search regular expression
name_search_re = re.compile("seq[0-9a-f]*")

# Compile the chunk search regular expression
chunk_search_re = re.compile("Chunk [^ ]*")

# Compile the match for prepare large file search
prepare_match_re = re.compile(".*Entering PrepareBzLargeFileDirWithLargeFile.*")

# Compile the search for dedup
dedup_search_re = re.compile("chunk ([^ ]*) for this largefile")

# Compile the search for dedup in processing file
processing_dedup_search_re = re.compile("dedup - 0 bytes - Chunk ([^ ]*) of")

# Set the width of the various parts of the line

time_len = 17
current_line_len = 107
moving_line_len = 78
total_line_len = 102
vertical_line = "|"  # u'\u2503'
header_vertical_line = color.END + vertical_line + color.BOLD

# Start the main loop
while True:
    pass_counter = pass_counter + 1
    # Count the number of passes through the loop
    #    logging.debug(f'Pass Counter = {pass_counter}')

    # Set the current day
    utclogday = datetime.datetime.utcnow().day
    logday = datetime.datetime.now().day

    # Check to see if we crossed over midnight and now its a new day. lastfiletransmit uses now, while transmit uses utc
    if logday != oldlogday:
        # If it is a new day, reset the log files
        reset_lastfiletransmit_log()

        # Set what the current day is as old day
        oldlogday = logday

        # If we have successfully opened the lastfiletransmitted log,
        #   then set the pointer to the end of the file, because we do
        #   not care about the log lines that happened before, because
        #   I only care about the currently transmitting file
        if lastfilestransmitted_log is not None:
            lastfilestransmitted_log.seek(0, 2)
            oldlastfilestransmitted_logspot = lastfilestransmitted_log.tell()

    # If we have not changed days ...
    elif utclogday != oldutclogday:
        reset_transmit_log()

        # Set what the current day is as old day
        oldutclogday = utclogday

    else:
        # If we couldn't open the logfile previously, try again. Sometimes
        #   when crossing days the file isn't created immediately
        if lastfilestransmitted_log is None:
            reset_lastfiletransmit_log()

            # If it successfully opens this time, then go to the end of the file
            if lastfilestransmitted_log is not None:
                lastfilestransmitted_log.seek(0, 2)
                oldlastfilestransmitted_logspot = lastfilestransmitted_log.tell()

        # If the transmit_log isn't open, try and open it
        if transmit_log is None:
            reset_transmit_log()

    # Because sometimes reading the logfile takes a long time
    #   (especially since I have the sleep in there to make it readable),
    #   sometimes it goes for many minutes before it returns. To avoid
    #   this, I put a timer in and if it is over a minute, then I will
    #   skip the normal sleep and just continue at the next pass

    start_log_scan = datetime.datetime.now()
    skip_sleep = False

    # The following is an example of the log line that we are searching for:
    # 20200728083746 - Entering PrepareBzLargeFileDirWithLargeFile - procid=80360, numMBytesStartMemSize=5454, using external scratch drive path_A_XYZ: /Volumes/Temp Backups/.bzvol/bzscratch/bzcurrentlargefile/, dir for: /Volumes/Photo Storage/Photos.dmg
    #   From this file we pull out the large file we are currently working
    #   on. Since it might have started prior to the program starting, we
    #   scan the entire file and don't start at the end.

    if transmit_log is not None:
        try:
            line = transmit_log.readline()
        except:
            continue

        # If we discover a new largefile, then we want to reset the
        #   statistics, but we don't need to do it multiple times if
        #   we are scanning a log file, so just check at the end of the
        #   while loop to see if we found one
        new_largefile_found = False

        while line:
            if prepare_match_re.match(line):
                largefilename_long = line.split(": ")[-1].rstrip()
                largefilename = line.split("/")[-1].rstrip()
                logtimestamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                    int(line[0:4]),
                    int(line[4:6]),
                    int(line[6:8]),
                    int(line[8:10]),
                    int(line[10:12]),
                    int(line[12:14]),
                )

                # Since we have the file name, get the size of the file
                #   that we can use as a comparison
                try:
                    largefile_size = os.path.getsize(largefilename_long)
                    total_filecount = int(largefile_size / 1024 / 1024 / 10)  # MB
                except:
                    largefile_size = 0
                    total_filecount = 0

                # Create the timestamp
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(
                    "{}{}{} Discovered large filename: {} via logfile at {}".format(
                        color.REWIND,
                        color.CLEAR,
                        timestamp,
                        largefilename_long,
                        logtimestamp,
                    )
                )

                # Reset header_counter so that a header gets printed
                # header_counter = 0

                # Since we've discovered a new file, we are going to reset
                #   the statistics
                new_largefile_found = True

            # If we are growing a large file, but have a lot of dedups, record
            #  the number we are up to. The format is:
            # 20200926215431 - PRE_DEDUP: procid=28591, the best kind of dedup (pre_dedup) for chunk 8310 for this largefile: /Volumes/Media/Alisha.dmg
            x = dedup_search_re.search(line)
            if x is not None:
                total_dedups = total_dedups + 1
                highestnum = int(x.group(1))

                if highestnum > total_filecount:
                    total_filecount = highestnum

                if total_filecount == 0:
                    percentage = 0
                    percentage = 0
                else:
                    percentage = highestnum / total_filecount

                # Show the progress via log entries
                if indebugger:
                    print(
                        "{}{}{}log: Deduped chunk {:,d} of {:,d} ({:2.1%}){}\r".format(
                            color.REWIND,
                            color.CLEAR,
                            color.BLUE,
                            highestnum,
                            total_filecount,
                            percentage,
                            color.END,
                        ),
                        flush=True,
                        end="",
                    )
                    # pass
                else:
                    print(
                        "{}{}{}log: Deduped chunk {:,d} of {:,d} ({:2.1%}){}\r".format(
                            color.REWIND,
                            color.CLEAR,
                            color.BLUE,
                            highestnum,
                            total_filecount,
                            percentage,
                            color.END,
                        ),
                        flush=True,
                        end="",
                    )

            try:
                line = transmit_log.readline()
            except:
                line = "\n"

        # If in the scan of the file we found a new largefile, we will
        #   reset the statistics
        if new_largefile_found:
            reset_statistics()
            new_largefile_found = False

    # Check lastfilestransmitted_logfile if we have opened it
    #   successfully

    if lastfilestransmitted_log is not None:
        lastfilestransmitted_log.seek(0, 2)
        newlastfilestransmitted_logspot = lastfilestransmitted_log.tell()

        # The following gets executed if something new has been added to the
        #    logfile. If we are at the same spot, then we don't do it.
        if newlastfilestransmitted_logspot != oldlastfilestransmitted_logspot:
            # The line we are looking for looks like this:
            # 2020-07-23 16:29:22 -  large  - throttle manual   11 -  3933 kBits/sec -  1858394 bytes - Chunk 0001f of /Users/script/Library/Messages/chat.db
            # The part we care about starts with "chunk" at position 54

            # Set the file to the last point we read through, and read the
            #   next line. If the read fails, just keep going and we'll try
            #   to do it again next time
            lastfilestransmitted_log.seek(oldlastfilestransmitted_logspot, 0)
            while True:
                try:
                    line = lastfilestransmitted_log.readline()
                except:
                    continue

                # Count the dedup lines
                x = processing_dedup_search_re.search(line)
                if x is not None:
                    total_dedups = total_dedups + 1

                # The part of the line we care about.
                line_output = line[54:]

                # Find the chunk number and convert it to int
                x = chunk_search_re.search(line_output)
                chunknum = None
                chunkstr = ""
                if x is not None:
                    chunkhex = x.group()[6:]
                    chunknum = int(chunkhex, base=16)
                    chunkstr = f" ({chunknum:,d})"

                    # Keep track of the highest processed chunk
                    if chunknum > highestprocessed:
                        highestprocessed = chunknum

                if len(line_output) > 0:
                    print(
                        "{}{}{}log: {}{}{}\r".format(
                            color.REWIND,
                            color.CLEAR,
                            color.BLUE,
                            line_output.rstrip(),
                            chunkstr,
                            color.END,
                        ),
                        flush=True,
                        end="",
                    )

                #  Set the new last spot to the point in the file we are at
                oldlastfilestransmitted_logspot = lastfilestransmitted_log.tell()

                # We want to process the whole file, in this pass, even if there
                #    are many lines, so drop the pass_counter by one so that we
                #    continue reading lines until we are done
                pass_counter = pass_counter - 1

                # Sleep for a fraction of a second (5/100th of a second) just to
                #    let the line be readable
                time.sleep(0.02)

                # See if its been over a minute. If it has been, stop processing
                #   the logfile

                logtime_diff = datetime.datetime.now() - start_log_scan
                if logtime_diff.total_seconds() > large_sleeptime:
                    skip_sleep = True
                    break
                else:
                    #                # Go to the next line
                    continue

    # Parse the XML file to see if the file has changed
    oldFileInfo = parseXMLFile(oldFileInfo)

    # Sleep a short time
    if not skip_sleep:
        time.sleep(sleeptime)

    # 3 passes (seconds) before we do the main part we run the precheck
    #   in a different thread
    if pass_counter == large_sleeptime - 3:
        t = threading.Timer(0.1, precheck)
        t.start()
        continue

    if skip_sleep:
        t = threading.Timer(0.1, precheck)
        t.start()
        # Give the precheck time to complete
        time.sleep(3)
    elif pass_counter != large_sleeptime:
        # Continue until we reach the right time
        continue

    # If wa are at this point then we do the calculations and print the
    #   information out

    # First, reset the pass_counter back to zero for next time.
    pass_counter = 0

    # Get the list of files
    files = os.listdir(path)

    # Get the name of the last file
    if len(files) == 0:
        lastname = "Unknown"
        firstname = "Unknown"
    else:
        lastname = files[-1]
        if len(files) == 1:
            firstname = files[0]
        else:
            firstname = files[1]

    # Search for the number of the file. Filenames are increasing numbers
    #   in hex. This gives us an idea of where we are.
    #   Initially I was getting the first one by the first number in the
    #   directory, but sometimes a file doesn't get processed, and then it
    #   stays there till the end. So for the firstnum, I am going to use
    #   the lastnum minus the total in the directory

    x = name_search_re.search(lastname)
    if x is not None:
        lasthex = x.group()[3:]
        lastnum = int(lasthex, base=16)
        firstnum = lastnum - len(files)
    else:
        lastnum = 0
        firstnum = 0

    # Get the count of the files
    filecount = len(files)

    # Set the difference of previous filecount to the current one
    filediff = oldfilecount - filecount

    # Set the difference of the original filecount to the current one
    total_filediff = original_filecount - filecount

    # Check for slow connections. Sometimes the internet connection slows down.
    #   If the count of files transmitted is below the threshold, but not
    #   completely stopped, record the speed. If its above the threshold
    #   then reset the list
    if slow_threshold > filediff > 0:
        slow_process.append(filediff)
    else:
        slow_process = []

    # Send an alert if we are slow for more than the correct number attempts,
    #    send an alert and reset the count
    if len(slow_process) > slow_process_threshold and not no_reset:
        slow_alert(slow_process)
        slow_process = []

    # Get the time
    timenow = datetime.datetime.now()

    # Create the timestamp
    timestamp = timenow.strftime("%Y-%m-%d %H:%M:%S")

    # Record the differences in time
    timediff = timenow - oldtime
    total_timediff = timenow - original_time

    # Seconds aren't recorded in days? I'm going to try total_seconds and
    #    see if that works
    total_seconds = int(total_timediff.total_seconds())

    # Calculate the process rate and total process rate
    process_rate: float = abs(filediff) / float(timediff.total_seconds())
    total_process_rate: float = abs(total_filediff) / float(
        total_timediff.total_seconds()
    )

    # Check to see if the process rate is zero, which means nothing is going
    #   on. If it is, mark it as stalled. If it is not, then calculate
    #   the time remaining, both for the current time and the total time

    if process_rate == 0:
        remaining_time = "stalled"
    else:
        remaining_time = format_seconds(filecount / process_rate)

    if total_process_rate == 0:
        total_remaining_time = "stalled"
    else:
        total_remaining_time = format_seconds(filecount / total_process_rate)

    if largefilename is not None:
        thisfilename = largefilename
    else:
        thisfilename = oldFileInfo["basename"]

    # Create and format the line
    prefix = f"{timestamp} ({thisfilename}) "
    prefix_len = len(prefix)

    # Every {header_interval} lines print out a header line, or when there
    #   is a new file
    if (header_counter % header_interval) == 0:
        print(
            "{}{}\n{} {} {} {} {} {} {} {}".format(
                color.REWIND,
                color.BOLD,
                "".rjust(prefix_len),
                header_vertical_line,
                "Current".center(current_line_len),
                header_vertical_line,
                "1-Hour Moving Average".center(moving_line_len),
                header_vertical_line,
                "Total".center(total_line_len),
                header_vertical_line,
            )
        )

        print(
            "{} {} {} {} {} {} {} {}{}".format(
                "".rjust(prefix_len),
                header_vertical_line,
                "".rjust(current_line_len, "-"),
                header_vertical_line,
                "".rjust(moving_line_len, "-"),
                header_vertical_line,
                "".rjust(total_line_len, "-"),
                header_vertical_line,
                color.END,
            )
        )

    header_counter = header_counter + 1

    # Before we print out the data, we need the existing file sizes, which
    #   is gathered by the precheck thread, so we wait for that to end
    #   before we continue
    t.join()

    # The differences in files can go one of two ways. Either it is a positive
    #   number, which means that we are processing the files downward, or
    #   it is a negative number, in which case the number of files is
    #   growing. What we print out will be different based on that.
    #   First, if we are processing files down
    if filediff > 0:
        if direction != PROCESSING:
            # If we have changed direction, reset the statistics
            if first_transition:
                first_transition = False
            else:
                reset_statistics()
            direction = PROCESSING
            logging.debug("Changed direction to PROCESSING")

        # Add the current information to the rotating buffer
        buffer.add(
            {
                "rate": process_rate,
                "time": timenow,
                "files": filediff,
                "seconds": int(timediff.total_seconds()),
            }
        )

        # Get the data from the moving average
        moving = buffer.get()
        if moving["rate"] > 0:
            moving_remaining_time = format_seconds(filecount / moving["rate"])
        else:
            moving_remaining_time = "0"

        if filediff > 0:
            current_sec_per_file = timediff.total_seconds() / filediff
            current_file_per_sec = filediff / timediff.total_seconds()
        else:
            current_sec_per_file = 0
            current_file_per_sec = 0

        # Format the information for the current minute
        #        current_line = "{:4,d} of {:7,d} files ({}) in {} seconds at {:5.2f} sec/file ({:5,.2f} Mb/sec) - {}" \
        #            .format(filediff, filecount, file_size_string(total_file_size),  # the filesize in GB
        #                    int(timediff.total_seconds()), current_sec_per_file,
        #                    filediff * default_file_size / int(timediff.total_seconds()),
        #                    remaining_time.rjust(time_len))

        current_line = "{:5,d} of {:7,d} files ({:9s}) in {:3} seconds at {:5.2f} files/sec ({:8,.2f} Mb/sec) - {}".format(
            filediff,
            filecount,
            file_size_string(total_file_size),  # the filesize in GB
            int(timediff.total_seconds()),
            current_file_per_sec,
            filediff * default_file_size / int(timediff.total_seconds()),
            remaining_time.rjust(time_len),
        )

        if moving["files"] > 0:
            moving_sec_per_file = moving["totaltime"] / moving["files"]
            moving_file_per_sec = moving["files"] / moving["totaltime"]
        else:
            moving_sec_per_file = 0
            moving_file_per_sec = 0

        # Format the information for the moving average
        #       moving_line = '{:7,d} in {} at {:5.2f} sec/file ({:5,.2f} Mb/sec) - {}' \
        #           .format(moving["files"], format_seconds(moving["totaltime"]), moving_sec_per_file,
        #                   moving["files"] * default_file_size / moving["totaltime"],
        #                   moving_remaining_time.rjust(time_len))

        moving_line = "{:7,d} in {} at {:5.2f} files/sec ({:8,.2f} Mb/sec) - {}".format(
            moving["files"],
            format_seconds(moving["totaltime"]),
            moving_file_per_sec,
            moving["files"] * default_file_size / moving["totaltime"],
            moving_remaining_time.rjust(time_len),
        )

        if original_filecount == 0:
            percentage_done = 0
        else:
            percentage_done = total_filediff / original_filecount

        #        if total_filediff == 0:
        #            percentage_dups = 0
        #        else:
        #            percentage_dups = total_dedups / total_filediff

        if highestprocessed == 0:
            percentage_dups = 0
        else:
            percentage_dups = total_dedups / highestprocessed

        total_line = "{:7,d} of {:7,d} files ({:>5.1%}) ({:7,d} tx, {:7,d} dups ({:>5.1%})) in {:s} at {:6.2f}/sec".format(
            total_filediff,
            original_filecount,
            percentage_done,
            highestprocessed - total_dedups,  # total_filediff - total_dedups,
            total_dedups,
            percentage_dups,
            format_seconds(total_seconds).rjust(time_len),
            total_process_rate,
        )

        # Use moving metric for complete time, because the current is too
        #   variable, and the total has too much cruft in it
        if moving["rate"] == 0:
            projected_complete = ""
        else:
            difference_in_seconds = timenow + timedelta(
                seconds=int(filecount / moving["rate"])
            )
            projected_complete = "{:%a %m/%d %I:%M %p}".format(difference_in_seconds)
            # '%a %b %d, %Y %I:%M %p'

        # Set slow data, to either blank if it is not slow,
        #    or a warming if it is
        slow_data = ""
        if len(slow_process) > 0:
            if slow_process == 1:
                minute = "minute"
            else:
                minute = "minutes"

        # slow_data = f", {color.RED}{color.BOLD}last {len(slow_process):2d} {minute} under {slow_threshold}/minute{
        # color.END}"

        if lastnum == 0:
            percentage = 0
        else:
            # Originally I did percentage of total_filediff and total_filecount, but
            #   that is based on what is being done this go around, which looks different
            #   than what is being displayed, because its showing the highestprocessed and
            #   the total_filecount.
            #            percentage = total_filediff / original_filecount
            #            percentage = highestprocessed / original_filecount
            # I don't really want original_filecount, I want to see the percentage of the
            #   file that is done, not the percentage of this pass. Is that right? We'll see.

            percentage = highestprocessed / lastnum

        # Print out the line
        if len(current_line) > current_line_len:
            current_line_len = len(current_line)

        if len(moving_line) > moving_line_len:
            moving_line_len = len(moving_line)

        if len(total_line) > total_line_len:
            total_line_len = len(total_line)

        print(
            "{}{} {} {} {} {} {} {} {} {:2.1%} Complete {} - {:,d} of {:,d} parts{}".format(
                color.REWIND,
                prefix,
                vertical_line,
                current_line.ljust(current_line_len),
                vertical_line,
                moving_line.ljust(moving_line_len),
                vertical_line,
                total_line.ljust(total_line_len),
                vertical_line,
                percentage,
                projected_complete,
                highestprocessed,  # not highestnum ??
                # total_filediff, # total_filecount,
                lastnum,
                slow_data,
            )
        )

    # If BackBlaze is creating the largefiles, print info about that
    #    elif filediff < 0:
    else:
        if direction != GROWING:
            # If we have changed direction, reset everything
            if first_transition:
                first_transition = False
            else:
                # Since we reset with a new file name, is this reset needed?
                pass  # reset_statistics()
            logging.debug("Changed direction to GROWING")
            direction = GROWING

        filediff = abs(filediff)

        original_filecount = original_filecount + filediff

        # If there is an error or something and BackBlaze needs to clear out
        #   the large file directory, it does that after it says that there
        #   is a new file, so when the reset_statistics is done, there
        #   are more files in the directory than when it starts.
        #   Therefore, I will check to see if the number of
        #   original_filecount is greater than the current filecount
        #   (when the directory is growing, only), and if it is, adjust it
        #   down.
        if original_filecount > filecount:
            logging.debug(
                f"{timestamp} Adjusting original_filecount from {original_filecount} to {filecount}"
            )
            original_filecount = filecount

        # If we have the total size of the file, display that
        if largefile_size > 0:
            largefile_size_gb = largefile_size / 1024 / 1024 / 1024
            largefile_size_string = f" ({largefile_size_gb:7,.2f} GB)"

            # The largefile is broken up into 10MB chunks, so the total number
            #   that we will have is largefile_size / 1024 / 1024 / 10
            total_filecount = int(largefile_size / 1024 / 1024 / 10)  # MB
            total_remaining_files = total_filecount - filecount
            if total_process_rate == 0:
                total_remaining_time = 0
            else:
                total_remaining_time = format_seconds(
                    total_remaining_files / total_process_rate
                )

            largefile_size_total_string = " at {:6.2f}/sec".format(total_process_rate)
        else:
            largefile_size_gb = 0
            largefile_size_string = ""
            largefile_size_total_string = "              "
            # If we don't have a total file size, make the lastnum
            #   what we have so far
            total_filecount = lastnum
            total_remaining_files = total_filecount - (filecount + total_dedups)

        # If we are growing with lots of dedups, set the total_processed to
        #   the number found there, otherwise, to the original_filecount
        if highestnum > original_filecount:
            total_processed = highestnum
            moving_filediff = highestnum - previous_highestprocessed
            previous_highestprocessed = highestnum
        else:
            total_processed = original_filecount
            moving_filediff = filediff

        # Calculate the process rate and total process rate
        moving_process_rate: float = abs(moving_filediff) / float(
            timediff.total_seconds()
        )

        # Add the current information to the rotating buffer
        buffer.add(
            {
                "rate": moving_process_rate,
                "time": timenow,
                "files": moving_filediff,
                "seconds": int(timediff.total_seconds()),
            }
        )

        # Get the data from the moving average
        moving = buffer.get()
        if moving["rate"] > 0:
            moving_remaining_time = format_seconds(
                total_remaining_files / moving["rate"]
            )
        else:
            moving_remaining_time = "0"

        if moving["files"] == 0:
            moving_sec_per_file = 0
            moving_file_per_sec = 0
        else:
            moving_sec_per_file = moving["totaltime"] / moving["files"]
            moving_file_per_sec = moving["files"] / moving["totaltime"]

        # Format the information for the moving average
        #        moving_line = '{:7,d} in {} at {:5.2f} sec/file - {}' \
        #            .format(moving["files"], format_seconds(moving["totaltime"]),
        #                    moving_sec_per_file, moving_remaining_time.rjust(time_len))

        moving_line = "{:7,d} in {} at {:5.2f} files/sec - {}".format(
            moving["files"],
            format_seconds(moving["totaltime"]),
            moving_file_per_sec,
            moving_remaining_time.rjust(time_len),
        )

        total_line = " Processed {:7,d} files in {:s} at {:6.2f}/sec".format(
            total_processed,
            format_seconds(total_seconds).rjust(time_len),
            abs(total_filediff) / total_seconds,
        )

        # Use moving metric for complete time, because the current is too
        #   variable, and the total has too much cruft in it
        if moving["rate"] == 0:
            projected_complete = ""
        else:
            difference_in_seconds = timenow + timedelta(
                seconds=int(total_remaining_files / moving["rate"])
            )
            projected_complete = "{:%a %m/%d %I:%M %p}".format(difference_in_seconds)

        if total_filecount == 0:
            percentage = 0
        else:
            percentage = total_processed / total_filecount

        if total_processed == 0:
            dedup_percentage = 0
        else:
            dedup_percentage = total_dedups / total_processed

        if filediff > 0:
            current_sec_per_file = timediff.total_seconds() / filediff
            current_file_per_sec = filediff / timediff.total_seconds()
        else:
            current_sec_per_file = 0
            current_file_per_sec = 0

        #        growth_string = 'Added {:,d} files at {:5.2f} sec/file (now: {:,d}, {}, {:,d} ({:2.1%}) dups)' \
        #            .format(filediff, current_sec_per_file, filecount,
        #                    file_size_string(total_file_size), total_dedups,
        #                    dedup_percentage, largefile_size_string) \
        #            .center(current_line_len)  # GB

        growth_string = "Added {:,d} files at {:5.2f} files/sec (now: {:,d}, {}, {:,d} ({:2.1%}) dups)".format(
            filediff,
            current_file_per_sec,
            filecount,
            file_size_string(total_file_size),
            total_dedups,
            dedup_percentage,
            largefile_size_string,
        ).center(
            current_line_len
        )  # GB

        if len(growth_string) > current_line_len:
            current_line_len = len(growth_string)

        if len(moving_line) > moving_line_len:
            moving_line_len = len(moving_line)

        if len(total_line) > total_line_len:
            total_line_len = len(total_line)

        print(
            "{}{} {} {} {} {} {} {} {} {:2.1%} Complete {} - {:,d} of {:,d} parts {}".format(
                color.REWIND,
                prefix,
                vertical_line,
                growth_string,
                vertical_line,
                moving_line.center(moving_line_len),
                vertical_line,
                total_line.center(total_line_len),
                vertical_line,
                percentage,
                projected_complete,
                total_processed,
                total_filecount,
                largefile_size_string,
            )
        )

    # Process if no files have been added or removed from the directory
    #    else:
    #        if largefile_size > 0:
    #            total_filecount = int(largefile_size / 1024 / 1024 / 10) #MB
    #            largefile_size_gb = largefile_size / 1024 / 1024 / 1024
    #            largefile_size_string = f" ({largefile_size_gb:7,.2f} GB)"
    #        else:
    #            total_filecount = original_filecount
    #            largefile_size_string = ""

    #        if largefile_size > 0:
    #            total_process_rate:float = (total_filecount - highestnum) / float(total_timediff.total_seconds())
    #
    #            if total_filecount == 0:
    #                totalpercentage = 1
    #            else:
    # totalpercentage = len(files) / original_filecount
    #                totalpercentage = highestnum / total_filecount

    #            total_line = "{:7,d} of {:7,d} files ({:5.1%}) in {:s} at {:6.2f}/sec" \
    #                .format(#len(files),
    #                        highestnum, total_filecount, totalpercentage,
    #                        format_seconds(total_seconds).rjust(time_len),
    #                        total_process_rate)
    #            print("{}{} {} {} {} {} {} {} {} {:2.1%} Complete - {:,d} ({:,d}) of {:,d} parts {}"
    #                .format(color.REWIND, prefix, vertical_line,
    #                        'No Change'.center(current_line_len),
    #                        vertical_line, ''.center(moving_line_len), vertical_line,
    #                        total_line.ljust(total_line_len), vertical_line,
    #                        highestnum / total_filecount, highestnum,
    #                        original_filecount, total_filecount,
    #                        largefile_size_string))
    #        else:
    #            if total_filecount == 0:
    #                totalpercentage = 1
    #            else:
    #                totalpercentage = total_filediff / total_filecount

    #            total_line = "{:7,d} of {:7,d} files ({:5.1%}) in {:s} at {:6.2f}/sec" \
    #                .format(total_filediff, total_filecount, totalpercentage,
    #                    format_seconds(total_seconds).rjust(time_len),
    #                    total_process_rate)

    #            print("{}{} {} {} {} {} {} {} {} {:,d} of {:,d} parts {}"
    #                .format(color.REWIND, prefix, vertical_line,
    #                    'No Change'.center(current_line_len),
    #                    vertical_line, ''.center(moving_line_len), vertical_line,
    #                    total_line.ljust(total_line_len), vertical_line, firstnum,
    #                    total_filecount, largefile_size_string))

    oldfilecount = filecount
    oldtime = timenow
    old_total_file_size = total_file_size
