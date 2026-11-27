# SPDX-License-Identifier: LicenseRef-VorteX-Proprietary
"""Standalone prototype: local image comparison and authorized media processing."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
from PIL import Image, ImageChops, ImageStat

MAX_PIXELS = 16_000_000

def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def load_rgb(path):
    with Image.open(path) as image:
        if image.width * image.height > MAX_PIXELS:
            raise ValueError('Image exceeds pixel budget')
        rgba = image.convert('RGBA')
        background = Image.new('RGBA', rgba.size, 'white')
        return Image.alpha_composite(background, rgba).convert('RGB')

def compare(reference, candidate, tolerance=12, minimum=99.0):
    if not 0 <= tolerance <= 255 or not math.isfinite(minimum) or not 0 <= minimum <= 100:
        raise ValueError('Invalid thresholds')
    a, b = load_rgb(reference), load_rgb(candidate)
    report = {'reference_sha256': digest(reference), 'candidate_sha256': digest(candidate),
              'reference_size': a.size, 'candidate_size': b.size,
              'tolerance': tolerance, 'minimum_percent': minimum}
    if a.size != b.size:
        return report | {'status': 'SIZE_MISMATCH', 'match_percent': None}
    delta = ImageChops.difference(a,b)
    r,g,bl = delta.split()
    maximum = ImageChops.lighter(ImageChops.lighter(r,g),bl)
    hist = maximum.histogram()
    changed = maximum.point(lambda x: 255 if x > tolerance else 0)
    total = a.width * a.height
    score = 100 * sum(hist[:tolerance+1]) / total
    return report | {'status': 'VISUAL_PASS' if score >= minimum else 'VISUAL_FAIL',
                     'match_percent': score, 'mean_absolute_channel_error': sum(ImageStat.Stat(delta).mean)/3,
                     'changed_pixels': total-sum(hist[:tolerance+1]), 'changed_bbox': changed.getbbox(),
                     'scope': 'pixel comparison only; behavior and accessibility not tested'}

def rank(reference, candidates, tolerance=12, minimum=99.0):
    rows = [dict(candidate=str(p), **compare(reference,p,tolerance,minimum)) for p in candidates]
    return sorted(rows, key=lambda r: (r['match_percent'] is None, -(r['match_percent'] or 0), r['candidate']))

def film_trim(source, destination, start, duration):
    if not all(math.isfinite(v) for v in (start,duration)) or start < 0 or duration <= 0 or duration > 120:
        raise ValueError('Invalid time range; max duration is 120 seconds')
    source = Path(source).resolve(strict=True)
    destination = Path(destination).absolute()
    if not source.is_file() or destination.suffix.lower() != '.mp4' or destination.exists() or destination.is_symlink():
        raise ValueError('Require existing input and new MP4 output')
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        raise RuntimeError('Install FFmpeg and FFprobe separately')
    def probe(path):
        r = subprocess.run([ffprobe,'-v','error','-protocol_whitelist','file,pipe','-show_streams','-show_format','-of','json',str(path)],check=True,capture_output=True,timeout=60)
        return json.loads(r.stdout)
    original = probe(source)
    length = float(original['format']['duration'])
    if start+duration > length+0.001:
        raise ValueError('Requested range exceeds input duration')
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        out = Path(tmp)/'clip.mp4'
        command = [ffmpeg,'-nostdin','-v','error','-protocol_whitelist','file,pipe','-i',str(source),'-ss',str(start),'-t',str(duration),'-map','0:v:0','-map','0:a:0?','-c:v','libx264','-pix_fmt','yuv420p','-vf','scale=trunc(iw/2)*2:trunc(ih/2)*2','-c:a','aac','-movflags','+faststart','-y',str(out)]
        subprocess.run(command,check=True,capture_output=True,timeout=300)
        result = probe(out)
        if not any(s['codec_type']=='video' for s in result['streams']):
            raise RuntimeError('Missing video output')
        actual = float(result['format']['duration'])
        if abs(actual-duration)>0.25:
            raise RuntimeError('Unexpected output duration')
        with destination.open('xb') as target:
            try:
                with out.open('rb') as f: shutil.copyfileobj(f,target)
            except BaseException:
                target.close(); destination.unlink(); raise
    return {'status':'ENCODED','duration':actual,'sha256':digest(destination),'streams':[s['codec_type'] for s in result['streams']]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    c=sub.add_parser('compare'); c.add_argument('reference'); c.add_argument('candidate',nargs='+'); c.add_argument('--tolerance',type=int,default=12); c.add_argument('--minimum',type=float,default=99)
    f=sub.add_parser('trim'); f.add_argument('source'); f.add_argument('destination'); f.add_argument('--start',type=float,required=True); f.add_argument('--duration',type=float,required=True)
    a=p.parse_args()
    r=rank(a.reference,a.candidate,a.tolerance,a.minimum) if a.command=='compare' else film_trim(a.source,a.destination,a.start,a.duration)
    print(json.dumps(r,indent=2))
    return 0 if (r[0]['status']=='VISUAL_PASS' if a.command=='compare' else r['status']=='ENCODED') else 1

if __name__=='__main__': raise SystemExit(main())
