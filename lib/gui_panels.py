#!/usr/bin/env python
"""
Main GUI form for setting up and executing Step Scans

Principle features:
   1.  Overall Configuration file in home directory
   2.  wx.ChoiceBox (exclusive panel) for
         Linear Scans
         Mesh Scans (2d maps)
         XAFS Scans
         Fly Scans (optional)

   3.  Other notes:
       Linear Scans support Slave positioners
       A Scan Definition files describes an individual scan.
       Separate popup window for Detectors (Trigger + set of Counters)
       Allow adding any additional Counter
       Builtin Support for Detectors: Scalers, MultiMCAs, and AreaDetectors
       Give File Prefix on Scan Form
       options window for settling times
       Plot Window allows simple math of columns
       Plot Window supports shows position has "Go To" button.

   4. To consider / add:
       keep sqlite db of scan defs / scan names (do a scan like 'xxxx')
       plot window can do simple analysis?

"""
import os
import time

import wx
import wx.lib.agw.flatnotebook as flat_nb
import wx.lib.scrolledpanel as scrolled
import wx.lib.mixins.inspection

import epics
from epics.wx import DelayedEpicsCallback, EpicsFunction
from gui_utils import SimpleText, FloatCtrl, Closure
from gui_utils import pack, add_choice


from file_utils import new_filename, increment_filename, nativepath
from scan_config import ScanConfig

MAX_POINTS = 4000

ALL_CEN =  wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL
FNB_STYLE = flat_nb.FNB_NO_X_BUTTON|flat_nb.FNB_SMART_TABS|flat_nb.FNB_NO_NAV_BUTTONS


class GenericScanPanel(scrolled.ScrolledPanel):
    __name__ = 'genericScan'
    def __init__(self, parent, config=None,
                 size=(625,300), style=wx.GROW|wx.TAB_TRAVERSAL):

        self.config = config
        scrolled.ScrolledPanel.__init__(self, parent,
                                        size=size, style=style,
                                        name=self.__name__)
        self.Font13=wx.Font(13, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "")

    def layout(self, panel, sizer):
        pack(panel, sizer)
        msizer = wx.BoxSizer(wx.VERTICAL)
        msizer.Add(panel, 1, wx.EXPAND)
        pack(self, msizer)
        self.Layout()
        self.SetupScrolling()

    def generate_scan(self):
        print 'generate scan ', self.__name__


