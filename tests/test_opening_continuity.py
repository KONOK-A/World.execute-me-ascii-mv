"""Preserve actual scene geometry and character provenance across the opening."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from player import Canvas,Film,FONT
import scenes
import visuals as v

SIZES=((64,24),(80,30),(120,30),(128,44),(180,55))


class OpeningContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.film=Film()

    def test_title_begins_with_the_actual_last_simulation_frame(self):
        for w,h in SIZES:
            with self.subTest(size=(w,h)):
                source=self.film.render(15.999,w,h,hud_visible=False)
                start=self.film.render(16.,w,h,hud_visible=False)
                self.assertEqual(source.cells[1:-3],start.cells[1:-3])
                self.assertEqual(''.join(ch for ch,_ in start.cells[-2]).strip(),'world.execute(me);')

    def test_first_title_frame_keeps_visible_source_cells_near_their_origins(self):
        for w,h in SIZES:
            with self.subTest(size=(w,h)):
                source=self.film.render(15.999,w,h,hud_visible=False)
                next_frame=self.film.render(16.+1/30,w,h,hud_visible=False)
                cells=[(x,y,cell) for y,row in enumerate(source.cells[1:-3],1)
                       for x,cell in enumerate(row) if cell[0].strip()]
                retained=sum(next_frame.cells[y][x]==cell for x,y,cell in cells)
                self.assertGreater(retained/len(cells),.90)

    def test_simulation_keeps_the_cores_docked_at_the_vocal_boundary(self):
        for w,h in SIZES:
            for role,ink in (('ME',v.ME),('YOU',v.YOU)):
                with self.subTest(size=(w,h),role=role):
                    positions=[]
                    for t in (13.890,13.891):
                        c=self.film.render(t,w,h,hud_visible=False)
                        positions.append(next((x,y) for y,row in enumerate(c.cells[3:-3],3)
                                              for x in range(w-len(role)+1)
                                              if all(row[x+i]==(ch,ink) for i,ch in enumerate(role))))
                    self.assertLessEqual(sum(abs(a-b) for a,b in zip(*positions)),1)

    def test_source_is_read_only_and_scrubbing_does_not_change_the_opening(self):
        source=Canvas(128,40);source.put(10,20,'ME -> SIMULATION -> YOU',v.CYAN)
        saved=[row[:] for row in source.cells]
        out=Canvas(128,40)
        scenes.title_takeover(out,16.4,FONT,self.film.music.at(16.4),source)
        self.assertEqual(source.cells,saved)
        for w,h in SIZES:
            times=(.4,2.9,4.5,9.5,12.5,13.891,14.7,16.,16.4,18.5,19.216327,21.2,22.907937)
            expected={t:self.film.render(t,w,h,hud_visible=False).cells for t in times}
            for t in reversed(times):
                self.film.render(t+1/24,w,h,hud_visible=False)
                self.assertEqual(expected[t],self.film.render(t,w,h,paused=True,hud_visible=False).cells)


if __name__=='__main__':unittest.main(verbosity=2)
