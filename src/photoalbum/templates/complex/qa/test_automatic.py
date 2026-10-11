"""Qt-free selector tests: variants, chronological signatures and per-signature rotation."""
from __future__ import annotations
from dataclasses import dataclass,field
import importlib,json,sys
from pathlib import Path
from types import ModuleType
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1]
for name in ('photoalbum','photoalbum.templates','photoalbum.templates.complex','photoalbum.templates.complex.photo_page'):
    mod=ModuleType(name)
    mod.__path__=[str(ROOT/'photo_page')] if name.endswith('photo_page') else [str(ROOT)]
    sys.modules[name]=mod
album=ModuleType('photoalbum.album'); models=ModuleType('photoalbum.models')
@dataclass(frozen=True)
class PageInstance:
    template_id:str
    settings:dict=field(default_factory=dict)
@dataclass(frozen=True)
class AutomaticPhotoPageContext:
    photos:tuple
    page_width_mm:float
    page_height_mm:float
    selection_counts:dict|None=None
album.PageInstance=PageInstance;album.AutomaticPhotoPageContext=AutomaticPhotoPageContext
models.displayed_photo_dimensions=lambda photo:photo
sys.modules['photoalbum.album']=album;sys.modules['photoalbum.models']=models
A=importlib.import_module('photoalbum.templates.complex.photo_page.automatic')
V=importlib.import_module('photoalbum.templates.complex.photo_page.variants')
wh={'portrait':(210,297),'landscape':(297,210),'square':(210,210)}
P=(3000,4000);L=(4000,3000);S=(4000,4000)
def choose(pattern,fmt,counts=None):
    photos=tuple({'P':P,'L':L,'S':S}[p] for p in pattern)
    r=A.select_automatic_1_5(AutomaticPhotoPageContext(photos,*wh[fmt],counts))
    return (r,None) if isinstance(r,str) else (r.template_id,r.settings.get('layout_variant'))

expected5={
'portrait':Counter({'PPPLL':1,'PPLPL':1,'PPLLP':1,'PLLPP':1,'LPLPP':1,'LLPPP':1,'LLLLL':3}),
'landscape':Counter({'PPPLL':2,'PPLLP':1,'PLLPP':1,'LLPPP':2,'LLLLL':2}),
'square':Counter({'PPLPL':1,'PPLLP':1,'PLPPL':2,'PLPLP':2,'PLLPP':1,'LPPPL':2,'LPPLP':2,'LPLPP':1}),
}
expected4={
'portrait':Counter({'PLLL':1,'LPLL':1,'LLPL':1,'LLLP':1}),
'landscape':Counter({'PLLL':2,'LLLP':2}),
'square':Counter({'PLLL':1,'LLLP':1}),
}
for fmt,(w,h) in wh.items():
    sigs5=Counter(''.join(A.signature(5,name,fmt)) for name in V.variants_for(5,w,h))
    sigs4=Counter(''.join(A.signature(4,name,fmt)) for name in V.variants_for(4,w,h))
    assert sigs5==expected5[fmt],(fmt,'five',sigs5,expected5[fmt])
    assert sigs4==expected4[fmt],(fmt,'four',sigs4,expected4[fmt])
    for n,expected in ((4,expected4[fmt]),(5,expected5[fmt])):
        for signature,frequency in expected.items():
            options=A.compatible_options(n,fmt,tuple(signature))
            assert len(options)==frequency,(fmt,signature,options,frequency)
            state={}
            for i in range(frequency*3):
                actual=choose(signature,fmt,state)
                assert actual==(f'complex-photo-{n}',options[i%frequency]),(fmt,signature,i,actual)
            if frequency>1:
                assert state[(fmt,signature)]==frequency*3
            # Without the host counts, pure selector has no process-global changes.
            assert choose(signature,fmt)[1]==options[0]
    # A square never uses Sequence, even when all images are landscapes.
    if fmt=='square':assert all('sequence' not in v for v in V.variants_for(5,w,h))

# Independently rotating two signatures; manual selection has no call here.
counts={}
assert [choose('LLLLL','portrait',counts)[1] for _ in range(4)] == [
    'five-sequence-top','five-sequence-center','five-sequence-bottom','five-sequence-top']
assert choose('PPLPL','portrait',counts)[1]=='five-mosaic-left'
assert counts[('portrait','LLLLL')]==4
assert ('portrait','PPLPL') not in counts # unique candidate: no rotation needed
# 5>4>3>2>1 + unknown/square fallback and DO NOT reorder.
assert choose('PLLLP','portrait')[0]=='complex-photo-4'
assert choose('PS','landscape')[0]=='complex-photo-1'
assert choose('LLLLL','square')[0]=='complex-photo-2'
assert choose('LPLL','landscape')[0]!='complex-photo-4'

manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
assert len(manifest['automatic_photo_page_modes'])==1
assert manifest['automatic_photo_page_modes'][0]['id']=='complex-auto-1-5'
for source in ROOT.rglob('*.py'):
    if source.name != 'test_automatic.py':
        assert 'photoalbum.templates.msb' not in source.read_text(encoding='utf-8'),source
print('PASS: 29 five-photo variants, 10 reportage variants, all compatible patterns, round-robin, greedy fallback')
