# VorteX Studio — source-available prototype 0.1

Original standalone Python prototype, published with owner authorization. The directory LICENSE applies to original Studio material; the existing public framework remains Apache-2.0. No third-party source, assets or binary is bundled. This is not an end-user distribution.

## Run
Python 3.13+; install Pillow separately. For Film, install FFmpeg/FFprobe with libx264 and AAC support separately. Use only trusted, authorized local input files in an isolated environment.

```
python vortex_studio.py compare original.png candidate1.png candidate2.png --tolerance 12 --minimum 99
python vortex_studio.py trim input.mp4 output.mp4 --start 1 --duration 2
python -m unittest discover -s tests -v
```

Rebuild compares equal-sized screenshots, counts pixels whose largest RGB channel difference is within tolerance, reports changed bounds and hashes, and ranks candidate images. Visual comparison alone does not establish behavior, accessibility or legal clearance.

Film performs a local H.264/AAC trim, checks duration and video stream, and refuses existing output. No timeline, transitions, full-HD 60 fps preset or GUI yet. Decoder isolation and complete validation of arbitrary inputs are not implemented.

External dependencies: Pillow (https://github.com/python-pillow/Pillow/blob/main/LICENSE) and FFmpeg (https://ffmpeg.org/legal.html). Check exact versions and notices before redistribution. Craft Anything is an architectural reference only; no code copied. See ../THIRD_PARTY_NOTICES.md.
