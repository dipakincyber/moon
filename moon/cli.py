import argparse, sys, time, tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta
from .core import load, save, parse_date, parse_time, prompt_time, notify, render, play_sound, SOUNDS_DIR, AUDIO_EXTS
from .sheets import SheetsError, get_period_store

def ask(label, default=""):
    v=input(f"{label}{' ['+default+']' if default else ''}: ").strip()
    return v or default

def choose_time_gui():
    try:
        w=tk.Tk(); w.title("Moon — Choose time"); w.resizable(False,False)
        f=ttk.Frame(w,padding=14); f.grid(); ttk.Label(f,text="Choose a time").grid(row=0,column=0,columnspan=3,pady=6)
        h=tk.StringVar(value="08"); m=tk.StringVar(value="00"); ap=tk.StringVar(value="AM"); result=[]
        ttk.Spinbox(f,from_=1,to=12,width=4,textvariable=h,wrap=True).grid(row=1,column=0)
        ttk.Label(f,text=":").grid(row=1,column=1)
        ttk.Spinbox(f,from_=0,to=59,width=4,textvariable=m,wrap=True).grid(row=1,column=2)
        ttk.Combobox(f,textvariable=ap,values=("AM","PM"),state="readonly",width=5).grid(row=2,column=0,columnspan=3,pady=7)
        def ok():
            try:
                hh=int(h.get()); mm=int(m.get())
                if not 1<=hh<=12 or not 0<=mm<=59: raise ValueError
                result.append(f"{(hh%12)+(12 if ap.get()=='PM' else 0):02d}:{mm:02d}"); w.destroy()
            except ValueError: messagebox.showerror("Invalid time","Choose a valid hour and minute.")
        ttk.Button(f,text="Cancel",command=w.destroy).grid(row=3,column=0); ttk.Button(f,text="Use time",command=ok).grid(row=3,column=2)
        w.mainloop(); return result[0] if result else None
    except tk.TclError: return None

def choose_date_gui():
    import calendar
    try:
        w=tk.Tk(); w.title("Moon — Calendar"); w.resizable(False,False)
        today=date.today(); state={"y":today.year,"m":today.month}; result=[]
        outer=ttk.Frame(w,padding=10); outer.grid(); head=ttk.Frame(outer); head.grid(row=0,column=0,columnspan=7)
        grid=ttk.Frame(outer); grid.grid(row=1,column=0,columnspan=7)
        def draw():
            for x in head.winfo_children()+grid.winfo_children(): x.destroy()
            def shift(n):
                v=state['m']+n; state['y']+=(v-1)//12; state['m']=(v-1)%12+1; draw()
            ttk.Button(head,text="‹",command=lambda:shift(-1)).grid(row=0,column=0)
            ttk.Label(head,text=f"{calendar.month_name[state['m']]} {state['y']}",width=18,anchor="center").grid(row=0,column=1)
            ttk.Button(head,text="›",command=lambda:shift(1)).grid(row=0,column=2)
            for c,n in enumerate(("Mo","Tu","We","Th","Fr","Sa","Su")): ttk.Label(grid,text=n,width=4,anchor="center").grid(row=0,column=c)
            first,days=calendar.monthrange(state['y'],state['m'])
            for d in range(1,days+1):
                r=1+(first+d-1)//7; c=(first+d-1)%7
                ttk.Button(grid,text=str(d),width=3,command=lambda day=d:pick(day)).grid(row=r,column=c,padx=1,pady=1)
        def pick(day): result.append(date(state['y'],state['m'],day).isoformat()); w.destroy()
        draw(); w.mainloop(); return result[0] if result else None
    except tk.TclError: return None

def named_sound(stem):
    if SOUNDS_DIR.exists():
        for f in sorted(SOUNDS_DIR.iterdir()):
            if f.is_file() and f.stem.lower()==stem and f.suffix.lower() in AUDIO_EXTS: return str(f)
    return None

