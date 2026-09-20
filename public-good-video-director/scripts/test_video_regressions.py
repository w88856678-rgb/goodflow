"""Offline regressions for whole-sentence captions and opaque-card occlusion."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'assets/runtime/src'))
from pg_video import caption_chunks, make_captions, material_hash
from validate_visual_layout import validate

def box(x=0, y=0, width=100, height=100, **extra):
    return dict(x=x, y=y, width=width, height=height, **extra)

def sample():
    return {'scenes': 1, 'records': [dict(scene_id=1, time=.5,
        opaqueCards=[box()], protected=[box(20,20,60,60)],
        overlays=[box(140,20,200,50,text='一个完整说明')],
        captions=[box(100,1600,880,150,text='戴上小红花头像框，一块做好事。')],
        captionLines=[box(120,1620,840,60,text='戴上小红花头像框，一块做好事。',scrollWidth=820,clientWidth=840)])]}

class CaptionTests(unittest.TestCase):
    def test_long_sentence_not_cut_at_comma(self):
        sentence = '这些善意来自日常生活中的一件小事，'*8+'一起行动。'
        self.assertEqual(caption_chunks(sentence, max_chars=10), [sentence])

    def test_existing_timed_clauses_preserved(self):
        data={'captions':[{'from':1,'to':3,'text':'戴上小红花头像框，','lines':['戴上小红花头像框，']},
                          {'from':3,'to':5,'text':'一块做好事。','lines':['一块做好事。']}]}
        self.assertEqual(make_captions('戴上小红花头像框，一块做好事。', 5, data), data['captions'])

    def test_explicit_lines_do_not_create_new_timestamps(self):
        text='9月3日至9日，一块做好事。'
        rows=make_captions(text,4,{'captions':[{'from':0,'to':4,'text':text,'lines':['9月3日至9日，','一块做好事。']}]})
        self.assertEqual(len(rows),1)
        self.assertEqual(''.join(rows[0]['lines']),text)
        self.assertEqual((rows[0]['from'],rows[0]['to']),(0,4))

    def test_changed_line_text_rejected(self):
        with self.assertRaises(ValueError):
            make_captions('一块做好事。',3,{'captions':[{'from':0,'to':3,'text':'一块做好事。','lines':['一块做好事！']}]})

    def test_template_change_invalidates_approval_hash(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            (p/'project.json').write_text(json.dumps({'rendering':{'template':'layout.html'},'assets':{}}))
            (p/'layout.html').write_text('<main>original</main>')
            before=material_hash(p)
            (p/'layout.html').write_text('<main>changed layout</main>')
            self.assertNotEqual(before,material_hash(p))

class GeometryTests(unittest.TestCase):
    def test_safe_layout(self):
        self.assertTrue(validate(sample())['passed'])

    def test_white_border_occlusion_even_when_image_does_not_overlap(self):
        data=sample();data['records'][0]['overlays']=[box(2,20,12,30,text='被白边挡住')]
        result=validate(data)
        self.assertFalse(result['passed'])
        self.assertTrue(any(e.get('group')=='opaqueCards' for e in result['errors']))
        self.assertFalse(any(e.get('group')=='protected' for e in result['errors']))

    def test_empty_capture_not_pass(self):
        self.assertFalse(validate({'scenes':1,'records':[]})['passed'])

    def test_legacy_capture_without_whole_card_bounds_not_pass(self):
        data=sample();del data['records'][0]['opaqueCards']
        self.assertFalse(validate(data)['passed'])

    def test_missing_scene_not_pass(self):
        data=sample();data['scenes']=2
        self.assertFalse(validate(data)['passed'])

    def test_line_overflow(self):
        data=sample();data['records'][0]['captionLines'][0]['scrollWidth']=1000
        self.assertFalse(validate(data)['passed'])

    def test_caption_over_source(self):
        data=sample();data['records'][0]['captions']=[box(30,30,200,50)]
        self.assertFalse(validate(data)['passed'])

    def test_caption_outside_canvas(self):
        data=sample();data['records'][0]['captions'][0]['y']=1900
        self.assertFalse(validate(data)['passed'])

    def test_nonfinite_geometry_rejected(self):
        data=sample();data['records'][0]['opaqueCards'][0]['x']=float('nan')
        self.assertFalse(validate(data)['passed'])

if __name__ == '__main__':
    unittest.main()
