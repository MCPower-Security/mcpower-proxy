from .constants import *

from tkinter import messagebox
from tkinter import filedialog

def open_file(title, filetypes, multiple=False):
    if multiple:
        return filedialog.askopenfilenames(title=title, filetypes=filetypes)
    else:
        return filedialog.askopenfilename(title=title) or ''

def save_file(title, filetypes):
    return filedialog.asksaveasfilename(title=title, filetypes=filetypes) or ''

def directory(title):
    return filedialog.askdirectory(mustexist=True) or ''

info = messagebox.showinfo
warning = messagebox.showwarning
error = messagebox.showerror

def yesno(title, message):
    if messagebox.askyesno(title, message):
        return YES
    else:
        return NO

def yesno_always(title, message, yes_always=False, no_always=False):
    """
    Enhanced yes/no dialog with optional always buttons
    Button order: No, No Always (if enabled), Yes, Yes Always (if enabled)
    
    Note: Tkinter messagebox doesn't support custom buttons, so we fall back to yesno
    for now. Full implementation would require custom Tkinter dialog creation.
    """
    # TODO: Implement custom Tkinter dialog with proper button layout
    # For now, fall back to standard yesno dialog
    return yesno(title, message)

def yesnocancel(title, message):
    r = messagebox.askyesnocancel(title, message)
    if r is None:
        return CANCEL
    elif r:
        return YES
    else:
        return NO

def retrycancel(title, message):
    if messagebox.askretrycancel(title, message):
        return RETRY
    else:
        return CANCEL

def okcancel(title, message):
    if messagebox.askokcancel(title, message):
        return OK
    else:
        return CANCEL

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
    
    Raises:
        NotImplementedError: Tkinter messagebox doesn't support custom buttons
    """
    raise NotImplementedError("generic_dialog is not supported on Tkinter - custom buttons require custom dialog implementation")
