"""
Windows Custom Dialog Module for MCPower
A module to display Windows dialogs with 4 custom buttons:
No, No (Always), Yes, Yes (Always)

This module is specifically designed for MCPower's
user confirmation dialogs on Windows platforms.
"""

import ctypes
from ctypes import wintypes
import sys
from .constants import NO, NO_ALWAYS, YES, YES_ALWAYS

# Custom button IDs (internal use)
_BUTTON_NO = 100
_BUTTON_NO_ALWAYS = 101
_BUTTON_YES = 102
_BUTTON_YES_ALWAYS = 103

# Global result storage (used internally)
_dialog_result = None

# Define WNDCLASSW structure
class _WNDCLASSW(ctypes.Structure):
    """Windows WNDCLASSW structure for window class registration"""
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HANDLE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", ctypes.c_wchar_p),
        ("lpszClassName", ctypes.c_wchar_p)
    ]

def _create_dialog_window(title, main_text, buttons_config, default_button_index=0):
    """
    Internal function to create the Windows dialog with native styling
    
    Args:
        title (str): Window title
        main_text (str): Main message text
        buttons_config (list): List of (text, button_id) tuples for buttons to show
        default_button_index (int): Index of default button (0-based)
        
    Returns:
        int: Button result mapped to xdialog constants
    """
    global _dialog_result
    _dialog_result = None
    
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    gdi32 = ctypes.windll.gdi32
    
    # Set proper argument types and return types for Windows API functions
    user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = wintypes.LPARAM
    
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, ctypes.c_wchar_p, ctypes.c_wchar_p, wintypes.DWORD, 
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.CreateWindowExW.restype = wintypes.HWND
    
    user32.RegisterClassW.argtypes = [ctypes.POINTER(_WNDCLASSW)]
    user32.RegisterClassW.restype = wintypes.ATOM
    
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint]
    user32.GetMessageW.restype = ctypes.c_int
    
    kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    
    # Get system fonts for native appearance
    def get_message_font():
        """Get the system font used for dialogs/message boxes"""
        try:
            # Get the font used by the system for message boxes
            ncm_size = 504 if sys.getwindowsversion().major >= 6 else 440
            ncm = ctypes.create_string_buffer(ncm_size)
            ctypes.windll.user32.SystemParametersInfoW(0x0029, ncm_size, ncm, 0)  # SPI_GETNONCLIENTMETRICS
            # Extract font info from NONCLIENTMETRICS
            return gdi32.CreateFontW(
                -14,  # Height (negative for character height) - increased from -11
                0,    # Width
                0,    # Escapement
                0,    # Orientation
                400,  # Weight (FW_NORMAL)
                0,    # Italic
                0,    # Underline
                0,    # StrikeOut
                1,    # CharSet (DEFAULT_CHARSET)
                0,    # OutPrecision
                0,    # ClipPrecision
                5,    # Quality (CLEARTYPE_QUALITY)
                0,    # PitchAndFamily
                "Segoe UI"  # Face name
            )
        except:
            # Fallback to default GUI font
            return gdi32.GetStockObject(17)  # DEFAULT_GUI_FONT
    
    system_font = get_message_font()
    
    # Window procedure
    def WndProc(hwnd, msg, wparam, lparam):
        global _dialog_result
        
        WM_COMMAND = 0x0111
        WM_CLOSE = 0x0010
        WM_DESTROY = 0x0002
        
        if msg == WM_COMMAND:
            button_id = wparam & 0xFFFF
            if button_id in [_BUTTON_NO, _BUTTON_NO_ALWAYS, _BUTTON_YES, _BUTTON_YES_ALWAYS]:
                _dialog_result = button_id
                user32.DestroyWindow(hwnd)
                return 0
                
        elif msg == WM_CLOSE:
            _dialog_result = _BUTTON_NO  # Default to No on close
            user32.DestroyWindow(hwnd)
            return 0
            
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
            
        # Let Windows handle the default background and colors
        
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
    
    # Window procedure callback
    WNDPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)
    wndproc_callback = WNDPROC(WndProc)
    
    # Get instance handle
    hInstance = kernel32.GetModuleHandleW(None)
    className = "MCPSecurityDialog"
    
    # Register class with proper styling
    wc = _WNDCLASSW()
    wc.style = 0x0008 | 0x0020  # CS_DBLCLKS | CS_CLASSDC
    wc.lpfnWndProc = ctypes.cast(wndproc_callback, ctypes.c_void_p)
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = hInstance
    wc.hIcon = user32.LoadIconW(None, 32514)  # IDI_QUESTION
    wc.hCursor = user32.LoadCursorW(None, 32512)  # IDC_ARROW
    wc.hbrBackground = user32.GetSysColorBrush(15)  # COLOR_3DFACE
    wc.lpszMenuName = None
    wc.lpszClassName = className
    
    atom = user32.RegisterClassW(ctypes.byref(wc))
    if not atom:
        return None
    
    # Calculate proper dialog dimensions with padding
    padding = 25
    text_padding = 20
    button_padding = 20
    
    # Estimate text dimensions (more generous calculation)
    text_lines = main_text.count('\n') + 1
    # Use a more generous calculation for text height
    char_height = 18  # Larger character height
    line_height = 24  # More generous line spacing
    text_height = max(text_lines * line_height + text_padding * 2, 120)
    
    # Calculate button area
    button_count = len(buttons_config)
    btn_width = 100  # Wider buttons to fit text like "Yes (Always)"
    btn_height = 26  # Slightly taller buttons
    btn_spacing = 8  # More space between buttons
    
    total_btn_width = button_count * btn_width + (button_count - 1) * btn_spacing
    button_area_height = btn_height + button_padding * 2
    
    # Calculate window dimensions
    min_width = max(total_btn_width + padding * 2, 550)  # Wider minimum dialog width
    content_width = min_width - padding * 2
    window_width = min_width
    window_height = text_height + button_area_height + padding + 40  # Extra space for title bar and margins
    
    # Calculate center position
    screen_width = user32.GetSystemMetrics(0)
    screen_height = user32.GetSystemMetrics(1)
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    
    # Window styles for a proper dialog
    WS_POPUP = 0x80000000
    WS_VISIBLE = 0x10000000
    WS_CAPTION = 0x00C00000
    WS_SYSMENU = 0x00080000
    WS_DLGFRAME = 0x00400000
    WS_EX_DLGMODALFRAME = 0x00000001
    WS_EX_TOPMOST = 0x00000008
    
    # Create main window with dialog styling
    hwnd = user32.CreateWindowExW(
        WS_EX_DLGMODALFRAME | WS_EX_TOPMOST,
        className,
        title,
        WS_POPUP | WS_CAPTION | WS_SYSMENU | WS_DLGFRAME | WS_VISIBLE,
        x, y, window_width, window_height,
        None,  # Parent window
        None,  # Menu
        hInstance,
        None   # Additional data
    )
    
    if not hwnd:
        try:
            user32.UnregisterClassW(ctypes.c_wchar_p(className), wintypes.HINSTANCE(hInstance))
        except:
            pass
        return None
    
    # Create controls with proper styling
    WS_CHILD = 0x40000000
    WS_VISIBLE = 0x10000000
    WS_TABSTOP = 0x00010000
    SS_CENTER = 0x00000001
    SS_CENTERIMAGE = 0x00000200
    BS_PUSHBUTTON = 0x00000000
    BS_DEFPUSHBUTTON = 0x00000001
    
    # Create static text with better positioning
    text_x = padding
    text_y = padding
    text_w = content_width
    text_h = text_height - padding
    
    # Create static text with left alignment instead of center
    SS_LEFT = 0x00000000  # Left-aligned text
    text_hwnd = user32.CreateWindowExW(
        0, "STATIC", main_text,
        WS_VISIBLE | WS_CHILD | SS_LEFT,
        text_x, text_y, text_w, text_h,
        hwnd, None, hInstance, None
    )
    
    # Set font for text
    if text_hwnd and system_font:
        user32.SendMessageW(text_hwnd, 0x0030, system_font, 1)  # WM_SETFONT
    
    # Create buttons with proper spacing and styling
    btn_y = text_height + button_padding + 10  # Extra margin from text
    start_x = (window_width - total_btn_width) // 2
    
    button_hwnds = []
    for i, (btn_text, btn_id) in enumerate(buttons_config):
        btn_x = start_x + i * (btn_width + btn_spacing)
        
        # Use default button style for the specified default button
        is_default = (i == default_button_index)
        btn_style = BS_DEFPUSHBUTTON if is_default else BS_PUSHBUTTON
        
        btn_hwnd = user32.CreateWindowExW(
            0, "BUTTON", btn_text,
            WS_VISIBLE | WS_CHILD | WS_TABSTOP | btn_style,
            btn_x, btn_y, btn_width, btn_height,
            hwnd, btn_id, hInstance, None
        )
        
        # Set font for button
        if btn_hwnd and system_font:
            user32.SendMessageW(btn_hwnd, 0x0030, system_font, 0)  # WM_SETFONT
        
        button_hwnds.append(btn_hwnd)
        
        # Set focus to default button
        if is_default and btn_hwnd:
            user32.SetFocus(btn_hwnd)
    
    # Make dialog modal and bring to front
    user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0010 | 0x0002 | 0x0001)  # HWND_TOPMOST | SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    
    # Enable the parent window to be disabled (modal behavior)
    parent = user32.GetWindow(hwnd, 4)  # GW_OWNER
    if parent:
        user32.EnableWindow(parent, False)
    
    # Simple message loop
    msg = wintypes.MSG()
    while True:
        bRet = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if bRet == 0:  # WM_QUIT
            break
        elif bRet == -1:  # Error
            break
        else:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    
    # Re-enable parent window
    if parent:
        user32.EnableWindow(parent, True)
        user32.SetForegroundWindow(parent)
    
    # Cleanup
    if system_font:
        gdi32.DeleteObject(system_font)
    try:
        user32.UnregisterClassW(ctypes.c_wchar_p(className), wintypes.HINSTANCE(hInstance))
    except:
        pass  # Ignore cleanup errors
    
    return _dialog_result

