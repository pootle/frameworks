#!/usr/bin/python3

import tkinter
from tkinter import messagebox
from tkinter import font as tkfont
from tkinter.ttk import Button, Checkbutton, Label, Entry, Style, Scrollbar, Treeview, Combobox, Scale, Notebook
from tkinter import Frame
import json
from pootleWatched import watchable, watchableInt
import astroangles as asa
import pathlib

class Field():
    """
    A field is the basic app building unit, fields form a tree to represent the entire app.
    
    see http://wiki.tcl.tk/37973
    
    A field starts as just a simple container for data, with a parent, a definition (a dict), the field's data (its value).
    
    It defines the way in which the value will be represented to the user.

    The definiton (self.fielddef) provides all the invariant information about the field:
         'name'    : a name for the field - must be unique within the parent
         'class'   : the class of object to be used for the field
         'value'   : the value of the field if the value never changes, or the default value if no fvalue passed
         'font'    : if present then the name of a pfont to be used as the font in this Field, defaults to 'basefont'.
                        only used for a couple of fields whose widgets don't pickup style based fonts properly
         'format'  : if present then this string is used to format the value to create the string that is displayed in the widget
         'command: : if present then arrange to call the command when the field value changes / button is pressed as appropriate
                     a callable is a direct reference, a string is the name of the function
         'comfield': if present and 'command' is not callable then the path to the field (from self) with the function 'command' to call
                     defaults to self
         'persist' : if present then the value of this field is saved when the application closes and restored when it is run.

          all other elements depend on the class of field, but mostly comprise info about how to build the gui widget when required.
    
    The data is either a watchable or something else, where something else is typically is simple type like a string, but a panel
    could be a dict or even a class. A watchable is used when the value can be updated elsewhere in the app and needs to update
    the value displayed on screen.
    """
    def __init__(self, parentField, fdef, fvalue):
        self.fielddef = fdef
        self.pfield = parentField
        self.myname = self.fielddef['name']
        if fvalue is None:
            self.fval = self.fielddef.get('value', None)
        else:
            print('create ', self.myname, ' (', str(type(self)), ')', ' using value: ', str(fvalue)) 
            self.fval = fvalue
        if isinstance(self.fval, watchable):
            self.watchkey = self.fval.setWatch(self.updateFromWatched, True)
        else:
            self.watchkey = None
        self.widg=None
        if 'persist' in self.fielddef:
            self.pfield.makeChildValue(self.myname, self.getValue())

    def widgetClass(self):
        raise NotImplementedError('Field.widgetClass should be overridden')

    def makeWidget(self):
        wclass = self.widgetClass()
        if 'TOP' == wclass:
            self.widg=tkinter.Toplevel(master=self.pfield.widg)
        elif 'tkparams' in self.fielddef:
            self.widg = wclass(master=self.pfield.widg, **self.fielddef['tkparams'])
        else:
            self.widg = wclass(master=self.pfield.widg)
        if 'style' in self.fielddef:
            self.widg.configure(style=self.fielddef['style'])
        if 'font' in self.fielddef:
            self.setFont(self.fielddef['font'])
        if 'command' in self.fielddef:
            comm = self.fielddef['command']
            if callable(comm):
                self.addCommand(comm)
            else:
                if 'comfield' in self.fielddef:
                    targf = self.getRelative(self.fielddef['comfield'])
                else:
                    targf = self
                try:
                    cfunc = getattr(targf,comm)
                except AttributeError:
                    print('Failed to find ', self.fielddef['command'], 'in ', str(type(targf)),'(',targf.myname,')', 'when building ButtonField ',self.myname)
                    raise
                self.addCommand(cfunc)
        if 'autohelp' in self.fielddef:
            self.autohelper = autohelp(self.widg,self.fielddef['autohelp'])

        self._updateDisplay()

    def setFont(self, fontname):
        try:
            self.widg.configure(font=pfont.allfonts[fontname].wfont)
        except:
            print("failed to apply font to", self.myname, 'in a', type(self))
            print(self.fielddef)
            raise

    def addCommand(self, cfunc):
        raise NotImplementedError('command calling not available on this (', self.myname,') field (type ', type(self), ').')

    def clearField(self):
        """
        release any non tkinter resources related to the widget because we're about to get rid of it.
        """
        pass

    def dropwidget(self):
        """
        the widget has been discarded by tk (probably by destroy() on it or its parent) so drop the reference to it
        """
        self.widg = None

    def show(self):
        if self.widg is None:
            self.makeWidget()

    def updateFromWatched(self, ignore1, ignore2):
        self._updateDisplay()

    def setValue(self, newval):
        if isinstance(self.fval, watchable):
            self.fval.val = newval
        else:
            self.fval = newval
        self._updateDisplay()

    def getValue(self):
        if isinstance(self.fval, watchable):
            return self.fval.val
        return self.fval

    def _updateDisplay(self):
        if self.widg is None:
            return
        vval = self.getValue()
        if 'format' in self.fielddef:
            try:
                vval = self.fielddef['format'].format(vval)
            except ValueError:
                print('Value Error processing a ', str(type(vval)), 'using >', self.fielddef['format'], '<.', ' in field ', self.myname, '(Field._updateDisplay)')
                vval='EEEEK'
        self._updateWidgetContent(vval)

    def _updateWidgetContent(self, textcontent):
        """
        called only from _updatedeDisplay, allows for different widget types to have different variable names for content
        """
        self.widg.configure(text=textcontent) # many widgets use text as the option - override in subclasses if necessary

    def getRelative(self, rpath):
        """
        hierarchically fetches the child field identified by rpath
        
        rpath: A string or tuple that identifies another field in the field hierarchy
            if a string then it is a '.' separated sequence of names (no '.' means it is a child of this frame)
                    '..' at the start of the string means start from the parent with the remainder of the string
            if a tuple then an ordered sequence of names, the sequence can start with 1 or more '..' to navigate 
                    to parent fields
        """
        if isinstance(rpath,str):
            if rpath.startswith('..'):
                if len(rpath) > 2:
                    return self.pfield.getRelative(rpath[2:])
                else:
                    return self.pfield
            targ = rpath.split('.')
        else:
            targ = rpath
        if targ[0]=='..':
            if len(targ) == 1:
                return self.pfield
            else:
                return self.pfield.getRelative(targ[1:])
        ch = self.children[targ[0]]
        if len(targ) > 1:
            return ch.getRelative(targ[1:])
        return ch

    def saveme(self):
        if 'persist' in self.fielddef:
            return self.myname, self.getValue()
        else:
            return None

