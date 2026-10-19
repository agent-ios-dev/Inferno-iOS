"""Observe private local logs; hand off only after final restore and patcher success."""
import argparse
import json
from pathlib import Path
import re
import time

from qmp import execute


def tail(path):
    try:
        with path.open('rb') as stream:
            stream.seek(max(0, path.stat().st_size - (256 << 10)))
            return stream.read().decode('utf-8', errors='replace')
    except FileNotFoundError:
        return ''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vm', type=Path)
    parser.add_argument('--handoff', action='store_true')
    args = parser.parse_args()
    report = args.vm / 'local-restore-observation.json'
    if report.exists() and json.loads(report.read_text()).get('handoff_completed'):
        raise SystemExit('Handoff already recorded; refusing a second reset.')
    state = {'restore_completed': False, 'filesystem_patcher_completed': False,
             'handoff_completed': False, 'springboard_confirmed': False,
             'backboardd_confirmed': False}
    last = None
    deadline = time.monotonic() + 4 * 3600
    while time.monotonic() < deadline:
        console = tail(args.vm / 'restore-logs/guest-console.log')
        client = tail(args.vm / 'restore-logs/idevicerestore.log')
        values = re.findall(r'ASR RESTORE PROGRESS: (\d+)%', console)
        if values:
            state['asr_restore_percent'] = int(values[-1])
        state['restore_completed'] |= 'Status: Restore Finished' in client
        state['filesystem_patcher_completed'] |= 'PATCHER: done, the machine can be reset now' in console
        if 'PATCHER: failed' in console or 'PATCHER: no shared cache' in console:
            state['failure'] = 'Guest filesystem patcher failed; inspect private log'
        if 'panic(cpu' in console:
            state['failure'] = 'Guest kernel panic; inspect private log'
        if state['restore_completed'] and state['filesystem_patcher_completed']:
            if args.handoff:
                for name, arguments in [
                    ('stop', None),
                    ('qom-set', {'path': '/machine', 'property': 'system-boot-after-restore', 'value': True}),
                    ('system_reset', None), ('cont', None)]:
                    execute(name, arguments)
                state['handoff_completed'] = True
                state['handoff_unix_time'] = int(time.time())
            report.write_text(json.dumps(state, indent=2))
            print(json.dumps(state), flush=True)
            return
        serialized = json.dumps(state, sort_keys=True)
        if serialized != last:
            report.write_text(json.dumps(state, indent=2))
            print(serialized, flush=True)
            last = serialized
        if 'failure' in state:
            return
        time.sleep(2)
    raise SystemExit('Observation deadline reached; VM was not stopped or reset.')


if __name__ == '__main__':
    main()
