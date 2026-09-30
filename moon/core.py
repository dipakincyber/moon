from __future__ import annotations
import json, os, re, shutil, subprocess, time
from datetime import date, datetime, timedelta
from pathlib import Path

DATA_DIR = Path(os.environ.get("MOON_HOME", Path.home()/".config/moon"))
DATA_FILE = DATA_DIR/"moon.json"
_PACKAGE_SOUNDS_DIR = Path("/usr/share/moon/sounds")
SOUNDS_DIR = Path(os.environ.get("MOON_SOUNDS_DIR", _PACKAGE_SOUNDS_DIR))
if not SOUNDS_DIR.exists():
    SOUNDS_DIR = Path(__file__).resolve().parent.parent/"sounds"
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}

def load():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        return {"period": [], "messages": {}, "hydration": None, "alarms": []}
    try:
        data=json.loads(DATA_FILE.read_text())
        for k,v in {"period": [], "messages": {}, "hydration": None, "alarms": []}.items():
            data.setdefault(k,v)
        return data
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Cannot read {DATA_FILE}: {e}")

def save(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp=DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(DATA_FILE)

def parse_date(value):
    value=value.strip()
    for fmt in ("%Y-%m-%d","%Y/%m/%d","%B %d, %Y","%B %d %Y","%d %B, %Y","%d %B %Y",
                "%b %d, %Y","%b %d %Y","%d %b, %Y","%d %b %Y","%d %b"):
        try:
            d=datetime.strptime(value,fmt).date()
            if fmt=="%d %b": d=d.replace(year=date.today().year)
            return d.isoformat()
        except ValueError: pass
    raise ValueError("Use a date like 2026-01-20, January 20, 2026, or 20 Jan.")

def parse_time(value):
    s=value.strip().upper().replace(".", "")
    for fmt in ("%H:%M","%I:%M %p","%I:%M%p","%I %p","%I%p"):
        try: return datetime.strptime(s,fmt).strftime("%H:%M")
        except ValueError: pass
    if re.fullmatch(r"\d{1,2}:\d{2}",s):
        h,m=map(int,s.split(":"))
        if 0<=h<=12 and 0<=m<60:
            if h==0: return "00:%02d"%m
            ampm=input(f"Did you mean {h}:{m:02d} AM or PM? ").strip().lower()
            if ampm in ("am","a"): return f"{h%12:02d}:{m:02d}"
            if ampm in ("pm","p"): return f"{h%12+12:02d}:{m:02d}"
        raise ValueError("Ambiguous/invalid time. Use 13:00 or 1:00 PM.")
    raise ValueError("Use 24-hour HH:MM or 12-hour H:MM AM/PM.")

def prompt_time(label="Time"):
    while True:
        s=input(f"{label} (24h e.g. 13:00 / 12h e.g. 1:00 PM / 'p' picker): ").strip()
        if s.lower()=="p":
            while True:
                try:
                    h=int(input("Hour (1-12): ")); m=int(input("Minute (0-59): "))
                    ap=input("AM or PM: ").strip().upper()
                    if 1<=h<=12 and 0<=m<=59 and ap in ("AM","PM"):
                        return f"{(h%12)+(12 if ap=='PM' else 0):02d}:{m:02d}"
                except ValueError: pass
                print("Please enter a valid hour, minute, and AM/PM.")
        try: return parse_time(s)
        except ValueError as e: print(e)

def notify(title, body):
    if shutil.which("notify-send"):
        # Freedesktop action support varies by notification daemon. A 60s timeout
        # is requested; the CLI's stop action is offered where supported.
        try:
            p=subprocess.run(["notify-send", "--app-name=Moon", "--expire-time=60000", "--action=stop=Stop", title, body], capture_output=True, text=True, timeout=65)
            return p.stdout.strip()=="stop"
        except (OSError, subprocess.TimeoutExpired): return False
    print(f"\n[{title}] {body}\n", flush=True)
    return False

def time_of_day(now=None):
    h=(now or datetime.now()).hour
    return "morning" if 5<=h<12 else "afternoon" if 12<=h<17 else "evening" if 17<=h<21 else "night"

def render(template, now=None):
    now=now or datetime.now()
    return template.replace("{time_of_day}",time_of_day(now)).replace("{date}",now.strftime("%Y-%m-%d")).replace("{day}",now.strftime("%A")).replace("{time}",now.strftime("%I:%M %p").lstrip("0"))

def audio_is_headphones():
    """Best-effort detection from the active Linux audio sink metadata."""
    if shutil.which("wpctl"):
        out=subprocess.run(["wpctl","inspect","@DEFAULT_AUDIO_SINK@"],capture_output=True,text=True).stdout.lower()
        if any(x in out for x in ("headphone","headset","bluetooth","bluez","earphone")): return True
        if out: return False
    if shutil.which("pactl"):
        sink=subprocess.run(["pactl","get-default-sink"],capture_output=True,text=True).stdout.strip()
        info=subprocess.run(["pactl","list","sinks"],capture_output=True,text=True).stdout
        for block in info.split("Sink #"):
            if sink and sink in block[:600]:
                return any(x in block.lower() for x in ("headphone","headset","bluetooth","bluez","earphone"))
    return False

def set_volume_cap():
    data=load(); prefs=data.get("volumes",{"headphones":49,"speakers":80})
    key="headphones" if audio_is_headphones() else "speakers"
    target=max(0,min(100,int(prefs.get(key,49 if key=="headphones" else 80))))/100
    if shutil.which("wpctl"):
        out=subprocess.run(["wpctl","get-volume","@DEFAULT_AUDIO_SINK@"],capture_output=True,text=True).stdout
        m=re.search(r"Volume:\s*([0-9.]+)",out); old=float(m.group(1)) if m else None
        subprocess.run(["wpctl","set-volume","@DEFAULT_AUDIO_SINK@",str(target)],check=False)
        return ("wpctl",old)
    if shutil.which("pactl"):
        out=subprocess.run(["pactl","get-sink-volume","@DEFAULT_SINK@"],capture_output=True,text=True).stdout
        m=re.search(r"(\d+)%",out); old=int(m.group(1))/100 if m else None
        subprocess.run(["pactl","set-sink-volume","@DEFAULT_SINK@",f"{round(target*100)}%"],check=False)
        return ("pactl",old)
    return (None,None)

def restore_volume(state):
    tool,old=state
    if tool=="wpctl" and old is not None: subprocess.run(["wpctl","set-volume","@DEFAULT_AUDIO_SINK@",str(old)],check=False)
    elif tool=="pactl" and old is not None: subprocess.run(["pactl","set-sink-volume","@DEFAULT_SINK@",f"{round(old*100)}%"],check=False)

def play_sound(path):
    if not path or not Path(path).is_file():
        notify("Moon", "Sound file not found; playing notification silently.")
        return
    cmd=None
    if shutil.which("paplay"): cmd=["paplay",path]
    elif shutil.which("ffplay"): cmd=["ffplay","-nodisp","-autoexit","-loglevel","quiet",path]
    elif shutil.which("aplay"): cmd=["aplay","-q",path]
    if not cmd:
        notify("Moon", "No supported audio player found.")
        return
    state=set_volume_cap()
    try: subprocess.run(cmd,check=False)
    finally: restore_volume(state)
