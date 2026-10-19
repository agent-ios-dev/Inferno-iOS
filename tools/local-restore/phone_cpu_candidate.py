"""Stage the installed-guest single-AP option for native platform checks first."""
from pathlib import Path
import sys

path = Path(sys.argv[1]) / 'app/Sources/Settings.swift'
source = path.read_text(encoding='utf-8')
changes = {
    '''        // A count saved while 2 and 3 were still on offer would otherwise
        // reach the command line, and leave the picker with nothing selected.
        if cores < Settings.coreChoices[0] { cores = Settings.coreChoices[0] }''':
    '''        // Preserve a supported saved value; reject legacy unsupported counts.
        if !Settings.coreChoices.contains(cores) { cores = 4 }''',
    '''    /// Nothing below 4: one core goes to the SEP, and with fewer than three
    /// left beside it the SEP panics initialising its key store, so the guest
    /// never boots. 2 and 3 used to be offered and only ever caught people out.
    static let coreChoices = [4, 5, 7]''':
    '''    /// Two total cores provide one main CPU plus SEP. This option is useful
    /// for installed guests affected by SMP spinlock timeouts; it does not
    /// establish restore compatibility or change the existing default.
    static let coreChoices = [2, 4, 5, 7]'''
}
for old, new in changes.items():
    if old not in source and source.count(new) == 1:
        continue
    if source.count(old) != 1:
        raise ValueError('Settings candidate no longer matches the checked source')
    source = source.replace(old, new)
path.write_text(source, encoding='utf-8')
