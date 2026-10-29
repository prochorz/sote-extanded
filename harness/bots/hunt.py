"""Boot the patched ROM, enter level L from the carousel, enable debug
invincibility, then let a 'hunter' bot play with the patched controls.
Records shots (every 2nd VI), input/label log and audio (run/hunt_<tag>.json/.raw/.wav)."""
import sys,os,math,json,struct,random,ctypes as C, wave
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from m64 import *; from inject import syms
from game import boot_events, play_events, unlock_levels
ROM=sys.argv[1]; L=int(sys.argv[2]); PLAY=int(sys.argv[3]); TAG=sys.argv[4]
S=syms(); e=Emu(ROM)
AUD=C.CDLL(os.environ['AUDIOPLUGIN']) if os.environ.get('AUDIOPLUGIN') else None
if AUD: AUD.audio_dump_frames.restype=C.c_long
ev,T0=boot_events(L)
OUT=os.path.join(RUN,f'hunt_{TAG}')
st=dict(log=[],phase='intro',t=0,last=None,stuck=0,bias=0,bias_t=0,blocked={},nolock=0,label='',seq=[])
def wrap(a): return (a+180)%360-180
def enemies(e,pl):
    pool=0x80112838; cnt=e.r32(pool+8); sd=e.r32(pool+12); base=e.r32(pool+16); out=[]
    if not (0<cnt<1024): return out
    px,py=e.rf(pl+0x50),e.rf(pl+0x54)
    for i in range(cnt):
        r=base+i*sd; ob=e.r32(r+0x98)
        if not (0x80000000<=ob<0x80800000) or not (e.r16(r+0x68)&2) or not e.r32(r+0x84): continue
        if not (e.r16(ob+6)&2) or not (e.rf(ob+0x60)>0) or tag(e.r32(ob)) in ('Boxx','Anim','Humn','Boss'): continue
        x,y=e.rf(ob+0x50),e.rf(ob+0x54); d=math.hypot(x-px,y-py)
        if d<400 and abs(e.rf(ob+0x58)-e.rf(pl+0x58))<12: out.append((d,ob,x,y))
    return sorted(out)
