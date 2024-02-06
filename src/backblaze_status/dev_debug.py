from icecream import ic, IceCreamDebugger
from datetime import datetime
import inspect
from types import FrameType, FunctionType, TracebackType
from typing import cast


class DevDebug(IceCreamDebugger):
    """
    DevDebug class lets you turn on or off debugging for items with specific tags and sub-tags

    If your tag is "a.b.c", then it is true if you specify "a", "a.b" or "a.b.c"

    """

    _enabled: set = set()
    _disabled: set = set()

    def __init__(self, enabled_mode: bool = True):
        """
        This class runs in one of two modes, enabled_mode and disabled_mode.
        In enabled_mode, all tags are enabled unless you explicitly disable them
        In disabled_mode, all tags are disabled unless you explicitly enable them

        :param enabled_mode: bool: The default, uses enabled_mode
        """
        super().__init__()

        self.enabled_mode = enabled_mode

        self.configureOutput(
            includeContext=True, prefix=self.get_timestamp
        )

    @staticmethod
    def get_timestamp():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S ")

    def _found_in_tags(self, tag: str) -> tuple:
        """
        This method returns a tuple of (enabled, disabled) where the value is the precision of the item.
        So for instance, for tag a.b.c, if a.b.c is in the set, then it return 3, if a is in the set, it returns 1
        """
        split_items = tag.split(".")
        tag_items = []

        while len(split_items) > 0:
            tag_items.append(".".join(split_items))
            del split_items[-1]

        def _scan_list(tags: set) -> int:
            for check_tag in tag_items:
                if check_tag in tags:
                    return len(check_tag.split("."))
            return 0

        return _scan_list(self._enabled), _scan_list(self._disabled)

    def is_enabled(self, tag: str) -> bool:
        """
        The logic for enabled:
            - if tag is "a.b.c" then:
                 For specific matches:
                    - if "a.b.c" is in enabled, then it is enabled
                    - if "a.b.c" is in disabled, then it is disabled
                 If there is nto a specific match
        """

        found_in_enabled, found_in_disabled = self._found_in_tags(tag)
        if found_in_enabled == found_in_disabled:
            # Not found in either, or they are both the same. In that case, if enabled_mode, then it defaults enabled
            #  If disabled mode, it defaults disabled

            if self.enabled_mode:
                return True
            else:
                return False

        if found_in_enabled > found_in_disabled:
            return True
        else:
            return False

    def _add_tag(self, tag: str) -> None:
        self._tags.add(tag)

    def _discard_tag(self, tag: str) -> None:
        super_tag = f"{tag}."
        for item in self._tags:
            if item == tag or item.startswith(super_tag):
                self._tags.discard(item)

        # The special tag '.' removes all items from the list

    def is_disabled(self, tag: str) -> bool:
        return not self.is_enabled(tag)

    def enable(self, tag: str) -> None:

        # Add it to enabled, and make sure it's not in disabled
        self._enabled.add(tag)
        self._disabled.discard(tag)

        return

    def disable(self, tag: str) -> None:

        # Add it to disabled and make sure its not in enabled
        self._disabled.add(tag)
        self._enabled.discard(tag)
        return

    def show(self):
        enabled_tags = ", ".join(self._enabled)
        disabled_tags = ", ".join(self._disabled)
        tags = []
        if self.enabled_mode:
            for tag in self._disabled:
                if self.is_disabled(tag):
                    tags.append(tag)
            print(f"All tags enabled except: {', '.join(tags)}")
        else:
            for tag in self._enabled:
                if self.is_enabled(tag):
                    tags.append(tag)
            print(f"All tags disabled except: {', '.join(tags)}")

    def print(self, tag: str, message: str):
        if self.is_enabled(tag):
            self(f"<{tag}> {message}")

    def __call__(self, *args):
        if self.enabled:
            callFrame = inspect.currentframe().f_back
            previous_frame = cast(FrameType, callFrame.f_back)
            self.outputFunction(self._format(previous_frame, *args))

        if not args:  # E.g. ic().
            passthrough = None
        elif len(args) == 1:  # E.g. ic(1).
            passthrough = args[0]
        else:  # E.g. ic(1, 2, 3).
            passthrough = args

        return passthrough


if __name__ == "__main__":
    debug = DevDebug(enabled_mode=False)
    debug.enable("a")
    debug.enable("a.b")
    debug.disable("a.b.c")
    debug.enable("d")
    debug.disable("f")

    a = debug.is_enabled("a")
    b = debug.is_enabled("a.b")
    c = debug.is_enabled("a.b.c")
    f = debug.is_enabled("f.d")
    d = debug.is_enabled("d.f")
    debug.show()

    test_debug = DevDebug(enabled_mode=True)

    assert debug.is_enabled("a") == True
    assert debug.is_enabled("a.b") == True
    assert debug.is_enabled("a.b.c") == False
    pass