class LinearScanPanel(GenericScanPanel):
    """ linear scan """
    __name__ = 'StepScan'
    def __init__(self, parent, config=None):
        GenericScanPanel.__init__(self, parent, size=(750, 250), config=config)

        panel = wx.Panel(self)
        sizer = wx.GridBagSizer(7, 8)
        sty=wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL
        lsty=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL
        title =  SimpleText(panel, 'Linear Step Scan Setup',
                            font=self.Font13, colour='#880000',
                            style=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)

        ir = 0
        sizer.Add(title, (ir, 1), (1, 3), sty, 4)

        absrel = add_choice(panel,('Absolute', 'Relative'), action = self.onAbsRel)
        self.dwelltime = FloatCtrl(panel, precision=3, value=1., minval=0, size=(80, -1))
        self.est_time  = SimpleText(panel, '00:00:00')

        ir += 1
        sizer.Add(SimpleText(panel, "Scan Mode:"),   (ir, 0), (1, 1), sty, 4)
        sizer.Add(absrel, (ir, 1), (1, 1), sty, 4)
        sizer.Add(SimpleText(panel, "Time/Point (sec):"),  (ir, 2), (1, 2), sty, 3)
        sizer.Add(self.dwelltime, (ir, 4), (1, 1), lsty, 2)

        ir += 1
        l = wx.StaticLine(panel, size=(675, 3), style=wx.LI_HORIZONTAL)
        sizer.Add(l, (ir, 0), (1, 8), wx.ALIGN_CENTER)

        ir += 1
        for ic, lab in enumerate(("Role", "Positioner", "Units", "Current", "Start",
                                  "Stop", "Step", " Npts")):
            s  = sty
            if lab == " Npts": s = lsty
            sizer.Add(SimpleText(panel, lab), (ir, ic), (1, 1), s, 2)

        self.pos_settings = []
        pchoices=self.config.positioners.keys()
        fsize = (95, -1)
        for i in range(3):
            lab = 'Slave'
            if i == 0: lab = 'Master'
            if i > 0 and 'None' not in pchoices:
                pchoices.insert(0, 'None')

            pos = add_choice(panel, pchoices, size=(100, -1),
                             action=Closure(self.onPos, index=i))

            role = wx.StaticText(panel, -1, label=lab)
            units = wx.StaticText(panel, -1, size=(30, -1), label=' ')
            cur = wx.StaticText(panel, -1, size=(80, -1), label=' ')
            start = FloatCtrl(panel, size=fsize, value=0,  act_on_losefocus=True,
                              action=Closure(self.onVal, index=i, label='start'))
            stop  = FloatCtrl(panel, size=fsize, value=0, act_on_losefocus=True,
                              action=Closure(self.onVal, index=i, label='stop'))
            step  = FloatCtrl(panel, size=fsize, value=0, act_on_losefocus=True,
                              action=Closure(self.onVal, index=i, label='step'))
            if i == 0:
                npts  = FloatCtrl(panel, precision=0,  value=1, size=(50, -1),
                                  action=Closure(self.onVal, index=i, label='npts'))
            else:
                npts  = wx.StaticText(panel, -1, size=fsize, label='    1')
            self.pos_settings.append((pos, units, cur, start, stop, step, npts))
            if i > 0:
                start.Disable()
                stop.Disable()
                step.Disable()
                npts.Disable()
            ir += 1
            sizer.Add(role,  (ir, 0), (1, 1), wx.ALL, 2)
            sizer.Add(pos,   (ir, 1), (1, 1), wx.ALL, 2)
            sizer.Add(units, (ir, 2), (1, 1), wx.ALL, 2)
            sizer.Add(cur,   (ir, 3), (1, 1), wx.ALL, 2)
            sizer.Add(start, (ir, 4), (1, 1), wx.ALL, 2)
            sizer.Add(stop,  (ir, 5), (1, 1), wx.ALL, 2)
            sizer.Add(step,  (ir, 6), (1, 1), wx.ALL, 2)
            sizer.Add(npts,  (ir, 7), (1, 1), wx.ALL, 2)

        ir += 1
        l = wx.StaticLine(panel, size=(675, 3), style=wx.LI_HORIZONTAL|wx.GROW)
        sizer.Add(l, (ir, 0), (1, 8), wx.ALIGN_CENTER)

        ir += 1
        sizer.Add(SimpleText(panel, "Estimated Scan Time:"),  (ir, 0,), (1, 2), sty, 3)
        sizer.Add(self.est_time, (ir, 2), (1, 2), lsty, 2)

        self.layout(panel, sizer)

    def onVal(self, index=0, label=None, value=None, **kws):
        print 'on Value ', index, label, value, kws

    def onPos(self, evt=None, index=0):
        print 'On Position   ', index, evt

    def onAbsRel(self, evt=None):
        print 'On AbsRel  ', evt


