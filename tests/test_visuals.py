"""Semantic colors and deterministic program-world drawing primitives."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from player import Canvas
import player
import visuals as v


class VisualPrimitiveTests(unittest.TestCase):
    def test_palette_keeps_original_style_ids_and_has_distinct_roles(self):
        self.assertIs(player.STYLES,v.STYLES)
        self.assertEqual(set(range(8))-v.STYLES.keys(),set())
        self.assertEqual(v.ME,2)
        self.assertNotEqual(v.ME,v.YOU)
        for role in (v.ME,v.YOU,v.ROSE,v.R,v.W,v.CYAN_DIM):
            self.assertRegex(v.STYLES[role],r'^\x1b\[[01];38;5;\d+m$')

    def test_actor_shape_color_and_label_identify_each_object(self):
        for role,ink in (('ME',v.ME),('YOU',v.YOU)):
            c=Canvas(64,24);c.clip=(1,20)
            box=v.actor(c,32,12,role,radius=3)
            self.assertIn(role,c.plain())
            cells={(x,y)for y,row in enumerate(c.cells)for x,(ch,_)in enumerate(row)if ch.strip()}
            self.assertTrue(cells)
            self.assertTrue(all(box[0]<=x<=box[2]and box[1]<=y<=box[3]for x,y in cells))
            self.assertTrue(any(style==ink for row in c.cells for ch,style in row if ch.strip()))
            twin=Canvas(64,24);twin.clip=c.clip
            v.actor(twin,32,12,role,radius=3)
            self.assertEqual(c.cells,twin.cells)
        me=Canvas(64,24);you=Canvas(64,24)
        v.actor(me,32,12,'ME',radius=3);v.actor(you,32,12,'YOU',radius=3)
        self.assertNotEqual(me.cells,you.cells)

    def test_code_card_keeps_active_step_visible_and_limits_rows(self):
        lines=('me = allocate();','you = allocate();','me.connect(you);','result = you.reply();','assert(result);')
        for w,h,limit in ((64,24,2),(120,30,2),(128,44,4),(180,55,4)):
            c=Canvas(w,h);c.clip=(1,h-4)
            box=v.code_card(c,(2,1,w-3,h-4),lines,4)
            self.assertLessEqual(box[3]-box[1]+1,limit)
            self.assertIn('> assert(result);',c.plain())
            self.assertTrue(c.protected)
            self.assertTrue(all(len(row)==w for row in c.cells))

    def test_signal_has_one_deterministic_head_moving_towards_receiver(self):
        a=Canvas(64,24);b=Canvas(64,24)
        v.signal(a,(8,12),(52,12),.25,ink=v.YOU)
        v.signal(b,(8,12),(52,12),.75,ink=v.YOU)
        ax=next(x for x,(ch,_)in enumerate(a.cells[12])if ch=='>')
        bx=next(x for x,(ch,_)in enumerate(b.cells[12])if ch=='>')
        self.assertLess(ax,bx)


if __name__=='__main__':unittest.main(verbosity=2)
