import numpy as np
from PIL import Image
from moviepy.editor import VideoClip, concatenate_videoclips

def _ken_burns(clip, zoom_start, zoom_end, pan_x, pan_y, duration):
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS

    def make_frame(t):
        progress = t / duration
        zoom = zoom_start + (zoom_end - zoom_start) * progress
        px = pan_x * progress
        py = pan_y * progress

        orig_t = min(t, clip.duration) if clip.duration is not None else t
        img = Image.fromarray(clip.get_frame(orig_t))
        w, h = img.size

        zw, zh = int(w / zoom), int(h / zoom)

        cx = int((w - zw) / 2 + px * (w - zw) / 2)
        cy = int((h - zh) / 2 + py * (h - zh) / 2)

        cx = max(0, min(cx, w - zw))
        cy = max(0, min(cy, h - zh))

        cropped = img.crop((cx, cy, cx + zw, cy + zh))
        resized = cropped.resize((w, h), resample)

        return np.array(resized)

    fps = clip.fps if hasattr(clip, 'fps') and clip.fps else 24
    return VideoClip(make_frame, duration=duration).set_fps(fps)

def ken_burns_zoom_in(clip, duration):
    return _ken_burns(clip, zoom_start=1.0, zoom_end=1.15, pan_x=0.0, pan_y=0.0, duration=duration)

def ken_burns_zoom_out(clip, duration):
    return _ken_burns(clip, zoom_start=1.15, zoom_end=1.0, pan_x=0.0, pan_y=0.0, duration=duration)

def ken_burns_pan_right(clip, duration):
    return _ken_burns(clip, zoom_start=1.1, zoom_end=1.1, pan_x=1.0, pan_y=0.0, duration=duration)

def ken_burns_pan_left(clip, duration):
    return _ken_burns(clip, zoom_start=1.1, zoom_end=1.1, pan_x=-1.0, pan_y=0.0, duration=duration)

KB_PRESETS = [
    ken_burns_zoom_in,
    ken_burns_zoom_out,
    ken_burns_pan_right,
    ken_burns_pan_left
]

def apply_ken_burns(clip, section_index=0, duration=None):
    if duration is None:
        duration = clip.duration
    preset = KB_PRESETS[section_index % len(KB_PRESETS)]
    return preset(clip, duration)

GRADES = {
    "cinematic_teal_orange": {
        "shadow_mult": np.array([0.85, 0.95, 1.1]),
        "highlight_mult": np.array([1.1, 1.05, 0.9]),
        "contrast": 1.12,
        "saturation": 1.15,
        "vignette": 0.75
    },
    "warm_film": {
        "shadow_mult": np.array([1.05, 0.95, 0.85]),
        "highlight_mult": np.array([1.1, 1.05, 0.95]),
        "contrast": 1.08,
        "saturation": 1.10,
        "vignette": 0.80
    },
    "cold_thriller": {
        "shadow_mult": np.array([0.8, 0.9, 1.1]),
        "highlight_mult": np.array([0.85, 0.95, 1.05]),
        "contrast": 1.20,
        "saturation": 0.85,
        "vignette": 0.65
    }
}

def apply_cinematic_grade(clip, style="cinematic_teal_orange"):
    grade_config = GRADES.get(style, GRADES["cinematic_teal_orange"])

    def grade_frame(frame):
        img = frame.astype(np.float32) / 255.0
        lum = np.mean(img, axis=2, keepdims=True)

        shadow_mask = np.clip(1 - lum * 2, 0, 1)
        highlight_mask = np.clip(lum * 2 - 1, 0, 1)

        img = img * (1 - shadow_mask) + img * shadow_mask * grade_config["shadow_mult"]
        img = img * (1 - highlight_mask) + img * highlight_mask * grade_config["highlight_mult"]

        img = (img - 0.5) * grade_config["contrast"] + 0.5

        gray = np.mean(img, axis=2, keepdims=True)
        img = gray + (img - gray) * grade_config["saturation"]

        h, w = frame.shape[:2]
        y, x = np.ogrid[:h, :w]
        cy, cx = h / 2, w / 2
        max_dist = np.sqrt(cy**2 + cx**2)
        dist = np.sqrt((y - cy)**2 + (x - cx)**2)
        vignette_mask = 1 - (dist / max_dist) * (1 - grade_config["vignette"])
        img = img * vignette_mask[:, :, np.newaxis]

        return (np.clip(img, 0, 1) * 255).astype(np.uint8)

    return clip.fl_image(grade_frame)

def cross_dissolve(clip1, clip2, duration=0.7):
    c1 = clip1.crossfadeout(duration)
    c2 = clip2.crossfadein(duration)
    return concatenate_videoclips([c1, c2], method="compose", padding=-duration)

def zoom_transition(clip1, clip2, duration=0.5):
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS

    c1_main = clip1.subclip(0, clip1.duration - duration)
    c1_trans = clip1.subclip(clip1.duration - duration, clip1.duration)

    c2_trans = clip2.subclip(0, duration)
    c2_main = clip2.subclip(duration, clip2.duration)

    def zoom_out_frame(t):
        progress = t / duration
        zoom = 1.0 + progress * 0.5

        orig_t = min(t, c1_trans.duration) if c1_trans.duration is not None else t
        img = Image.fromarray(c1_trans.get_frame(orig_t))
        w, h = img.size

        zw, zh = int(w / zoom), int(h / zoom)
        cx = int((w - zw) / 2)
        cy = int((h - zh) / 2)

        cropped = img.crop((cx, cy, cx + zw, cy + zh))
        resized = cropped.resize((w, h), resample)
        return np.array(resized)

    def zoom_in_frame(t):
        progress = t / duration
        zoom = 1.5 - progress * 0.5

        orig_t = min(t, c2_trans.duration) if c2_trans.duration is not None else t
        img = Image.fromarray(c2_trans.get_frame(orig_t))
        w, h = img.size

        zw, zh = int(w / zoom), int(h / zoom)
        cx = int((w - zw) / 2)
        cy = int((h - zh) / 2)

        cropped = img.crop((cx, cy, cx + zw, cy + zh))
        resized = cropped.resize((w, h), resample)
        return np.array(resized)

    fps = clip1.fps if hasattr(clip1, 'fps') and clip1.fps else 24
    v_out = VideoClip(zoom_out_frame, duration=duration).set_fps(fps)
    v_in = VideoClip(zoom_in_frame, duration=duration).set_fps(fps)

    return concatenate_videoclips([c1_main, v_out, v_in, c2_main])

def build_video_with_transitions(section_clips, transition="cross_dissolve"):
    if not section_clips:
        return None
    if len(section_clips) == 1:
        return section_clips[0]

    assembled = section_clips[0]
    for clip in section_clips[1:]:
        if transition == "cross_dissolve":
            assembled = cross_dissolve(assembled, clip, duration=0.7)
        elif transition == "zoom_transition":
            assembled = zoom_transition(assembled, clip, duration=0.5)
        else:
            assembled = concatenate_videoclips([assembled, clip])

    return assembled
