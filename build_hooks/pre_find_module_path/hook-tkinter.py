"""SnowRelay build override: Tcl/Tk files are supplied explicitly by SnowRelay.spec."""


def pre_find_module_path(hook_api):
    # Keep tkinter's normal search directory even if PyInstaller's isolated
    # Tcl probe cannot initialize on this Windows host.
    return None