class ButtonField(Field):
    """
    A ButtonField is used to place a button on the app's display.
    
    The button has an associated function that is called when the button is pressed.
    
    The text is generally fixed, but can be linked to a watchable value, in which case the displayed text always
    matches the the watched value
    """
    def widgetClass(self):
        return Button

    def addCommand(self, cfunc):
        self.widg.configure(command=cfunc)

    def setFont(self, fontname):
        pass

class CheckbuttonField(ButtonField):
    def __init__(self, **kwargs):
        self.tksvar = None # when we fist start tkinter may not be set up so the StringVar has to be created later
        super().__init__(**kwargs)

    def widgetClass(self):
        return Checkbutton

    def makeWidget(self):
        self.callthis=None
        if self.tksvar is None:
            self.tksvar = tkinter.IntVar()
            self.tksvar.set(self.getValue())
        super().makeWidget()
        self.widg.configure(variable=self.tksvar, command=self.cbclick)

    def _updateWidgetContent(self, content):
        if not self.tksvar is None and self.tksvar.get() != content:
            self.tksvar.set(content)

    def cbclick(self):
        self.setValue(self.tksvar.get())
        if not self.callthis is None:
            self.callthis(self, self.getValue())

    def addCommand(self, cfunc):
        self.callthis = cfunc

