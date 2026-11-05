"""Qt-free authoritative checks for every 4- and 5-photo layout."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DOC=json.loads((ROOT/'photo_page'/'geometry.json').read_text(encoding='utf-8'))
CAPTION=float(DOC['caption_reserve_mm'])
COUNTS={'portrait':(4,9),'landscape':(4,8),'square':(2,12)}
count=0
for family,doc in DOC['families'].items():
    W,H=doc['page_width_mm'],doc['page_height_mm']
    expected4,expected5=COUNTS[family]
    layouts=doc['layouts']
    assert sum(k.startswith('four-') for k in layouts)==expected4
    assert sum(k.startswith('five-') for k in layouts)==expected5
    for name,photos in layouts.items():
        count+=1
        expected=4 if name.startswith('four-') else 5
        assert len(photos)==expected,(family,name,len(photos))
        for i,p in enumerate(photos):
            x,y,w,h=(p[k] for k in ('x','y','w','h'))
            assert w>0 and h>0
            assert abs(w/h-{'3:4':0.75,'4:3':4/3}[p['ratio']]) < 0.0001,(family,name,i,'ratio',p)
            assert x>=14.999 and y>=14.999,(family,name,i,'margin start',p)
            assert x+w <=W-14.999 and y+h+CAPTION<=H-14.999,(family,name,i,'margin end',p)
            for j,q in enumerate(photos[:i]):
                qx,qy,qw,qh=(q[k] for k in ('x','y','w','h'))
                overlap_w=min(x+w,qx+qw)-max(x,qx)
                overlap_h=min(y+h+CAPTION,qy+qh+CAPTION)-max(y,qy)
                assert overlap_w <= 0.001 or overlap_h <= 0.001,(family,name,j,i,'OVERLAP')
assert count==39,count
print(f'PASS: {count} layouts, precise 3:4/4:3 ratios, no overlap, 15-mm safe area and caption bands')
