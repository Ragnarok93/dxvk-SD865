"""Join render attachments to timestamped Vulkan view lifetimes; not a GPU cost profiler."""
import argparse
from bisect import bisect_right
from collections import Counter,defaultdict
import json
from pathlib import Path
import re
FIELD=re.compile(r'([a-z_]+)=([^\s]+)')
def summarize(lines_factory):
    lifetimes=defaultdict(list)
    for line in lines_factory():
        if 'DXVK-FF7R-VIEW-CREATE ' in line or 'DXVK-FF7R-VIEW-DESTROY ' in line:
            f=dict(FIELD.findall(line));f['created']='VIEW-CREATE' in line
            lifetimes[int(f['image_view'])].append((int(f['ts_us']),f))
    ordered={v:sorted(events,key=lambda e:e[0]) for v,events in lifetimes.items()}
    times={v:[t for t,f in events] for v,events in ordered.items()}
    groups=Counter();missing=Counter();matched=0
    for line in lines_factory():
        if 'DXVK-FF7R-ATTACHMENT ' not in line:continue
        f=dict(FIELD.findall(line))
        if f.get('bound')!='1':continue
        if 'image_view' not in f:missing['attachment_identity_absent']+=1;continue
        v=int(f['image_view']);ts=int(f['ts_us']);idx=bisect_right(times.get(v,[]),ts)-1
        if idx<0:missing['creation_record_absent']+=1;continue
        resource=ordered[v][idx][1]
        if not resource['created']:missing['view_destroyed_at_record_time']+=1;continue
        key=(resource['image'],resource['format'],resource['mip_index'],resource['layer_index'],f['aspect'],f['load_op'],f['store_op'])
        groups[key]+=1;matched+=1
    return dict(scope='CPU-recorded attachment use joined to view/image identities and formats; counts are not GPU cost, bytes, or proof of redundant work',view_lifetimes_recorded=sum(len(e) for e in ordered.values()),matched_bound_aspect_records=matched,unmatched=dict(missing),groups=[dict(image=image,format=int(fmt),mip_index=int(mip),layer_index=int(layer),aspect=aspect,load_op=int(load),store_op=int(store),count=n) for (image,fmt,mip,layer,aspect,load,store),n in groups.most_common()])
def analyze(text):return summarize(lambda:iter(text.splitlines()))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('log',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    def lines():
        with a.log.open(errors='replace') as f:yield from f
    report=json.dumps(summarize(lines),indent=2)
    if a.output:
        with a.output.open('x') as f:f.write(report+'\n')
    else:print(report)
if __name__=='__main__':main()