class XAFSScanPanel(GenericScanPanel):
    """ exafs  scan """
    __name__ = 'XAFSScan'
    edges_list = ('K','L3','M5','L2','L1')
    units_list = ('eV', '1/A')

    def __init__(self, parent, config=None):
        GenericScanPanel.__init__(self, parent, size=(750, 325), config=config)
        self.reg_settings = []
        panel = wx.Panel(self)
        sizer = wx.GridBagSizer(7, 7)

        e0_wid  = FloatCtrl(panel, precision=2, value=10000., minval=0, maxval=1e7,
                            size=(80, -1), act_on_losefocus=True,
                            action=Closure(self.onVal, label='e0'))


        self.elemchoice = add_choice(panel, ('Cu', 'Zn'),
                             action=self.onElemChoice)
        self.edgechoice = add_choice(panel, self.edges_list,
                             action=self.onEdgeChoice)

        absrel = add_choice(panel,('Absolute', 'Relative'), size=(100, -1),
                            action = self.onAbsRel)

        nregs_wid = FloatCtrl(panel, precision=0, value=3, minval=0, maxval=5,
                            size=(25, -1),  act_on_losefocus=True,
                            action=Closure(self.onVal, label='nreg'))

        global_dt = FloatCtrl(panel, precision=2, value=1., minval=0, maxval=1.e5,
                              size=(65, -1),
                              action=Closure(self.onVal, label='global_dwell'))


        nregs = nregs_wid.GetValue()

        self.est_time  = SimpleText(panel, '00:00:00')

        sty=wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL
        lsty=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL
        title =  SimpleText(panel, 'EXAFS Scan Setup',
                            font=self.Font13, colour='#880000',
                            style=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)

        ir = 0
        sizer.Add(title, (ir, 1), (1, 3), sty, 4)

        ir += 1
        sizer.Add(SimpleText(panel, "Edge Energy:", size=(120, -1),
                             style=wx.ALIGN_LEFT), (ir, 0), (1, 1), sty, 2)
        sizer.Add(e0_wid,   (ir, 1), (1, 1), lsty, 2)
        sizer.Add(SimpleText(panel, "Element:"),  (ir, 2), (1, 1), lsty)
        sizer.Add(self.elemchoice,                (ir, 3), (1, 1), lsty)
        sizer.Add(SimpleText(panel, "Edge:"),     (ir, 4), (1, 1), lsty)
        sizer.Add(self.edgechoice,                (ir, 5), (1, 1), lsty)

        ir += 1
        sizer.Add(SimpleText(panel, "Scan Mode:", size=(120, -1),
                             style=wx.ALIGN_LEFT), (ir, 0), (1, 1), sty, 2)
        sizer.Add(absrel, (ir, 1), (1, 1), sty, 4)
        sizer.Add(SimpleText(panel, "Number of Scan Regions:"),  (ir, 2), (1, 2), lsty, 3)
        sizer.Add(nregs_wid,   (ir, 4), (1, 1), lsty, 2)

        sizer.Add(SimpleText(panel, "Time/Point (sec):"),  (ir, 5), (1, 1), lsty, 3)
        sizer.Add(global_dt, (ir, 6), (1, 1), lsty, 2)


        ir += 1
        l = wx.StaticLine(panel, size=(675, 3), style=wx.LI_HORIZONTAL)
        sizer.Add(l, (ir, 0), (1, 7), wx.ALIGN_CENTER)

        ir += 1
        for ic, lab in enumerate(("Region", "Start", "Stop", "Step",
                                    "Npts", "Time (s)", "Units")):
            sizer.Add(SimpleText(panel, lab),  (ir, ic), (1, 1), lsty, 2)

        fsize = (80, -1)
        for i, label in enumerate(('Pre-Edge', 'XANES', 'EXAFS')):
            ir += 1
            reg   = wx.StaticText(panel, -1, size=(120, -1), label=' %s' % label)
            start = FloatCtrl(panel, size=fsize, value=0,  act_on_losefocus=True,
                              action=Closure(self.onVal, index=i, label='start'))
            stop  = FloatCtrl(panel, size=fsize, value=0,  act_on_losefocus=True,
                              action=Closure(self.onVal, index=i, label='stop'))
            step  = FloatCtrl(panel, size=fsize, value=0,  act_on_losefocus=True,
                              action=Closure(self.onVal, index=i, label='step'))
            npts  = FloatCtrl(panel, precision=0,  act_on_losefocus=True,
                              value=1, minval=1, size=(50, -1),
                              action=Closure(self.onVal, index=i, label='npts'))
            dtime = FloatCtrl(panel, size=(65, -1), value=0, minval=0, precision=2,
                              action=Closure(self.onVal, index=i, label='dtime'))

            if i < 2:
                units = wx.StaticText(panel, -1, size=(30, -1), label='eV')
            else:
                units = add_choice(panel, self.units_list,
                                   action=Closure(self.onUnitsChoice, index=i))

            self.reg_settings.append((start, stop, step, npts, dtime, units))
            if i >= nregs:
                start.Disable()
                stop.Disable()
                step.Disable()
                npts.Disable()
                dtime.Disable()
                reg.Disable()
                units.Disable()
            sizer.Add(reg,   (ir, 0), (1, 1), wx.ALL, 5)
            sizer.Add(start, (ir, 1), (1, 1), wx.ALL, 2)
            sizer.Add(stop,  (ir, 2), (1, 1), wx.ALL, 2)
            sizer.Add(step,  (ir, 3), (1, 1), wx.ALL, 2)
            sizer.Add(npts,  (ir, 4), (1, 1), wx.ALL, 2)
            sizer.Add(dtime, (ir, 5), (1, 1), wx.ALL, 2)
            sizer.Add(units, (ir, 6), (1, 1), wx.ALL, 2)

        ir += 1
        l = wx.StaticLine(panel, size=(675, 3), style=wx.LI_HORIZONTAL|wx.GROW)
        sizer.Add(l, (ir, 0), (1, 7), wx.ALIGN_CENTER)

        self.kwtimechoice = add_choice(panel, ('0', '1', '2', '3'), size=(70, -1))

        self.kwtime = FloatCtrl(panel, precision=2, value=0, minval=0,
                                size=(65, -1),
                                action=Closure(self.onVal, label='kwtime'))

        ir += 1
        sizer.Add(SimpleText(panel, "k-weight time of last region:"),  (ir, 1,), (1, 2), sty, 3)
        sizer.Add(self.kwtimechoice, (ir, 3), (1, 1), lsty, 2)
        sizer.Add(SimpleText(panel, "Max Time:"),  (ir, 4,), (1, 1), sty, 3)
        sizer.Add(self.kwtime, (ir, 5), (1, 1), lsty, 2)

        ir += 1
        sizer.Add(SimpleText(panel, "Estimated Scan Time:"),  (ir, 0,), (1, 2), sty, 3)
        sizer.Add(self.est_time, (ir, 2), (1, 2), lsty, 2)

        self.layout(panel, sizer)

    def onVal(self, index=0, label=None, value=None, **kws):
        print 'on Value ', index, label, value, kws
        if label == 'global_dwell':
            for reg in self.reg_settings:
                reg[4].SetValue(value)
            try:
                self.kwtime.SetValue(value)
            except:
                pass
        elif label == 'stop':
            if index < len(self.reg_settings)-1:
                self.reg_settings[index+1][0].SetValue(value, act=False)
        elif label == 'start':
            if index > 0:
                self.reg_settings[index-1][1].SetValue(value, act=False)
        elif label == 'nreg':
            nregs = value
            for ireg, reg in enumerate(self.reg_settings):
                if ireg < nregs:
                    for wid in reg: wid.Enable()
                else:
                    for wid in reg: wid.Disable()

    def onPos(self, evt=None, index=0):
        print 'On Position   ', index, evt

    def onAbsRel(self, evt=None):
        print 'On AbsRel  ', evt.GetString()

    def onUnitsChoice(self, evt=None, index=0):
        print 'On Units:  ', evt.GetString(), index

    def onEdgeChoice(self, evt=None):
        print 'On Edge:  ', evt.GetString()

    def onElemChoice(self, evt=None):
        print 'On Elem:  ', evt.GetString()

