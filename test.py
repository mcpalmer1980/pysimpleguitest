import PySimpleGUI as sg
import os, time

def browser(
        mode = 'files', # file, folder, files
        path = None,  # starting path
        title = None,
        default = None, # value returned on cancel
        input = False, # allow string input
        types = None ): # filter extensions

    path = path or os.getenv('HOME') or '/'
    mode = mode if mode in ('file', 'files', 'folder') else 'file'
    listmode = 'multiple' if mode == 'files' else 'browse'
    title = title or dict(file='Select File', folder='Select Folder', files='Select File(s)')[mode]
    PATH_LENGTH = 60
    BOX_HEIGHT = 15
    def get_listing(path, window=None):
        folders = []; files = []
        path = os.path.normpath(path)
        for f in sorted(os.listdir(path), key=lambda x:x.lower()):
            p = os.path.join(path, f)
            if os.path.isdir(p):
                folders.append(os.sep+f)
            else:
                if mode == 'folder':
                    files.append('  '+f)
                else: files.append(f)

        p = path
        parents = [path[-PATH_LENGTH:]]
        while True:
            p = os.path.normpath(os.path.join(p, '..'))
            parents.append(p[-PATH_LENGTH:])
            if p == os.sep or p[1:].startswith(':\\'):
                break
        items = folders+files
        window['LIST'].update(items)
        window['PARENTS'].update(parents[0] or os.sep, values=parents[1:])

        items = folders if mode == 'folder' else items
        return items, parents

    layout = [[sg.Combo([], size=PATH_LENGTH, readonly=True, key='PARENTS',
                    enable_events=True, bind_return_key=True),
                sg.Push(), sg.Button('\u21e7', key='UP')],
            [sg.Listbox([], size = (PATH_LENGTH+5, BOX_HEIGHT), select_mode=listmode,
                    key='LIST', enable_events=True, bind_return_key=True)]]
            
    if input:
        layout += [[sg.Input(key='TEXT', expand_x=True)]]
    layout += [[sg.Push(), sg.Button('Cancel'), sg.Button('Okay')]]
    window = sg.Window(title, layout, modal=True,
            finalize=True, return_keyboard_events=True)
    scroller = get_key_selector(window, window['LIST'])

    items, parents = get_listing(path, window)
    window['LIST'].set_focus()
    selected = full_path = None
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Cancel'):
            window.close()
            return default
        elif event == 'UP' or (event.startswith('BackSpace') and
                window.find_element_with_focus() == window['LIST']):
            path = os.path.normpath(os.path.join(path, '..'))
            items, parents = get_listing(path, window)
            window['LIST'].set_focus()
        elif event == 'PARENTS':
            v = values[event]
            if v in parents:
                index = parents.index(v)
                for _ in range(index):
                    path = os.path.normpath(os.path.join(path, '..'))
            elif os.path.isdir(v):
                path = v
            else:
                path = path
            items, parents = get_listing(path, window)
            selected = None
            window['LIST'].set_focus()
        elif event == 'LIST':
            if values[event] and len(values[event]) == 1:
                clicked = values[event][0]
                if clicked == selected:
                    if clicked.startswith('/'):
                        p = os.path.join(path, values[event][0][1:])
                        if os.path.isdir(p):
                            path = p
                        items, parents = get_listing(path, window)
                        selected = None
                selected = clicked
            else:
                selected = None
            print(selected, values[event])
        elif event == 'Okay':
            if input:
                window.close()
                return values['TEXT']
            elif mode == 'file' and os.path.isfile(full_path):
                print('isfile')
                window.close()
                return full_path
            elif mode == 'folder' and os.path.isdir(full_path):
                window.close()
                return full_path
            elif mode == 'files':
                if window['LIST'].get():
                    sel = [os.path.join(path, i) for i in window['LIST'].get()
                            if os.path.isfile(os.path.join(path, i))]
                    if sel:
                        window.close()
                        return sel

        elif scroller(event, items):
            selected = scroller.selected
        else:
            print(event)
            continue
            
        full_path = os.path.join(path, selected.lstrip(os.sep)) if selected else path
        if input:
            window['TEXT'].update(full_path)

    window.close()


