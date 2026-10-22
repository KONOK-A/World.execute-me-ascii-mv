"""Existence impact and the surrounding playback invariants."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from player import Film,Canvas
import scenes
import visuals as v

SIZES=((64,24),(80,30),(120,30),(128,44),(180,55))


class IdentityExpressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.film=Film()

    def test_proof_must_arrive_before_the_world_is_confirmed(self):
        for t,confirmed in ((85.8,False),(86.538,False),(87.7,False),(87.922,True),(88.3,True)):
            with self.subTest(time=t):
                shown=self.film.render(t,128,44,hud_visible=False)
                self.assertEqual('WORLD ACTIVE' in shown.plain(),confirmed)
                self.assertEqual('> ME.manifest();' in shown.plain(),confirmed)
        shown=self.film.render(88.1,128,44,hud_visible=False)
        self.assertGreater(sum(ch=='#' and ink==v.W for row in shown.cells[26:39] for ch,ink in row),80)

    def test_roles_words_and_captions_survive_at_all_sizes(self):
        for w,h in SIZES:
            for t in (86.7,88.1,90.6,93.6,96.5,98.4,100.3,102.3):
                with self.subTest(size=(w,h),time=t):
                    c=self.film.render(t,w,h,hud_visible=False)
                    for role,ink in (('ME',v.ME),('YOU',v.YOU)):
                        self.assertTrue(any(all(row[x+i]==(ch,ink) for i,ch in enumerate(role))
                                            for row in c.cells[3:-3] for x in range(w-len(role)+1)),role)
                    cue=self.film.cue(t)
                    self.assertEqual(''.join(ch for ch,_ in c.cells[-2]).strip(),cue['en'])

    def test_existence_music_response_and_surrounding_playback_are_deterministic(self):
        for t,draw in ((86.8,lambda c,m:scenes.lyric_god_existence(c,86.8,(2,1,125,40),1.722,m)),):
            m=self.film.music.at(t)
            a=Canvas(128,44);b=Canvas(128,44)
            draw(a,replace(m,beat=0.,low=.1,mid=.1))
            draw(b,replace(m,beat=1.,low=1.,mid=1.))
            self.assertNotEqual(a.cells,b.cells)
        for w,h in SIZES:
            for t in (86.8,88.1,90.6,94.2,96.5,98.5,100.4,102.3):
                expected=self.film.render(t,w,h,hud_visible=False).cells
                self.film.render(t+.3,w,h,hud_visible=False)
                self.assertEqual(expected,self.film.render(t,w,h,paused=True,hud_visible=False).cells)


if __name__=='__main__':unittest.main(verbosity=2)