class MeshScanPanel(GenericScanPanel):
    """ mesh / 2-d scan """
    __name__ = 'MeshScan'
    def __init__(self, parent, config=None):
        GenericScanPanel.__init__(self, parent, size=(750, 250), config=config)

        panel = wx.Panel(self)
        sizer = wx.GridBagSizer(7, 8)

        sty=wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL
        lsty=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL
        title =  SimpleText(panel, 'Mesh Scan (Slow Map) Setup',
                            font=self.Font13, colour='#880000',
                            style=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)
        ir = 0
        sizer.Add(title, (ir, 1), (1, 3), sty, 4)

        absrel = add_choice(panel,('Absolute', 'Relative'),
                            action = self.onAbsRel)

        self.dwelltime = FloatCtrl(panel, precision=3, value=1., minval=0, size=(80, -1))
        self.est_time  = SimpleText(panel, '00:00:00')

        ir += 1
        sizer.Add(SimpleText(panel, "Scan Mode:"),   (ir, 0), (1, 1), sty, 4)
        sizer.Add(absrel, (ir, 1), (1, 1), sty, 4)
        sizer.Add(SimpleText(panel, "Time/Point (sec):"),  (ir, 2), (1, 2), sty, 3)
        sizer.Add(self.dwelltime, (ir, 4), (1, 1), lsty, 2)

        ir += 1
        l = wx.StaticLine(panel, size=(675, 3), style=wx.LI_HORIZONTAL)
        sizer.Add(l, (ir, 0), (1, 8), wx.ALIGN_CENTER)

        ir += 1
        for ic, lab in enumerate(("Loop", "Positioner", "Units",
                                  "Current", "Start","Stop", "Step", " Npts")):
            s  = sty
            if lab == " Npts": s = lsty
            sizer.Add(SimpleText(panel, lab), (ir, ic), (1, 1), s, 2)

        self.pos_settings = []
        pchoices=self.config.positioners.keys()
        fsize = (95, -1)
        for i, label in enumerate(("Inner", "Outer")):
            lab = wx.StaticText(panel, -1, label=label)
            pos = add_choice(panel, pchoices, size=(100, -1),
                             action=Closure(self.onPos, index=i))

            units = wx.StaticText(panel, -1, size=(30, -1), label=' ')
            cur = wx.StaticText(panel, -1, size=(80, -1), label=' ')
            start = FloatCtrl(panel, size=fsize, value=0,
                              action=Closure(self.onVal, index=i, label='start'))
            stop  = FloatCtrl(panel, size=fsize, value=0,
                              action=Closure(self.onVal, index=i, label='stop'))
            step  = FloatCtrl(panel, size=fsize, value=0,
                              action=Closure(self.onVal, index=i, label='step'))
            npts  = FloatCtrl(panel, precision=0,  value=1, size=(50, -1),
                              action=Closure(self.onVal, index=i, label='npts'))
            self.pos_settings.append((pos, units, cur, start, stop, step, npts))
            ir += 1
            sizer.Add(lab,   (ir, 0), (1, 1), wx.ALL, 2)
            sizer.Add(pos,   (ir, 1), (1, 1), wx.ALL, 2)
            sizer.Add(units, (ir, 2), (1, 1), wx.ALL, 2)
            sizer.Add(cur,   (ir, 3), (1, 1), wx.ALL, 2)
            sizer.Add(start, (ir, 4), (1, 1), wx.ALL, 2)
            sizer.Add(stop,  (ir, 5), (1, 1), wx.ALL, 2)
            sizer.Add(step,  (ir, 6), (1, 1), wx.ALL, 2)
            sizer.Add(npts,  (ir, 7), (1, 1), wx.ALL, 2)

        ir += 1
        l = wx.StaticLine(panel, size=(675, 3), style=wx.LI_HORIZONTAL|wx.GROW)
        sizer.Add(l, (ir, 0), (1, 8), wx.ALIGN_CENTER)

        ir += 1
        sizer.Add(SimpleText(panel, "Estimated Scan Time:"),  (ir, 0,), (1, 2), sty, 3)
        sizer.Add(self.est_time, (ir, 2), (1, 2), lsty, 2)

        self.layout(panel, sizer)


    def onVal(self, index=0, label=None, value=None, **kws):
        print 'on Value ', index, label, value, kws

    def onPos(self, evt=None, index=0):
        print 'On Position   ', index, evt

    def onAbsRel(self, evt=None):
        print 'On AbsRel  ', evt