def get_key_selector(window, element):
    def scroll_to_index(event, data, col=None):
        nonlocal last_press, keys_pressed, skipped, exact, hits
        ti = time.perf_counter()
        skip = False

        # scroll through matches with UP/DOWN if filter hasn't timed out
        if ti - last_press < KEY_DELAY:
            if event.startswith('Down'):
                skipped = (skipped + 1) % hits if hits else 0
                skip = True
            if event.startswith('Up'):
                skipped = (skipped - 1) % hits if hits else 0
                skip = True

        # update match string if proper key pressed before timeout
        hits = foundin = 0
        if (len(event)==1 or event[1]==':' or event.split(':')[0] in conv or skip) and (
                window.find_element_with_focus() == element and data):
            if skip: # don't update match string if up/down pressed
                pass
            else:
                c = conv.get(event.split(':')[0], event[0]).lower()
                if ti - last_press < KEY_DELAY:
                    keys_pressed += c
                elif c == ' ':
                    return
                else:
                    skipped = exact = 0
                    if c == '=':
                        exact = True
                        keys_pressed = ''
                    else:
                        keys_pressed = c

            # loop across file list
            last_press = ti + KEY_DELAY if exact else ti
            items = (r[col].lower() for r in data) if col is not None else (d.lower() for d in data)
            for i, item in enumerate(items):
                if item.startswith(keys_pressed) and not exact:
                    if skip: return
                    break
                elif keys_pressed in item and len(keys_pressed) > 1:
                    if not foundin and hits == skipped:
                        foundin = i
                    hits += 1

            else: 
                i = foundin
                if not foundin:
                    scroll_to_index.selected = None
                    return

            # select found item depending on widget type
            if isinstance(element, sg.Table):
                element.update(select_rows=[i])
                element.TKTreeview.focus(i+1)
                element.TKTreeview.see(i+1)
            elif isinstance(element, sg.Listbox):
                if element.SelectMode != 'multiple':
                    element.update(set_to_index=i)
                element.TKListbox.see(i)
                element.TKListbox.activate(i)
            else:
                perc = i / len(data)
                element.set_vscroll_position(perc)

            scroll_to_index.selected = data[i]
            return i
    KEY_DELAY = 1
    keys_pressed = ''
    last_press = skipped = exact = hits = 0
    conv = {'slash': '/', 'period': '.', 'space': ' ', 'equal': '='}
    return scroll_to_index


import tkinter as tk
class BrowseButton(sg.Button):
    def __init__(self, mode, path=None):
        super().__init__(button_text='Browse', button_type=sg.BUTTON_TYPE_BROWSE_FOLDER, target=(sg.ThisRow, -1))
        self.mybinfo = 'file', path
        print('init')

    def ButtonCallBack(self):
        """
        Not user callable! Called by tkinter when a button is clicked.  This is where all the fun begins!
        """

        print('in function')
        target_element, strvar, should_submit_window = self._find_target()

        filetypes = FILE_TYPES_ALL_FILES if self.FileTypes is None else self.FileTypes

        mode, path = self.mybinfo
        results = browser(mode, path)#(initialdir=self.InitialFolder)  # show the 'get folder' dialog box
        if results:
            try:
                strvar.set(results)
                self.TKStringVar.set(results)
            except:
                pass
        else:  # if "cancel" button clicked, don't generate an event
            should_submit_window = False

        if should_submit_window and False:
            self.ParentForm.LastButtonClicked = target_element.Key
            self.ParentForm.FormRemainedOpen = True
            sg._exit_mainloop(self.ParentForm)

        return

def test_browser():
    layout = [[sg.Combo([], size=(30,1), key='Source'),
              BrowseButton('file'), sg.Button('New')]]
    
    window = sg.Window('Test Browser', layout)
    
    while True:
        event, values = window.read()

        if event in ('Cancel', sg.WIN_CLOSED):
            window.close()
            break
        elif event == 'New':
            test_browser()

if __name__ == '__main__':
    test_browser()