def show_confirmation_dialog(title, message, yes_always=False, no_always=False):
    """
    Show a Windows confirmation dialog with configurable buttons.
    
    Args:
        title (str): Window title
        message (str): Main message text
        yes_always (bool): Whether to show "Yes (Always)" button
        no_always (bool): Whether to show "No (Always)" button
    
    Returns:
        int: One of the xdialog constants (NO, NO_ALWAYS, YES, YES_ALWAYS)
        NO: If dialog was cancelled or closed
    """
    # Check if we're on Windows
    if sys.platform != "win32":
        raise OSError("This module only works on Windows")
    
    # Build button configuration based on parameters
    # Order: No, No (Always), Yes, Yes (Always)
    buttons_config = []
    
    buttons_config.append(("No", _BUTTON_NO))
    if no_always:
        buttons_config.append(("No (Always)", _BUTTON_NO_ALWAYS))
    buttons_config.append(("Yes", _BUTTON_YES))
    if yes_always:
        buttons_config.append(("Yes (Always)", _BUTTON_YES_ALWAYS))
    
    # Try to create the dialog
    try:
        result = _create_dialog_window(title, message, buttons_config, 2)  # Default to "Yes" button
        
        # Map internal button IDs to xdialog constants
        mapping = {
            _BUTTON_NO: NO,
            _BUTTON_NO_ALWAYS: NO_ALWAYS,
            _BUTTON_YES: YES,
            _BUTTON_YES_ALWAYS: YES_ALWAYS
        }
        
        return mapping.get(result, NO)  # Default to NO if unknown result
        
    except Exception:
        # Fallback to NO on any error
        return NO

