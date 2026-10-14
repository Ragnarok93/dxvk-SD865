"""Render-pass workload proxy; never interprets attachment area as GPU time or bytes."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
FIELD=re.compile(r"([a-z_]+)=([^\s]+)")
def analyze(text):
    passes={}; attachments=[]
    for line in text.splitlines():
        if 'DXVK-FF7R-RENDER-PASS ' in line:
            f=dict(FIELD.findall(line)); pid=int(f['pass'])
            if pid in passes: raise ValueError('duplicate pass ID; do not concatenate process logs')
            p={k:int(f[k]) for k in ['pass','ts_us','width','height','layers','view_mask','colors']}
            if min(p['width'],p['height'],p['layers'],p['view_mask'],p['colors'])<0: raise ValueError('negative Vulkan extent/count')
            passes[pid]=p
        elif 'DXVK-FF7R-ATTACHMENT ' in line:
            attachments.append(dict(FIELD.findall(line)))
    groups={}; orphan=0; seen=set(); totals=Counter()
    for p in passes.values():
        key=(p['width'],p['height'],p['view_mask'].bit_count() if p['view_mask'] else p['layers'])
        g=groups.setdefault(key,Counter());g['passes']+=1
    for f in attachments:
        pid=int(f['pass']); aspect=f['aspect']; index=int(f['index']); key=(pid,aspect,index)
        if key in seen: raise ValueError('duplicate attachment record')
        seen.add(key)
        if aspect not in ('color','depth','stencil'):raise ValueError('unknown attachment aspect')
        if pid not in passes: orphan+=1;continue
        p=passes[pid]
        if int(f['ts_us'])!=p['ts_us']:raise ValueError('mismatched pass timestamp')
        if aspect=='color' and not 0<=index<p['colors']:raise ValueError('invalid color index')
        if int(f['bound'])!=1:totals['unbound_slots']+=1;continue
        key=(p['width'],p['height'],p['view_mask'].bit_count() if p['view_mask'] else p['layers'])
        g=groups[key];g['bound_aspects']+=1
        # Vulkan LOAD=0 and STORE=0, not DONT_CARE/NONE. Depth/stencil aspects
        # sharing a view are separate logical operations, not additive bytes.
        for label,flag in [('load_aspects',int(f['load_op'])==0),('store_aspects',int(f['store_op'])==0),('resolve_aspects',int(f['resolve_mode'])!=0 and int(f['resolve_bound'])==1)]:
            if flag:g[label]+=1
    ranked=[]
    for (w,h,l),g in groups.items():
        ranked.append(dict(width=w,height=h,effective_layers=l,**dict(g),attachment_area_store_proxy=w*h*l*g['store_aspects']))
    ranked.sort(key=lambda g:g['attachment_area_store_proxy'],reverse=True)
    return dict(scope='Recorded render-pass configuration; area proxies are not bytes, GPU execution time, FPS, or proof of redundant work',pass_count=len(passes),orphan_attachment_records=orphan,**dict(totals),groups=ranked)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('log',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    report=json.dumps(analyze(a.log.read_text(errors='replace')),indent=2)
    if a.output:
        with a.output.open('x') as f:f.write(report+'\n')
    else: print(report)
if __name__=='__main__':main()
