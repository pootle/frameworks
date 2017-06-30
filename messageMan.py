#!/usr/bin/python3
"""
This module provides base classes to support inter-process and inter-machine function execution for both gui and headless based 
programs.

This is NOT remote procedure call - there is no response. The connections used are bi-directional so everything works (at
this plumbing level) symmetrically.

2 sets of inheriting classes are provided in further modules with similar interfaces - one set work within a tkinter framework, the other set provide
a basic socket / timer scheduler and are run in a freestanding process (or processes) with no direct user interaction.

These further classes are defined in tkMessageMan and selMessageMan to avoid unnecessary packages being imported.

"""
import socket
import os, sys, traceback

class baseListener():
    """
    abstract class for a IP4 listener as a base for specializations to run within tkinter or within a selector.
    
    All the common stuff is here and not much needs to happen in the specializations.
    """
    def __init__(self, framework, listenon, newsocketcallback, name):
        self.fw = framework
        self.name=name
        self.requestcount=0
        self.listenon = listenon
        self.callback = newsocketcallback
        self.sockaccept = socket.socket()
        self.sockaccept.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sockaccept.bind(self.listenon)
        self.sockaccept.listen(4)
        self.registerlisten()
        print(self.name, "listening on ", str(self.listenon))

    def connectrequest(self, sock, mask):
        newsocket, cfrom = sock.accept()
        print(self.name, "incoming request using"
            , str(self.listenon)
            , 'from', str(cfrom))
        self.requestcount += 1
        self.callback(newsocket, cfrom) # this should probably be wrapped

    def closelistener(self):
        print(self.name, "cancel listen on ", str(self.listenon),'received', self.requestcount,'connect requests.')
        self.unregisterlisten()
        self.sockaccept.close()
        self.sockaccept = None

def wrappedRunMethod(targetob, method, kwargs):
    func = getattr(targetob, method, None)
    if func is None:
        print( {'fail': 'method fail', 'etype': 'AttributeError','value': str(method), 'fromlink':0})
        return
    try:
        if kwargs is None:
            mresp = func()
        else:
            mresp = func(**kwargs)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        print( {'fail': 'exception', 'type':str(exc_type), 'value':str(exc_value)
                , 'trace':(''.join(traceback.format_tb(exc_traceback)) )
                , 'fromlink':0})
        if not kwargs is None:
            print("Using arguments", kwargs)

class baseSocket():
    def __init__(self, framework, iosocket, targetob, name, reportGone=None):
        """
        A very basic socket wrapper that takes a socket like object that is already created.

        framework   : the thing that will call back when data available
        
        iosocket    : socket all ready to go
        
        targetob    : the object on which commands will be run
        
        name        : name used in report / log meesages
        
        reportGone  : if not None then this will be called if the connection breaks
        """
        self.msgInCount = 0
        self.msgOutCount = 0
        self.targetob = targetob
        self.fw = framework
        self.name = name
        self.rwagent = sockreadwriter()
        self.reportGone = reportGone
        self.iosock = iosocket
        self.registerSocket()

    def closeLink(self):
        """
        a low level close function that should just release any resources used by the link.
        """
        self.unregisterSocket()
        self.iosock.close()
        self.iosock=None

    def processReady(self, sock, mask):
        requestlen = self.rwagent.requestreadlength()
        try:
            rdata = self.iosock.recv(requestlen)
        except ConnectionResetError:
            self.connectionLost("processReady: connection lost")
            return
        except OSError as oe:
            if oe.errno == 107:
                self.connectionLost("processReady: OSError - transport endpoint no longer connected")
                return
            self.connectionLost("processReady: OSError(%d)" % oe.errno)
            return
        if len(rdata) == 0:
            self.connectionLost("processReady: with zero data - connection has terminated")
        else:
            inmsg = self.rwagent.morereaddata(rdata)
            if inmsg is None:
                pass
#                print(self.name, "processReady: received %d bytes -%d more needed" % (len(rdata), self.rwagent.requestreadlength()),5)
            else:
                self.msgInCount += 1
                wrappedRunMethod(self.targetob, method = inmsg[0], kwargs = inmsg[1])

    def connectionLost(self, msg):
        print(self.name, msg)
        if not self.reportGone is None:
            self.reportGone()
        self.closeLink()

    def runFunc(self, method, **kwargs):
        self.rwagent.writemessage((method,kwargs), self.iosock)
        self.msgOutCount += 1

