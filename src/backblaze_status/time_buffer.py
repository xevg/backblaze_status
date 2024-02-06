import datetime
from datetime import timedelta


class TimeBuffer:
    # Data object contains:
    #   "rate": process_rate,
    #   "time": time_now,
    #   "files": file_diff,
    #   "seconds": timediff.seconds

    def __init__(self, expiration):
        self.data = []
        self.expiration = expiration + datetime.timedelta(minutes=1)

    def add(self, new_data):
        self.data.append({"timestamp": datetime.datetime.now(), "data": new_data})
        self.test = "test"

    # I could make this more generic by
    def get(self):
        #        calcdata = []
        total_time = 0
        total_files = 0

        for item in self.data:
            timestamp = item["timestamp"]
            now = datetime.datetime.now()
            if (now - timestamp) > self.expiration:  # Remove items over expiration
                self.data.remove(item)
            else:
                #                calcdata.append(item["data"]["rate"])
                total_time = total_time + item["data"]["seconds"]
                total_files = total_files + item["data"]["files"]
        if total_time == 0:
            return {"files": total_files, "rate": 0, "total_time": 0}
        else:
            rate = float(total_files) / float(total_time)
            return {"files": total_files, "rate": rate, "total_time": total_time}
