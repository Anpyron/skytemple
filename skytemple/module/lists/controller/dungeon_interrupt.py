#  Copyright 2020-2024 Capypara and the SkyTemple Contributors
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
from typing import TYPE_CHECKING

from range_typed_integers import u16, u8_checked, u16_checked, u8

from skytemple_files.common.i18n_util import _

from gi.repository import Gtk

from skytemple.core.ui_utils import (
    glib_async,
    catch_overflow,
    builder_get_assert,
    iter_tree_model,
)
from skytemple.controller.main import MainController
from skytemple.core.message_dialog import SkyTempleMessageDialog
from skytemple.core.module_controller import AbstractController
from skytemple.core.string_provider import StringType
from skytemple_files.data.inter_d.model import InterDEntry, InterDEntryType

if TYPE_CHECKING:
    from skytemple.module.lists.module import ListsModule

logger = logging.getLogger(__name__)


class DungeonInterruptController(AbstractController):
    def __init__(self, module: "ListsModule", *args):
        super().__init__(module, *args)
        self.module = module
        self.sp_effects = None
        self._string_provider = module.project.get_string_provider()

    def get_view(self) -> Gtk.Widget:
        self.builder = self._get_builder(__file__, "dungeon_interrupt.glade")
        stack = builder_get_assert(self.builder, Gtk.Stack, "list_stack")

        if not self.module.has_dungeon_interrupts():
            stack.set_visible_child(
                builder_get_assert(self.builder, Gtk.Widget, "box_na")
            )
            return stack
        self.inter_d = self.module.get_dungeon_interrupts()

        self._init_combos()

        stack.set_visible_child(
            builder_get_assert(self.builder, Gtk.Widget, "box_list")
        )
        self.builder.connect_signals(self)

        return stack

    def _init_combos(self):
        store = builder_get_assert(self.builder, Gtk.ListStore, "type_store")
        store.clear()
        for v in InterDEntryType:
            store.append([v.value, v.explanation])
        store = builder_get_assert(self.builder, Gtk.ListStore, "var_store")
        store.clear()
        self.var_names = []
        for i, g in enumerate(
            self.module.project.get_rom_module()
            .get_static_data()
            .script_data.game_variables
        ):
            self.var_names.append(g.name)
            store.append([i, g.name])
        store = builder_get_assert(self.builder, Gtk.ListStore, "dungeon_store")
        store.clear()
        for i in range(len(self.inter_d.list_dungeons)):
            store.append(
                [i, self._string_provider.get_value(StringType.DUNGEON_NAMES_MAIN, i)]
            )
        cb = builder_get_assert(self.builder, Gtk.ComboBox, "cb_dungeon")
        cb.set_active(0)

    def _get_current_dungeon(self) -> int:
        cb_store = builder_get_assert(self.builder, Gtk.ListStore, "dungeon_store")
        cb = builder_get_assert(self.builder, Gtk.ComboBox, "cb_dungeon")

        active_iter = cb.get_active_iter()
        if active_iter is not None:
            return cb_store[active_iter][0]
        else:
            return 0

    def on_cb_dungeon_changed(self, *args):
        store = builder_get_assert(self.builder, Gtk.ListStore, "interrupt_store")
        store.clear()
        for p in self.inter_d.list_dungeons[self._get_current_dungeon()]:
            store.append(
                [
                    p.floor,
                    p.ent_type.value,
                    p.game_var_id,
                    p.param1,
                    p.param2,
                    p.ent_type.explanation,
                    self.var_names[p.game_var_id],
                    p.continue_music,
                ]
            )

    def _build_list(self):
        dungeon = self._get_current_dungeon()

        self.inter_d.list_dungeons[dungeon] = []

        store_inter = builder_get_assert(self.builder, Gtk.ListStore, "interrupt_store")

        for v in iter_tree_model(store_inter):
            e = InterDEntry()
            e.floor = u8_checked(v[0])
            e.ent_type = InterDEntryType(v[1])  # type: ignore
            e.game_var_id = u16_checked(v[2])
            e.param1 = u8_checked(v[3])
            e.param2 = u8_checked(v[4])
            e.continue_music = v[7]
            self.inter_d.list_dungeons[dungeon].append(e)

        self.module.mark_dungeon_interrupts_as_modified()

    def on_btn_help_clicked(self, *args):
        md = SkyTempleMessageDialog(
            MainController.window(),
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.INFO,
            Gtk.ButtonsType.OK,
            _(
                "Here you can edit dungeon interruptions. \n"
                + "Interruptions can occur when transitioning to next floor (e.g. for an interruption defined at floor 3 it will occur when going from floor 2 to 3). \n"
                + "Script-side, it works exactly as if you finished the dungeon (call to common routines GETOUT_SCENARIO_DUNGEON or GETOUT_REQUEST_DUNGEON). \n"
                + "Only one interruption is allowed per floor. \n"
                + "One condition can be defined for each interruption. If not met, the game goes to the next floor as normal. \n"
                + "Parameters function by check type: \n"
                + " - Always: 0, 0\n"
                + " - Flag Not Set: flag_id, 0\n"
                + " - Flag Set: flag_id, 0\n"
                + " - Scenario Equals: scenario, level\n"
                + " - Scenario Below or Equal: scenario, level\n"
                + " - Scenario Greater or Equal: scenario, level"
            ),
        )
        md.run()
        md.destroy()

    def on_btn_add_clicked(self, *args):
        store = builder_get_assert(self.builder, Gtk.ListStore, "interrupt_store")
        store.append(
            [
                0,
                0,
                0,
                0,
                0,
                InterDEntryType(0).explanation,  # type: ignore
                self.var_names[0],
                0,
            ]
        )
        self._build_list()

    def on_btn_remove_clicked(self, *args):
        active_rows: list[Gtk.TreePath] = (
            builder_get_assert(self.builder, Gtk.TreeView, "interrupt_tree")
            .get_selection()
            .get_selected_rows()[1]
        )
        store = builder_get_assert(self.builder, Gtk.ListStore, "interrupt_store")
        for x in reversed(sorted(active_rows, key=lambda x: x.get_indices())):
            del store[x.get_indices()[0]]
        self._build_list()

    @catch_overflow(u8)
    def on_text_floor_edited(self, widget, path, text):
        try:
            tree_store = builder_get_assert(
                self.builder, Gtk.ListStore, "interrupt_store"
            )
            tree_store[path][0] = int(text)
        except ValueError:
            return
        self._build_list()

    @glib_async
    def on_combo_type_changed(self, w, treepath, treeiter):
        store_inter = builder_get_assert(self.builder, Gtk.ListStore, "interrupt_store")
        store_type = builder_get_assert(self.builder, Gtk.ListStore, "type_store")
        store_inter[treepath][1] = store_type[treeiter][0]
        store_inter[treepath][5] = store_type[treeiter][1]
        self._build_list()

    @catch_overflow(u16)
    @glib_async
    def on_combo_game_var_changed(self, w, treepath, treeiter):
        store_inter = builder_get_assert(self.builder, Gtk.ListStore, "interrupt_store")
        store_var = builder_get_assert(self.builder, Gtk.ListStore, "var_store")
        store_inter[treepath][2] = store_var[treeiter][0]
        store_inter[treepath][6] = store_var[treeiter][1]
        self._build_list()

    @catch_overflow(u8)
    def on_text_param1_edited(self, widget, path, text):
        try:
            tree_store = builder_get_assert(
                self.builder, Gtk.ListStore, "interrupt_store"
            )
            tree_store[path][3] = int(text)
        except ValueError:
            return
        self._build_list()

    @catch_overflow(u8)
    def on_text_param2_edited(self, widget, path, text):
        try:
            tree_store = builder_get_assert(
                self.builder, Gtk.ListStore, "interrupt_store"
            )
            tree_store[path][4] = int(text)
        except ValueError:
            return
        self._build_list()

    def on_continue_music_toggled(self, widget, path):
        tree_store = builder_get_assert(self.builder, Gtk.ListStore, "interrupt_store")
        tree_store[path][7] = not widget.get_active()
        self._build_list()
