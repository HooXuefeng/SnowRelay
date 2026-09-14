import os
import sys
import ctypes

root = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
# On some Windows installations Tcl snapshots its library search state when
# the DLL is first loaded. Load/register the executable before setting the
# library variables; reversing this order can make an existing init.tcl look
# unusable and causes the packaged GUI to fail before its first window.
if os.name == "nt":
    tcl_dll = os.path.join(root, "tcl86t.dll")
    if os.path.isfile(tcl_dll):
        library = ctypes.CDLL(tcl_dll)
        library.Tcl_FindExecutable.argtypes = [ctypes.c_char_p]
        library.Tcl_FindExecutable(os.fsencode(sys.executable))
os.environ["TCL_LIBRARY"] = os.path.join(root, "_tcl_data")
os.environ["TK_LIBRARY"] = os.path.join(root, "_tk_data")
