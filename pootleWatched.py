#!/usr/bin/python3
"""
The classes here provide objects with simple underlying types that will automatically call a function
when the value is accessed or changed.

Various specialisations police the value to make these convenient to use for user interfaces, and allow automatic parsing
from text.

"""
class watchable():
    """
    a basic observer that enables property to be used so that simple objects can be accessed in an almost ordinary way,
    but still trigger the watcher(s).
    """
    def __init__(self, initValue=None):
        """
        setup a watchable with the given initial Value
        """
        self._changeWatchers = {}
        self._readWatchers = {} # this may be handy for diagnostics......
        self._value = self.checkValue(initValue)
        self._wcounter=0

    @property
    def val(self):
        """
        fetches the value, notifying any watchers first
        """
        for wk, wf in self._readWatchers.items():
            wf(wk, self, self._value)
        return self._value

    @val.setter
    def val(self, newval):
        """
        check that the new value is valid before updating and notifying watchers if appropriate
        """
        checkedval = self.checkValue(newval)
        if checkedval != self._value:
            self._value = checkedval
            for wk, wf in self._changeWatchers.items():
                wf(wk, self)

    def checkValue(self, newval):
        """
        Here, this takes no action, but including this here makes inheriting classes easily able to police the value and
        make sure it is the appropriate class
        """
        return newval

    def setWatch(self, wf, onchange, onread=False):
        """
        anyone interested can nominate a callback to trigger on update or access.
        It returns an id that can later be used to cancel interest
        """
        self._wcounter += 1
        if onchange:
            self._changeWatchers[self._wcounter]=wf
        if onread:
            self._readWatchers[self._wcounter]=wf
        return self._wcounter

    def stopWatch(self,wk, wf):
        """
        cancel a callback on update or access.
        """
        assert self._changeWatchers.get(wk, None) == wf or self._readWatchers.get(wk, None) == wf, "unwatch key and callback do not match"
        self._changeWatchers.pop(wk, None)
        self._readWatchers.pop(wk, None)

    def __str__(self):
        """
        makes it easy to treat a watcher as if it is actually it's value
        """
        return str(self._value)

    def __format__(self, formstr):
        """
        makes it easy to treat a watcher as if it is actually it's value
        """
        return self._value.__format__(formstr)

class watchableInt(watchable):
    """
    This extends watchable such that the value should always be an int. The setter accepts either an int or tries to
    convert to an int, which can raise a value error (and the value will be unchanged)
    """
    def checkValue(self, newval):
        if newval=='':
            return 0
        return int(newval) # will throw value error if it can't be converted to an int
