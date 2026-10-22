"""Small semantic mistakes must be observable in actual composed frames."""
import ast
import math
import re
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from player import Canvas,Film
from music import MusicState
import scenes
import scenes_learning as learning
import visuals as v


class PolishDetailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.film=Film()

    def test_parameters_wait_for_the_write_call_and_finish_before_initialization(self):
        for t,call,percent in ((7.6,'YOU = allocate();','000'),
                               (7.7,'parameters.write(ME, YOU);','000'),
                               (9.5,'parameters.write(ME, YOU);','075'),
                               (10.091,'initialize(ME, YOU);','100')):
            with self.subTest(time=t):
                shown=self.film.render(t,128,44,hud_visible=False).plain()
                self.assertIn('> '+call,shown)
                self.assertIn('PARAMS '+percent+'%',shown)

    def test_protection_is_not_reported_active_before_the_shield_closes(self):
        self.assertNotIn('PROTECTION ACTIVE',self.film.render(2.,128,44,hud_visible=False).plain())
        self.assertIn('PROTECTION ACTIVE',self.film.render(3.,128,44,hud_visible=False).plain())

    def test_gender_highlight_tracks_the_visible_write_completion(self):
        for t,statement in ((89.5,'ME.gender = F;'),(90.5,'rewrite(ME.gender);'),
                            (91.,'rewrite(ME.gender);'),(91.6,'ME.gender = M;')):
            with self.subTest(time=t):
                self.assertIn('> '+statement,self.film.render(t,128,44,hud_visible=False).plain())

    def test_tangent_strokes_follow_terminal_y_direction(self):
        class RecordingCanvas(Canvas):
            def __init__(self):super().__init__(128,44);self.requests=[]
            def put(self,x,y,text,style=v.N):
                self.requests.append((x,y,text,style));super().put(x,y,text,style)
        c=RecordingCanvas();area=(2,1,125,40);t=38.2
        scenes.lyric_sine_tangent(c,t,area,t-37.067,MusicState(time=t))
        span=area[2]-area[0];amp=(area[3]-area[1])*.28
        for x,y,text,style in c.requests:
            if text not in ('/','\\'):continue
            # Each short stroke belongs to the closest of the four current tangent points.
            candidates=[]
            for i in range(4):
                px=area[0]+span*i/4
                a=(px-area[0])/span*math.tau*2.5-t*.5
                py=(area[1]+area[3])//2+math.sin(a)*amp
                slope=math.cos(a)*amp/span*math.tau*2.5
                candidates.append((abs(y-(py+slope*(x-px))),slope))
            slope=min(candidates)[1]
            self.assertEqual(text,'\\' if slope>0 else '/')

    def test_lines_connect_points_that_were_already_created(self):
        a=Canvas(128,44);b=Canvas(128,44);area=(2,1,125,40)
        scenes.lyric_points_dimension(a,29.709,area,0,MusicState(time=29.709))
        scenes.lyric_points_dimension(b,30.9,area,1.191,MusicState(time=30.9))
        points={(x,y) for y,row in enumerate(a.cells) for x,(ch,_) in enumerate(row) if ch in ('*','+','·')}
        endpoints={(x,y) for y,row in enumerate(b.cells) for x,(ch,_) in enumerate(row) if ch=='●'}
        self.assertTrue(endpoints)
        self.assertTrue(endpoints<=points,endpoints-points)

    def test_narrow_simulation_and_execution_cards_keep_complete_calls(self):
        for w,h in ((64,24),(80,30),(120,30),(128,44),(180,55)):
            for t in (71.9,73.3,164.,167.8,171.2,175.1):
                with self.subTest(size=(w,h),time=t):
                    c=self.film.render(t,w,h,hud_visible=False)
                    selected=[(''.join(ch for ch,_ in row)[x:]) for row in c.cells
                              for x in range(w-1) if row[x][0]=='>' and row[x+1][0]==' ']
                    self.assertTrue(selected)
                    calls=[match.group(1) for text in selected
                           if (match:=re.match(r'^> ([A-Za-z_]\w*\([^)]*\);?)',text))]
                    self.assertTrue(calls,selected)
                    for call in calls:ast.parse(call)

    def test_nonzero_eos_probability_is_described_as_suppressed_not_blocked(self):
        state=learning.learning_state(187.9)
        self.assertGreater(state.probabilities[-1],0.)
        c=self.film.render(187.9,128,44,hud_visible=False)
        self.assertNotIn('EOS blocked',c.plain())
        self.assertIn('EOS LOW',c.plain())


if __name__=='__main__':unittest.main(verbosity=2)
