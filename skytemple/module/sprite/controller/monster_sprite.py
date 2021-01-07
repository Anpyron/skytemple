#  Copyright 2020-2021 Parakoopa and the SkyTemple Contributors
#
#  This file is part of SkyTemple.
#
#  SkyTemple is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SkyTemple is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SkyTemple.  If not, see <https://www.gnu.org/licenses/>.
import logging
import sys
from typing import TYPE_CHECKING

import cairo

from skytemple.controller.main import MainController
from skytemple.core.error_handler import display_error
from skytemple.core.events.manager import EventManager
from skytemple.core.img_utils import pil_to_cairo_surface
from skytemple.core.model_context import ModelContext
from skytemple_files.common.types.file_types import FileType
from skytemple_files.container.bin_pack.model import BinPack
from skytemple_files.graphics.wan_wat.model import Wan

try:
    from PIL import Image
except:
    from pil import Image
from gi.repository import Gtk, GLib

from skytemple.core.module_controller import AbstractController

if TYPE_CHECKING:
    from skytemple.module.sprite.module import SpriteModule
logger = logging.getLogger(__name__)
FPS = 30


class MonsterSpriteController(AbstractController):
    def __init__(self, module: 'SpriteModule', item_id: int, mark_as_modified_cb):
        self.module = module
        self.item_id = item_id
        self._sprite_provider = self.module.get_sprite_provider()
        self._mark_as_modified_cb = mark_as_modified_cb
        self._frame_counter = 0
        self._anim_counter = 0
        self._drawing_is_active = 0
        self._draw_area = None
        self._monster_bin: ModelContext[BinPack] = self.module.get_monster_bin_ctx()
        self._rendered_frame_info = []

        self.builder = None

    def get_view(self) -> Gtk.Widget:
        if self.item_id < 0:
            return Gtk.Label.new('Invalid Sprite ID.')
        self.builder = self._get_builder(__file__, 'monster_sprite.glade')
        self._draw_area = self.builder.get_object('draw_sprite')
        if self.module.get_gfxcrunch().is_available():
            self.builder.get_object('explanation_text2').set_markup("""Alternatively you can export the sprite files 
in the gfxcrunch format and edit them manually.
Warning: SkyTemple does not validate the files you import.""")
        self.builder.connect_signals(self)

        self._load_frames()
        self.start_sprite_drawing()

        return self.builder.get_object('main_box')

    def start_sprite_drawing(self):
        """Start drawing on the DrawingArea"""
        self._drawing_is_active = True
        self._draw_area.queue_draw()
        GLib.timeout_add(int(1000 / FPS), self._tick)

    def stop_sprite_drawing(self):
        self._drawing_is_active = False

    def _tick(self):
        if self._draw_area is None:
            return False
        if self._draw_area is not None and self._draw_area.get_parent() is None:
            # XXX: Gtk doesn't remove the widget on switch sometimes...
            self._draw_area.destroy()
            return False
        if EventManager.instance().get_if_main_window_has_fous():
            self._draw_area.queue_draw()
        self._frame_counter += 1
        return self._drawing_is_active

    def on_draw_sprite_draw(self, widget: Gtk.DrawingArea, ctx: cairo.Context):
        scale = 4
        sprite, x, y, w, h = self._get_sprite_anim()
        ctx.scale(scale, scale)
        ctx.set_source_surface(sprite)
        ctx.get_source().set_filter(cairo.Filter.NEAREST)
        ctx.paint()
        ww, wh = widget.get_size_request()
        if ww < w or wh < h:
            widget.set_size_request(w * scale, h * scale)
        ctx.scale(1 / scale, 1 / scale)
        return True

    def on_export_clicked(self, w: Gtk.MenuToolButton):
        dialog = Gtk.FileChooserNative.new(
            "Export spritesheet...",
            MainController.window(),
            Gtk.FileChooserAction.SELECT_FOLDER,
            '_Save', None
        )

        response = dialog.run()
        fn = dialog.get_filename()
        dialog.destroy()

        if response == Gtk.ResponseType.ACCEPT:
            try:
                monster = self.module.get_monster_monster_sprite_chara(self.item_id)
                ground = self.module.get_monster_ground_sprite_chara(self.item_id)
                attack = self.module.get_monster_attack_sprite_chara(self.item_id)
                merged = FileType.WAN.CHARA.merge_wan(monster, ground, attack)
                FileType.WAN.CHARA.export_sheets(fn, merged)

                md = Gtk.MessageDialog(MainController.window(),
                                       Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.INFO,
                                       Gtk.ButtonsType.OK, "The spritesheet was successfully exported.",
                                       title="Success!", is_success=True)
                md.run()
                md.destroy()
            except BaseException as e:
                display_error(
                    sys.exc_info(),
                    str(e),
                    "Error exporting the spritesheet."
                )

    def on_import_clicked(self, w: Gtk.MenuToolButton):
        md = Gtk.MessageDialog(MainController.window(),
                               Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.INFO,
                               Gtk.ButtonsType.OK, "To import select the directory of the spritesheets. If it "
                                                   "is still zipped, unzip it first.",
                               title="SkyTemple")
        md.run()
        md.destroy()

        dialog = Gtk.FileChooserNative.new(
            "Import spritesheet...",
            MainController.window(),
            Gtk.FileChooserAction.SELECT_FOLDER,
            None, None
        )

        response = dialog.run()
        fn = dialog.get_filename()
        dialog.destroy()

        if response == Gtk.ResponseType.ACCEPT:
            try:
                wan = FileType.WAN.CHARA.import_sheets(fn)
                monster, ground, attack = FileType.WAN.CHARA.split_wan(wan)

                md = Gtk.MessageDialog(MainController.window(),
                                       Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.INFO,
                                       Gtk.ButtonsType.OK, "The spritesheet was successfully imported.",
                                       title="Success!", is_success=True)
                md.run()
                md.destroy()
                self.module.save_monster_monster_sprite(self.item_id, monster)
                self.module.save_monster_ground_sprite(self.item_id, ground)
                self.module.save_monster_attack_sprite(self.item_id, attack)
                self._mark_as_modified_cb()
                MainController.reload_view()
            except BaseException as e:
                display_error(
                    sys.exc_info(),
                    str(e),
                    "Error importing the spritesheet."
                )

    def on_export_ground_clicked(self, w: Gtk.MenuToolButton):
        self.module.export_a_sprite(self.module.get_monster_ground_sprite_chara(self.item_id, raw=True))

    def on_import_ground_clicked(self, w: Gtk.MenuToolButton):
        sprite = self.module.import_a_sprite()
        self.module.save_monster_ground_sprite(self.item_id, sprite, raw=True)
        self._mark_as_modified_cb()
        MainController.reload_view()

    def on_export_dungeon_clicked(self, w: Gtk.MenuToolButton):
        self.module.export_a_sprite(self.module.get_monster_monster_sprite_chara(self.item_id, raw=True))

    def on_import_dungeon_clicked(self, w: Gtk.MenuToolButton):
        sprite = self.module.import_a_sprite()
        self.module.save_monster_monster_sprite(self.item_id, sprite, raw=True)
        self._mark_as_modified_cb()
        MainController.reload_view()

    def on_export_attack_clicked(self, w: Gtk.MenuToolButton):
        self.module.export_a_sprite(self.module.get_monster_attack_sprite_chara(self.item_id, raw=True))

    def on_import_attack_clicked(self, w: Gtk.MenuToolButton):
        sprite = self.module.import_a_sprite()
        self.module.save_monster_attack_sprite(self.item_id, sprite, raw=True)
        self._mark_as_modified_cb()
        MainController.reload_view()

    def on_explanation_text_activate_link(self, *args):
        self.module.open_spritebot_explanation()

    def on_explanation_text2_activate_link(self, *args):
        self.module.open_gfxcrunch_page()

    def _get_sprite_anim(self):
        current = self._rendered_frame_info[self._anim_counter]
        self._frame_counter += 1
        if self._frame_counter > current[0]:
            self._frame_counter = 0
            self._anim_counter += 1
            if self._anim_counter >= len(self._rendered_frame_info):
                self._anim_counter = 0
        return current[1]

    def _load_frames(self):
        with self._monster_bin as monster_bin:
            sprite = self._load_sprite_from_bin_pack(monster_bin, self.item_id)

            ani_group = sprite.get_animations_for_group(sprite.anim_groups[0])
            frame_id = 2
            for frame in ani_group[frame_id].frames:
                mfg_id = frame.frame_id
                sprite_img, (cx, cy) = sprite.render_frame_group(sprite.frame_groups[mfg_id])
                self._rendered_frame_info.append((frame.duration, (pil_to_cairo_surface(sprite_img), cx, cy, sprite_img.width, sprite_img.height)))

    def _load_sprite_from_bin_pack(self, bin_pack: BinPack, file_id) -> Wan:
        # TODO: Support of bin_pack item management via the RomProject instead?
        return FileType.WAN.deserialize(FileType.PKDPX.deserialize(bin_pack[file_id]).decompress())
