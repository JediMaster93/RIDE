#  Copyright 2008-2009 Nokia Siemens Networks Oyj
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import os
import wx

from robotide.publish import RideSavingDatafile, RideSavedDatafiles
from robotide.utils import OnScreenEnsuringFrame, RideEventHandler
from robotide.context import SETTINGS

from menu import ActionRegisterer, MenuBar, ToolBar, Actions, ActionInfo
from dialogs import KeywordSearchDialog, AboutDialog
from filedialogs import NewProjectDialog, NewResourceDialog, ChangeFormatDialog
from pluginmanager import PluginManager
from tree import Tree
from notebook import NoteBook


_menudata = """
[File]
!&Open | Open file containing tests | Ctrl-O | ART_FILE_OPEN
!Open &Directory | Open dir containing Robot files | Shift-Ctrl-O | ART_FOLDER_OPEN
!Open &Resource | Open a resource file | Ctrl-R
---
!&New Suite | Create a new top level suite | Ctrl-N
!N&ew Resource | Create New Resource File | Ctrl-Shift-N
---
!Save &All | Save all changes | Ctrl-Shift-S
---
!E&xit | Exit RIDE | Ctrl-Q

[Tools]
!Manage Plugins | Please Implement
!Search Keywords | Search keywords from libraries and resources 

[Help]
!About | Information about RIDE
"""


class RideFrame(wx.Frame, RideEventHandler, OnScreenEnsuringFrame):
    _default_dir = property(lambda self: os.path.abspath(SETTINGS['default directory']),
                            lambda self, path: SETTINGS.set('default directory', path))


    def __init__(self, application, keyword_filter):
        wx.Frame.__init__(self, parent=None, title='RIDE',
                          pos=SETTINGS['mainframe position'],
                          size=SETTINGS['mainframe size'])
        self._application = application
        self._init_ui()
        self._plugin_manager = PluginManager(self.notebook)
        self._kw_search_dialog = KeywordSearchDialog(self, keyword_filter)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.ensure_on_screen()
        self.Show()

    def _init_ui(self):
        self.actions = ActionRegisterer(MenuBar(self), ToolBar(self))
        self.actions.register_actions(Actions(_menudata, self))
        splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        splitter.SetMinimumPaneSize(200)
        self.notebook = NoteBook(splitter, self._application)
        self.tree = Tree(splitter, self.actions)
        splitter.SplitVertically(self.tree, self.notebook, 300)
        #FIXME: Is this needed? Who should do this currently also MenuBar does this
        self.CreateStatusBar()
        save = ActionInfo('File', '&Save', self.OnSave, self.tree, 'Ctrl-S',
                          'ART_FILE_SAVE', 'Save current suite or resource')
        save.set_menu_position(before='Save All')
        self.actions.register_action(save)

    def get_selected_datafile(self):
        return self.tree.get_selected_datafile()

    def OnClose(self, event):
        SETTINGS['mainframe size'] = self.GetSizeTuple()
        SETTINGS['mainframe position'] = self.GetPositionTuple()
        if self._application.ok_to_exit():
            self.Destroy()
        else:
            wx.CloseEvent.Veto(event)

    def OnNewSuite(self, event):
        if not self._application.ok_to_open_new():
            return
        dlg = NewProjectDialog(self, self._default_dir)
        if dlg.ShowModal() == wx.ID_OK:
            dirname = os.path.dirname(dlg.get_path())
            if not os.path.isdir(dirname):
                os.mkdir(dirname)
            self._default_dir = dirname
            self._application.open_suite(dlg.get_path())
            self.tree.populate(self._application.model)
        dlg.Destroy()

    def OnNewResource(self, event):
        dlg = NewResourceDialog(self, self._default_dir)
        if dlg.ShowModal() == wx.ID_OK:
            self._default_dir = os.path.dirname(dlg.get_path())
            self._application.open_resource(dlg.get_path())
        dlg.Destroy()

    def OnOpen(self, event):
        if not self._application.ok_to_open_new():
            return
        path = self._get_path()
        if path:
            self.open_suite(path)

    def OnOpenResource(self, event):
        path = self._get_path()
        if path:
            self._application.open_resource(path)

    def _get_path(self):
        wildcard = ('All files|*.*|Robot data (*.html)|*.*htm*|'
                    'Robot data (*.tsv)|*.tsv|Robot data (*txt)|*.txt')
        dlg = wx.FileDialog(self, message='Open', wildcard=wildcard,
                            defaultDir=self._default_dir, style=wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self._default_dir = os.path.dirname(path)
        else:
            path = None
        dlg.Destroy()
        return path

    def open_suite(self, path):
        self._application.open_suite(path)
        self.tree.populate(self._application.model)

    def OnOpenDirectory(self, event):
        if not self._application.ok_to_open_new():
            return
        path = wx.DirSelector(message='Choose a directory containing Robot files',
                              defaultPath=self._default_dir)
        if path:
            self._default_dir = os.path.dirname(path)
            self.open_suite(path)

    def OnSave(self, event):
        self.save(self.get_selected_datafile())

    def OnSaveAll(self, event):
        self.save()

    def save(self, datafile=None):
        files_without_format = self._application.get_files_without_format(datafile)
        for f in files_without_format:
            self._show_format_dialog_for(f)
        RideSavingDatafile(datafile=datafile).publish()
        saved = self._application.save(datafile)
        self._report_saved_files(saved)
        self.tree.unset_dirty()

    def _show_format_dialog_for(self, file_without_format):
        help = 'Please provide format of initialization file for directory suite\n"%s".' %\
                file_without_format.source
        dlg = ChangeFormatDialog(self, 'HTML', help_text=help)
        if dlg.ShowModal() == wx.ID_OK:
            file_without_format.set_format(dlg.get_format())
        dlg.Destroy()

    def _report_saved_files(self, saved):
        if not saved:
            return
        RideSavedDatafiles(datafiles=saved).publish()
        s = len(saved) > 1 and 's' or ''
        self.SetStatusText('Wrote file%s: %s' %
                          (s, ', '.join(item.source for item in saved)))

    def OnExit(self, event):
        self.Close()

    def OnManagePlugins(self, event):
        self._plugin_manager.show(self._application.get_plugins())

    def OnSearchKeywords(self, event):
        if not self._kw_search_dialog.IsShown():
            self._kw_search_dialog.Show()

    def OnAbout(self, event):
        dlg = AboutDialog(self)
        dlg.ShowModal()
        dlg.Destroy()
