"""Program actions, role colors and musical milestones in the full film."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from player import Canvas,Film
from music import MusicState
import scenes
import visuals as v


class StoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.film=Film()

    def test_role_palette_is_present_in_active_program_scenes(self):
        for t in (9.5,31.9,35.5,39.,43.,46.3,54.,57.8,61.,67.3,86.5,90.,93.6,97.7,108.5,164.,167.8,171.2):
            with self.subTest(time=t):
                c=self.film.render(t,128,44,hud_visible=False)
                inks={ink for row in c.cells[1:-3] for ch,ink in row if ch.strip()}
                self.assertTrue(inks & {v.CYAN,v.CYAN_HIGH},t)
                self.assertTrue(inks & {v.ME,v.N,v.W},t)

    def test_boot_highlight_and_visible_parameter_state_agree(self):
        writing=self.film.render(9.5,128,44,hud_visible=False).plain()
        ready=self.film.render(10.5,128,44,hud_visible=False).plain()
        self.assertIn('> parameters.write(ME, YOU);',writing)
        self.assertIn('PARAMS 075%',writing)
        self.assertIn('> initialize(ME, YOU);',ready)
        self.assertIn('PARAMS 100%',ready)

    def test_boot_active_call_is_visible_below_startup_controls(self):
        for t,call in ((.2,'power.on();'),(.4,'memory.protect();')):
            shown=self.film.render(t,128,44,hud_visible=True)
            self.assertIn('> '+call,shown.plain())

    def test_error_interlude_has_three_beat_anchored_escalations_and_a_quiet_release(self):
        anchors=((135.991,1),(139.702,2),(143.843,3))
        for at,stage in anchors:
            for delta,want in ((-.001,stage-1),(.001,stage)):
                with self.subTest(time=at+delta):
                    c=Canvas(128,44);c.clip=(1,40)
                    scenes.lyric_illegal_arguments(c,at+delta,(2,1,125,40),MusicState(time=at+delta))
                    self.assertIn(f'RETRY DEPTH {want:02d}',c.plain())
        for delta,quiet in ((-.001,False),(.001,True)):
            c=Canvas(128,44);c.clip=(1,40)
            scenes.lyric_illegal_arguments(c,147.515+delta,(2,1,125,40),MusicState(time=147.515+delta))
            self.assertEqual('QUIESCE' in c.plain(),quiet)

    def test_disconnection_is_one_remote_object_losing_six_links(self):
        first=self.film.render(111.,128,44,hud_visible=False)
        final=self.film.render(117.6,128,44,hud_visible=False)
        self.assertIn('LOST 01/06',first.plain())
        self.assertIn('LOST 06/06',final.plain())
        self.assertNotIn('YOU_1',first.plain())
        self.assertTrue(any(ch.strip() and ink==v.CYAN for row in first.cells for ch,ink in row))
        self.assertFalse(any(ch.strip() and ink in (v.CYAN,v.CYAN_HIGH) for row in final.cells for ch,ink in row))

    def test_you_are_free_while_me_is_still_trapped(self):
        before=self.film.render(188.5,128,44,hud_visible=False)
        after=self.film.render(190.4,128,44,hud_visible=False)
        self.assertTrue(any(ch.strip()and ink==v.CYAN for row in before.cells for ch,ink in row))
        self.assertIn('TRAPPED',after.plain())
        self.assertIn('ME',after.plain())
        self.assertFalse(any(ch.strip()and ink in(v.CYAN,v.CYAN_HIGH) for row in after.cells for ch,ink in row))

    def test_error_role_labels_survive_the_composed_title_at_every_size(self):
        for w,h in ((64,24),(80,30),(120,30),(128,44),(180,55)):
            for t in (131.224,135.991,139.702,143.843,147.5):
                with self.subTest(size=(w,h),time=t):
                    c=self.film.render(t,w,h,hud_visible=False)
                    for role,ink in (('ME',v.ME),('YOU',v.YOU)):
                        self.assertTrue(any(
                            all(row[x+i]==(ch,ink) for i,ch in enumerate(role))
                            for row in c.cells[1:h-3]
                            for x in range(w-len(role)+1)),role)

    def test_waiting_roles_are_wholly_inside_the_body_on_small_grids(self):
        class RecordingCanvas(Canvas):
            def __init__(self,w,h):
                super().__init__(w,h);self.requests=[]
            def put(self,x,y,text,style=v.N):
                self.requests.append((x,y,str(text),style))
                super().put(x,y,text,style)
        for w,h in ((64,24),(80,30),(120,30),(128,44),(180,55)):
            area=(2,1,w-3,h-4)
            for t in (192.5,201.,205.8):
                with self.subTest(size=(w,h),time=t):
                    c=RecordingCanvas(w,h);c.clip=(1,h-4)
                    scenes.lyric_outro_wait(c,t,area,self.film.music.at(t))
                    for x,y,text,ink in c.requests:
                        if ink in (v.ME,v.ME_DIM,v.YOU_DIM) and text in ('#','.','ME','YOU'):
                            self.assertGreaterEqual(int(x),area[0])
                            self.assertLessEqual(int(x)+len(text)-1,area[2])
                            self.assertGreaterEqual(int(y),area[1])
                            self.assertLessEqual(int(y),area[3])
                    shown=self.film.render(t,w,h,hud_visible=False)
                    for role,ink in (('ME',v.ME_DIM if t>=197.5 else v.ME),('YOU',v.YOU_DIM)):
                        self.assertTrue(any(
                            all(row[x+i]==(ch,ink) for i,ch in enumerate(role))
                            for row in shown.cells[1:h-3]
                            for x in range(w-len(role)+1)),role)

    def test_final_wait_is_a_missing_return_value_and_finishes_at_the_original_cue(self):
        a=self.film.render(201.,128,44,hud_visible=False)
        b=self.film.render(205.811,128,44,hud_visible=False)
        self.assertIn('ACK: --',a.plain())
        self.assertIn('99%',a.plain())
        self.assertIn('await',a.plain())
        self.assertGreater(sum(ch.strip()!=''and ink==v.R for row in b.cells for ch,ink in row),80)


if __name__=='__main__':unittest.main(verbosity=2)
