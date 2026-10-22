"""Regression checks for the simulation cue and previously static music breaks."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from music import MusicEvent,MusicState
from player import Canvas,Film,FONT
import scenes
import visuals as v


SIZES=((64,24),(80,30),(120,30),(128,44),(180,55))


class SceneMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.film=Film()

    def test_simulation_start_follows_the_vocal_cue_instead_of_a_fixed_timer(self):
        cue=MusicEvent(14.1,'accent','SIMULATION')
        for t,started in ((14.099,False),(14.1,True),(14.133,True)):
            c=Canvas(128,44);c.clip=(1,40)
            scenes.lyric_boot_program(c,t,(2,1,125,40),MusicState(time=t,cues=(cue,)))
            self.assertEqual('> WORLD.simulate();' in c.plain(),started)
            pixels=sum(ch=='#' and ink==v.W for row in c.cells[12:30] for ch,ink in row)
            self.assertGreater(pixels,100) if started else self.assertLess(pixels,100)

    def test_first_simulation_has_a_visible_hit_and_keeps_its_full_phrase(self):
        for t in (13.891,14.3,15.85,15.99):
            with self.subTest(time=t):
                c=self.film.render(t,128,44,hud_visible=False)
                self.assertIn('> WORLD.simulate();',c.plain())
                self.assertGreater(sum(ch=='#' and ink==v.W for row in c.cells[12:30]
                                       for ch,ink in row),100)

    def test_instrumental_motion_responds_to_music_beyond_a_blinking_status(self):
        for kind,t in (('title',24.1),('retry',141.2),('wait',201.1)):
            state=self.film.music.at(t)
            calm=replace(state,beat_position=50.1,beat=0.,low=.15,mid=.1,onset=.05)
            hit=replace(state,beat_position=50.7,beat=.9,low=.85,mid=.65,onset=.8)
            for w,h in SIZES:
                with self.subTest(scene=kind,size=(w,h)):
                    frames=[]
                    for music in (calm,hit):
                        c=Canvas(w,h);c.clip=(1,h-4)
                        if kind=='title':
                            # Film composites this local canvas into the body at row 1.
                            c=Canvas(w,h-4)
                            scenes.title_takeover(c,t,FONT,music)
                        elif kind=='retry':
                            scenes.lyric_illegal_arguments(c,t,(2,1,w-3,h-4),music)
                        else:
                            scenes.lyric_outro_wait(c,t,(2,1,w-3,h-4),music)
                            self.assertIn('99%',c.plain())
                            self.assertIn('ACK: --',c.plain())
                        frames.append(c)
                    changed=sum(a!=b for row_a,row_b in zip(frames[0].cells,frames[1].cells)
                                for a,b in zip(row_a,row_b))
                    self.assertGreater(changed,w*(h-4)*.012)

    def test_termination_keeps_dissolving_after_audio_features_end(self):
        for w,h in SIZES:
            with self.subTest(size=(w,h)):
                a=self.film.render(209.8,w,h,hud_visible=False)
                b=self.film.render(210.3,w,h,hud_visible=False)
                changed=sum(x!=y for row_a,row_b in zip(a.cells[3:-3],b.cells[3:-3])
                            for x,y in zip(row_a,row_b))
                self.assertGreater(changed,20)

    def test_new_motion_uses_audio_time_and_is_stable_when_paused_or_seeking(self):
        for w,h in SIZES:
            for t in (14.4,24.4,141.4,201.4,209.4):
                with self.subTest(size=(w,h),time=t):
                    expected=self.film.render(t,w,h,hud_visible=False)
                    for dt in (-1/24,1/30,-1.,2.):
                        self.film.render(t+dt,w,h,hud_visible=False)
                    self.assertEqual(expected.cells,self.film.render(
                        t,w,h,paused=True,hud_visible=False).cells)


if __name__=='__main__':unittest.main(verbosity=2)