def main():
    if len(sys.argv)>1 and sys.argv[1]=="help": sys.argv[1]="--help"
    p=argparse.ArgumentParser(prog="moon",description="A private personal companion CLI")
    sub=p.add_subparsers(dest="cmd",required=True)
    t=sub.add_parser("track",help="Record a period entry")
    t.add_argument("date"); t.add_argument("note",nargs="?",default=""); t.add_argument("feedback",nargs="?",default=""); t.add_argument("--time",default="")
    r=sub.add_parser("report",help="Show period entries for a date"); r.add_argument("date",nargs="?")
    msg=sub.add_parser("message",help="Manage daily messages"); ms=msg.add_subparsers(dest="message_cmd",required=True)
    mset=ms.add_parser("set"); mset.add_argument("date"); mset.add_argument("text")
    ms.add_parser("show")
    h=sub.add_parser("hydration",aliases=["hydrate"],help="Configure a hydration reminder")
    h.add_argument("--stop",action="store_true"); h.add_argument("--sound")
    a=sub.add_parser("alarm",help="Manage alarms"); ass=a.add_subparsers(dest="alarm_cmd",required=True)
    aset=ass.add_parser("set"); aset.add_argument("--time"); aset.add_argument("--sound")
    al=ass.add_parser("list"); ass.add_parser("clear")
    sub.add_parser("daemon",help="Run scheduled messages, hydration, and alarms")
    sub.add_parser("set-volume",aliases=["volume"],help="Set music volume for headphones and speakers")
    args=p.parse_args()
    data=load()
    try:
        if args.cmd in ("set-volume","volume"):
            prefs=data.setdefault("volumes",{"headphones":49,"speakers":80})
            print(f"Current headphone/earphone volume: {prefs.get('headphones',49)}%")
            print(f"Current speaker volume: {prefs.get('speakers',80)}%")
            for key,label in (("headphones","Headphones / Bluetooth earphones"),("speakers","Speakers")):
                val=int(ask(f"Set {label} music volume (0-100)",str(prefs.get(key,49 if key=="headphones" else 80))))
                if not 0<=val<=100: raise ValueError("Volume must be between 0 and 100.")
                prefs[key]=val
            save(data); print("Music volumes saved.")
        elif args.cmd=="track":
            d=parse_date(args.date); stamp=parse_time(args.time) if args.time else datetime.now().strftime("%H:%M")
            entry={"date":d,"note":args.note,"feedback":args.feedback,"time":stamp}
            store=get_period_store()
            if store:
                action=store.save(entry)
                print(f"Period entry {action} for {d} at {stamp} in Google Sheets.")
            else:
                data["period"]=[x for x in data["period"] if not (x.get("date")==d and x.get("time")==stamp)]
                data["period"].append(entry); save(data); print(f"Saved period entry for {d} at {stamp} to local JSON.")
        elif args.cmd=="report":
            d=parse_date(args.date) if args.date else (choose_date_gui() or parse_date(ask("Date (e.g. 2026-09-27)")))
            store=get_period_store()
            entries=store.report(d) if store else [x for x in data["period"] if x.get("date")==d]
            print(f"Moon report — {d}\n"+("-"*30))
            if not entries: print("No entries for this date.")
            for x in entries: print(f"Time: {x.get('time','')}\nNote: {x.get('note','')}\nFeedback: {x.get('feedback','')}\nRecorded at: {x.get('recorded_at','')}\n")
        elif args.cmd=="message":
            if args.message_cmd=="set":
                d=parse_date(args.date); data["messages"][d]=args.text; save(data); print(f"Message saved for {d}.")
            else:
                print("No messages configured." if not data["messages"] else "\n".join(f"{k}: {v}" for k,v in sorted(data["messages"].items())))
        elif args.cmd in ("hydration","hydrate"):
            if args.stop: data["hydration"]=None; save(data); print("Hydration reminders stopped.")
            else:
                mode=ask("Reminder type: once or interval","interval").lower()
                if mode not in ("once","interval"): raise ValueError("Choose once or interval.")
                at=(choose_time_gui() or prompt_time("Reminder time")) if mode=="once" else ""
                minutes=0 if mode=="once" else int(ask("Repeat every how many minutes","30"))
                if mode=="interval" and minutes<1: raise ValueError("Interval must be at least 1 minute.")
                sound=args.sound or ask("Sound path (blank uses sounds/hydration.*)") or named_sound("hydration")
                data["hydration"]={"mode":mode,"time":at,"minutes":minutes,"sound":sound,"next":""}
                save(data); print("Hydration reminder configured. Run 'moon daemon' to deliver it.")
        elif args.cmd=="alarm":
            if args.alarm_cmd=="set":
                at=parse_time(args.time) if args.time else (choose_time_gui() or prompt_time("Alarm time"))
                sound=args.sound or ask("Sound path (blank uses sounds/alarm.*)") or named_sound("alarm")
                data["alarms"].append({"time":at,"sound":sound,"enabled":True,"last_fired":""})
                save(data); print(f"Alarm set for {at}. Run 'moon daemon' to deliver it.")
            elif args.alarm_cmd=="list":
                for i,x in enumerate(data["alarms"],1): print(f"{i}. {x['time']} — {x.get('sound') or 'no sound'} — {'on' if x.get('enabled') else 'off'}")
            else: data["alarms"]=[]; save(data); print("All alarms cleared.")
        elif args.cmd=="daemon":
            print("Moon daemon running. Ctrl+C to stop.")
            while True:
                now=datetime.now(); today=now.date().isoformat(); minute=now.strftime("%H:%M")
                # Daily message: one delivery per date, at first daemon check that day.
                if data["messages"].get(today) and data.get("_message_delivered")!=today:
                    notify("Moon 🌙",render(data["messages"][today],now)); data["_message_delivered"]=today; save(data)
                hyd=data.get("hydration")
                if hyd:
                    fire=False
                    if hyd["mode"]=="once":
                        fire=minute==hyd["time"] and hyd.get("last_date")!=today
                        if fire: hyd["last_date"]=today
                    else:
                        if not hyd.get("next"):
                            hyd["next"]=(now+timedelta(minutes=hyd["minutes"])).isoformat(timespec="minutes")
                        try: fire=now>=datetime.fromisoformat(hyd["next"])
                        except ValueError: hyd["next"]=""
                        if fire: hyd["next"]=(now+timedelta(minutes=hyd["minutes"])).isoformat(timespec="minutes")
                    if fire:
                        notify("Moon — Hydration","Time for your hydration reminder.")
                        if hyd.get("sound"): play_sound(hyd["sound"])
                        save(data)
                for alarm in data["alarms"]:
                    if alarm.get("enabled") and minute==alarm["time"] and alarm.get("last_fired")!=today:
                        notify("Moon — Alarm","Your alarm is ringing.")
                        alarm["last_fired"]=today; save(data)
                        if alarm.get("sound"): play_sound(alarm["sound"])
                time.sleep(15)
    except (ValueError, RuntimeError, SheetsError, KeyboardInterrupt) as e:
        if isinstance(e,KeyboardInterrupt): print("\nMoon stopped."); return
        print(f"moon: {e}",file=sys.stderr); raise SystemExit(2)

if __name__=="__main__": main()