def finish(e):
    json.dump(st['log'],open(OUT+'.json','w'))
    if AUD:
        AUD.audio_dump_stop(); data=open(OUT+'.raw','rb').read()
        w=wave.open(OUT+'.wav','wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(AUD.audio_dump_freq()); w.writeframes(data); w.close()
    e.stop()
def script(e,n):
    if n==1: e.unlimit()
    if 1600<n<2900 and n%30==0: unlock_levels(e)
    if n<T0:
        play_events(e,ev,n); return
    k=n-T0; b=0; x=y=0
    pl=e.r32(S['g_player'])
    if pl and 0x80000000<=pl<0x80800000: e.w32(pl+0xB4, struct.unpack('<I',struct.pack('<f',100.0))[0])   # health (HUD) kept full
    gate=e.rf(0x800DEB78)>0 or e.rf(0x800E0EA0)>0
    if st['phase']=='intro':
        # 1) dismiss communicator messages while they are up, 2) once the screen has
        # been message-free for 2 s: pause -> debug menu -> Invincibility -> resume.
        if not st.get('menu_at'):
            if gate:
                st['calm']=0
                if k%90<6: b=BTN['START']
            else:
                st['calm']=st.get('calm',0)+1
                if st['calm']>60 and k>200:
                    st['menu_at']=k
                    st['seq']=[]
        else:
            t=k-st['menu_at']
            for t0,nm in st['seq']:
                if 0<=t-t0<6: b|=BTN[nm]
            if t>10:
                st['phase']='play'; st['t']=k
                if AUD: AUD.audio_dump_start((OUT+'.raw').encode())
        e.pad(b,0,0); return
    ov=e.r32(S['g_ov_frames']); dov=e.r32(S['g_decode_ov'])
    if k%3000==0: print(TAG,'raw k',k,'lvl',hex(e.r16(0x8013CE0E)),'ov-dov',ov-dov,'shots',len(st['log'])//2,flush=True)
    if ov-dov>5:                                   # cutscene / dialogue: advance with A, don't record
        st['t']+=1
        st['idle']=st.get('idle',0)+1
        if st['idle']==1800:                       # 30 s without control: give up on this level
            e.shot(); print(TAG,'STUCK, ending level early',flush=True)
        if st['idle']>1810: finish(e); return
        if AUD: AUD.audio_dump_pause(1)
        e.pad(BTN['A'] if k%40<6 else 0,0,0); return
    if AUD: AUD.audio_dump_pause(0)
    st['idle']=0
    kk=k-st['t']
    if gate and kk%90<6: b|=BTN['START']; st['label']='Skip message'
    elif pl:
        px,py=e.rf(pl+0x50),e.rf(pl+0x54); face=e.rf(pl+0x8C)+90
        lk=e.r32(S['g_lock']); en=[t for t in enemies(e,pl) if t[1] not in st['blocked'] or st['blocked'][t[1]]<kk]
        lazy=e.rf(S['g_cam_facing'])
        def stick(want,mag=80):
            a=math.radians(want-lazy); return int(-math.sin(a)*mag),int(math.cos(a)*mag)
        if lk and st.get('release',0)>0:
            st['release']-=1; lk=0
        elif lk:
            hp=e.rf(lk+0x60)
            if st.get('lk')!=lk: st['lk']=lk; st['lkhp']=hp; st['lkt']=kk
            if hp<st['lkhp']-0.01: st['lkhp']=hp; st['lkt']=kk
            if kk-st['lkt']>150:                        # no damage in 5 s: give up on it
                st['blocked'][lk]=kk+900; st['release']=20; lk=0
        if lk:
            st['nolock']=0; b|=BTN['Z']
            x=70 if (kk//80)%2==0 else -70
            if (kk//6)%2==0: b|=BTN['B']
            if kk%240<20: y=40
            st['label']='Z-target: strafe + fire'
        elif en:
            d,ob,tx,ty=en[0]; bear=math.degrees(math.atan2(ty-py,tx-px)); err=wrap(bear-face)
            if d<90:
                st['nolock']+=1
                if abs(err)>30: x,y=stick(bear,25); st['label']='Turn toward enemy'
                elif st['nolock']%14<9: b|=BTN['Z']; st['label']='Z: lock on'
                else: st['label']='Z: lock on'
                if st['nolock']>30: st['blocked'][ob]=kk+900; st['nolock']=0
            else:
                st['nolock']=0
                want=bear+st['bias']; x,y=stick(want); st['label']='Hunting the next enemy'
                if kk%300<12 and kk>60: b|=BTN['A']                 # hop now and then
        else:
            # nobody near: roam forward, turning away from walls
            want=face+st['bias']; x,y=stick(want); st['label']='Exploring'
        if kk%10==0:
            if st['last'] and math.hypot(px-st['last'][0],py-st['last'][1])<0.8 and (x or y) and not lk:
                st['stuck']+=1
                if st['stuck']>=2: st['bias']=random.Random(kk).choice([70,-70,120,-120]); st['bias_t']=kk; st['stuck']=0
            else: st['stuck']=0
            if st['bias'] and kk-st['bias_t']>80: st['bias']=0
            st['last']=(px,py)
    e.pad(b,x,y)
    ent=dict(k=kk,b=b,x=x,y=y,label=st['label'],shot=(kk%2==0))
    if AUD: ent['aud']=AUD.audio_dump_frames()
    st['log'].append(ent)
    if kk%2==0: e.shot()
    if kk%600==0: print(TAG,'k',kk,'lvl',hex(e.r16(0x8013CE0E)),'locks', sum(1 for q in st['log'] if q['label'].startswith('Z-target')),flush=True)
    if kk>=PLAY: finish(e)
e.run(script)
