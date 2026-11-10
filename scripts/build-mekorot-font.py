"""Build the LPPL-derived Mekorot-Rashi Folio font; requires fonttools.
Original glyph outlines, advances, GSUB, final-kaf and furtive-patah rules remain.
See the bundled CHANGES.md and upstream sources for provenance and license.
"""
from pathlib import Path
import copy, hashlib, json
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.otlLib.builder import buildAnchor, buildMarkBasePosSubtable
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/'public/fonts/collection/mekorotrashi'
if not DIR.exists():DIR=Path(__file__).resolve().parent
f=TTFont(DIR/'Mekorot-Rashi.ttf',recalcTimestamp=False)
cmap=f.getBestCmap(); gpos=f['GPOS'].table; glyphs=f['glyf']; base_positions={}
for name,record in zip(gpos.LookupList.Lookup[3].SubTable[0].BaseCoverage.glyphs,gpos.LookupList.Lookup[3].SubTable[0].BaseArray.BaseRecord):
    base_positions[name]=[(a.XCoordinate,a.YCoordinate) for a in record.BaseAnchor]
# Keep established horizontal placement; give below-base vowels ink clearance
# on the few non-final letters which descend below the baseline.
finals={cmap[c] for c in [0x5da,0x5dd,0x5df,0x5e3,0x5e5]}
for name,anchors in base_positions.items():
    dy=0 if name in finals else min(0,glyphs[name].yMin+22)
    for i in [0,1]: anchors[i]=(anchors[i][0],dy)
# GSUB can form vav-holam; it must still accept subsequent marks.
if 'uniFB4B' in f.getGlyphOrder():base_positions['uniFB4B']=copy.deepcopy(base_positions[cmap[0x5d5]])
sub=gpos.LookupList.Lookup[3].SubTable[0]
mark_map={n:(r.Class,r.MarkAnchor) for n,r in zip(sub.MarkCoverage.glyphs,sub.MarkArray.MarkRecord)}
mark_map[cmap[0x5ba]]=(2,buildAnchor(0,0))
f['GDEF'].table.GlyphClassDef.classDefs[cmap[0x5ba]]=3
base_map={n:{i:buildAnchor(*a) for i,a in enumerate(anchors)} for n,anchors in base_positions.items()}
gpos.LookupList.Lookup[3].SubTable=[buildMarkBasePosSubtable(mark_map,base_map,f.getReverseGlyphMap())]
# The original only attached hataf vowels on five letters and rafe on ten.
# Cover every base, keeping the three compound vowels centered as a unit.
for index,marks,positions in [
    (4,[0x5b1,0x5b2,0x5b3],{n:{0:buildAnchor(*a[0])} for n,a in base_positions.items()}),
    (1,[0x5bf],{n:{0:buildAnchor(round((glyphs[n].xMin+glyphs[n].xMax)/2),max(185,glyphs[n].yMax+40-715))} for n in base_positions}),
]:
    sub=buildMarkBasePosSubtable({cmap[c]:(0,buildAnchor(0,0)) for c in marks},positions,f.getReverseGlyphMap())
    gpos.LookupList.Lookup[index].SubTable=[sub]
# Add the absent meteg as a zero-advance mark, with a matching stem weight.
name='uni05BD';pen=TTGlyphPen(None)
pen.moveTo((-22,-300));pen.lineTo((22,-300));pen.lineTo((22,-57));pen.lineTo((-22,-57));pen.closePath()
f.setGlyphOrder(f.getGlyphOrder()+[name]);glyphs[name]=pen.glyph();f['hmtx'][name]=(0,-22)
for table in f['cmap'].tables:
    if table.isUnicode():table.cmap[0x5bd]=name
f['maxp'].numGlyphs=len(f.getGlyphOrder())
f['GDEF'].table.GlyphClassDef.classDefs[name]=3
# Compile isolated meteg lookups then merge, preserving all original contextual
# lookups. Mark filtering skips dagesh/shin dots between the vowel and meteg.
below=[cmap[c] for c in list(range(0x5b0,0x5b9))+[0x5bb,0x5c7]]
fea='languagesystem DFLT dflt; languagesystem hebr dflt;\n'
fea+='@below = ['+' '.join(below+[name])+'];\nmarkClass '+name+' <anchor 0 0> @Meteg;\n'
fea+='feature mark {\n'
for n,a in base_positions.items():fea+=f'pos base {n} <anchor {a[0][0]-190} {a[0][1]}> mark @Meteg;\n'
fea+='} mark;\nfeature mkmk { lookupflag UseMarkFilteringSet @below;\n'
for n in below:fea+=f'pos mark {n} <anchor {glyphs[n].xMin-60} 0> mark @Meteg;\n'
fea+='} mkmk;\n'
tmp=copy.deepcopy(f);addOpenTypeFeaturesFromString(tmp,fea,tables={'GPOS','GDEF'})
new=tmp['GPOS'].table;offset=len(gpos.LookupList.Lookup)
gpos.LookupList.Lookup.extend(new.LookupList.Lookup);gpos.LookupList.LookupCount=len(gpos.LookupList.Lookup)
for feature in new.FeatureList.FeatureRecord:
    target=next(r.Feature for r in gpos.FeatureList.FeatureRecord if r.FeatureTag==feature.FeatureTag)
    target.LookupListIndex.extend(offset+i for i in feature.Feature.LookupListIndex);target.LookupCount=len(target.LookupListIndex)
f['GDEF'].table.Version=0x00010002
f['GDEF'].table.MarkGlyphSetsDef=tmp['GDEF'].table.MarkGlyphSetsDef
# Identify this derivative explicitly (LPPL 6a/b), keeping the upstream intact.
family='Mekorot-Rashi Folio'
values={1:family,2:'Regular',3:'Folio:Mekorot-Rashi:1.004',4:family,5:'Version 1.004; Folio niqqud corrections',6:'Mekorot-Rashi-Folio',16:family,17:'Regular'}
for record in f['name'].names:
    if record.nameID in values:record.string=values[record.nameID].encode(record.getEncoding(),errors='replace')
for key,value in values.items():f['name'].setName(value,key,3,1,0x409)
f['name'].setName(f['name'].getDebugName(0)+'\nModified by the Folio project: see CHANGES.md; original authors do not maintain this derivative.',0,3,1,0x409)
f['head'].modified=3866500800
f['hhea'].ascent=max(f['hhea'].ascent,1150);f['OS/2'].usWinAscent=max(f['OS/2'].usWinAscent,1150)
out=DIR/'Mekorot-Rashi-Folio.ttf';f.save(out)
manifest=DIR.parent/'manifest.json';entries=json.loads(manifest.read_text())
entries=[e for e in entries if e['file']!='mekorotrashi/'+out.name]
entries.append({'file':'mekorotrashi/'+out.name,'source':'Folio derivative: scripts/build-mekorot-font.py; see mekorotrashi/CHANGES.md','sha256':hashlib.sha256(out.read_bytes()).hexdigest()})
manifest.write_text(json.dumps(entries,indent=2)+'\n',encoding='utf8',newline='\n')
# Ship the complete derivative source with the font, including offline packages.
source=Path(__file__).resolve()
if source!=DIR/source.name:(DIR/source.name).write_bytes(source.read_bytes())
print(out,entries[-1]['sha256'])