class CyclicButtonField(ButtonField):
    """
    A button that has multiple states (although typically only 2 - so like a checkbox), with text that reflects the state.
    
    If you want to trigger on a click, use a watchable.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        validvals = self.fielddef['values']
        if not self.getValue() in validvals:
            self.setValue(validvals[0])

    def widgetClass(self):
        return Button

    def makeWidget(self):
        self.callthis = None
        super().makeWidget()
        self.widg.configure(command=self.lbclick)

    def addCommand(self, cfunc):
        self.callthis = cfunc

    def lbclick(self):
        validvals = self.fielddef['values']
        cind = validvals.index(self.getValue()) + 1
        if cind >= len(validvals):
            cind = 0
        super().setValue(validvals[cind])
        print("cyclic button now", self.getValue())
        if not self.callthis is None:
            self.callthis()

    def setValue(self, newval):
        validvals = self.fielddef['values']
        if newval in validvals:
            super().setValue(newval)

    def getIndex(self):
        return self.fielddef['values'].index(self.getValue())

class ShowhideButton(CyclicButtonField):
    """
    simple specialization of a cyclic button to enable a group of fields to be hidden / viewed at will.
    
    The list of fields is identified by an additional entry ion the field definition - 'vset' - which 
    lists relative paths to all the fields to be affected by the button.
    """
    def showhide(self):
        hidefields = self.getValue()=='S'
        if self.getValue()=='H':
            print("H set")
        else:
            print("S set")
        for fn in self.fielddef['vset']:
            tf = self.getRelative(fn)
            if hidefields:
                tf.widg.grid_remove()
            else:
                tf.widg.grid()

    def makeWidget(self):
        super().makeWidget()
        if self.getValue() == 'S':
            self.widg.after_idle(self.showhide)


class TextField(Field):
    """
    A TextField is to put text on the app's display. The field does not accept focus, the text cannot be selected or copied, but can be updated.
    
    Typically used for labels, headings etc.
    """
    def widgetClass(self):
        return Label

class InOutField(Field):
    """
    A field that displays text that can be selected and copied, and can optionally be edited by the user.
    
    Extends the definiton (self.fielddef) with:
        'readonly' if present, means field can be selected and copied with CTRL-C, but not changed by user.
                implemented using ttk state readonly
    
    http://stackoverflow.com/questions/28792368/onvalidate-registering-lots-of-different-validations
    """
    def __init__(self, **kwargs):
        self.tksvar = None # when we fist start tkinter may not be set up so the StringVar has to be created later
        super().__init__(**kwargs)

    def widgetClass(self):
        return Entry

    def createtkVar(self):
        self.tksvar = tkinter.StringVar()
        self.tksvar.set(self.getValue())

    def makeWidget(self):
        self.callthis=None
        if self.tksvar is None:
            self.createtkVar()
        super().makeWidget()
        self.widg.configure(textvariable=self.tksvar)
        if 'readonly' in self.fielddef:
            self.widg.state(('readonly',))
        else:
            self.widg.bind("<Return>", self.userUpdateComplete)
            self.widg.bind("<FocusOut>", self.userUpdateComplete)

#            vcmd = (self.widg.register(self.fieldchanged), '%P')
#            self.widg = Entry(self.ppanel.widg, textvariable=self._strvar, validate='key', validatecommand=vcmd, **allpars)

    def _updateWidgetContent(self, textcontent):
        if not self.tksvar is None and self.tksvar.get() != textcontent:
            self.tksvar.set(textcontent)

    def userUpdateComplete(self,event):
        validVal = self.userUpdateValid()
        if validVal is None:
            pass # flashy error thing
            return
        self.setValue(validVal)
        if not self.callthis is None:
            self.callthis(self, self.getValue())

    def userUpdateValid(self):
        return self.tksvar.get()

    def addCommand(self, cfunc):
        self.callthis = cfunc

class FloatField(InOutField):
    def userUpdateValid(self):
        try:
            newval = float(self.tksvar.get())
        except:
            return None
        if 'minval' in self.fielddef and newval < self.fielddef['minval']:
            return None
        if 'maxval' in self.fielddef and newval > self.fielddef['maxval']:
            return None
        return newval

class IntField(InOutField):
    def userUpdateValid(self):
        try:
            newval = int(self.tksvar.get())
        except:
            return None
        if 'minval' in self.fielddef and newval < self.fielddef['minval']:
            return None
        if 'maxval' in self.fielddef and newval > self.fielddef['maxval']:
            return None
        return newval

class AngField(InOutField):
    """
    A specialization of an input / output field using an astroangles field type which can be dynamically updated to any 
    subclass of astroangles.degradval
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dataclass=self.fielddef.get('dataclass','latVal')
        self.makeVal()

    def makeVal(self):
        self.fval = getattr(__import__('astroangles'),self.dataclass)(self.getValue())

    def setType(self, tname):
        if tname != self.dataclass:
            cval = self.fval.deg
            self.dataclass=tname
            self.fval = getattr(__import__('astroangles'),self.dataclass)(cval)
            self._updateDisplay()

    def _updateDisplay(self):
        if self.widg is None:
            return
        vval = self.getValue()
        if 'format' in self.fielddef:
            try:
                vval = format(vval,self.fielddef['format'])
            except ValueError:
                print('Value Error processing a ', str(type(vval)), 'using >', self.fielddef['format']
                    , '<.', ' in field ', self.myname, '(LatField._updateDisplay)')
                vval='EEEEK'
        self._updateWidgetContent(vval)

    def userUpdateComplete(self,event):
        try:
            self.getValue().set(self.tksvar.get())
        except:
            pass # flashy error thing
            return
        if not self.callthis is None:
            self.callthis(self, self.getValue())

    def saveme(self):
        if 'persist' in self.fielddef:
            return self.myname, '{0:9f}'.format(self.getValue().deg)
        else:
            return None