class SlewScanPanel(GenericScanPanel):
    """ mesh / 2-d scan """
    __name__ = 'SlewScan'
    def __init__(self, parent, config=None):
        GenericScanPanel.__init__(self, parent, size=(750, 250), config=config)

        panel = wx.Panel(self)
        sizer = wx.GridBagSizer(7, 8)

        sty=wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL
        lsty=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL
        title =  SimpleText(panel, 'Slew Scan (Fast Map) Setup',
                            font=self.Font13, colour='#880000',
                            style=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)
        ir = 0
        sizer.Add(title, (ir, 1), (1, 3), sty, 4)

        absrel = add_choice(panel,('Absolute', 'Relative'),
                            action = self.onAbsRel)

        self.dwelltime = FloatCtrl(panel, precision=3, value=1., minval=0, size=(80, -1))
        self.est_time  = SimpleText(panel, '00:00:00')

        ir += 1
        sizer.Add(SimpleText(panel, "Scan Mode:"),   (ir, 0), (1, 1), sty, 4)
        sizer.Add(absrel, (ir, 1), (1, 1), sty, 4)
        sizer.Add(SimpleText(panel, "Time/Point (sec):"),  (ir, 2), (1, 2), sty, 3)
        sizer.Add(self.dwelltime, (ir, 4), (1, 1), lsty, 2)

        ir += 1
        l = wx.StaticLine(panel, size=(675, 3), style=wx.LI_HORIZONTAL)
        sizer.Add(l, (ir, 0), (1, 8), wx.ALIGN_CENTER)

        ir += 1
        for ic, lab in enumerate(("Loop", "Positioner", "Units",
                                  "Current", "Start","Stop", "Step", " Npts")):
            s  = sty
            if lab == " Npts": s = lsty
            sizer.Add(SimpleText(panel, lab), (ir, ic), (1, 1), s, 2)

        self.pos_settings = []
        pchoices=self.config.positioners.keys()
        fsize = (95, -1)
        for i, label in enumerate(("Inner", "Outer")):
            lab = wx.StaticText(panel, -1, label=label)
            pos = add_choice(panel, pchoices, size=(100, -1),
                             action=Closure(self.onPos, index=i))

            units = wx.StaticText(panel, -1, size=(30, -1), label=' ')
            cur = wx.StaticText(panel, -1, size=(80, -1), label=' ')
            start = FloatCtrl(panel, size=fsize, value=0,
                              action=Closure(self.onVal, index=i, label='start'))
            stop  = FloatCtrl(panel, size=fsize, value=0,
                              action=Closure(self.onVal, index=i, label='stop'))
            step  = FloatCtrl(panel, size=fsize, value=0,
                              action=Closure(self.onVal, index=i, label='step'))
            npts  = FloatCtrl(panel, precision=0,  value=1, size=(50, -1),
                              action=Closure(self.onVal, index=i, label='npts'))
            self.pos_settings.append((pos, units, cur, start, stop, step, npts))
            ir += 1
            sizer.Add(lab,   (ir, 0), (1, 1), wx.ALL, 2)
            sizer.Add(pos,   (ir, 1), (1, 1), wx.ALL, 2)
            sizer.Add(units, (ir, 2), (1, 1), wx.ALL, 2)
            sizer.Add(cur,   (ir, 3), (1, 1), wx.ALL, 2)
            sizer.Add(start, (ir, 4), (1, 1), wx.ALL, 2)
            sizer.Add(stop,  (ir, 5), (1, 1), wx.ALL, 2)
            sizer.Add(step,  (ir, 6), (1, 1), wx.ALL, 2)
            sizer.Add(npts,  (ir, 7), (1, 1), wx.ALL, 2)

        ir += 1
        l = wx.StaticLine(panel, size=(675, 3), style=wx.LI_HORIZONTAL|wx.GROW)
        sizer.Add(l, (ir, 0), (1, 8), wx.ALIGN_CENTER)

        ir += 1
        sizer.Add(SimpleText(panel, "Estimated Scan Time:"),  (ir, 0,), (1, 2), sty, 3)
        sizer.Add(self.est_time, (ir, 2), (1, 2), lsty, 2)

        self.layout(panel, sizer)

    def onVal(self, index=0, label=None, value=None, **kws):
        print 'on Value ', index, label, value, kws

    def onPos(self, evt=None, index=0):
        print 'On Position   ', index, evt

    def onAbsRel(self, evt=None):
        print 'On AbsRel  ', evt

    def OLDSLEWSCANPanel(self):
        pane = wx.Panel(self, -1)

        self.dimchoice = wx.Choice(pane, size=(120,30))
        self.m1choice = wx.Choice(pane,  size=(120,30))
        self.m1units  = SimpleText(pane, "",minsize=(50,20))
        self.m1start  = FloatCtrl(pane, precision=4, value=0)
        self.m1stop   = FloatCtrl(pane, precision=4, value=1)
        self.m1step   = FloatCtrl(pane, precision=4, value=0.1)

        self.m1npts   = SimpleText(pane, "0",minsize=(55,20))
        # self.rowtime  = FloatCtrl(pane, precision=1, value=10., minval=0.)
        self.pixtime  = FloatCtrl(pane, precision=3, value=0.100, minval=0.)

        self.m2choice = wx.Choice(pane, size=(120,30),choices=[])
        self.m2units  = SimpleText(pane, "",minsize=(50,20))
        self.m2start  = FloatCtrl(pane, precision=4, value=0)
        self.m2stop   = FloatCtrl(pane, precision=4, value=1)
        self.m2step   = FloatCtrl(pane, precision=4, value=0.1)
        self.m2npts   = SimpleText(pane, "0",minsize=(60,20))

        self.maptime  = SimpleText(pane, "0")
        self.rowtime  = SimpleText(pane, "0")
        self.t_rowtime = 0.0

        self.filename = wx.TextCtrl(pane, -1, "")
        self.filename.SetMinSize((350, 25))

        self.usertitles = wx.TextCtrl(pane, -1, "",
                                      style=wx.TE_MULTILINE)
        self.usertitles.SetMinSize((350, 75))
        self.startbutton = wx.Button(pane, -1, "Start")
        self.abortbutton = wx.Button(pane, -1, "Abort")

        self.startbutton.Bind(wx.EVT_BUTTON, self.onStartScan)
        self.abortbutton.Bind(wx.EVT_BUTTON, self.onAbortScan)

        self.m1choice.Bind(wx.EVT_CHOICE, self.onM1Select)
        self.m2choice.Bind(wx.EVT_CHOICE, self.onM2Select)
        self.dimchoice.Bind(wx.EVT_CHOICE, self.onDimension)


        self.m1choice.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.m2choice.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.abortbutton.SetBackgroundColour(wx.Colour(255, 72, 31))

        gs = wx.GridBagSizer(8, 8)
        all_cvert = wx.ALL|wx.ALIGN_CENTER_VERTICAL
        all_bot   = wx.ALL|wx.ALIGN_BOTTOM|wx.ALIGN_CENTER_HORIZONTAL
        all_cen   = wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL

        # Title row
        nr = 0
        gs.Add(SimpleText(pane, "XRF Map Setup",
                     minsize=(200, 30),
                     font=self.Font16, colour=(120,0,0)),
               (nr,0), (1,4),all_cen)
        gs.Add(SimpleText(pane, "Scan Type",
                     minsize=(80,20),style=wx.ALIGN_RIGHT),
               (nr,5), (1,1), all_cvert)
        gs.Add(self.dimchoice, (nr,6), (1,2),
               wx.ALIGN_LEFT)
        nr +=1
        gs.Add(wx.StaticLine(pane, size=(650,3)),
               (nr,0), (1,8), all_cen)
        # title
        nr +=1
        gs.Add(SimpleText(pane, "Stage"),  (nr,1), (1,1), all_bot)
        gs.Add(SimpleText(pane, "Units",minsize=(50,20)),  (nr,2), (1,1), all_bot)
        gs.Add(SimpleText(pane, "Start"),  (nr,3), (1,1), all_bot)
        gs.Add(SimpleText(pane, "Stop"),   (nr,4), (1,1), all_bot)
        gs.Add(SimpleText(pane, "Step"),   (nr,5), (1,1), all_bot)
        gs.Add(SimpleText(pane, "Npoints"),(nr,6), (1,1), all_bot)
        gs.Add(SimpleText(pane, "Time Per Point (s)",
                     minsize=(140,20)),(nr,7), (1,1), all_cvert|wx.ALIGN_LEFT)
        # fast motor row
        nr +=1
        gs.Add(SimpleText(pane, "Fast Motor", minsize=(90,20)),
               (nr,0),(1,1), all_cvert )
        gs.Add(self.m1choice, (nr,1))
        gs.Add(self.m1units,  (nr,2))
        gs.Add(self.m1start,  (nr,3))
        gs.Add(self.m1stop,   (nr,4)) # 0, all_cen)
        gs.Add(self.m1step,   (nr,5))
        gs.Add(self.m1npts,   (nr,6),(1,1),wx.ALIGN_CENTER_HORIZONTAL)
        gs.Add(self.pixtime,  (nr,7))

        # slow motor row
        nr +=1
        gs.Add(SimpleText(pane, "Slow Motor", minsize=(90,20)),
               (nr,0),(1,1), all_cvert )
        gs.Add(self.m2choice, (nr,1))
        gs.Add(self.m2units,  (nr,2))
        gs.Add(self.m2start,  (nr,3))
        gs.Add(self.m2stop,   (nr,4)) # 0, all_cen)
        gs.Add(self.m2step,   (nr,5))
        gs.Add(self.m2npts,   (nr,6),(1,1),wx.ALIGN_CENTER_HORIZONTAL)
        #
        nr +=1
        gs.Add(wx.StaticLine(pane, size=(650,3)),(nr,0), (1,8),all_cen)

        # filename row
        nr +=1
        gs.Add(SimpleText(pane, "File Name", minsize=(90,20)), (nr,0))
        gs.Add(self.filename, (nr,1), (1,4))

        gs.Add(SimpleText(pane, "Time per line (sec):",
                     minsize=(-1, 20), style=wx.ALIGN_LEFT),
               (nr,5), (1,2), wx.ALIGN_LEFT)
        gs.Add(self.rowtime, (nr,7))

        # title row
        nr +=1
        gs.Add(SimpleText(pane, "Comments ",
                     minsize=(80,50)), (nr,0))
        gs.Add(self.usertitles,        (nr,1),(1,4))
        gs.Add(SimpleText(pane, "Time for map (H:Min:Sec):",
                     minsize=(-1,20), style=wx.ALIGN_LEFT),
               (nr,5), (1,2), wx.ALIGN_LEFT)
        gs.Add(self.maptime, (nr,7))

        # button row
        nr +=1
        gs.Add(SimpleText(pane, " ", minsize=(90,35)), (nr,0))
        gs.Add(self.startbutton, (nr,1))
        gs.Add(self.abortbutton, (nr,3))
        #
        # nr +=1
        #gs.Add(wx.StaticLine(pane, size=(650,3)),(nr,0), (1,7),all_cen)

        pane.SetSizer(gs)

        MainSizer = wx.BoxSizer(wx.VERTICAL)
        MainSizer.Add(pane, 1, 0,0)
        self.SetSizer(MainSizer)
        MainSizer.SetSizeHints(self)
        MainSizer.Fit(self)
        self.Layout()


