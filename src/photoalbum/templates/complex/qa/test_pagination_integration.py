"""Tests patched Photo Album engine against the actual Complex selector."""
from datetime import datetime,timedelta
from pathlib import Path
from photoalbum.album import (
    AlbumPlan,PlanItem,PlanItemKind,PaginationEngine,TemplateRegistry,TemplateKind,
    TemplateDefinition,AutomaticPhotoPageModeDefinition,AutomaticPhotoPageSettings,
    PhotoPageSettings,AlbumStructureSettings,DividerSettings,PageInstance,PhotoPageOverride,PageOrientation
)
from photoalbum.models import Photo
registry=TemplateRegistry()
for n in range(1,6):
    registry.register(TemplateDefinition(f'complex-photo-{n}',f'Complex {n}',frozenset({TemplateKind.PHOTO_PAGE}),photo_capacity=n,pack_id='complex'))
registry.register_automatic_photo_page_mode(AutomaticPhotoPageModeDefinition(
    mode_id='complex-auto-1-5',name='Complex 1–5',pack_id='complex',pack_name='Complex',
    template_ids=tuple(f'complex-photo-{n}' for n in range(1,6)),settings_template_id='complex-photo-1',
    selector_reference='photoalbum.templates.complex.photo_page.automatic:select_automatic_1_5'))
mode=AutomaticPhotoPageSettings('complex-auto-1-5')
settings=AlbumStructureSettings(covers={},day_dividers=DividerSettings(False,'day'),month_dividers=DividerSettings(False,'month'),year_dividers=DividerSettings(False,'year'),photo_pages=PhotoPageSettings(automatic_mode=mode))
photos=tuple(Photo(path=Path(f'/tmp/sample{i:02}.jpg'),filename=f'sample{i:02}.jpg',width=4000,height=3000,
                   capture_datetime=datetime(2025,1,1)+timedelta(minutes=i)) for i in range(20))
plan=AlbumPlan([PlanItem(kind=PlanItemKind.PHOTO_GROUP,template_id=None,photos=photos,automatic_photo_page_mode=mode)])
engine=PaginationEngine(registry)
def variants(result):
    return [p.page_instance.settings.get('layout_variant') for p in result.pages if p.photos]

expected=['five-sequence-top','five-sequence-center','five-sequence-bottom','five-sequence-top']
assert variants(engine.paginate(plan,settings))==expected
assert variants(engine.paginate(plan,settings))==expected  # SAME engine object; reset
assert engine._automatic_variant_counts=={('portrait','LLLLL'):4}
# User-selected middle page must not advance the rotation.
settings.photo_page_overrides=[PhotoPageOverride(photos[5].identity,PageInstance('complex-photo-5',settings={'layout_variant':'five-sequence-bottom'}))]
assert variants(engine.paginate(plan,settings))==['five-sequence-top','five-sequence-bottom','five-sequence-center','five-sequence-bottom']
assert engine._automatic_variant_counts=={('portrait','LLLLL'):3}
# Manual BEFORE any automatic page also doesn't consume first choice.
settings.photo_page_overrides=[PhotoPageOverride(photos[0].identity,PageInstance('complex-photo-5',settings={'layout_variant':'five-sequence-center'}))]
assert variants(engine.paginate(plan,settings))==['five-sequence-center','five-sequence-top','five-sequence-center','five-sequence-bottom']
# This does NOT change other format/signature counts.
settings.photo_page_overrides=[]
settings.orientation=PageOrientation.LANDSCAPE
assert variants(engine.paginate(plan,settings))==['five-sequence-top','five-sequence-bottom','five-sequence-top','five-sequence-bottom']
assert engine._automatic_variant_counts=={('landscape','LLLLL'):4}
print('PASS: Real pagination: cyclic rotation, manual interleaving, repeated regeneration, format isolation')
