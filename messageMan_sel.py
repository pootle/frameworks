#!/usr/bin/python3
"""
This module provides base classes to support inter-process and inter-machine function execution for both gui and headless based 
programs.

This is NOT remote procedure call - there is no response. The connections used are bi-directional so everything works
(at this plumbing level) symmetrically.

2 sets of classes are provided in further modules with similar interfaces - one set work within a tkinter framework,
the other set provide a basic socket / timer scheduler and are run in a freestanding process (or processes) with
no direct user interaction.

"""
import selectors, time, heapq
import messageMan

class selListener(messageMan.baseListener):
    """
    A TCP/IP connection handler that waits for an incoming connect request within a timerSelector framework. On connect
    request, it invokes the callback and passes the connection it has setup. The timerSelector must be created before
    this can be called.
    """
    def __init__(self, name='selListener', **kwargs):
        super().__init__(name=name, **kwargs)

    def registerlisten(self):
        self.fw.register(self.sockaccept, selectors.EVENT_READ, self.connectRequest)

    def unregisterlisten(self):
        self.fw.unregister(self.sockaccept)

class selSocket(messageMan.baseSocket):
    """
    A class to support asynch function calling using a socket like object within a timerselector based framework
    at 'this' end.
    """
    def registerSocket(self):
        self.fw.register(self.iosock, selectors.EVENT_READ, self.processReady)

    def unregisterSocket(self):
        self.fw.unregister(self.iosock)

class autoSocket(messageMan.autoSocket):
    def registerSocket(self):
        self.fw.register(self.iosock, selectors.EVENT_READ, self.processReady)

    def unregisterSocket(self):
        self.fw.unregister(self.iosock)

    def setfwCallback(self, delay, callback):
        self.fw.runafter(delay, callback)

class timerSelector(selectors.DefaultSelector):
    """
    adds a 'runafter' capability to the standard selector class to support my headless / guiless apps.
    """
    def __init__(self, name='timerSelector', printloglevel=31, sendloglevel=15):
        self.funclist=tuple()
        self.timervals=[]
        self.timers={}
        super().__init__()
        self.magentName = name
        self.startedat = time.time()
        self.printll = printloglevel
        self.sendll = sendloglevel
        self.cpuTotal = 0
        self.timeTotal = 0
        self.logmsg(message="started printloglevel %d, sendloglevel %d" % (self.printll, self.sendll), level=LOGLVLLIFE)
        self.running = True

    def runat(self, timedue, thandler):
        """
        where maintaining the tick (even if individual ticks are delayed) is important, use this method
        """
#        assert not timedue in self.timers, 'failed at elapsed %f' % (timedue-self.starttime)
        if timedue in self.timers:
#            print("clash time: %s with %s" % (str(thandler), str(self.timers[timedue])))
            self.timers[timedue].append(thandler)
        else:
            self.timers[timedue] = [thandler]
            heapq.heappush(self.timervals, timedue)

    def runafter(self, delay, thandler):
        """
        where the poll time is not critical, we'll just wait a bit from now
        """
        self.runat(time.time()+delay, thandler)

    def select(self, maxwait):
        try:
            nexttimerdue = self.timervals[0]
        except IndexError:
            nexttimerdue = None
        try:                                            # check to see if we have any files to wait on
            active = self.get_map()
        except AttributeError:
            active = False
        if nexttimerdue is None:
            if active:
                todo = super().select(maxwait)
                if self.makeLog(LOGLVLSCHED):
                    self.logmsg(level=LOGLVLSCHED, message="just waited for a flo to trigger -  have %d" % len(todo))
            else:
                print("no wait, no active flos, nothing to do - bizarre")
                if maxwait > 0:
                    time.sleep(maxwait)
                todo = ()
        else:
            delay = nexttimerdue-time.time()
            if delay > maxwait:
                delay = maxwait
            if active:
                if self.makeLog(LOGLVLSCHED):
                    self.logmsg(level=LOGLVLSCHED, message="tick and active - select with timeout %f" % delay)
                todo = super().select(delay)
            else:
                if self.makeLog(LOGLVLSCHED):
                    self.logmsg(level=LOGLVLSCHED, message="no active flos, waiting for %f" % delay)
                if delay > 0:
                    time.sleep(delay)
                todo=()
        for skey, mask in todo:                           # process any outstanding file i/o
            skey.data(None, mask)
        if not nexttimerdue is None and time.time() >= nexttimerdue:
            heapq.heappop(self.timervals)
            tlist = self.timers.pop(nexttimerdue)
            for t in tlist:
                self.wrappedRunMethod(t,None)

    def closeAgent(self):
        self.running = False
        self.close()

    def runforever(self):
        try:
            while self.running:
                self.select(5)
        except KeyboardInterrupt:
            self.closeAgent()

    def wrappedRunMethod(self, meth, kwargs):
        msgStartTime = time.time()
        msgCPUstart = time.process_time()
        try:
            if kwargs is None:
                meth()
            else:
                meth(**kwargs)
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            print("wrapped call caught exception >%s<" % type(e))
            try:
                print("wrappedRunMethod: %s exception in called code - \n%s\n%s" %
                    (str(exc_type), str(exc_value), ''.join(traceback.format_tb(exc_traceback))))
            except:
                pass
            if self.crashabortcount > 0:
                self.crashabortcount -= 1
                if self.crashabortcount == 0:
                    if not self.killhandler is None:
                        self.wrappedRunMethod(self.killhandler,{})
                    else:
                        self.running=False

        self.timeTotal += time.time() - msgStartTime
        self.cpuTotal += time.process_time() - msgCPUstart

    def makeLog(self, level):
        """
        checks logging levels and returns true if this loglevel is active. - Use to check if we need to generate
        non-trivial messages
        """
        return self.printll & level or self.sendll & level

    def logmsg(self, level, message, tstamp=None, agent=None, **kwargs):
        if tstamp is None:
            tstamp=time.time()-self.startedat
        if agent is None:
            agent=(self.magentName,)
        else:
            agent=agent+(self.magentName,)
        if self.printll & level:
            if level != LOGLVLDETAIL or kwargs.get('func', None) in self.funclist:
                print('%3.2f' % tstamp, '.'.join(agent), message)
        if self.sendll & level:
            if level != LOGLVLDETAIL or kwargs.get('func', None) in self.funclist:
                self.sendLogmsg(level=level, message=message, tstamp=tstamp, agent=agent, **kwargs)

    def sendLogmsg(self, **kwargs):
        pass 

LOGLVLFAIL=1
LOGLVLSTATE=4
LOGLVLLIFE=2
LOGLVLINFO=8
LOGLVLDETAIL=16
LOGLVLSCHED=16
