import wx
import wx.adv
import os
import re
import json
from collections import OrderedDict

# --- Constants ---
APP_NAME = "FTL Translator"
MAX_RECENT_FILES = 9

# Status Levels (lower number = higher sort priority)
STATUS_UNTRANSLATED = 0
STATUS_ERROR_PUNCTUATION = 1
STATUS_OK = 2

# Suffixes for display in the listbox
STATUS_SUFFIX = {
    STATUS_UNTRANSLATED: " (not translated)",
    STATUS_ERROR_PUNCTUATION: " (error)", # Base error suffix, detail added later
    STATUS_OK: " (done)"
}

# Status descriptions for the detailed status label in the right panel
STATUS_DESC = {
    STATUS_UNTRANSLATED: "Status: Untranslated",
    STATUS_ERROR_PUNCTUATION: "Status: Punctuation mismatch", # Detail added later
    STATUS_OK: "Status: Translated (OK)" # Clarify OK status
}

# Simple punctuation check: Checks if the last non-whitespace char is one of these
PUNCTUATION_CHARS = ['.', '!', '?', ':']

# Context Menu IDs
ID_CONTEXT_LOOKUP = wx.NewIdRef()


# --- FTL Parsing Logic ---
# (parse_ftl function remains the same)
def parse_ftl(filepath):
    lines_structure = []
    translations = OrderedDict()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                stripped_line = line.strip()
                if not stripped_line: lines_structure.append(('blank', line))
                elif stripped_line.startswith('#'): lines_structure.append(('comment', line))
                elif stripped_line.startswith('##') or stripped_line.startswith('--'): lines_structure.append(('section', line))
                elif '=' in line:
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        key, value = parts
                        key = key.strip()
                        if key and not key.startswith('#'):
                            value = value.lstrip()
                            value_stripped_end = value.rstrip('\n\r')
                            lines_structure.append(('translation', (key, value_stripped_end), line))
                            translations[key] = value_stripped_end
                        else: lines_structure.append(('comment', line))
                    else: lines_structure.append(('comment', line))
                else: lines_structure.append(('comment', line))
    except FileNotFoundError:
        wx.LogError(f"File not found: {filepath}")
        return None, None
    except Exception as e:
        wx.LogError(f"Error parsing FTL file {filepath}: {e}")
        return None, None
    return lines_structure, translations

# (save_ftl function remains the same)
def save_ftl(filepath, lines_structure, current_translations):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            for item_type, data, *original_line in lines_structure:
                if item_type == 'translation':
                    key, original_value = data
                    current_value = current_translations.get(key, original_value)
                    f.write(f"{key} = {current_value}\n")
                elif item_type in ('comment', 'blank', 'section'):
                     f.write(data)
    except Exception as e:
        wx.LogError(f"Error saving FTL file {filepath}: {e}")
        return False
    return True

# --- Dictionary Logic ---
# (load_dictionary and save_dictionary remain the same)
def load_dictionary(filepath):
    if not filepath or not os.path.exists(filepath): return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception as e:
        wx.LogError(f"Error loading dictionary {filepath}: {e}")
        return {}

