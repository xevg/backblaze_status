"""
Custom exceptions for backblaze_status
"""


class CurrentFileNotSet(Exception):
    pass


class PreviousFileNotSet(Exception):
    pass


class CompletedFileNotFound(Exception):
    pass