class ComboField(InOutField):
    """
    A comboField re-interprets 'readonly' to mean that only values in the valuelist can be selected, if this is not present
    then the user can type in new values
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        print("combo field with readonly ...", 'readonly' in self.fielddef)
        if 'readonly' in self.fielddef:
            validvals = self.fielddef['values']
            if not callable(validvals) and not self.getValue() in validvals:
                self.setValue(validvals[0])
                print("value set to", validvals[0])
            else:
                print("value set to", self.getValue())

    def widgetClass(self):
        return Combobox

    def createtkVar(self):
        self.tksvar = tkinter.StringVar()
        self.tksvar.set(self.getValue())
        self.tksvar.trace('w', self.valchanged)

    def makeWidget(self):
        super().makeWidget()
        wv = self.fielddef.get('values',('empty',))
        if callable(wv):
            wv = wv()
            if not self.getValue() in wv:
                self.setValue(wv[0])
        self.widg.configure(values=wv)
        print("variable value is", self.getValue())
        print(self.myname, "command is", self.callthis)

    def valchanged(self, *args):
        print("updated", self.myname)
        self.userUpdateComplete(None)

    def userUpdateValid(self):
        newval = self.tksvar.get()
        if 'readonly' in self.fielddef:
            validvals = self.fielddef.get('values','empty')
            if callable(validvals):
                validvals=validvals()
            if newval in validvals:
                super().setValue(newval)
                print("set value to", newval)
                return newval
            else:
                print("set values ignores", newval)
                return None
        else:
            super().setValue(newval)
            print("new value unchecked - set to", newval)
            return newval

    def getIndex(self):
        return self.widg.current()

class ContainerField(Field):
    """
    A class for fields that contain other fields 
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.listeners=None
        self._initChildren()

    def _initChildren(self):
        if 'children' in self.fielddef:
            self.childdeflist = list(self.fielddef['children']) # shallow copy so we can add and remove entries later
            self.childlayouts = self.fielddef['layout']['params'].copy()
            self.children = {cdefn['name']: cdefn['class'](
                      parentField=self
                    , fdef=cdefn
                    , fvalue=None if self.fval is None else self.fval.get(cdefn['name'], None))
                        for cdefn in self.childdeflist}
        else:
            self.childdeflist = []
            self.children={}

    def addChild(self, childdef, childlayout, childdata, cpos=-1):
        print('current children are ', str(self.children.keys()), ' new child is ', childdef['name']    )
        
        assert not childdef['name'] in self.children
        newchild = childdef['class'](
                      parentField=self
                    , fdef = childdef
                    , fvalue=None if self.fval is None else self.fval.get(cdefn['name'], None))
        self.children[childdef['name']] = newchild
        self.childdeflist.append(childdef)
        self.childlayouts[childdef['name']] = childlayout
        if not self.widg is None:
            newchild.show()
            self.layoutchild(newchild)

    def makeWidget(self):
        super().makeWidget()
        self._makeChildrensWidgets()

    def _makeChildrensWidgets(self):
        if 'children' in self.fielddef:
            for cdefn in self.fielddef['children']: # use the declaration order here as it defines the tab sequence order
                cname = cdefn['name']
                child = self.children[cname]
                child.show()
                self.layoutchild(child)
            if self.fielddef['layout']['type'] == 'grid' and 'colconfigs' in self.fielddef['layout']:
                for cf in self.fielddef['layout']['colconfigs']:
                    self.widg.columnconfigure(cf[0], **cf[1])

    def layoutchild(self, child):
        assert child.myname in self.childlayouts, "failed to find layout info for child %s in %s" % (child.myname, self.myname)
        ltype = self.fielddef['layout']['type']
        lparam = self.childlayouts[child.myname]
        if ltype == 'pack':
            self.layoutPackChild(lparam,child)
        elif ltype=='grid':
            self.layoutGridChild(lparam,child)
        elif ltype=='tab':
            self.layoutTabChild(lparam,child)
        else:
            raise ValueError('No layout info found for ', self.myname)            

    def layoutGridChild(self, ldef, child):
        child.widg.grid(**ldef)

    def layoutPackChild(self, ldef, child):
        child.widg.pack(**ldef)

    def layoutTabChild(self, ldef, child):
        if child.widgetClass() == 'TOP':
            return
        self.widg.add(child.widg, **ldef)

    def clearField(self):
        for child in self.children.values():
            child.clearField()
        if not self.listeners is None:
            for c in self.listeners:
                c.closelistener()
            self.listeners=None
        super().clearField()

    def saveme(self):
        dlist = tuple(s for s in (ch.saveme() for ch in self.children.values()) if not s is None)
        if len(dlist) > 0:
            return self.myname, dict(dlist)
        else:
            return None

    def makeChildValue(self, chname, value):
        if self.fval is None:
            self.fval = {chname:value}
        elif not chname in self.fval:
            self.fval[chname]=value

    def dropwidget(self):
        for ch in self.children.values():
            ch.dropwidget()
        super().dropwidget()


