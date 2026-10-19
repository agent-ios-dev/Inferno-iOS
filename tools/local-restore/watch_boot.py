"""Observe the actual local framebuffer; never infer successful UI or reset VM.

Frame and private console stay inside the VM folder. Output only bounded screen
geometry/progress observations. A changed screen requires human visual review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from PIL import Image
from qmp import execute
from watch import tail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vm', type=Path)
    parser.add_argument('--after-progress', action='store_true',
                        help='Keep observing screen changes after progress row disappears')
    args = parser.parse_args()
    logs = args.vm / 'boot-logs'
    last_bucket = None
    pause_reported = False
    deadline = time.monotonic() + 30 * 60
    while time.monotonic() < deadline:
        console = tail(logs / 'guest-console.log')
        if 'panic(cpu' in console:
            print(json.dumps({'failure': 'Guest panic; inspect private console',
                              'visible_ui_confirmed': False}), flush=True)
            return
        status = execute('query-status')
        if not status.get('running'):
            if not pause_reported:
                print('VM paused by another operation; observing only, never resuming it.', flush=True)
                pause_reported = True
            time.sleep(15)
            continue
        pause_reported = False
        execute('screendump', {'filename': '/vm/boot-logs/observed.ppm'})
        with Image.open(logs / 'observed.ppm') as raw:
            frame = raw.convert('RGB')
        if frame.size != (828, 1792):
            raise RuntimeError('Unexpected display size; inspect actual frame')
        white = sum(min(frame.getpixel((x, 1026))) > 200 for x in range(160, 668))
        state = {'observed_unix_time': int(time.time()), 'white_progress_pixels': white,
                 'progress_row_width': 508, 'visible_ui_confirmed': False}
        if args.after_progress:
            state['frame_sha256'] = hashlib.sha256(frame.tobytes()).hexdigest()
        bucket = state['frame_sha256'] if args.after_progress else white // 32
        if bucket != last_bucket:
            frame.save(logs / 'observed.png')
            print(json.dumps(state), flush=True)
            last_bucket = bucket
        (logs / 'frame-observation.json').write_text(json.dumps(state, indent=2))
        # A completed or replaced progress row does not establish what the
        # screen means. Save it and return for actual visual inspection.
        if not args.after_progress and (white == 0 or white >= 500):
            frame.save(logs / 'observed.png')
            print('Screen requires visual review; UI success has not been inferred.', flush=True)
            return
        time.sleep(15)
    print('Observation deadline reached; VM left running, no UI claim.', flush=True)


if __name__ == '__main__':
    main()
