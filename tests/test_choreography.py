"""Rendering invariants for the music-led CRT revision."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from player import Canvas, Film, width


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.film = Film()

    def test_running_hud_is_hidden_without_moving_scene_or_subtitles(self):
        for w,h in ((64,24),(80,30),(120,30),(128,44),(180,55)):
            with self.subTest(size=(w,h)):
                hidden = self.film.render(67.3,w,h,hud_visible=False)
                shown = self.film.render(67.3,w,h,hud_visible=True)
                self.assertNotIn('SPACE play/pause', hidden.plain())
                self.assertIn('SPACE play/pause', ''.join(ch for ch,_ in shown.cells[2]))
                self.assertEqual(hidden.cells[3:], shown.cells[3:])

    def test_every_caption_is_complete_in_last_two_rows(self):
        for w,h in ((64,24),(80,30),(120,30),(128,44),(180,55)):
            for cue in self.film.lyrics:
                t=cue['time']+min(.05,(cue['end']-cue['time'])/2)
                with self.subTest(size=(w,h),time=t):
                    c=self.film.render(t,w,h,hud_visible=False)
                    self.assertEqual(''.join(ch for ch,_ in c.cells[-2]).strip(),cue['en'])
                    self.assertEqual(''.join(ch for ch,_ in c.cells[-1]).strip(),cue['zh'])
                    self.assertTrue(all(ch in ' ._:=|' for ch,_ in c.cells[-3]))

    def test_spectrum_has_own_row_above_captions(self):
        for w,h in ((64,24),(80,30),(120,30),(128,44),(180,55)):
            with self.subTest(size=(w,h)):
                with patch.object(self.film,'energy',return_value=[1.]*48), \
                     patch('scenes.draw_scene'), patch('scenes.phosphor'):
                    c=self.film.render(67.3,w,h,hud_visible=False)
                self.assertEqual(''.join(ch for ch,_ in c.cells[-3]).strip(),'|'*min(80,w-8))
                self.assertTrue(all(ch==' ' for row in c.cells[1:-3] for ch,_ in row))

    def test_scene_bounds_reserve_exactly_three_footer_rows(self):
        for w,h in ((64,24),(80,30),(120,30),(128,44),(180,55)):
            bounds=[]
            def scene(c,t,top,bottom,music,cue):
                bounds.append((top,bottom))
                c.put(2,bottom,'BODY BOTTOM')
                c.put(2,bottom+1,'LEAK')
            with patch('scenes.draw_scene',side_effect=scene), patch('scenes.phosphor'):
                for state in ({},{'paused':True},{'help_on':True},{'ready':True}):
                    c=self.film.render(67.3,w,h,hud_visible=False,**state)
                    self.assertNotIn('LEAK',c.plain())
                    if not state:self.assertIn('BODY BOTTOM',''.join(ch for ch,_ in c.cells[h-4]))
            self.assertEqual(bounds,[(1,h-4)]*4)

    def test_title_uses_same_expanded_scene_area(self):
        for w,h in ((64,24),(120,30),(128,44)):
            def title(c,*args):
                self.assertEqual(c.h,h-4)
                c.put(2,c.h-1,'TITLE BOTTOM')
            with patch('scenes.title_takeover',side_effect=title):
                c=self.film.render(23.5,w,h,hud_visible=False)
            self.assertIn('TITLE BOTTOM',''.join(ch for ch,_ in c.cells[h-4]))

    def test_footer_stays_clear_of_paused_help_and_interludes(self):
        for w,h in ((64,24),(80,30),(120,30),(128,44),(180,55)):
            for t in (23.5,67.3,93.2,211.8):
                normal=self.film.render(t,w,h,hud_visible=False)
                for state in ({'paused':True},{'help_on':True}):
                    with self.subTest(size=(w,h),time=t,state=state):
                        shown=self.film.render(t,w,h,**state)
                        self.assertEqual(normal.cells[-3:],shown.cells[-3:])

    def test_paused_and_help_show_controls(self):
        self.assertIn('SPACE play/pause', self.film.render(67.3,128,44,paused=True).plain())
        self.assertIn('CONTROLS', self.film.render(67.3,128,44,help_on=True).plain())

    def test_wide_character_overwrite_keeps_grid_valid(self):
        c = Canvas(8, 1)
        c.put(1, 0, '中文')
        c.put(2, 0, 'x')
        self.assertEqual(c.cells[0][1][0], ' ')
        self.assertEqual(c.cells[0][2][0], 'x')
        self.assertEqual(width(c.plain()), 8)
        c.put(3, 0, 'a')
        self.assertEqual(c.cells[0][4][0], ' ')
        self.assertEqual(width(c.plain()), 8)

    def test_caption_offset_does_not_retime_animation(self):
        a=self.film.render(113.0,128,44,offset=0,hud_visible=False)
        b=self.film.render(113.0,128,44,offset=1,hud_visible=False)
        self.assertEqual(a.cells[:-2],b.cells[:-2])

    def test_scaled_bitmap_preserves_strokes_and_column_width(self):
        c=Canvas(30,20)
        c.big(2,'A',scale=2)
        self.assertEqual(''.join(ch for ch,_ in c.cells[2][10:20]),'  ######  ')
        self.assertEqual(c.cells[2],c.cells[3])
        self.assertEqual(width(c.plain().splitlines()[2]),30)

    def test_bitmap_protection_does_not_restore_over_later_status_line(self):
        c=Canvas(80,24)
        c.big(3,'LOVE')
        status='P(LOVE) -> 1.0 / ALL OTHER TOKENS SUPPRESSED'
        c.put(2,8,status)
        c.restore_protected()
        self.assertIn(status,c.plain())


class GeometryTests(unittest.TestCase):
    def test_circle_reaches_readable_scale_before_second_half(self):
        from scenes import lyric_circle_circumference
        from music import MusicState
        for w,h in ((64,24),(80,30),(120,30),(128,44),(180,55)):
            with self.subTest(size=(w,h)):
                c=Canvas(w,h)
                top,bottom=1,h-8
                c.clip=(top,bottom)
                lyric_circle_circumference(c,35.0,(2,top,w-3,bottom),35.0-33.412,MusicState(time=35))
                ys=[y for y,row in enumerate(c.cells) for ch,_ in row if ch in ('o','●','○','◉')]
                extent=max(ys)-min(ys)+1
                self.assertGreaterEqual(extent,(bottom-top+1)*.55)
                self.assertLessEqual(extent,(bottom-top+1)*.78)


class MusicalSceneTests(unittest.TestCase):
    def state(self,t,kind,starts,labels=None,**kwargs):
        from music import MusicEvent, MusicState
        labels=labels or [kind.upper()]*len(starts)
        return MusicState(time=t,cues=tuple(MusicEvent(at,kind,label) for at,label in zip(starts,labels)),**kwargs)

    def test_each_execution_has_one_readable_numbered_hit(self):
        from scenes import lyric_execution_queue
        starts=(147.66,148.6,149.52,150.54,151.52,152.28,153.16,153.98,155.2,156.08,157.04,158.0)
        for index,at in enumerate(starts):
            for age in (0,.033,.25,.5):
                with self.subTest(hit=index+1,age=age):
                    c=Canvas(128,44);c.clip=(1,36)
                    lyric_execution_queue(c,at+age,(2,1,125,36),self.state(at+age,'execution',starts))
                    self.assertIn(f'EXECUTION {index+1:02d}/12',c.plain())
                    self.assertIn(('QUEUE','OVERWRITE','LOCK')[index//4],c.plain())
                    self.assertGreater(sum(ch=='#' for row in c.cells[15:22] for ch,_ in row),70)

    def test_first_four_hits_have_distinct_subject_motion(self):
        from scenes import lyric_execution_queue
        starts=(147.66,148.6,149.52,150.54,151.52,152.28,153.16,153.98,155.2,156.08,157.04,158.0)
        shapes=[]
        for at in starts[:4]:
            c=Canvas(128,44);c.clip=(1,36)
            lyric_execution_queue(c,at+.1,(2,1,125,36),self.state(at+.1,'execution',starts))
            shapes.append(frozenset((x,y) for y,row in enumerate(c.cells) if 10<=y<=26
                                    for x,(ch,_) in enumerate(row) if ch=='#'))
        self.assertEqual(len(set(shapes)),4,'The four queue hits must not repeat one unchanged word pose')

    def test_disconnect_count_changes_on_each_lyric_not_before(self):
        from scenes import lyric_isolation_disconnect
        starts=(110.9,112.22,113.1,114.18,114.92,115.78)
        for index,at in enumerate(starts):
            for delta,want in ((-.001,index),(.001,index+1)):
                c=Canvas(128,44);c.clip=(1,36)
                lyric_isolation_disconnect(c,at+delta,(2,1,125,36),self.state(at+delta,'disconnect',starts))
                self.assertIn(f'LOST {want:02d}/06',c.plain())

    def test_ecg_uses_musical_phase(self):
        from music import MusicState
        from scenes import lyric_vibration_sync
        a=Canvas(128,44);b=Canvas(128,44)
        lyric_vibration_sync(a,105.0,(2,1,125,36),MusicState(time=105,beat_position=10))
        lyric_vibration_sync(b,105.0,(2,1,125,36),MusicState(time=105,beat_position=11))
        self.assertNotEqual(a.cells,b.cells)
        self.assertIn('HALF TIME',a.plain())

    def test_final_execution_starts_at_anchor_and_decays(self):
        from music import MusicEvent,MusicState
        from scenes import lyric_outro_wait
        cues=(MusicEvent(192.5,'transition','outro_start'),MusicEvent(205.811,'transition','final_execution'))
        frames=[]
        for t in (205.810,205.812,211.5):
            c=Canvas(128,44);c.clip=(1,36)
            lyric_outro_wait(c,t,(2,1,125,36),MusicState(time=t,cues=cues))
            frames.append(c)
        count=lambda c:sum(ch!=' ' and style==4 for row in c.cells for ch,style in row)
        self.assertEqual(count(frames[0]),0)
        self.assertGreater(count(frames[1]),80)
        self.assertLess(count(frames[2]),count(frames[1])//5)

    def test_title_releases_into_same_initial_point_set(self):
        from music import MusicEvent,MusicState
        from player import FONT
        from scenes import title_takeover,lyric_points_dimension
        cues=tuple(MusicEvent(at,'transition',label) for at,label in ((16,'title_scatter'),(19.1,'title_gather'),(22.9,'title_lock'),(27.35,'title_release'),(29.709,'point_handoff')))
        title=Canvas(128,36)
        title_takeover(title,29.709,FONT,MusicState(time=29.709,cues=cues))
        points=Canvas(128,36)
        lyric_points_dimension(points,29.709,(2,0,125,35),0,MusicState(time=29.709))
        expected={(x,y) for y,row in enumerate(points.cells) for x,(ch,_) in enumerate(row) if ch in ('*','+','·')}
        actual={(x,y) for y,row in enumerate(title.cells) for x,(ch,_) in enumerate(row) if ch in ('*','+','·')}
        self.assertEqual(actual,expected)


class TimelineRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.film=Film()

    def test_every_event_boundary_at_all_supported_sizes(self):
        times={0.,15.8,29.709,33.412,37.067,40.706,44.452,47.672,51.363,55.083,
               59.223,62.589,66.601,70.084,74.045,85.078,88.587,92.015,95.465,
               99.349,103.489,110.9,118.333,125.708,147.66,158.9,162.632,
               177.246,188.483,192.5,205.811,211.906667}
        times.update(e.time for e in self.film.music.at(0).cues)
        for w,h in ((64,24),(80,30),(120,30),(128,44),(180,55)):
            for at in sorted(times):
                for delta in (-1/60,0,1/60):
                    t=max(0,at+delta)
                    with self.subTest(size=(w,h),time=t):
                        c=self.film.render(t,w,h,hud_visible=False)
                        self.assertEqual(len(c.cells),h)
                        for row in c.cells:
                            self.assertEqual(len(row),w)
                            for x,(char,style) in enumerate(row):
                                if char=='':
                                    self.assertGreater(x,0)
                                    self.assertEqual(width(row[x-1][0]),2)
                                elif width(char)==2:
                                    self.assertLess(x+1,w)
                                    self.assertEqual(row[x+1][0],'')

    def test_seek_order_and_pause_do_not_change_scene(self):
        times=(0.7,12.5,16.1,23.5,29.709,35,67.3,80,105,113.1,124.95,135,150.6,159.85,183.2,206,211.8)
        expected={t:self.film.render(t,128,44,hud_visible=False).cells for t in times}
        for t in reversed(times):
            self.assertEqual(self.film.render(t,128,44,paused=True,hud_visible=False).cells,expected[t])

    def test_execution_glyph_survives_all_post_effects(self):
        from scenes import lyric_execution_queue
        for event in self.film.music.at(0).events('execution'):
            t=event.time+.033
            direct=Canvas(128,44);direct.clip=(1,40)
            lyric_execution_queue(direct,t,(2,1,125,40),self.film.music.at(t))
            final=self.film.render(t,128,44,hud_visible=False)
            for (x,y),cell in direct.protected.items():
                self.assertEqual(final.cells[y][x],cell,(event.time,x,y))

    def test_small_execution_fallback_is_protected_from_glitch(self):
        for frame in range(24):
            c=self.film.render(172.712+frame/60,64,24,hud_visible=False)
            body='\n'.join(''.join(ch for ch,_ in row) for row in c.cells[1:-3])
            self.assertIn('EXECUTION',body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