class PanelField(ContainerField):
    def widgetClass(self):
        return Frame

    def _updateDisplay(self):
        pass

    def makeWidget(self):
        super().makeWidget()
        if 'background' in self.fielddef:
            self.widg.configure(background=self.fielddef['background'])

    def setFont(self,f):
        pass

dockablebutton = {'class': CyclicButtonField, 'name': 'dockbut', 'value': 'undock', 'comfield': '..', 'command':'docker'
        , 'values':('undock', 'dock'), 'persist':0, 'style':'Astro.TButton'}

class DockablePanel(PanelField):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not 'pstate' in self.fval:
            self.fval['pstate'] = {}
        if not 'geom' in self.fval['pstate']:
            print("reset dockable geometry")
            self.fval['pstate']['geom'] = self.fielddef.get('defgeometry','200x200+150+150')
        else:
            print("retrieved dockable geometry ", str(self.fval['pstate']['geom']))

    def widgetClass(self):
        return Frame if self.children['dockbut'].getIndex() == 0 else 'TOP'

    def makeWidget(self):
        super().makeWidget()
        if self.children['dockbut'].getIndex() == 0:
            self.pfield.widg.add(self.widg, **self.pfield.fielddef['layout']['params'][self.myname])
        else:
            self.widg.geometry(self.fval['pstate']['geom'])
            self.widg.title(self.pfield.fielddef['layout']['params'][self.myname]['text'])
            self.widg.protocol("WM_DELETE_WINDOW", self.docker)

    def docker(self):
        print("flip dock", )
        if self.children['dockbut'].getIndex() == 0: # button value already updated.....
            self.fval['pstate']['geom'] = self.widg.geometry()
        self.clearField()
        self.widg.destroy()
        self.dropwidget()
        self.pfield.widg.after_idle(self.show)
        
    def panelstate(self):
        if self.children['dockbut'].getIndex() == 1:
            self.fval['pstate']['geom'] = self.widg.geometry()
        return self.fval['pstate']

    def saveme(self):
        sd = super().saveme()
        ps = self.panelstate()
        if sd is None:
            return self.myname, {'pstate': ps}
        else:
            sd[1]['pstate'] = ps
            return self.myname, sd[1]

class TabPanel(PanelField):
    def widgetClass(self):
        return Notebook

class autohelp():
    """
    A basic class to provide tooltip style help for widgets
    """
    def __init__(self, widget, text):
        """
        just declare an interest in the mouse entering or leaving the widget.
        """
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.hw = None

    def enter(self, event):
        """
        if the mouse enters the widget area and there is no tooltip on display, set a timer
        """
        if self.hw is None:
            self.widget.after(500, self.disphelp)

    def leave(self, event):
        """
        triggered on leaving the widget or its tooltip
        """
        if event.widget == self.widget:
            # left the widget, but mouse may just be over the tooltip...
            ww = self.widget.winfo_width()
            wh = self.widget.winfo_height()
            if not 0 < event.x < ww or not 0 < event.y < wh:
                self.closehelp()
        elif event.widget==self.hw:
            # left the tooltip, but may still be within the widget....
            px, py = self.widget.winfo_pointerxy()
            wx = self.widget.winfo_rootx()
            wy = self.widget.winfo_rooty()
            ww = self.widget.winfo_width()
            wh = self.widget.winfo_height()
            if not wx < px < (wx+ww) or not  wy < py < (wy+wh):
                self.closehelp()

    def disphelp(self):
        """
        When the timer goes off, if the mouse is still within the widget, popup the tooltip
        """
        px, py = self.widget.winfo_pointerxy()
        wx = self.widget.winfo_rootx()
        wy = self.widget.winfo_rooty()
        ww = self.widget.winfo_width()
        wh = self.widget.winfo_height()
        if wx < px < (wx+ww) and wy < py < (wy+wh) and self.hw is None:
            self.state='dhshow'
            x, y, cx, cy = self.widget.bbox()
            x += self.widget.winfo_rootx() + 20
            y += self.widget.winfo_rooty() + 20
            # creates a toplevel window
            self.hw = tkinter.Toplevel(self.widget)
            # Leaves only the label and removes the app window
            self.hw.wm_overrideredirect(True)
            self.hw.wm_geometry("+%d+%d" % (x, y))
            label = tkinter.Label(self.hw, text=self.text, justify='left',
                           background='yellow', relief='solid', borderwidth=1,
                           font=("times", "10", "normal"))
            label.pack(ipadx=1)
            self.hw.bind("<Leave>", self.leave)

    def closehelp(self):
        """
        time to close the tooltip
        """
        if not self.hw is None:
            self.hw.destroy()
            self.hw=None

