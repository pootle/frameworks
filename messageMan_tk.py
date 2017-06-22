#!/usr/bin/python3
"""
This module provides classes to support inter-process and inter-machine function execution with 'this' end
of the connection as a tkinter based program.
"""
import messageMan
import socket
import tkinter

class tklistener(messageMan.baseListener):
    """
    A TCP/IP connection handler that waits for an incoming connect request within a tk framework. On connect request,
    it invokes the callback and passes the connection it has setup. tk must be running before this can be called.
    """
    def __init__(self, name='tklistener', **kwargs):
        super().__init__(name=name, **kwargs)

    def registerlisten(self):
        self.fw.createfilehandler(self.sockaccept, tkinter.READABLE, self.connectrequest)

    def unregisterlisten(self):
        self.fw.deletefilehandler(self.sockaccept)


class tkSocket(messageMan.baseSocket):
    """
    A class to support asynch function calling using a socket like object within a tkinter app at 'this' end.
    """
    def registerSocket(self):
        self.fw.createfilehandler(self.iosock, tkinter.READABLE, self.processReady)

    def unregisterSocket(self):
        self.fw.deletefilehandler(self.iosock)