def save_dictionary(filepath, dictionary_data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f: json.dump(dictionary_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        wx.LogError(f"Error saving dictionary {filepath}: {e}")
        return False

# --- Main Frame ---

class FTLFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title=APP_NAME, size=(900, 700))

        self.current_file_path = None
        self.original_lines_structure = []
        self.original_translations = OrderedDict()
        self.current_translations = OrderedDict()
        self.display_to_key_map = {}
        self.is_modified = False
        self.selected_key = None
        self.target_language = "Unknown"

        self.dictionary_path = None
        self.dictionary_data = {}

        # --- UI Elements ---
        self.panel = wx.Panel(self)
        self.splitter = wx.SplitterWindow(self.panel, style=wx.SP_LIVE_UPDATE | wx.SP_3D)

        # Left Panel
        self.left_panel = wx.Panel(self.splitter)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        self.list_label = wx.StaticText(self.left_panel, label="Translatable Keys:")
        self.keys_listbox = wx.ListBox(self.left_panel, style=wx.LB_SINGLE | wx.LB_NEEDED_SB) # Manual sort
        left_sizer.Add(self.list_label, 0, wx.ALL | wx.EXPAND, 5)
        left_sizer.Add(self.keys_listbox, 1, wx.ALL | wx.EXPAND, 5)
        self.left_panel.SetSizer(left_sizer)
        accessible_list = self.keys_listbox.GetAccessible()
        if accessible_list:
            accessible_list.SetName(self.list_label.GetLabel() + " list box. Items include a status like (done) or (not translated).")

        # Right Panel
        self.right_panel = wx.Panel(self.splitter)
        right_sizer = wx.GridBagSizer(5, 5)

        # Row 0: Key
        self.key_label = wx.StaticText(self.right_panel, label="Selected Key:")
        self.key_text = wx.TextCtrl(self.right_panel, style=wx.TE_READONLY | wx.BORDER_STATIC)
        accessible_key_text = self.key_text.GetAccessible()
        if accessible_key_text: accessible_key_text.SetName(self.key_label.GetLabel() + " read only text")
        right_sizer.Add(self.key_label, pos=(0, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=5)
        right_sizer.Add(self.key_text, pos=(0, 1), span=(1, 2), flag=wx.EXPAND | wx.ALL, border=5)

        # Row 1: Original Value
        self.original_label = wx.StaticText(self.right_panel, label="Original Value:")
        self.original_text = wx.TextCtrl(self.right_panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_PROCESS_TAB | wx.BORDER_SUNKEN)
        accessible_original_text = self.original_text.GetAccessible()
        if accessible_original_text: accessible_original_text.SetName(self.original_label.GetLabel() + " read only text area")
        right_sizer.Add(self.original_label, pos=(1, 0), flag=wx.ALIGN_TOP | wx.ALL, border=5)
        right_sizer.Add(self.original_text, pos=(1, 1), span=(1, 2), flag=wx.EXPAND | wx.ALL, border=5)

        # Row 2: Translation
        self.translation_label = wx.StaticText(self.right_panel, label="Translation:")
        self.translation_text = wx.TextCtrl(self.right_panel, style=wx.TE_MULTILINE | wx.TE_PROCESS_TAB | wx.BORDER_SUNKEN)
        accessible_translation_text = self.translation_text.GetAccessible()
        if accessible_translation_text: accessible_translation_text.SetName(self.translation_label.GetLabel() + " edit area")
        right_sizer.Add(self.translation_label, pos=(2, 0), flag=wx.ALIGN_TOP | wx.ALL, border=5)
        right_sizer.Add(self.translation_text, pos=(2, 1), span=(1, 2), flag=wx.EXPAND | wx.ALL, border=5)

        # Row 3: Status Label
        self.status_label = wx.StaticText(self.right_panel, label="Status: No file loaded.")
        right_sizer.Add(self.status_label, pos=(3, 0), span=(1, 3), flag=wx.EXPAND | wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        # Row 4: Buttons (Only Lookup remains)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.lookup_button = wx.Button(self.right_panel, label="Lookup in Dictionary")
        button_sizer.Add(self.lookup_button, 0, wx.ALL, 5)
        right_sizer.Add(button_sizer, pos=(4, 0), span=(1, 3), flag=wx.ALIGN_LEFT | wx.ALL, border=0)

        # Sizer growth rules
        right_sizer.AddGrowableRow(1); right_sizer.AddGrowableRow(2)
        right_sizer.AddGrowableCol(1);

        self.right_panel.SetSizer(right_sizer)

        # Setup Splitter
        self.splitter.SplitVertically(self.left_panel, self.right_panel, 350)
        self.splitter.SetMinimumPaneSize(200)

        # Main Sizer
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.splitter, 1, wx.EXPAND)
        self.panel.SetSizer(sizer)

        # --- Menu Bar ---
        self.menubar = wx.MenuBar()
        # File Menu
        self.file_menu = wx.Menu()
        self.menu_new = self.file_menu.Append(wx.ID_NEW, "&New\tCtrl+N"); self.menu_open = self.file_menu.Append(wx.ID_OPEN, "&Open...\tCtrl+O")
        self.menu_save = self.file_menu.Append(wx.ID_SAVE, "&Save\tCtrl+S"); self.menu_save_as = self.file_menu.Append(wx.ID_SAVEAS, "Save &As...")
        self.file_menu.AppendSeparator()
        self.recent_files_menu = wx.Menu(); self.file_history = wx.FileHistory(MAX_RECENT_FILES); self.file_history.UseMenu(self.recent_files_menu)
        self.Bind(wx.EVT_MENU_RANGE, self.OnRecentFile, id=wx.ID_FILE1, id2=wx.ID_FILE9)
        self.file_menu.AppendSubMenu(self.recent_files_menu, "&Recent Files"); self.file_menu.AppendSeparator()
        self.menu_exit = self.file_menu.Append(wx.ID_EXIT, "&Exit\tAlt+F4"); self.menubar.Append(self.file_menu, "&File")
        # Language Menu
        self.lang_menu = wx.Menu(); self.menu_set_lang = self.lang_menu.Append(wx.ID_ANY, "Set Target &Language...")
        self.menubar.Append(self.lang_menu, "&Language")
        # Dictionary Menu
        self.dict_menu = wx.Menu(); self.menu_dict_load = self.dict_menu.Append(wx.ID_ANY, "&Load Dictionary...")
        self.menu_dict_save = self.dict_menu.Append(wx.ID_ANY, "&Save Dictionary"); self.menu_dict_save_as = self.dict_menu.Append(wx.ID_ANY, "Save Dictionary &As...")
        self.dict_menu.AppendSeparator(); self.menu_dict_add = self.dict_menu.Append(wx.ID_ANY, "&Add Term to Dictionary...")
        self.menubar.Append(self.dict_menu, "&Dictionary")
        self.SetMenuBar(self.menubar)

        # --- Status Bar ---
        self.statusbar = self.CreateStatusBar(3)
        self.statusbar.SetStatusWidths([-3, -1, -1])
        self.UpdateStatusBar()

        # --- Accelerator Table ---
        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('N'), wx.ID_NEW), (wx.ACCEL_CTRL, ord('O'), wx.ID_OPEN),
            (wx.ACCEL_CTRL, ord('S'), wx.ID_SAVE), (wx.ACCEL_ALT, wx.WXK_F4, wx.ID_EXIT),
        ])
        self.SetAcceleratorTable(accel_tbl)

        # --- Event Bindings ---
        # File Menu
        self.Bind(wx.EVT_MENU, self.OnNewFile, id=wx.ID_NEW); self.Bind(wx.EVT_MENU, self.OnFileOpen, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self.OnFileSave, id=wx.ID_SAVE); self.Bind(wx.EVT_MENU, self.OnFileSaveAs, id=wx.ID_SAVEAS)
        self.Bind(wx.EVT_MENU, self.OnExit, id=wx.ID_EXIT); self.Bind(wx.EVT_CLOSE, self.OnExit)
        # Language Menu
        self.Bind(wx.EVT_MENU, self.OnSetLanguage, self.menu_set_lang)
        # Dictionary Menu
        self.Bind(wx.EVT_MENU, self.OnDictLoad, self.menu_dict_load); self.Bind(wx.EVT_MENU, self.OnDictSave, self.menu_dict_save)
        self.Bind(wx.EVT_MENU, self.OnDictSaveAs, self.menu_dict_save_as); self.Bind(wx.EVT_MENU, self.OnDictAddTerm, self.menu_dict_add)
        # UI Elements
        self.keys_listbox.Bind(wx.EVT_LISTBOX, self.OnKeySelected)
        self.translation_text.Bind(wx.EVT_TEXT, self.OnTranslationChanged) # Will handle dynamic updates
        self.lookup_button.Bind(wx.EVT_BUTTON, self.OnLookupDictionaryAction)
        # KeyDown Handlers
        self.original_text.Bind(wx.EVT_KEY_DOWN, self.OnEditorKeyDown)
        self.translation_text.Bind(wx.EVT_KEY_DOWN, self.OnEditorKeyDown)
        self.keys_listbox.Bind(wx.EVT_KEY_DOWN, self.OnKeysListKeyDown)
        # Context Menu Binding
        self.keys_listbox.Bind(wx.EVT_CONTEXT_MENU, self.OnListContextMenu)
        self.Bind(wx.EVT_MENU, self.OnLookupFromContext, id=ID_CONTEXT_LOOKUP)

        # Initial state
        self.EnableEditing(False)
        self.menu_save.Enable(False); self.menu_save_as.Enable(False)
        self.menu_dict_save.Enable(False); self.menu_dict_save_as.Enable(False)
        self.menu_dict_add.Enable(False); self.lookup_button.Enable(False)

        # Load file history
        self.config = wx.Config(APP_NAME)
        self.file_history.Load(self.config)

        self.Center()
        self.Show()


    # --- Event Handlers ---

    def OnNewFile(self, event):
        if self.CheckUnsavedChanges():
            self.current_file_path = None; self.original_lines_structure = [('comment', '# New FTL File\n'), ('blank', '\n')]
            self.original_translations = OrderedDict(); self.current_translations = OrderedDict(); self.display_to_key_map = {}
            self.is_modified = False; self.selected_key = None
            self.LoadDataIntoUI(); self.SetTitle(f"{APP_NAME} - Untitled"); self.UpdateStatusBar()
            self.EnableEditing(False); self.keys_listbox.Enable(False); self.menu_save.Enable(False); self.menu_save_as.Enable(True)
            wx.LogStatus("Created a new empty FTL structure. Use 'Save As'.")


    def OnFileOpen(self, event):
        if not self.CheckUnsavedChanges(): return
        wildcard = "FTL files (*.ftl)|*.ftl|All files (*.*)|*.*"
        dlg = wx.FileDialog(self, "Open FTL file", wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_CANCEL: dlg.Destroy(); return
        filepath = dlg.GetPath(); dlg.Destroy(); self.LoadFTLFile(filepath)

    def OnRecentFile(self, event):
        if not self.CheckUnsavedChanges(): return
        file_index = event.GetId() - wx.ID_FILE1; filepath = self.file_history.GetHistoryFile(file_index)
        if filepath and os.path.exists(filepath): self.LoadFTLFile(filepath)
        else:
            wx.LogError(f"Recent file not found or inaccessible: {filepath}"); self.file_history.RemoveFileFromHistory(file_index); self.file_history.Save(self.config)


    def LoadFTLFile(self, filepath):
        wx.BeginBusyCursor()
        lines_structure, translations = parse_ftl(filepath)
        wx.EndBusyCursor()
        if lines_structure is not None and translations is not None:
            self.current_file_path = filepath; self.original_lines_structure = lines_structure
            self.original_translations = translations.copy(); self.current_translations = translations
            self.is_modified = False; self.selected_key = None
            self.LoadDataIntoUI()
            self.SetTitle(f"{APP_NAME} - {os.path.basename(filepath)}"); self.UpdateStatusBar()
            self.keys_listbox.Enable(True); self.EnableEditing(False, enable_list=True)
            self.menu_save.Enable(False); self.menu_save_as.Enable(True)
            self.file_history.AddFileToHistory(filepath); self.file_history.Save(self.config)
            wx.LogStatus(f"Loaded {len(translations)} keys from {filepath}")
        else:
            self.current_file_path = None; self.original_lines_structure = []; self.original_translations = OrderedDict()
            self.current_translations = OrderedDict(); self.display_to_key_map = {}; self.is_modified = False; self.selected_key = None
            self.LoadDataIntoUI(); self.SetTitle(APP_NAME); self.UpdateStatusBar(); self.EnableEditing(False)


    def OnFileSave(self, event):
        if not self.current_file_path: self.OnFileSaveAs(event)
        elif self.is_modified:
            wx.BeginBusyCursor(); save_successful = save_ftl(self.current_file_path, self.original_lines_structure, self.current_translations); wx.EndBusyCursor()
            if save_successful:
                self.is_modified = False; self.original_translations = self.current_translations.copy(); title = self.GetTitle()
                if title.endswith('*'): self.SetTitle(title[:-1])
                self.UpdateStatusBar(); self.menu_save.Enable(False)
                self.LoadDataIntoUI() # Refresh list
                wx.LogStatus(f"File saved: {self.current_file_path}")
            else: wx.LogError(f"Failed to save file: {self.current_file_path}")
        else: wx.LogStatus("No changes to save.")


    def OnFileSaveAs(self, event):
        if not self.current_translations and not self.original_lines_structure: wx.LogWarning("Nothing to save."); return
        wildcard = "FTL files (*.ftl)|*.ftl|All files (*.*)|*.*"
        dlg = wx.FileDialog(self, "Save FTL file As", wildcard=wildcard, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        default_dir = os.path.dirname(self.current_file_path) if self.current_file_path else ""
        default_file = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled.ftl"
        dlg.SetDirectory(default_dir); dlg.SetFilename(default_file)
        if dlg.ShowModal() == wx.ID_CANCEL: dlg.Destroy(); return
        filepath = dlg.GetPath(); _, ext = os.path.splitext(filepath);
        if not ext: filepath += ".ftl";
        dlg.Destroy()
        wx.BeginBusyCursor(); save_successful = save_ftl(filepath, self.original_lines_structure, self.current_translations); wx.EndBusyCursor()
        if save_successful:
            self.current_file_path = filepath; self.is_modified = False; self.original_translations = self.current_translations.copy()
            self.SetTitle(f"{APP_NAME} - {os.path.basename(self.current_file_path)}"); self.UpdateStatusBar()
            self.menu_save.Enable(False); self.file_history.AddFileToHistory(filepath); self.file_history.Save(self.config)
            self.LoadDataIntoUI() # Refresh list
            wx.LogStatus(f"File saved successfully as {filepath}")
        else: wx.LogError(f"Failed to save file as: {filepath}")


    def OnSetLanguage(self, event):
        dlg = wx.TextEntryDialog(self, "Enter the target language name:", "Set Target Language", self.target_language)
        if dlg.ShowModal() == wx.ID_OK:
            self.target_language = dlg.GetValue().strip();
            if not self.target_language: self.target_language = "Unknown"
            self.UpdateStatusBar()
        dlg.Destroy()

    def OnDictLoad(self, event):
        wildcard = "JSON dictionary files (*.json)|*.json|All files (*.*)|*.*"
        dlg = wx.FileDialog(self, "Load Dictionary file", wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_CANCEL: dlg.Destroy(); return
        filepath = dlg.GetPath(); dlg.Destroy(); wx.BeginBusyCursor()
        loaded_dict = load_dictionary(filepath); wx.EndBusyCursor()
        if loaded_dict is not None:
            self.dictionary_path = filepath; self.dictionary_data = loaded_dict
            self.menu_dict_save.Enable(True); self.menu_dict_save_as.Enable(True)
            self.lookup_button.Enable(self.selected_key is not None and bool(self.dictionary_data))
            wx.LogStatus(f"Dictionary loaded from {filepath} with {len(self.dictionary_data)} terms.")


    def OnDictSave(self, event):
        if not self.dictionary_path: self.OnDictSaveAs(event)
        elif self.dictionary_data is not None:
            wx.BeginBusyCursor();
            if save_dictionary(self.dictionary_path, self.dictionary_data): wx.LogStatus(f"Dictionary saved to {self.dictionary_path}")
            wx.EndBusyCursor()

    def OnDictSaveAs(self, event):
        if self.dictionary_data is None or not self.dictionary_data: wx.LogWarning("No dictionary data to save."); return
        wildcard = "JSON dictionary files (*.json)|*.json|All files (*.*)|*.*"
        dlg = wx.FileDialog(self, "Save Dictionary As", wildcard=wildcard, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        default_file = "dictionary.json"; default_dir = ""
        if self.dictionary_path: default_dir = os.path.dirname(self.dictionary_path); default_file = os.path.basename(self.dictionary_path)
        dlg.SetDirectory(default_dir); dlg.SetFilename(default_file)
        if dlg.ShowModal() == wx.ID_CANCEL: dlg.Destroy(); return
        filepath = dlg.GetPath(); _, ext = os.path.splitext(filepath);
        if not ext: filepath += ".json" # Semicolon removed
        dlg.Destroy() # Destroy before save
        wx.BeginBusyCursor();
        if save_dictionary(filepath, self.dictionary_data):
            self.dictionary_path = filepath; self.menu_dict_save.Enable(True)
            wx.LogStatus(f"Dictionary saved to {filepath}")
        wx.EndBusyCursor()

    def OnDictAddTerm(self, event):
        key = self.selected_key;
        if not key: wx.LogWarning("No key selected to add to dictionary."); return
        translation = self.translation_text.GetValue().strip(); original = self.original_text.GetValue().strip()
        if not original: wx.LogWarning("Cannot add term with empty Original Value as source."); return
        if not translation: wx.LogWarning("Cannot add term with empty Translation field."); return
        dlg = wx.Dialog(self, title="Add Dictionary Term"); sizer = wx.BoxSizer(wx.VERTICAL); gs = wx.GridSizer(2, 2, 5, 5)
        gs.Add(wx.StaticText(dlg, label="Source Term:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5); source_ctrl = wx.TextCtrl(dlg, value=original, size=(350, -1)); gs.Add(source_ctrl, 1, wx.EXPAND|wx.ALL, 5)
        gs.Add(wx.StaticText(dlg, label="Translation Term:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5); trans_ctrl = wx.TextCtrl(dlg, value=translation, size=(350,-1)); gs.Add(trans_ctrl, 1, wx.EXPAND|wx.ALL, 5)
        sizer.Add(gs, 1, wx.EXPAND|wx.ALL, 5); btn_sizer = dlg.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL); sizer.Add(btn_sizer, 0, wx.CENTER|wx.ALL, 10)
        dlg.SetSizerAndFit(sizer); trans_ctrl.SetFocus(); trans_ctrl.SelectAll()
        if dlg.ShowModal() == wx.ID_OK:
            source_term = source_ctrl.GetValue().strip(); trans_term = trans_ctrl.GetValue().strip()
            if source_term and trans_term:
                self.dictionary_data[source_term] = trans_term; wx.LogStatus(f"Term '{source_term}' added/updated in dictionary.")
                if self.dictionary_data: self.menu_dict_save_as.Enable(True);
                if self.dictionary_path: self.menu_dict_save.Enable(True)
            else: wx.LogWarning("Cannot add empty source or translation term.")
        dlg.Destroy()

    def OnLookupDictionaryAction(self, event=None):
        if not self.dictionary_data: wx.LogWarning("No dictionary loaded."); return
        if not self.selected_key: wx.LogWarning("No key selected for dictionary lookup."); return

        selected_text = self.original_text.GetStringSelection().strip()
        term_to_lookup = ""
        if selected_text: term_to_lookup = selected_text
        else: term_to_lookup = self.original_text.GetValue().strip()

        if not term_to_lookup: wx.LogStatus("Nothing to look up (select text in 'Original Value' or ensure it's not empty)."); return

        translation = self.dictionary_data.get(term_to_lookup)
        if translation:
            dlg = wx.MessageDialog(self, f"Dictionary Result for '{term_to_lookup}':\n\n{translation}\n\nInsert into Translation field?",
                                   "Dictionary Lookup", wx.YES_NO | wx.ICON_INFORMATION | wx.CENTRE)
            if dlg.ShowModal() == wx.ID_YES: self.translation_text.SetValue(translation)
            dlg.Destroy()
        else: wx.MessageBox(f"Term '{term_to_lookup}' not found in the dictionary.", "Dictionary Lookup", wx.OK | wx.ICON_WARNING, self)

    # OnCheckStatus removed

    def OnKeySelected(self, event):
        selection_index = self.keys_listbox.GetSelection()
        if selection_index == wx.NOT_FOUND:
            self.selected_key = None; self.ClearEditFields(); self.EnableEditing(False, enable_list=True); return

        display_string = self.keys_listbox.GetString(selection_index)
        actual_key = self.display_to_key_map.get(display_string)

        if actual_key is None:
             wx.LogError(f"Error: Could not map display string '{display_string}' back to an FTL key.")
             self.selected_key = None; self.ClearEditFields(); self.EnableEditing(False, enable_list=True); return

        self.selected_key = actual_key
        focus_before_event = wx.Window.FindFocus()

        if self.selected_key in self.current_translations:
            current_val = self.current_translations.get(self.selected_key, "")
            original_val = self.original_translations.get(self.selected_key, "")
            self.key_text.SetValue(self.selected_key)
            self.original_text.SetValue(original_val)
            self.translation_text.ChangeValue(current_val)
            self.EnableEditing(True)
            self.UpdateStatusLabel() # Updates detail label and button states
            if focus_before_event != self.keys_listbox: wx.CallAfter(self.translation_text.SetFocus)
        else:
            wx.LogError(f"Selected key '{self.selected_key}' not found in internal data despite being mapped.")
            self.ClearEditFields(); self.EnableEditing(False, enable_list=True)


    # --- MODIFIED: Handles dynamic list update on status change ---
    def OnTranslationChanged(self, event):
        if self.selected_key is None or self.selected_key not in self.current_translations: return

        # 1. Get status BEFORE change
        old_status = self._get_item_status(self.selected_key)

        # 2. Update internal data and modified flag
        current_textbox_value = self.translation_text.GetValue()
        stored_value = self.current_translations.get(self.selected_key, "")
        if current_textbox_value != stored_value:
             self.current_translations[self.selected_key] = current_textbox_value
             if not self.is_modified:
                self.is_modified = True; title = self.GetTitle()
                if not title.endswith('*'): self.SetTitle(title + '*'); self.menu_save.Enable(True)

             # 3. Update the detailed status label immediately
             self.UpdateStatusLabel()

             # 4. Get status AFTER change
             new_status = self._get_item_status(self.selected_key)

             # 5. If status code changed, refresh the listbox
             if old_status != new_status:
                 # Use CallAfter to defer the list update slightly,
                 # allowing the current text event processing to complete.
                 # This can sometimes prevent focus issues or crashes.
                 wx.CallAfter(self.LoadDataIntoUI)
                 # Note: LoadDataIntoUI will handle resorting and selection restoration

        # No need to call event.Skip(), TextCtrl handles propagation


    def OnEditorKeyDown(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_ESCAPE:
            if self.keys_listbox and self.keys_listbox.IsEnabled() and self.keys_listbox.GetCount() > 0:
                 self.keys_listbox.SetFocus(); current_selection = self.keys_listbox.GetSelection()
                 if current_selection != wx.NOT_FOUND: wx.CallAfter(self.keys_listbox.EnsureVisible, current_selection)
        else: event.Skip()


    def OnKeysListKeyDown(self, event):
        event.Skip()


    # --- Context Menu Handlers ---
    def OnListContextMenu(self, event):
        pos = event.GetPosition(); selected_index = self.keys_listbox.GetSelection()
        if selected_index == wx.NOT_FOUND: return

        current_display_string = self.keys_listbox.GetString(selected_index)
        current_actual_key = self.display_to_key_map.get(current_display_string)
        if current_actual_key != self.selected_key:
             self.keys_listbox.SetSelection(selected_index)
             self.OnKeySelected(None)

        if not self.selected_key: return

        menu = wx.Menu()
        lookup_item = menu.Append(ID_CONTEXT_LOOKUP, "Lookup in Dictionary")
        # Check status item removed
        lookup_item.Enable(bool(self.dictionary_data) and bool(self.selected_key))
        self.PopupMenu(menu, pos); menu.Destroy()

    def OnLookupFromContext(self, event):
        self.OnLookupDictionaryAction(event)

    # OnCheckStatusFromContext removed

    def OnExit(self, event):
        if self.CheckUnsavedChanges():
            if hasattr(self, 'config') and self.config: self.file_history.Save(self.config)
            self.Destroy()


    # --- Helper Methods ---

    def _get_item_status(self, key):
        # (Same as before)
        if key not in self.current_translations or key not in self.original_translations: return STATUS_OK
        current_value = self.current_translations.get(key, ""); original_value = self.original_translations.get(key, "")
        if not current_value.strip(): return STATUS_UNTRANSLATED
        if self._check_punctuation_error(original_value, current_value): return STATUS_ERROR_PUNCTUATION
        return STATUS_OK

    def _check_punctuation_error(self, original_str, translated_str):
        # (Same as before)
        orig_stripped = original_str.rstrip(); trans_stripped = translated_str.rstrip()
        orig_punct = None; trans_punct = None
        if orig_stripped and orig_stripped[-1] in PUNCTUATION_CHARS: orig_punct = orig_stripped[-1]
        if trans_stripped and trans_stripped[-1] in PUNCTUATION_CHARS: trans_punct = trans_stripped[-1]
        if (orig_punct and not trans_punct) or (not orig_punct and trans_punct) or (orig_punct and trans_punct and orig_punct != trans_punct): return True
        else: return False

    def CheckUnsavedChanges(self):
        # (Same as before)
        if not self.is_modified: return True
        filename = os.path.basename(self.current_file_path or 'Untitled')
        dlg = wx.MessageDialog(self, f"File '{filename}' has unsaved changes.\nDo you want to save them?",
                               "Unsaved Changes", wx.YES_NO | wx.CANCEL | wx.ICON_WARNING | wx.CENTRE)
        result = dlg.ShowModal(); dlg.Destroy()
        if result == wx.ID_YES:
            save_success = False
            if not self.current_file_path:
                 temp_path = self.current_file_path; self.OnFileSaveAs(None); save_success = (self.current_file_path != temp_path or not self.is_modified)
            else:
                 self.OnFileSave(None); save_success = not self.is_modified
            return save_success
        elif result == wx.ID_NO: return True
        else: return False


    # --- MODIFIED: Handles sorting and status suffixes ---
    def LoadDataIntoUI(self):
        """Populates the listbox with sorted, suffixed items and clears edit fields."""
        self.keys_listbox.Freeze()
        # Store current selection index/key to restore *precisely* if possible
        old_selection_index = self.keys_listbox.GetSelection()
        old_selected_display_string = None
        if old_selection_index != wx.NOT_FOUND:
            old_selected_display_string = self.keys_listbox.GetString(old_selection_index)
        old_key_to_restore = self.selected_key # Use the internal key state

        self.keys_listbox.Clear()
        self.display_to_key_map.clear()

        items_to_sort = []
        if self.current_translations:
            for key in self.current_translations.keys():
                status = self._get_item_status(key)
                base_suffix = STATUS_SUFFIX.get(status, "")
                detailed_suffix = base_suffix
                # Add detail for punctuation errors specifically
                if status == STATUS_ERROR_PUNCTUATION:
                    detail = self._get_punctuation_mismatch_detail(
                        self.original_translations.get(key, ""),
                        self.current_translations.get(key, "")
                    )
                    if detail: detailed_suffix = f" (error: {detail.strip('()')})"

                display_text = key + detailed_suffix
                items_to_sort.append({'status': status, 'key': key, 'display': display_text})

            # Sort by status (primary) and key (secondary)
            sorted_items = sorted(items_to_sort, key=lambda item: (item['status'], item['key']))

            # Populate listbox and map
            for item in sorted_items:
                self.keys_listbox.Append(item['display'])
                self.display_to_key_map[item['display']] = item['key']

        self.keys_listbox.Thaw()

        # --- Refined Selection Restoration ---
        restored_selection = False
        if old_key_to_restore: # Try to restore based on the key that *was* selected
            new_display_text = None
            try:
                # Find the *new* display text for the key that was selected
                status = self._get_item_status(old_key_to_restore)
                base_suffix = STATUS_SUFFIX.get(status, "")
                detailed_suffix = base_suffix
                if status == STATUS_ERROR_PUNCTUATION:
                    detail = self._get_punctuation_mismatch_detail(self.original_translations.get(old_key_to_restore, ""), self.current_translations.get(old_key_to_restore, ""))
                    if detail: detailed_suffix = f" (error: {detail.strip('()')})"
                potential_display_text = old_key_to_restore + detailed_suffix

                # Check if this exact string exists in the *new* listbox content (via map keys)
                if potential_display_text in self.display_to_key_map:
                     new_display_text = potential_display_text

                if new_display_text:
                    idx = self.keys_listbox.FindString(new_display_text)
                    if idx != wx.NOT_FOUND:
                        self.keys_listbox.SetSelection(idx)
                        self.keys_listbox.EnsureVisible(idx)
                        # Fields should already be populated correctly if selected_key is set
                        # Avoid calling OnKeySelected here as it might cause loops/focus issues during refresh
                        restored_selection = True
            except Exception as e:
                wx.LogError(f"Error finding/restoring selection for '{old_key_to_restore}': {e}")

        # Clear fields only if no selection was restored
        if not restored_selection:
             self.ClearEditFields()
             self.selected_key = None # Clear key if selection couldn't be restored
        else:
             # Ensure buttons are updated based on restored selection
             self.UpdateStatusLabel() # Refresh right-panel status/buttons

        self.UpdateStatusBar()


    def ClearEditFields(self):
        self.key_text.ChangeValue(""); self.original_text.ChangeValue(""); self.translation_text.ChangeValue("")
        self.status_label.SetLabel("Status: Select a key from the list.")
        self.menu_dict_add.Enable(False)
        self.lookup_button.Enable(False)


    def EnableEditing(self, enable, enable_list=None):
        # --- MODIFIED: Removed check_status_button ---
        self.translation_text.Enable(enable)
        self.status_label.Enable(enable) # Always show status
        item_selected = (self.selected_key is not None)
        dict_loaded = bool(self.dictionary_data)
        # Lookup button depends on item selected AND dictionary loaded
        self.lookup_button.Enable(enable and item_selected and dict_loaded)

        if enable_list is not None: self.keys_listbox.Enable(enable_list)
        # Add dictionary term menu item depends on item selected
        self.menu_dict_add.Enable(enable and item_selected)


    def UpdateStatusBar(self):
        path_str = self.current_file_path or "No file loaded"; lang_str = f"Lang: {self.target_language}"; mod_str = " *" if self.is_modified else ""
        self.statusbar.SetStatusText(f"{path_str}{mod_str}", 0); self.statusbar.SetStatusText(lang_str, 1)
        key_count = len(self.current_translations); self.statusbar.SetStatusText(f"Keys: {key_count}", 2)


    def UpdateStatusLabel(self):
        # --- MODIFIED: Removed button enabling ---
        if self.selected_key is None:
            self.status_label.SetLabel("Status: Select a key from the list.")
            self.menu_dict_add.Enable(False); self.lookup_button.Enable(False)
            return
        current_value = self.current_translations.get(self.selected_key, ""); original_value = self.original_translations.get(self.selected_key, "")
        status = self._get_item_status(self.selected_key); status_text = STATUS_DESC.get(status, "Status: Unknown")
        if status == STATUS_ERROR_PUNCTUATION:
            punct_detail = self._get_punctuation_mismatch_detail(original_value, current_value)
            if punct_detail: status_text += f" {punct_detail}"
        self.status_label.SetLabel(status_text)
        # Update button/menu states
        can_edit = self.translation_text.IsEnabled()
        dict_loaded = bool(self.dictionary_data)
        self.menu_dict_add.Enable(can_edit and self.selected_key is not None)
        self.lookup_button.Enable(can_edit and self.selected_key is not None and dict_loaded)


    def _get_punctuation_mismatch_detail(self, original_str, translated_str):
        orig_stripped = original_str.rstrip(); trans_stripped = translated_str.rstrip(); orig_punct = None; trans_punct = None
        if orig_stripped and orig_stripped[-1] in PUNCTUATION_CHARS: orig_punct = orig_stripped[-1]
        if trans_stripped and trans_stripped[-1] in PUNCTUATION_CHARS: trans_punct = trans_stripped[-1]
        if orig_punct and not trans_punct: return f"(Expected trailing '{orig_punct}', Found none)"
        elif not orig_punct and trans_punct: return f"(Expected no trailing punctuation, Found '{trans_punct}')"
        elif orig_punct and trans_punct and orig_punct != trans_punct: return f"(Expected trailing '{orig_punct}', Found '{trans_punct}')"
        else: return None


# --- Application Entry Point ---
if __name__ == '__main__':
    app = wx.App(False)
    app.SetAppName(APP_NAME)
    frame = FTLFrame()
    app.MainLoop()