class pfont():
    """
    a wrapper for tkinter.font.Font that supports trees of fonts with properties that cascade through the tree.
    
    This can deliver both a string that can be used to setup a font as the 'font' parameter to a style (which works with most
    ttk styled widgets, and also a tkinter font object that can be used as a parameter when setting up a widget for things that don't
    work with style based fonts. Using these 2 techniques allows fonts to be changed dynamically in the app
    """

    allfonts={} # a dict with all the fonts we know about
    @classmethod
    def makefont(cls, parent, name, family=None, size=None, busi=None):
        """
        creates an "extended" font, based on the parent font (if given) and overriding the font characteristics given.
        
        Later updates to the font will propagate through to any child fonts, updating the whole gui dynamically.
        
        parent  : the new font will be a copy of this font (or of style .'s font if parent is None) changed by the following parameters....
        family  : The new font will use this font family
        size    : if an int, then the font size will be the given point size, or pixel size if -ve. If it is a string then the
                  size will be derived from parent font size adjusted by the int of the given string, e.g. +2 for 2 points larger
                  or pixels smaller
        busi    : a string with the characters 'b', 'u', 's', each optionally preceded by '-'. If the string contains
                  if the string contains '-b', bold is turned off. If it contains 'b', bold is turned on.
                  the same applies for 'u' - underline and 's' - strikethrough.
        """
        if parent == None:
            s = Style()
            afont=tkfont.nametofont(s.configure('.','font'))
            print("create font ", name, " from root.")
        else:
            afont=parent.wfont
            print("create font ", name, " from parent ", parent.name)
        return pfont(parent=parent, wrappedfont = afont.copy(), name=name, family=family, size=size, busi=busi)
#        return pfont(parent=parent, name=name, family=family, size=size, busi=busi)

    def __init__(self, parent, wrappedfont, name, family, size, busi):
        self.wfont=wrappedfont
        self.parent=parent
        self.name=name
        if not self.parent is None:
            self.parent.children.append(self)
        self.children=[]
        pfont.allfonts[name]=self
        self.fam = None
        self.size = None
        self.busi = None
        self.configure(family=family, size=size, busi=busi)

    def configure(self, family=None, size=None, busi=None):
        if not family is None:
            self.fam = family
        newfam = self._getfamily()
        if not newfam is None:
            self.wfont.configure(family=newfam)
        if not size is None:
            self.size=size
        newsize = self._getsize()
        if not newsize is None:
            print("set size of", self.name, "to", newsize)
            self.wfont.configure(size=newsize)
        bv = self._getbool('b')
        if not bv is None:
            self.wfont.configure(weight='BOLD' if bv else 'NORMAL')
        bv = self._getbool('u')
        if not bv is None:
            self.wfont.configure(underline=1 if bv else 0)
        bv = self._getbool('i')
        if not bv is None:
            self.wfont.configure(slant='italic' if bv else 'roman')
        bv = self._getbool('s')
        if not bv is None:
            self.wfont.configure(overstrike=1 if bv else 1)
        f=self._getfamily()
        if f is None:
            f='helvetica'
        bstr = 'bold ' if self._getbool('b') else ''
        bstr += 'italic ' if self._getbool('i') else ''
        bstr += 'overstrike ' if self._getbool('s') else ''
        self.fontparams = (f, self._getsize(), bstr)
        for ch in self.children:
            ch.configure()

    def getFontDesc(self):
        return self.fontparams

    def _getfamily(self):
        if self.fam is None:
            if self.parent is None:
                return None
            return self.parent._getfamily()
        return self.fam

    def _getsize(self):
        if self.size is None:
            if self.parent is None:
                return 12
            return self.parent._getsize()
        elif isinstance(self.size, int):
            return self.size
        adjust = int(self.size)
        if self.parent is None:
            resu = 12
            return resu
        return self.parent._getsize() + adjust

    def _getbool(self, ccode):
        if self.busi is None:
            if self.parent is None:
                return None
            return self.parent._getbool(ccode)
        if ccode in self.busi:
            return not '-'+ccode in busi