def is_available():
    """
    Check if the custom dialog is available on this platform.
    
    Returns:
        bool: True if custom dialogs can be used
    """
    return sys.platform == "win32"

def show_generic_dialog(title, message, buttons, default_button, icon):
    """
    Show a Windows generic dialog with custom buttons and icon.
    
    Args:
        title (str): Window title
        message (str): Main message text
        buttons (list): List of button text strings
        default_button (int): Index of default button (0-based)
        icon (str): Icon type (ICON_QUESTION, ICON_WARNING, ICON_ERROR, ICON_INFO)
    
    Returns:
        int: Index of clicked button (0-based), or default_button if dismissed
    """
    from .constants import ICON_QUESTION, ICON_WARNING, ICON_ERROR, ICON_INFO
    
    # Check if we're on Windows
    if sys.platform != "win32":
        raise OSError("This module only works on Windows")
    
    # Map icon constants (currently not used in UI, but validated)
    icon_map = {
        ICON_QUESTION: "question",
        ICON_WARNING: "warning", 
        ICON_ERROR: "error",
        ICON_INFO: "info"
    }
    
    if icon not in icon_map:
        raise ValueError(f"Unsupported icon: {icon}")
    
    # Build button configuration with custom button IDs starting from 100
    buttons_config = []
    for i, button_text in enumerate(buttons):
        buttons_config.append((button_text, 100 + i))
    
    # Try to create the dialog
    try:
        result = _create_dialog_window(title, message, buttons_config, default_button)
        
        # Map internal button IDs back to indices
        if result is not None and result >= 100:
            button_index = result - 100
            if 0 <= button_index < len(buttons):
                return button_index
        
        # Dialog was dismissed or unexpected result - return default button
        return default_button
        
    except Exception:
        # Return default button on any error
        return default_button