class autoSocket():
    def __init__(self, framework, connectTo, targetob, name, reportState=None):
        """
        A wrapper that attempts to connect to a given network address, and will reconnect if the connection fails. Connection status changes
        can be reported.

        framework   : the thing that will call back when data available, and can have a retry timer setup
        
        connectTo   : connection info
        
        targetob    : the object on which commands will be run when data received
        
        name        : name used in report / log messages
        
        reportState : if not None then this will be called when the connection state changes
        """
        self.msgInCount = 0
        self.msgOutCount = 0
        self.connectCount = 0
        self.connectTarget = connectTo
        self.targetob = targetob
        self.fw = framework
        self.name = name
        self.reportState = reportState
        self.state='startup'
        self.lastreportedState = None
        self.retrycount=0
        self.messagelim = 30
        self.tryConnect()

    def printmsg(self, *args):
        self.messagelim -= 1
        if self.messagelim >=0:
            print(self.name, 'state now', self.state, *args)

    def updateState(self, newstate, msg):
        if newstate != self.state:
            oldstate = self.state
            self.state = newstate
            self.printmsg('updated from state',oldstate, msg)
            if not self.reportState is None:
                self.reportState(self.name, self.state)

    def setRetryConnect(self):
        self.retrycount += 1
        delay = self.retrycount*.5
        if delay > 4:
            delay = 4
        self.setfwCallback(delay, self.tryConnect)

    def tryConnect(self):
        self.iosock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.iosock.connect(self.connectTarget)
            self.rwagent = sockreadwriter()
            self.registerSocket()
            self.updateState('initiated','connecting')
        except ConnectionRefusedError:
            self.iosock = None
            self.updateState('wait retry','connection refused')
            self.setRetryConnect()
        except OSError as oe:
            self.iosock = None
            self.updateState('wait retry',"tryConnect: OSError - %s" % format(oe))
            self.setRetryConnect()

    def closeLink(self):
        """
        a low level close function that should just release any resources used by the link.
        """
        if not self.iosock is None:
            self.unregisterSocket()
            self.iosock.close()
            self.iosock=None
        self.updateState('closed','Closelink called')

    def processReady(self, sock, mask):
        requestlen = self.rwagent.requestreadlength()
        try:
            rdata = self.iosock.recv(requestlen)
        except ConnectionResetError:
            self.connectionLost("processReady: connection lost")
            return
        except OSError as oe:
            if oe.errno == 107:
                self.connectionLost("processReady: OSError - transport endpoint no longer connected")
                return
            self.connectionLost("processReady: OSError(%d)" % oe.errno)
            return
        if len(rdata) == 0:
            self.unregisterSocket()
            self.iosock.close()
            self.iosock=None
            self.connectionLost("processReady: with zero data - connection has terminated")
        else:
            inmsg = self.rwagent.morereaddata(rdata)
            self.retrycount=0
            self.updateState('running', 'data received')
            if inmsg is None:
                self.printmsg("processReady: received %d bytes -%d more needed" % (len(rdata), self.rwagent.requestreadlength()),5)
            else:
                self.msgInCount += 1
                wrappedRunMethod(self.targetob, method = inmsg[0], kwargs = inmsg[1])

    def connectionLost(self, msg):
        self.setRetryConnect()
        self.updateState('wait retry', msg)

    def runFunc(self, method, **kwargs):
        if self.iosock is None:
            return
        try:
            self.rwagent.writemessage((method,kwargs), self.iosock)
            self.msgOutCount += 1
        except BrokenPipeError:
            self.unregisterSocket()
            self.iosock.close()
            self.iosock=None
            self.connectionLost('Broken Pipe')
        self.updateState('running','msg sent')

import pickle

class sockreadwriter():
    """
    This class provides simple serialise / deserialise functioanlity to stuff objects up and down a socket / file / pipe.
    
    it handles a single object which is encoded as <length><obdata> where:
         <length> is a 10 bytes text string with the number of bytes for the following obdata
         <obdata> is a pickle of the object
    """
    def __init__(self):
        self.reset()

    def reset(self):
        self.instate = 0
        self.partdata = b''

    def requestreadlength(self):
        """
        returns the length of data that should be requested for the next read on the file like object.
        
        morereaddata below will expect a maximum of this number of bytes when next called
        """
        if self.instate == 0:
            return 10
        if self.instate < 0:
            return -self.instate
        
        return self.instate

    def morereaddata(self, rdata):
        """
        gets passed the next lump of data, with a maximum length as defined by the preceding call to 
        'requestreadlength' above.
        
        it returns None if more data is needed to complete reconstruction of the object, or the reconstructed object
        """
        if self.instate <= 0:
            mdata = self.partdata + rdata
            if len(mdata) == 10:
                self.instate = int(rdata)
                self.partdata = b''
            else:
                self.instate = len(mdata) - 10
                if self.instate > 0:
                    cras = 5 / 0
                self.partdata = mdata
        else:
            mdata = self.partdata + rdata
            self.instate -= len(rdata)
            if self.instate == 0:
                self.partdata = b''
                return pickle.loads(mdata)
            else:
                self.partdata = mdata
#        print("datareader state %d, pendbuff >%s<" % (self.instate, self.partdata.decode('utf-8')))
        return None

    def writemessage(self, msg, flo):
        """
        A very simple implementation that just stuffs the picked object into the file like object in one go
        """
#        pstr = pickle.dumps(msg)
        pstr = pickle.dumps(msg, protocol=2)
        dlen = b'%10d' % len(pstr) if sys.version_info >= (3,5) else ('%10d' % len(pstr)).encode('utf-8')
        flo.sendall(dlen)
        flo.sendall(pstr)