def namedfonts():
    return tuple(pfont.allfonts.keys())

def allfontlist():
    return tuple(set(tkfont.families()))

class PanelUISettings(DockablePanel):
    """
    A Panel to set various aspects of the UI - font - font size,.....
    """
    def dofont(self):
        if 'basefont' in pfont.allfonts:
            print('amending font', self.children['fontname'].getValue())
            astr = {0:'', 1:'b',2:'-b'}[self.children['boldbtn'].getIndex()]
            astr += {0:'', 1:'i',2:'-i'}[self.children['italbtn'].getIndex()]
            print('>',astr,'<')
            pfont.allfonts['basefont'].configure(family=self.children['fontname'].getValue(), size=self.children['fnsize'].getValue())
            self.setstylefonts()
        else:
            x=17/0
#        self.recycle()

#    def recycle(self):
#        self.widg.destroy()
#        self.dropwidget()
#        self.setstylefonts()
#        self.pfield.widg.after_idle(self.show)

    def setupfontsandstyles(self):
        bf = pfont.makefont(None, 'basefont', family=None, size=12, busi=None)
        secthead = pfont.makefont(bf,'secthead', size='+3', busi='b')
        self.s = Style()
        self.s.configure('Astro.TEntry', fieldbackground='#353', background='#0f0', foreground='#cdc', selectbackground='#f00', selectforeground='#00f'
                , bordercolor='#ff0')
        self.s.map('Astro.TEntry', foreground=[('readonly','#aaa'),('','#fbb')], fieldbackground=[('readonly','#444'),('','#222')])
        self.s.configure('Astro.TLabel', background='#121', foreground='#cdc', font=bf.wfont, padding=2)
        self.s.configure('Secthead.TLabel',  background='#117', foreground='#ccd', font=secthead.wfont)
        self.s.configure('Astro.TCheckbutton',  background='#411', foreground='#eee', font=bf.wfont)
        self.s.configure('Astro.TCombobox',  background='#411', font=bf.wfont
                , selectbackground='#f00', selectforeground='#00f', fieldbackground='#000')
        self.s.map('Astro.TCombobox', foreground=[('readonly','#aaa'),('','#fbb')], fieldbackground=[('readonly','#444'),('','#222')])
        self.s.configure('Astro.TFrame',  background='#324', foreground='#eec')
        self.s.configure('Astro.TNotebook',  background='#324', foreground='#eec')
        self.s.configure('Astro.TNotebook.Tab', background='#555', foreground='#ccc', font=bf.wfont)
        self.s.map('Astro.TNotebook.Tab',background=[('selected','#222')],foreground=[('selected','#eee')])
        self.s.configure('Astro.TButton',  background='#324', foreground='#eec', font=bf.wfont)
        self.s.map("Astro.TButton",
            foreground=[('pressed', 'red'), ('active', '#fff')],
            background=[('pressed', '!disabled', 'ccc'), ('active', '#435')]
            )
        self.s.configure('Astro.TEntry',  background='#755', foreground='#eec')
        self.setstylefonts()

    def setstylefonts(self):
        pass

