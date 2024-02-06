# from https://gist.github.com/ganesh-k13/f8a9c09192841570033c69ffa4665e8d

import threading
import functools

# Constants
class Lock:
    DB_LOCK = threading.RLock()
    PROGRESS_CALCULATE = threading.RLock()


def lock(lock_name: threading.Lock):
    def deco(f):
        @functools.wraps(f)
        def inner(*args, **kwargs):
            with lock_name:
                return f(*args, **kwargs)

        return inner

    return deco
