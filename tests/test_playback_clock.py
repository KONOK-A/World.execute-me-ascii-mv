"""Replay observed device states through the real playback loop and renderer."""
import io
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import player


class PlaybackClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.film=player.Film()

    def replay(self,positions,keys=None):
        duration=211.98365
        states=[{'time':position,'duration':duration,'playing':playing} for position,playing in positions]
        class Device:
            index=0
            error=''
            proc=SimpleNamespace(poll=lambda:None)
            @property
            def state(self):return states[self.index]
            @property
            def last(self):return time.monotonic()
            def command(self,_):pass
            def close(self):pass
        device=Device()
        class Terminal:
            def size(self):return 129,44
            def read_keys(self,_):
                if device.index==len(states)-1:return 'q'
                key=(keys or {}).get(device.index,'')
                device.index+=1
                return key
        rendered=[]
        render=self.film.render
        def capture(t,*args,**kwargs):
            canvas=render(t,*args,**kwargs)
            rendered.append((t,canvas.plain()))
            return canvas
        with tempfile.TemporaryDirectory() as folder:
            audio=Path(folder)/'external-device.wav';audio.touch()
            args=SimpleNamespace(audio=str(audio),offset=None,autoplay=True,paused=False,
                                 start=positions[0][0],fps=30,stop_after=None,report=None)
            with patch.object(player,'Audio',lambda _:device),patch.object(self.film,'render',capture),patch('sys.stdout',io.StringIO()):
                player.play(args,self.film,Terminal())
        return rendered

    def test_transient_playing_zero_at_eof_does_not_render_boot(self):
        frames=self.replay(((211.829,True),(0,True),(211.98365,False)))
        self.assertEqual([t for t,_ in frames],[211.829,211.829,211.98365])
        self.assertNotIn('POWER / CHECK',frames[1][1])

    def test_stopped_zero_at_eof_keeps_the_final_scene(self):
        frames=self.replay(((211.829,True),(0,False),(211.96365,False)))
        self.assertEqual(frames[1][0],211.98365)
        self.assertNotIn('POWER / CHECK',frames[1][1])

    def test_restart_accepts_zero_even_before_playing_acknowledgement(self):
        frames=self.replay(((211.829,True),(0,False),(0,False),(.1,True)),{0:'r'})
        self.assertEqual([t for t,_ in frames],[211.829,0,0,.1])
        self.assertIn('POWER / CHECK',frames[1][1])

    def test_chapter_seek_is_not_mistaken_for_eof_rewind(self):
        for key,target in (('1',0),('2',29.709),('5',177.246)):
            with self.subTest(key=key):
                frames=self.replay(((211.98365,False),(target,True),(target+.1,True)),{0:key})
                self.assertEqual(frames[1][0],target)


if __name__=='__main__':unittest.main(verbosity=2)