puiopts = {
      'class': PanelUISettings, 'name': 'puiopts', 'defdocked': True, 'defgeometry':'300x200+100+500','background': '#324'
    , 'children':(
        dockablebutton
      , {'class': TextField, 'name':'deffontlab', 'value': 'ui font:', 'style':'Secthead.TLabel'}
      , {'class': ComboField, 'name':'deffont', 'value': '', 'values': namedfonts, 'persist':0, 'style': 'Astro.TCombobox', 'font': 'basefont'}
      , {'class': TextField, 'name':'fnlab', 'value': 'system font:', 'style':'Astro.TLabel'}
      , {'class': ComboField, 'name':'fontname', 'value': '', 'values': allfontlist, 'persist':0, 'readonly':1, 'style': 'Astro.TCombobox', 'font': 'basefont'}
      , {'class': TextField, 'name':'fnslab', 'value': 'size:', 'style':'Astro.TLabel'}
      , {'class': IntField, 'name':'fnsize', 'value': 12, 'minval':5, 'maxval':50, 'style':'Astro.TEntry', 'persist':0, 'font': 'basefont'}
      , {'class': ComboField, 'name':'boldbtn', 'value': 'inherit', 'values': ('inherit', 'set bold', 'set normal'), 'readonly':1
                ,'style': 'Astro.TCombobox', 'font':'basefont'}
      , {'class': ComboField, 'name':'italbtn', 'value': 'inherit', 'values': ('inherit', 'set italic', 'set normal'), 'readonly':1
                ,'style': 'Astro.TCombobox', 'font':'basefont'}
      , {'class': ButtonField, 'name':'makefontbtn', 'value':'setup font', 'comfield': '..', 'command': 'dofont', 'style': 'Astro.TButton'}
      )
  , 'layout': {'type': 'grid'
      , 'colconfigs': ((3,{'weight':1}),)
      , 'params': {
          'dockbut': {'row':0, 'column':4, 'sticky':'ne'}
        , 'deffontlab': {'row':1, 'column':0,'sticky':'e'}  
        , 'deffont': {'row':1, 'column':1}
        , 'fnlab': {'row':2, 'column':0, 'sticky':'e'}
        , 'fontname': {'row': 2, 'column':1, 'sticky':'w'}
        , 'fnslab': {'row':2, 'column':2, 'sticky':'e'}
        , 'fnsize': {'row':2, 'column':3, 'sticky':'w'}
        , 'boldbtn': {'row':3, 'column':1}
        , 'italbtn': {'row':3, 'column':3}
        , 'makefontbtn': {'row':3, 'column':4}
  }}
}

tkroot = None

class testApp(PanelField):
    """
    This creates the top level environment by using a tkinter.Tk() instead of a Frame as a PanelField would do. This may cause hassle later
    and need to be changed to create a frame within the tkinter.Tk()
    """
    def __init__(self, fvalue, statefile, **kwargs):
        self.statepath = pathlib.Path.home() / '.pmtest.cfg' if statefile is None else pathlib.Path(statefile)
        self.loadState()
        super().__init__(fvalue = self.fval, **kwargs)

    def makeWidget(self):
        global tkroot
        assert 'toptkparams' in self.fielddef
        self.widg=tkinter.Tk()
        tkroot = self.widg
        self.getRelative('tp1.puiopts').setupfontsandstyles()
        if not self.fval is None and 'pstate' in self.fval and 'geom' in self.fval['pstate']:
            self.widg.geometry(self.fval['pstate']['geom']) 
        else:
            self.widg.geometry(self.fielddef['toptkparams']['geometry'])
        self.widg.title(self.fielddef['toptkparams']['title'])
        self.widg.configure(background='#b00')
        self.widg.protocol("WM_DELETE_WINDOW", self.winclose)
        self._makeChildrensWidgets()

    def nextTheme(self):
        tf=self.getRelative('tp1.p1.f1')
        tf.setValue(tf.getValue()+'x')

    def downTheme(self):
        tf=self.getRelative('tp1.p2.f1')
        tf.setValue(tf.getValue()+'AZ')

    def mainloop(self):
        self.widg.mainloop()

    def fchanged(self, wkey, w):
        self.saveState()

    def addbtn(self):
        addto = self.getRelative('tp1.p2')
        print('adding to ', addto.myname)
        addto.addChild({'class': CyclicButtonField, 'name':'zz plural z', 'value': 'zeroish', 'values':('zeroish', 'oneish','twoish')}
            , {'row':3, 'column':0, 'columnspan':2}
            ,None)

    def winclose(self):
        self.clearField()
        self.widg.destroy() # this should close the app

    def loadState(self):
        print('loading ', str(self.statepath))
        try:
            with self.statepath.open(mode='r') as cs:
                self.fval = json.load(cs)
        except:
#            if messagebox.askokcancel("Config file", "file " + self.configpath.__bytes__().decode('utf-8') + " appears corrupt. Re-create the file?" ):
#                self.setDefaultConfig()
            self.fval = None

    def saveState(self):
        print('save to ', str(self.statepath))
        with self.statepath.open(mode='w') as cs:
            cs.write(json.dumps(self.saveme()[1], sort_keys=True, indent=3))

    def saveme(self):
        sd = super().saveme()
        psg = {'geom': self.widg.geometry()}
        if sd is None:
            return self.myname, {'pstate': psg}
        else:
            sd[1]['pstate'] = psg
            return self.myname, sd[1]
