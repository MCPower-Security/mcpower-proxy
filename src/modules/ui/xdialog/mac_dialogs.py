#!/usr/bin/env python3

import subprocess

from .constants import *

def osascript(*code: str):
    proc = subprocess.Popen(
        ["osascript", "-e", " ".join(code)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False
    )
    stdout, stderr = proc.communicate()

    return (proc.returncode, stdout.decode('utf-8'), stderr.decode('utf-8'))

def quote(text: str):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'

def dialog(title, message, icon, buttons=["OK"], default_button=None):
    script = [
        'display dialog', quote(message),
        'with icon', icon,
        'buttons', "{" + ",".join(quote(btn) for btn in buttons) + "}",
    ]
    if title: script.append('with title ' + quote(title))
    
    # Set default button if specified
    if default_button is not None and 0 <= default_button < len(buttons):
        script.append('default button ' + quote(buttons[default_button]))

    code, out, err = osascript(*script)
    if code: return ''
    else: return out[out.index(":")+1:].strip("\r\n")

def open_file(title, filetypes, multiple=False):
    script = ['choose file']
    if title: script.append('with prompt ' + quote(title))
    if filetypes:
        oftype = []
        for _, exts in filetypes:
            for ext in exts.split():
                if ext == "*": break
                if ext[:2] == "*.": oftype.append(quote(ext[2:]))
        else:
            if oftype: script.append("of type {" + ",".join(oftype) + "}")
    
    if multiple:
        script.append("multiple selections allowed true")
        code, out, err = osascript(f'set ps to ({" ".join(script)})\rrepeat with p in ps\r log (POSIX path of p)\rend repeat')
        if code: return []

        return err.strip("\r\n").splitlines()
    else:
        code, out, err = osascript(f'POSIX path of ({" ".join(script)})')
        if code: return ''

        return out.strip("\r\n")

def save_file(title, filetypes):
    script = ['choose file name']
    if title: script.append('with prompt ' + quote(title))
    if filetypes:
        for filetype, exts in filetypes:
            for ext in exts.split():
                if ext == "*": continue
                if ext[:2] == "*.":
                    script.append(f'default name "{filetype}.{ext[2:]}"') 
                    break

    code, out, err = osascript(f'POSIX path of ({" ".join(script)})')
    if code: return ''

    return out.strip("\r\n")

def directory(title):
    script = ['choose folder']
    if title: script.append('with prompt ' + quote(title))

    code, out, err = osascript(f'POSIX path of ({" ".join(script)})')
    if code: return ''

    return out.strip("\r\n")

def info(title, message):
    dialog(title, message, "note")

def warning(title, message):
    dialog(title, message, "caution")

def error(title, message):
    dialog(title, message, "stop")

def yesno(title, message):
    out = dialog(title, message, "caution", ["No", "Yes"])
    if not out or out == "No": return NO
    elif out == "Yes": return YES

def yesno_always(title, message, yes_always=False, no_always=False):
    """
    Enhanced yes/no dialog with optional always buttons
    Button order: No, No Always (if enabled), Yes, Yes Always (if enabled)
    """
    buttons = []
    
    # Build button list in order: No, No Always, Yes, Yes Always
    buttons.append("No")
    if no_always:
        buttons.append("No (Always)")
    buttons.append("Yes") 
    if yes_always:
        buttons.append("Yes (Always)")
    
    out = dialog(title, message, "caution", buttons)
    
    if not out or out == "No":
        return NO
    elif out == "No (Always)":
        return NO_ALWAYS
    elif out == "Yes":
        return YES
    elif out == "Yes (Always)":
        return YES_ALWAYS
    else:
        return NO  # Fallback

def yesnocancel(title, message):
    out = dialog(title, message, "note", ["Cancel", "No", "Yes"])
    if not out or out == "Cancel": return CANCEL
    elif out == "No": return NO
    elif out == "Yes": return YES

def retrycancel(title, message):
    out = dialog(title, message, "note", ["Cancel", "Retry"])
    if not out or out == "Cancel": return CANCEL
    elif out == "Retry": return RETRY

def okcancel(title, message):
    out = dialog(title, message, "note", ["Cancel", "OK"])
    if not out or out == "Cancel": return CANCEL
    elif out == "OK": return OK

def generic_dialog(title, message, buttons, default_button, icon):
    """
    Generic dialog with custom buttons and icon
    
    Args:
        title (str): Dialog title
        message (str): Dialog message
        buttons (list): List of button text strings
        default_button (int): Index of default button (0-based)
        icon (str): Icon type (ICON_QUESTION, ICON_WARNING, ICON_ERROR, ICON_INFO)
    
    Returns:
        int: Index of clicked button (0-based)
    """
    from .constants import ICON_QUESTION, ICON_WARNING, ICON_ERROR, ICON_INFO
    
    # Map icon constants to AppleScript icons
    icon_map = {
        ICON_QUESTION: "caution",
        ICON_WARNING: "caution", 
        ICON_ERROR: "stop",
        ICON_INFO: "note"
    }
    
    if icon not in icon_map:
        raise ValueError(f"Unsupported icon: {icon}")
    
    if not isinstance(buttons, list) or len(buttons) == 0:
        raise ValueError("buttons must be a non-empty list")
    
    if not isinstance(default_button, int) or default_button < 0 or default_button >= len(buttons):
        raise ValueError(f"default_button must be a valid index (0-{len(buttons)-1})")
    
    # Call AppleScript dialog with default button
    out = dialog(title, message, icon_map[icon], buttons, default_button)
    
    # Map response back to button index
    if not out:
        # Dialog was dismissed/cancelled - return default button index
        return default_button
    
    # Find the button that was clicked
    try:
        return buttons.index(out)
    except ValueError:
        # This should not happen unless AppleScript returns unexpected text
        raise RuntimeError(f"Unexpected dialog result: {out}, expected one of {buttons}")
