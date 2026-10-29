"""Scripted demo run: same route and fight, original controls vs the controls patch.
Logs per-frame input + labels for the overlay (run/demo_<mode>.json/.raw/.wav); screenshots every 2nd frame."""
import sys,os,math,json,struct
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths
from m64 import *; from inject import inject, syms
MODE=sys.argv[2]; S=syms(); e=Emu(sys.argv[1]); O=0x801A7B50
import ctypes as _C, wave as _wave
AUD=_C.CDLL(os.environ['AUDIOPLUGIN']) if os.environ.get('AUDIOPLUGIN') else None
OUT=os.path.join(RUN,f'demo_{MODE}'); RAW=OUT+'.raw'
def finish(e):
    json.dump(st['log'],open(OUT+'.json','w'))
    if AUD:
        AUD.audio_dump_stop(); data=open(RAW,'rb').read()
        w=_wave.open(OUT+'.wav','wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(AUD.audio_dump_freq()); w.writeframes(data); w.close()
    e.stop()
ROUTE=[(-338,47),(-317,13),'TURN',(-294,-24),(-263,-64),(-243,-64),(-214,-88)]
st=dict(phase='route',i=0,t0=0,log=[],label='',tgt=None,group='front')
def wrap(a): return (a+180)%360-180
def troops(e,group):
    pool=0x80112838; cnt=e.r32(pool+8); sd=e.r32(pool+12); base=e.r32(pool+16); out=[]
    for i in range(cnt):
        r=base+i*sd; ob=e.r32(r+0x98)
        if 0x80000000<=ob<0x80800000 and e.r16(r+0x68)&2 and e.rf(ob+0x60)>0 and tag(e.r32(ob))=='Trop':
            x,y=e.rf(ob+0x50),e.rf(ob+0x54)
            if (group=='front' and y<-80) or (group=='back' and y>-60 and x>-230): out.append((ob,x,y))
    return out
def facing(e): return e.rf(O+0x8C)+90
def steer(e,want,run=True):
    """Stick that moves Dash toward world angle `want` in the current control scheme."""
    if MODE=='patch':
        a=math.radians(want-e.rf(S['g_cam_facing']))
        return int(-math.sin(a)*80*run), int(math.cos(a)*80*run)
    err=wrap(want-facing(e))
    x=max(-80,min(80,int(-err*3)))
    y=(80 if abs(err)<25 else 30 if abs(err)<60 else 0) if run else 0
    return x,y
def script(e,n):
    if n==60: e.load_state(os.path.join(paths.STATES,'play.st'))
    if n==62 and MODE=='patch':
        inject(e)
        if os.environ.get('SKIPLOS'): e.w32(S['g_test_skip_los'],1)
    if n<70: return
    k=n-70; px,py=e.rf(O+0x50),e.rf(O+0x54); b=0; x=y=0
    if k==0 and AUD:
        AUD.audio_dump_start(RAW.encode())
        if os.environ.get('AUDLOG'): AUD.audio_dump_log(os.environ['AUDLOG'].encode())
    if os.environ.get('LIMITK') and k>=int(os.environ['LIMITK']): finish(e); return
    e.w32(O+0x60, struct.unpack('<I',struct.pack('<f',2.2))[0])     # keep both runs alive
    if st['phase']=='route':
        w=ROUTE[st['i']]
        if w=='TURN':
            st['label']='Turn back'
            if k-st['t0']<70: x,y=steer(e, math.degrees(math.atan2(47-py,-338-px)))
            else: st['i']+=1; st['t0']=k
        else:
            st['label']='Run along the route' if st['i']!=3 else 'Forward again'
            if math.hypot(w[0]-px,w[1]-py)<7:
                st['i']+=1; st['t0']=k
                if st['i']>=len(ROUTE): st['phase']='fight'; st['t0']=k; st['group']='front'
            else: x,y=steer(e, math.degrees(math.atan2(w[1]-py,w[0]-px)))
    elif st['phase']=='fight':
        t=k-st['t0']
        if t>420 and st['group']=='front': st['group']='back'; st['t0']=k; t=0; st['locked_once']=False
        if t>460 and st['group']=='back': st['phase']='end'; st['t0']=k
        tl=troops(e,st['group'])
        if tl:
            ob,tx,ty=min(tl,key=lambda o: math.hypot(o[1]-px,o[2]-py)); bear=math.degrees(math.atan2(ty-py,tx-px))
            err=wrap(bear-facing(e))
            if MODE=='orig':
                # Skip targets our shots can't reach (behind walls): no damage after 60 firing frames.
                bl=st.setdefault('blocked',{})
                live=[o for o in tl if bl.get(o[0],-1)<k]
                if live:
                    ob,tx,ty=min(live,key=lambda o: math.hypot(o[1]-px,o[2]-py))
                    bear=math.degrees(math.atan2(ty-py,tx-px)); err=wrap(bear-facing(e))
                hp=e.rf(ob+0x60)
                if st.get('tgt')!=ob: st['tgt']=ob; st['tgt_hp']=hp; st['fire_t']=0
                if hp<st['tgt_hp']-0.01: st['tgt_hp']=hp; st['fire_t']=0
                where='Enemy ahead' if st['group']=='front' else 'Enemy behind'
                if not live:
                    # Nothing reachable on this side: turn to the other group / finish.
                    if st['group']=='front': st['group']='back'; st['t0']=k
                    else: st['phase']='end'; st['t0']=k
                else:
                    st['label']=where+': turn + fire'
                    x,_=steer(e,bear,run=False)
                    if abs(err)<12:
                        if (k//6)%2==0: b|=BTN['B']
                        st['fire_t']+=1
                        if st['fire_t']>30: bl[ob]=10**9; st['tgt']=None
            else:
                # Stay in place like the original: a target Z can't lock twice is
                # treated as blocked; turn to the next one or to the group behind.
                bl=st.setdefault('pblocked',{})
                lk=e.r32(S['g_lock'])
                live=[o for o in tl if o[0] not in bl]
                if lk: st['nolock']=0
                else: st['nolock']=st.get('nolock',0)+1
                if not lk and st['nolock']>24 and live:
                    ob0=min(live,key=lambda o: math.hypot(o[1]-px,o[2]-py))[0]
                    bl[ob0]=1; st['nolock']=0
                    live=[o for o in live if o[0]!=ob0]
                if not live and not lk:
                    if st['group']=='front': st['group']='back'; st['t0']=k
                    else: st['phase']='end'; st['t0']=k
                else:
                    if live:
                        ob,tx,ty=min(live,key=lambda o: math.hypot(o[1]-px,o[2]-py))
                        bear=math.degrees(math.atan2(ty-py,tx-px)); err=wrap(bear-facing(e))
                    if not lk and abs(err)>25:
                        st['label']='Turn toward enemy'; x,y=steer(e,bear)
                        x,y=x//4,y//4                     # small push: turn in place
                    elif not lk and st['nolock']%12>=8:
                        st['label']='Next target: press Z again'
                    else:
                        b|=BTN['Z']; st['label']='Z-target: strafe + fire' if lk else 'Z: lock on'
                        if lk:
                            x=70 if (t//70)%2==0 else -70
                            if (k//6)%2==0: b|=BTN['B']
        else:
            st['label']='Area clear'
    else:
        st['label']='End'
        if k-st['t0']>60:
            finish(e); return
    e.pad(b,x,y)
    dbg={}
    if st['phase']=='fight' and MODE=='patch':
        tl=troops(e,st['group'])
        if tl:
            ob,tx,ty=min(tl,key=lambda o: math.hypot(o[1]-px,o[2]-py))
            dbg=dict(lock=hex(e.r32(S['g_lock'])),aim=e.r32(S['g_aiming'])>>24,g1=round(e.rf(0x800E0EA0),2),g2=round(e.rf(0x800DEB78),2),
                     tgt=hex(ob),dist=round(math.hypot(tx-px,ty-py),1),err=round(wrap(math.degrees(math.atan2(ty-py,tx-px))-facing(e)),1),hp=round(e.rf(ob+0x60),2),tz=round(e.rf(ob+0x58),1),pz=round(e.rf(O+0x58),1),pad=hex(e.r32(0x80113098)),btn=hex(e.r32(0x801130AC)))
    if AUD: AUD.audio_dump_frames.restype=_C.c_long; dbg['aud']=AUD.audio_dump_frames()
    st['log'].append(dict(k=k,b=b,x=x,y=y,label=st['label'],shot=(k%2==0),**dbg))
    if k%2==0: e.shot()
    if os.environ.get('DIAG') and k>800: json.dump(st['log'],open(OUT+'_diag.json','w')); e.stop(); return
    if k>3000: finish(e)
e.run(script)
