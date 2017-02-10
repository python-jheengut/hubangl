# -*- coding: utf-8 -*-

# This file is part of HUBAngl.
# HUBAngl Uses Broadcaster Angle
#
# HUBAngl is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# HUBAngl is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HUBAngl.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright (c) 2016 David Testé

import os
import sys

import gi
#gi.require_version("Gtk", "3.0")  # NOQA # DEBUG
gi.require_version("Gst", "1.0")  # NOQA # DEBUG
from gi.repository import Gst
from gi.repository import Gtk
from gi.repository import GdkX11
from gi.repository import GstVideo
from gi.repository import GObject

sys.path.insert(0, "..")  # NOQA # TODO: use __init__.py for managing backend package
import images
from backend import process
from backend import iofetch


AUDIO_VIDEO_STREAM = process.AUDIO_VIDEO_STREAM
VIDEO_ONLY_STREAM = process.VIDEO_ONLY_STREAM
AUDIO_ONLY_STREAM = process.AUDIO_ONLY_STREAM


def _pack_widgets(box, *widgets):
    """
    Pack each ``widget`` in ``box``.

    FIXME: Documentation to complete.

    TODO: Add kwargs for managing the 3 last args of pack_start.
          ``expand``, ``fill``, ``padding``

    :param box: :class:`Gtk.HBox` or :class:`Gtk.VBox`
    :param widgets: Gtk widgets
    """
    for widget in widgets:
        box.pack_start(widget, False, False, 0)


class NewFeed:
    """
    """
    def __init__(self, mode):
        self.hbox = Gtk.Box(Gtk.Orientation.HORIZONTAL)

        self.menu_revealer = self._build_revealer()

        self.video_monitor = Gtk.DrawingArea()
        self.video_monitor.set_margin_left(6)
        self.video_monitor.set_margin_right(6)
        self.video_monitor.set_margin_bottom(6)
        self.video_monitor.set_halign(Gtk.Align.FILL)
        self.video_monitor.set_valign(Gtk.Align.FILL)
        self.video_monitor.set_size_request(700, 400)

        self.placeholder_pipeline = self.get_placeholder_pipeline()
        self.placeholder_bus = self.create_gstreamer_bus(
            self.placeholder_pipeline.pipeline)

        self.pipeline = self.create_pipeline_instance(mode)
        self.bus = self.create_gstreamer_bus(self.pipeline.pipeline)
        self.xid = None

        self.video_menu = VideoMenu(
            self.pipeline, self.menu_revealer, self.placeholder_pipeline)
        self.audio_menu = AudioMenu(
            self.pipeline, self.menu_revealer, self.placeholder_pipeline)
        self.stream_menu = StreamMenu(self.pipeline, self.menu_revealer)
        self.store_menu = StoreMenu(self.pipeline, self.menu_revealer)
        self.info_menu = InfoMenu(self.pipeline, self.menu_revealer)

        self.controls = ControlBar(self.pipeline, self.menu_revealer,
                                   self.video_menu,
                                   self.audio_menu,
                                   self.stream_menu,
                                   self.store_menu,
                                   self.info_menu,
                                   self.placeholder_pipeline)
        self.controls.overlay_container.add(self.video_monitor)
        self.controls.display_controls()

        self.vumeter_box = self._build_vumeter()
        self.controls.overlay_container.add_overlay(self.vumeter_box)

        self.hbox.pack_start(self.controls.overlay_container, True, True, 0)
        self.hbox.pack_start(self.menu_revealer, False, False, 0)

    def set_xid(self):
        self.xid = self.video_monitor.get_property("window").get_xid()

    def get_placeholder_pipeline(self):
        """
        Get a placeholder pipeline from
        :class:`~backend.process.PlaceholderPipeline`
        """
        return process.PlaceholderPipeline()

    def create_pipeline_instance(self, mode):
        """
        Create pipeline instance and attaches it to GUI.

        :param mode: application mode as :class:`str`

        :return: :class:`~backend.process.Pipeline` or one of it subclasses
        """
        if mode == "standalone":
            return process.Pipeline()
        elif mode == "monitoring":
            return process.Monitoring()
        elif mode == "controlroom":
            return process.ControlRoom()
        else:
            raise ValueError

    def create_gstreamer_bus(self, pipeline_element):
        """
        """
        bus = pipeline_element.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        # Used to get messages that GStreamer emits.
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)
        return bus

    def _build_revealer(self):
        """
        """
        revealer = Gtk.Revealer()
        revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        revealer.set_transition_duration(250)
        return revealer

    def _build_vumeter(self):
        """
        """
        # TODO: True stereo feed has to be implemented.
        self.vumeter_left = Gtk.ProgressBar()
        self.vumeter_left.set_orientation(Gtk.Orientation.VERTICAL)
        self.vumeter_left.set_inverted(True)
        self.vumeter_right = Gtk.ProgressBar()
        self.vumeter_right.set_orientation(Gtk.Orientation.VERTICAL)
        self.vumeter_right.set_inverted(True)

        vumeter_hbox = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        vumeter_hbox.set_halign(Gtk.Align.END)
        vumeter_hbox.set_margin_top(6)
        vumeter_hbox.set_margin_bottom(6)
        _pack_widgets(vumeter_hbox,
                      self.vumeter_left,
                      self.vumeter_right)

        return vumeter_hbox

    def iec_scale(self, db):
        """
        Returns the meter deflection percentage given a db value.
        """
        percentage = 0.0

        if db < -70.0:
            percentage = 0.0
        elif db < -60.0:
            percentage = (db + 70.0) * 0.25
        elif db < -50.0:
            percentage = (db + 60.0) * 0.5 + 2.5
        elif db < -40.0:
            percentage = (db + 50.0) * 0.75 + 7.5
        elif db < -30.0:
            percentage = (db + 40.0) * 1.5 + 15.0
        elif db < -20.0:
            percentage = (db + 30.0) * 2.0 + 30.0
        elif db < 0.0:
            percentage = (db + 20.0) * 2.5 + 50.0
        else:
            percentage = 100.0

        return percentage / 100

    def on_sync_message(self, bus, message):
        if message.get_structure().get_name() == 'prepare-window-handle':
            imagesink = message.src
            imagesink.set_property('force-aspect-ratio', True)
            imagesink.set_window_handle(self.xid)

    def on_message(self, bus, message):
        # Getting the RMS audio level value:
        s = Gst.Message.get_structure(message)
        if message.type == Gst.MessageType.ELEMENT:
            if str(Gst.Structure.get_name(s)) == "level":
                percentage = self.iec_scale(s.get_value("rms")[0])
                # This is not a true stereo signal.
                #print('Level value: ', percentage, '%')  # DEBUG
                self.vumeter_left.set_fraction(percentage)
                self.vumeter_right.set_fraction(percentage)

        t = message.type
        if t == Gst.MessageType.EOS:
            self.streampipe.set_state(Gst.State.NULL)
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print ('%s' % err, debug)
            # Watching for feed loss during streaming:
            #if '(651)' not in debug:
            #    # The error is not a socket error.
            #    self.pipel.stream_stop()
            #    self.build_filename(streamfailed=True)
            #    self.create_backup_pipeline()


class ControlBar:
    """
    Class creating an horizontal control bar containing media controls.
    """
    def __init__(self, pipeline, menu_revealer,
                 video_menu, audio_menu, stream_menu, store_menu, info_menu,
                 placeholder_pipeline=None):
        self.images = images.HubanglImages()
        self.images.load_icons()

        self._pipeline = pipeline
        self._placeholder_pipeline = placeholder_pipeline
        self._menu_revealer = menu_revealer
        self.abstract_menu = AbstractMenu(
            self._pipeline, self._menu_revealer, self._placeholder_pipeline)  # DEBUG

        self.video_menu = video_menu
        self.audio_menu = audio_menu
        self.stream_menu = stream_menu
        self.store_menu = store_menu
        self.info_menu = info_menu

        self.overlay_container = Gtk.Overlay()
        self.controlbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.controlbox.set_valign(Gtk.Align.END)
        self.controlbox.set_margin_bottom(6)
        self.controlbox.set_halign(Gtk.Align.CENTER)

        self._load_toolbutton_icons()
        self.toolbar = self._build_toolbar()

        self._build_audio_volume()  # TODO: integrate it into _build_toolbar

    def display_controls(self):
        _pack_widgets(self.controlbox, self.toolbar)
        self.overlay_container.add_overlay(self.controlbox)

    def _load_toolbutton_icons(self):
        """
        Load all images used as icons for :class:`Gtk.ToolButton`.
        """
        self.play_icon = Gtk.Image()
        self.play_icon.set_from_file("")
        self.pause_icon = Gtk.Image()
        self.pause_icon.set_from_file("")
        self.stop_icon = Gtk.Image()
        self.stop_icon.set_from_file("")
        self.video_icon = Gtk.Image()
        self.video_icon.set_from_file("")
        self.audio_icon = Gtk.Image()
        self.audio_icon.set_from_file("")
        self.stream_icon = Gtk.Image()
        self.stream_icon.set_from_file("")
        self.store_icon = Gtk.Image()
        self.store_icon.set_from_file("")
        self.audiolevel_icon = Gtk.Image()
        self.audiolevel_icon.set_from_file("")

    def _build_toolbutton(self, name, icon,
                          on_signal=None, callback=None, tooltip_text=None):
        toolbutton = Gtk.ToolButton(name)
        # FIXME: Tooltip text does not appear on the screen
        if not tooltip_text:
            toolbutton.set_tooltip_text(name)
        else:
            toolbutton.set_tooltip_text(tooltip_text)
        toolbutton.set_icon_widget(icon)

        if on_signal and callback:
            toolbutton.connect(on_signal, callback)
        return toolbutton

    def _build_toolbar(self):
        """
        """
        toolbar = Gtk.Toolbar()

        self.play_button = self._build_toolbutton(
            "Play",
            self.images.icons["play"]["regular"],
            on_signal="clicked",
            callback=self.on_play_clicked
        )
        self.stop_button = self._build_toolbutton(
            "Stop",
            self.images.icons["stop"]["regular"],
            on_signal="clicked",
            callback=self.on_stop_clicked
        )
        self.video_button = self._build_toolbutton(
            "VIDEO",
            self.images.icons["camera"]["regular"],
            on_signal="clicked",
            callback=self.video_menu.on_video_input_clicked,
        )
        self.audio_button = self._build_toolbutton(
            "Audio",
            self.images.icons["micro"]["regular"],
            on_signal="clicked",
            callback=self.audio_menu.on_audio_input_clicked
        )
        self.stream_button = self._build_toolbutton(
            "Stream",
            self.images.icons["streaming"]["regular"],
            on_signal="clicked",
            callback=self.stream_menu.on_stream_clicked
        )
        self.store_button = self._build_toolbutton(
            "Store",
            self.images.icons["storage"]["regular"],
            on_signal="clicked",
            callback=self.store_menu.on_store_clicked
        )
        self.info_button = self._build_toolbutton(
            "Info",
            self.images.icons["info"]["regular"],
            on_signal="clicked",
            callback=self.info_menu.on_info_clicked
        )
        # FIXME: build this toolbutton correctly
        self.audio_level_button = Gtk.ToolButton("Audio lvl",)

        self._populate_toolbar(toolbar,
                               self.play_button,
                               self.stop_button,
                               self.video_button,
                               self.audio_button,
                               self.stream_button,
                               self.store_button,
                               self.info_button)
        return toolbar

    def _populate_toolbar(self, toolbar, *toolbuttons):
        """
        Populate a :class:`Gtk.Toolbar` with several :class:`Gtk.ToolButton`.

        .. note:: Tool buttons will be insert into ``toolbar`` following input
            arguments order.
        """
        for ind, toolbutton in enumerate(toolbuttons):
            toolbar.insert(toolbutton, ind)

    def _build_audio_volume(self):
        self.audio_volume_button = Gtk.VolumeButton()
        self.audio_volume_button.set_value(0)  # Muted by default
        self.audio_volume_button.connect(
            "value-changed", self.on_volume_change)

        self.controlbox.pack_end(self.audio_volume_button, False, False, 0)

    def on_volume_change(self, widget, value):
        if (not self.audio_menu.current_audio_source):
            self.audio_volume_button.set_value(0)
        else:
            self._pipeline.set_speaker_volume(value)

    def on_play_clicked(self, widget):
        if (not self.video_menu.current_video_source
                and not self.audio_menu.current_audio_source):
            return

        self._pipeline.set_text_overlay(*self.info_menu.get_text_overlay())

        # Ensure placeholder pipeline is stopped first in case of
        # loading a session configuration
        self._placeholder_pipeline.set_stop_state()
        self._pipeline.set_play_state()

        if isinstance(widget, Gtk.ToolButton):
            # Change icon to "pause"
            pass
            # A SEGFAULT is raised when the next line is uncommented
            # TODO: Has to be fixed.
            #widget.set_icon_widget(Gtk.STOCK_MEDIA_PAUSE)

    def on_stop_clicked(self, widget):
        self._pipeline.set_stop_state()


class AbstractMenu:
    """
    """
    def __init__(self, pipeline, menu_revealer, placeholder_pipeline=None):
        self.pipeline = pipeline
        self.placeholder_pipeline = placeholder_pipeline
        self.menu_revealer = menu_revealer

    def _build_revealer(self,
                        transition=Gtk.RevealerTransitionType.SLIDE_DOWN):
        """
        """
        revealer = Gtk.Revealer()
        revealer.set_transition_type(transition)
        revealer.set_transition_duration(400)
        return revealer

    def _manage_revealer(self, revealer_widget, container_widget):
        """
        """
        child = revealer_widget.get_child()

        if revealer_widget.get_child_revealed():
            if child == container_widget:
                revealer_widget.set_reveal_child(False)
                return

        if child:
            revealer_widget.remove(child)

        revealer_widget.add(container_widget)
        container_widget.show_all()
        revealer_widget.set_reveal_child(True)

    def _make_widget_available(self, *widgets):
        """
        Make widgets available to user.
        """
        for widget in widgets:
            widget.set_sensitive(True)

    def _make_widget_unavailable(self, *widgets):
        """
        Make widgets unavailable but visible to user.
        """
        for widget in widgets:
            widget.set_sensitive(False)

    def _build_confirm_changes_button(self, label=None, signal="clicked",
                                      callback=None):
        """
        Build a confirmation button used in every side bar menus.
        This button triggers interaction with the backend in case of settings
        changes. Otherwise it stays insensitive.
        """
        if not label:
            label = "Confirm"
        button = Gtk.Button(label)
        button.set_sensitive(False)
        button.set_margin_top(12)
        if callback:
            button.connect(signal, callback)

        return button

    def _build_add_button(self, label=None, signal="clicked",
                          callback=None):
        """
        Build an add button usable in side bar menu.
        This button triggers allow the creation of a new element in the menu.
        """
        if not label:
            label = "Add"
        button = Gtk.Button(label, stock=Gtk.STOCK_ADD)
        button.set_margin_top(12)
        button.set_size_request(250, 20)
        if callback:
            button.connect(signal, callback)

        return button

    def _build_ipv4_entry(self):
        """
        """
        self.ipv4_field1 = Gtk.Entry()
        self.ipv4_field2 = Gtk.Entry()
        self.ipv4_field3 = Gtk.Entry()
        self.ipv4_field4 = Gtk.Entry()

        for field in (self.ipv4_field1, self.ipv4_field2,
                      self.ipv4_field3, self.ipv4_field4):
            field.set_max_length(3)
            field.set_width_chars(3)
            field.set_input_purpose(Gtk.InputPurpose.DIGITS)

        self.port_entry = Gtk.Entry()
        self.port_entry.set_max_length(5)
        self.port_entry.set_width_chars(5)
        self.port_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        _pack_widgets(hbox,
                      self.ipv4_field1, Gtk.Label("."),
                      self.ipv4_field2, Gtk.Label("."),
                      self.ipv4_field3, Gtk.Label("."),
                      self.ipv4_field4, Gtk.Label(":"),
                      self.port_entry)
        return hbox

    def _build_ipv6_entry(self):
        """
        """
        # Has to be implemented
        pass

    def get_ipv4_address(self):
        """
        """
        ip_fields_values = []
        for field in (self.ipv4_field1, self.ipv4_field2,
                      self.ipv4_field3, self.ipv4_field4):
            text = field.get_text()
            if not text:
                raise TypeError
                break
            ip_fields_values.append(text)
        else:
            port_value = self.port_entry.get_text()
            if not port_value:
                raise TypeError
            else:
                ip_address = ".".join(ip_fields_values)
                port = int(port_value)
                return ip_address, port

    def _build_format_section(self, radio_button_label, format_labels,
                              callback_radio=None, callback_combo=None,
                              radio_group=None):
        """
        """
        radio_button = Gtk.RadioButton(
            radio_button_label, group=radio_group)
        if callback_radio:
            radio_button.connect("toggled", callback_radio)

        text_label = Gtk.Label("Format : ")
        combo_box = Gtk.ComboBoxText()
        for label in format_labels:
            combo_box.append_text(label)
            combo_box.set_active(0)
        # This version accept only one format for each stream type.
        # There is not point to allow user to use this combo box.
        # That way the format is displayed as information.
        combo_box.set_sensitive(False)
        if callback_combo:
            combo_box.connect("changed", callback_combo)

        hbox = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        hbox.set_margin_left(24)
        _pack_widgets(hbox, text_label, combo_box)

        return (radio_button, hbox, combo_box)

    def _build_format_group(self):
        """
        """
        (self.audiovideo_radiobutton,
         self._audiovideo_format_hbox,
         self._audiovideo_format_combobox) = self._build_format_section(
             "Audio/Video", (".webm",),
             callback_radio=self.on_format_radiobutton_toggle)
        self.audiovideo_radiobutton.set_active(True)

        self.current_stream_type = AUDIO_VIDEO_STREAM

        (self.video_radiobutton,
         self._video_format_hbox,
         self._video_format_combobox) = self._build_format_section(
             "Video Only", (".mkv",),
             callback_radio=self.on_format_radiobutton_toggle,
             radio_group=self.audiovideo_radiobutton)

        (self.audio_radiobutton,
         self._audio_format_hbox,
         self._audio_format_combobox) = self._build_format_section(
             "Audio Only", (".ogg",),
             callback_radio=self.on_format_radiobutton_toggle,
             radio_group=self.audiovideo_radiobutton)

        radiobutton_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        _pack_widgets(radiobutton_hbox,
                      self.audiovideo_radiobutton,
                      self.video_radiobutton,
                      self.audio_radiobutton)

        return radiobutton_hbox

    def _build_summary_box(self, filename):
        """
        Build a container that sums up information about an output sink.

        :param filename: filename of stored stream as :class:`str`

        :return: :class:`Gtk.Box`
        """
        self.full_filename_label = Gtk.Label(filename)
        settings_button = Gtk.Button(stock=Gtk.STOCK_PROPERTIES)
        settings_button.connect("clicked", self.on_settings_clicked)

        summary_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        summary_hbox.set_margin_top(6)
        _pack_widgets(summary_hbox,
                      self.full_filename_label, settings_button)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(6)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        _pack_widgets(vbox,
                      summary_hbox,
                      self._revealer,
                      separator)
        return vbox

    def _get_format_hbox(self):
        """
        Get format horizontal box currently displayed.

        :return: :class:`Gtk.Box`
        """
        for format_hbox in (self._audiovideo_format_hbox,
                            self._video_format_hbox,
                            self._audio_format_hbox):
            if format_hbox.get_parent():
                return format_hbox

    def _get_format_extension(self):
        """
        Get format extension from the combo box currently displayed.

        :return: a dotted extension as :class:`str`
        """
        hbox = self._get_format_hbox()
        for combobox in (self._audiovideo_format_combobox,
                         self._video_format_combobox,
                         self._audio_format_combobox):
            if combobox.get_parent() == hbox:
                return combobox.get_active_text()

    def on_format_radiobutton_toggle(self, widget):
        raise NotImplementedError

    def _change_output_format(self, widget):
        """
        """
        current_hbox = self._get_format_hbox()
        self.vbox.remove(current_hbox)

        button_label = widget.get_label()
        if button_label == self.audiovideo_radiobutton.get_label():
            child = self._audiovideo_format_hbox
            self.current_stream_type = AUDIO_VIDEO_STREAM
        elif button_label == self.video_radiobutton.get_label():
            child = self._video_format_hbox
            self.current_stream_type = VIDEO_ONLY_STREAM
        elif button_label == self.audio_radiobutton.get_label():
            child = self._audio_format_hbox
            self.current_stream_type = AUDIO_ONLY_STREAM

        self.vbox.pack_start(child, False, False, 0)
        self.vbox.reorder_child(child, -2)
        self.vbox.show_all()

    def on_combobox_change(self, widget):
        raise NotImplementedError

    def on_ipv46_toggle(self, widget):
        pass


class VideoMenu(AbstractMenu):
    """
    """
    def __init__(self, pipeline, menu_revealer, placeholder_pipeline=None):
        super().__init__(pipeline, menu_revealer, placeholder_pipeline)
        self.video_usb_widgets = []
        self.video_ip_widgets = []
        self.video_vbox = self._build_video_vbox()

        self.current_video_source = None
        self.requested_video_source = None

    def _build_video_vbox(self):
        """
        """
        title = Gtk.Label("Video Source")
        title.set_margin_top(6)

        usb_radiobutton = Gtk.RadioButton("USB")
        usb_radiobutton.set_active(True)
        usb_radiobutton.connect("toggled", self.on_commtype_toggle)
        usb_sources = Gtk.ComboBoxText()
        if not self.pipeline.video_sources:
            usb_sources.append_text("")
        else:
            for source in self.pipeline.video_sources:
                usb_sources.append_text(source.description)
        usb_sources.connect("changed", self.on_combobox_change)
        usb_sources.set_margin_left(24)
        self.video_usb_widgets.append(usb_sources)

        ip_radiobutton = Gtk.RadioButton(
            label="IP (available soon)", group=usb_radiobutton)
        ip_radiobutton.connect("toggled", self.on_commtype_toggle)
        # TODO: Remove the next line once IP camera are handled in a pipeline.
        ip_radiobutton.set_sensitive(False)
        # ---------------------------------

        ipv46_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        ipv46_hbox.set_margin_left(24)

        ipv4_radiobutton = Gtk.RadioButton("v4")
        ipv4_radiobutton.set_active(True)
        ipv4_radiobutton.connect("toggled", self.on_ipv46_toggle)

        ipv6_radiobutton = Gtk.RadioButton("v6", group=ipv4_radiobutton)
        ipv6_radiobutton.connect("toggled", self.on_ipv46_toggle)
        _pack_widgets(ipv46_hbox, ipv4_radiobutton, ipv6_radiobutton)

        ipv4_entry = self._build_ipv4_entry()
        ipv4_entry.set_margin_left(24)

        # TODO: Implement ipv6_entry
        # ipv6_entry = self._build_ipv6_entry()
        # ipv6_entry.set_margin_left(24)

        self.video_ip_widgets.extend(
            (ipv4_radiobutton, ipv6_radiobutton, ipv4_entry))
        self._make_widget_unavailable(*self.video_ip_widgets)

        self.video_confirm_button = self._build_confirm_changes_button(
            callback=self.on_confirm_clicked)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(6)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_margin_right(6)
        _pack_widgets(vbox,
                      title,
                      usb_radiobutton, usb_sources,
                      ip_radiobutton, ipv46_hbox,
                      ipv4_entry,
                      self.video_confirm_button,
                      separator)
        return vbox

    def on_video_input_clicked(self, widget):
        self._manage_revealer(self.menu_revealer, self.video_vbox)

    def on_commtype_toggle(self, widget):
        is_active = widget.get_active()
        if widget.get_label() == "USB" and is_active:
            self._make_widget_available(*self.video_usb_widgets)
            self._make_widget_unavailable(*self.video_ip_widgets)
        elif widget.get_label() == "IP" and is_active:
            self._make_widget_available(*self.video_ip_widgets)
            self._make_widget_unavailable(*self.video_usb_widgets)

    def on_combobox_change(self, widget):
        active_text = widget.get_active_text()
        if active_text:
            self.video_confirm_button.set_sensitive(True)
            self.requested_video_source = self.pipeline.get_source_by_description(
                active_text)

    def on_ipv46_toggle(self, widget):
        raise NotImplementedError

    def on_confirm_clicked(self, widget):
        if self.requested_video_source == self.current_video_source:
            return

        self.pipeline.set_input_source(self.requested_video_source)
        self.current_video_source = self.requested_video_source
        self.requested_video_source = None

        self.video_confirm_button.set_sensitive(False)

        if self.placeholder_pipeline.is_playing_state():
            self.placeholder_pipeline.set_stop_state()
            self.pipeline.set_preview_state("audio")
        elif self.pipeline.get_current_text() == "No video source":
            # An audio source is already set
            self.pipeline.set_text_overlay("PREVIEW", "left", "top")


class AudioMenu(AbstractMenu):
    """
    """
    def __init__(self, pipeline, menu_revealer, placeholder_pipeline=None):
        super().__init__(pipeline, menu_revealer, placeholder_pipeline)
        self.audio_vbox = self._build_audio_vbox()

        self.current_audio_source = None
        self.requested_audio_source = None

    def _build_audio_vbox(self):
        """
        """
        title = Gtk.Label("Audio Source")
        title.set_margin_top(6)

        mic_sources = Gtk.ComboBoxText()
        for source in self.pipeline.audio_sources:
            mic_sources.append_text(source.description)
        mic_sources.connect("changed", self.on_input_change)
        mic_sources.set_margin_left(24)

        mute_checkbutton = Gtk.CheckButton("Mute")
        mute_checkbutton.connect("toggled", self.on_mute_toggle)

        output_sinks = Gtk.ComboBoxText()
        index = 0
        for description, device in self.pipeline.speaker_sinks.items():
            output_sinks.append_text(description)
            if device == self.pipeline.speaker_sink.get_property("device"):
                output_sinks.set_active(index)
            index += 1
        output_sinks.connect("changed", self.on_output_change)
        output_sinks.set_margin_left(24)

        self.audio_confirm_button = self._build_confirm_changes_button(
            callback=self.on_confirm_clicked)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(6)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_margin_right(6)
        _pack_widgets(vbox,
                      title,
                      mic_sources,
                      mute_checkbutton,
                      output_sinks,
                      self.audio_confirm_button,
                      separator)
        return vbox

    def on_audio_input_clicked(self, widget):
        self._manage_revealer(self.menu_revealer, self.audio_vbox)

    def on_input_change(self, widget):
        self.audio_confirm_button.set_sensitive(True)
        self.requested_audio_source = self.pipeline.get_source_by_description(
            widget.get_active_text())

    def on_output_change(self, widget):
        self.audio_confirm_button.set_sensitive(True)
        #self.requested_audio_sink = self.pipeline.get_source_by_description(
        #    widget.get_active_text())  # DEV

    def on_mute_toggle(self, widget):
        """
        Mute audio input in the pipeline. This take effect immediatly.
        """
        pass

    def on_confirm_clicked(self, widget):
        if self.requested_audio_source != self.current_audio_source:
            self.pipeline.set_input_source(self.requested_audio_source)
            self.current_audio_source = self.requested_audio_source

        #if self.requested_audio_sink != self.current_audio_sink:  # DEV
        #    self.pipeline.set_speaker_sink(self.requested_audio_sink)  # DEV
        #    self.current_audio_sink = self.requested_audio_sink  # DEV

        self.audio_confirm_button.set_sensitive(False)

        if self.placeholder_pipeline.is_playing_state():
            self.placeholder_pipeline.set_stop_state()
            self.pipeline.set_preview_state("video")


class StreamMenu(AbstractMenu):
    """
    """
    def __init__(self, pipeline, menu_revealer):
        super().__init__(pipeline, menu_revealer)
        self.settings_revealer = self._build_revealer()
        self.stream_vbox = self._build_stream_vbox()

        self.feed_streamed = []

    def _build_stream_vbox(self):
        title = Gtk.Label("Streaming server")
        title.set_margin_top(6)

        self.stream_add_button = self._build_add_button(
            callback=self.on_add_clicked)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(6)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_margin_right(6)
        _pack_widgets(vbox,
                      title,
                      self.settings_revealer,
                      separator,
                      self.stream_add_button)
        return vbox

    def on_stream_clicked(self, widget):
        self._manage_revealer(self.menu_revealer, self.stream_vbox)

    def on_add_clicked(self, widget):
        stream_element = self.StreamSection(
            self.pipeline, self.settings_revealer,
            self.stream_vbox, len(self.feed_streamed) + 1)
        self.feed_streamed.append(stream_element)
        self._manage_revealer(self.settings_revealer, stream_element.vbox)

    class StreamSection(AbstractMenu):
        def __init__(self, pipeline, settings_revealer, parent_container, index):
            super().__init__(pipeline, None)
            self._parent_container = parent_container
            self._settings_revealer = settings_revealer
            self._revealer = self._build_revealer()
            self._index = index

            self.remote_server_radiobutton = None
            self.local_server_radiobutton = None
            self.server_address_entries = None
            self.port = None
            self.mountpoint = None
            self.password = None

            self.current_stream_type = None

            self.audiovideo_radiobutton = None
            self.video_radiobutton = None
            self.audio_radiobutton = None
            self.radiobuttons_hbox = None

            self._audiovideo_format_combobox = None
            self._video_format_combobox = None
            self._audio_format_combobox = None
            self._audiovideo_format_hbox = None
            self._video_format_hbox = None
            self._audio_format_hbox = None
            self.store_confirm_button = None

            self.stream_remote_widgets = []
            self.stream_local_widgets = []

            self.vbox = self._build_newstream_vbox()
            self.summary_vbox = None

            self.streamsink = None

        def _build_newstream_vbox(self):
            """
            """
            self.remote_server_radiobutton = Gtk.RadioButton("Remote")
            self.remote_server_radiobutton.set_active(True)
            self.remote_server_radiobutton.connect(
                "clicked", self.on_remote_server_toggle)

            self.local_server_radiobutton = Gtk.RadioButton(
                label="Local (soon)", group=self.remote_server_radiobutton)
            self.local_server_radiobutton.connect(
                "clicked", self.on_local_server_toggle)
            self.local_server_radiobutton.set_sensitive(False)  # DEV

            server_type_hbox = Gtk.Box(Gtk.Orientation.HORIZONTAL)
            _pack_widgets(server_type_hbox,
                          self.remote_server_radiobutton,
                          self.local_server_radiobutton)

            ipv46_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            ipv46_hbox.set_margin_left(24)
            ipv4_radiobutton = Gtk.RadioButton("v4")
            ipv4_radiobutton.set_active(True)
            ipv4_radiobutton.connect("toggled", self.on_ipv46_toggle)
            ipv6_radiobutton = Gtk.RadioButton("v6 (soon)", group=ipv4_radiobutton)
            ipv6_radiobutton.connect("toggled", self.on_ipv46_toggle)
            ipv6_radiobutton.set_sensitive(False)  # DEV
            _pack_widgets(ipv46_hbox, ipv4_radiobutton, ipv6_radiobutton)

            ipv4_entry = self._build_ipv4_entry()
            ipv4_entry.set_margin_left(24)

            # TODO: Implement ipv6_entry
            # ipv6_entry = self._build_ipv6_entry()
            # ipv6_entry.set_margin_left(24)

            self.stream_remote_widgets.extend(
                (ipv4_radiobutton, ipv6_radiobutton, ipv4_entry))

            #localhost_label = Gtk.Label("localhost : ")
            #port_entry = Gtk.Entry()
            #port_entry.set_max_length(5)
            #port_entry.set_width_chars(5)
            #port_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
            #port_entry.set_sensitive(False)  # DEV
            #localhost_hbox = Gtk.Box(Gtk.Orientation.HORIZONTAL)
            #localhost_hbox.set_margin_left(24)
            #_pack_widgets(localhost_hbox, localhost_label, self.port_entry)

            #self.stream_local_widgets.extend((self.port_entry,))  # DEBUG
            #self._make_widget_unavailable(*self.stream_local_widgets)  # DEBUG

            mountpoint_hbox = Gtk.Box(Gtk.Orientation.HORIZONTAL)
            mountpoint_label = Gtk.Label("Mountpoint : ")
            mountpoint_entry = Gtk.Entry()
            mountpoint_entry.connect("changed", self.on_mountpoint_change)
            _pack_widgets(mountpoint_hbox, mountpoint_label, mountpoint_entry)

            password_hbox = Gtk.Box(Gtk.Orientation.HORIZONTAL)
            password_label = Gtk.Label("Password :   ")
            password_entry = Gtk.Entry()
            password_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
            password_entry.set_visibility(False)
            password_entry.connect("changed", self.on_password_change)
            _pack_widgets(password_hbox, password_label, password_entry)

            radiobutton_hbox = self._build_format_group()

            self.stream_confirm_button = self._build_confirm_changes_button(
                callback=None)
            # Label only used at initialization
            self.stream_confirm_button.set_label("Create")

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            vbox.set_margin_right(6)
            _pack_widgets(vbox,
                          server_type_hbox,
                          ipv46_hbox,
                          ipv4_entry,
                          mountpoint_hbox,
                          password_hbox,
                          radiobutton_hbox,
                          self._audiovideo_format_hbox,
                          self.stream_confirm_button,)
            return vbox

        def on_remote_server_toggle(self, widget):
            if widget.get_active():
                # TODO: hide widgets related to local_server and then show
                # remote_server related ones.
                pass

        def on_local_server_toggle(self, widget):
            if widget.get_active():
                # TODO: hide widgets related to remote_server and then show
                # local_server related ones.
                pass

        def on_mountpoint_change(self, widget):
            self.get_ipv4_address()  # DEBUG
            text = widget.get_text()
            if text != self.mountpoint:
                self.mountpoint = text
                if self.server_address_entries and self.port_entry:
                    self.stream_confirm_button.set_sensitive(True)

        def on_password_change(self, widget):
            text = widget.get_text()
            if text != self.password:
                self.password = text

        def on_format_radiobutton_toggle(self, widget):
            self._change_output_format(widget)
            self.vbox.reorder_child(self.stream_confirm_button, -1)

            if (self.server_address_entries
                    and self.port_entry
                    and self.mountpoint_entry):
                self.stream_confirm_button.set_sensitive(True)

        def on_confirm_clicked(self, widget):
            element_name = self.mountpoint.split("/")[-1]
            if not self.streamsink:
                self.streamsink = self.pipeline.create_stream_sink(
                    self.current_stream_type, self.ip_address, self.port,
                    self.mountpoint, self.password, element_name)
            else:
                # It's a property update
                pass

            if not self.summary_vbox:
                self.summary_vbox = self._build_summary_box(self.mountpoint)
                self._parent_container.pack_start(
                    self.summary_vbox, False, False, 0)
                self._parent_container.reorder_child(
                    self.summary_vbox, self._index)

                self._settings_revealer.remove(self.vbox)
                self._parent_container.show_all()

            self.store_confirm_button.set_label("Confirm")
            self.store_confirm_button.set_sensitive(False)

        def on_settings_clicked(self, widget):
            self._manage_revealer(self._revealer, self.vbox)


class StoreMenu(AbstractMenu):
    """
    """
    def __init__(self, pipeline, menu_revealer):
        super().__init__(pipeline, menu_revealer)
        self.settings_revealer = self._build_revealer()
        self.store_vbox = self._build_store_vbox()

        self.file_stored = []

    def _build_store_vbox(self):
        title = Gtk.Label("Storing")
        title.set_margin_top(6)

        self.store_add_button = self._build_add_button(
            callback=self.on_add_clicked)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(6)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_margin_right(6)
        _pack_widgets(vbox,
                      title,
                      self.settings_revealer,
                      separator,
                      self.store_add_button)
        return vbox

    def on_store_clicked(self, widget):
        self._manage_revealer(self.menu_revealer, self.store_vbox)

    def on_add_clicked(self, widget):
        store_element = self.StoreSection(
            self.pipeline, self.settings_revealer,
            self.store_vbox, len(self.file_stored) + 1)
        self.file_stored.append(store_element)
        self._manage_revealer(self.settings_revealer, store_element.vbox)

    class StoreSection(AbstractMenu):
        def __init__(self, pipeline, settings_revealer, parent_container, index):
            super().__init__(pipeline, None)
            self._parent_container = parent_container
            self._settings_revealer = settings_revealer
            self._revealer = self._build_revealer()
            self._index = index

            self.folder_selection = None
            self.filename = ""
            self.full_filename_label = None
            self.current_stream_type = None

            self.audiovideo_radiobutton = None
            self.video_radiobutton = None
            self.audio_radiobutton = None
            self.radiobuttons_hbox = None

            self._audiovideo_format_combobox = None
            self._video_format_combobox = None
            self._audio_format_combobox = None
            self._audiovideo_format_hbox = None
            self._video_format_hbox = None
            self._audio_format_hbox = None
            self.store_confirm_button = None

            self.vbox = self._build_newfile_vbox()
            self.summary_vbox = None

            self.filesink = None

        def _build_newfile_vbox(self):
            """
            """
            folder_chooser_button = Gtk.FileChooserButton(
                action=Gtk.FileChooserAction.SELECT_FOLDER)
            folder_chooser_button.set_title("Select a folder")
            folder_chooser_button.connect("file-set", self.on_folder_selected)
            folder_chooser_button.set_margin_top(6)

            name_label = Gtk.Label("Name ")
            name_entry = Gtk.Entry()
            name_entry.set_width_chars(25)
            name_entry.set_input_purpose(Gtk.InputPurpose.ALPHA)
            name_entry.set_placeholder_text("Type a filename")
            name_entry.connect("changed", self.on_entry_change)

            name_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            _pack_widgets(name_hbox, name_label, name_entry)

            radiobutton_hbox = self._build_format_group()

            self.store_confirm_button = self._build_confirm_changes_button(
                callback=self.on_confirm_clicked)
            # Label only used at initialization
            self.store_confirm_button.set_label("Create")

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            _pack_widgets(vbox,
                          folder_chooser_button,
                          name_hbox,
                          radiobutton_hbox,
                          self._audiovideo_format_hbox,
                          self.store_confirm_button)
            return vbox

        def on_folder_selected(self, widget):
            self.folder_selection = widget.get_filename()
            if self.filename:
                self.store_confirm_button.set_sensitive(True)

        def on_entry_change(self, widget):
            text = widget.get_text()
            if text != self.filename:
                self.filename = text
                if self.folder_selection:
                    self.store_confirm_button.set_sensitive(True)

        def on_format_radiobutton_toggle(self, widget):
            self._change_output_format(widget)
            self.vbox.reorder_child(self.store_confirm_button, -1)

            if self.folder_selection and self.filename:
                self.store_confirm_button.set_sensitive(True)

        def on_confirm_clicked(self, widget):
            full_filename = self.filename + self._get_format_extension()
            filepath = os.path.join(self.folder_selection, full_filename)
            element_name = self.current_stream_type + "_" + self.filename
            if not self.filesink:
                self.filesink = self.pipeline.create_store_sink(
                    self.current_stream_type, filepath, element_name)
            else:
                # It's a property update
                self.full_filename_label.set_label(full_filename)

            if not self.summary_vbox:
                self.summary_vbox = self._build_summary_box(full_filename)
                self._parent_container.pack_start(
                    self.summary_vbox, False, False, 0)
                self._parent_container.reorder_child(
                    self.summary_vbox, self._index)

                self._settings_revealer.remove(self.vbox)
                self._parent_container.show_all()

            self.store_confirm_button.set_label("Confirm")
            self.store_confirm_button.set_sensitive(False)

        def on_settings_clicked(self, widget):
            self._manage_revealer(self._revealer, self.vbox)


class InfoMenu(AbstractMenu):
    """
    """
    def __init__(self, pipeline, menu_revealer):
        super().__init__(pipeline, menu_revealer)
        self.current_text_overlay = None
        self.requested_text_overlay = None
        self.current_image_path = None
        self.requested_image_path = None

        self.h_alignment = "left"  # DEV
        self.v_alignment = "top"  # DEV
        self.positions = ("Top-Left", "Top-Right",
                          "Bottom-Left", "Bottom-Right",
                          "Center")

        self.info_vbox = self._build_info_vbox()

    def _build_info_vbox(self):
        title = Gtk.Label("Information")
        title.set_margin_bottom(6)

        text_overlay_entry = Gtk.Entry()
        text_overlay_entry.set_placeholder_text("Text displayed on screen")
        text_overlay_entry.set_width_chars(30)
        text_overlay_entry.connect("changed", self.on_text_change)

        text_position_combobox = Gtk.ComboBoxText()
        for position in self.positions:
            text_position_combobox.append_text(position)
        text_position_combobox.set_active(0)
        text_position_combobox.set_margin_left(24)
        text_position_combobox.set_sensitive(False)  # DEV

        image_chooser_button = Gtk.FileChooserButton()
        image_chooser_button.set_title("Select an image to display")
        image_chooser_button.connect("file-set", self.on_image_selected)

        image_position_combobox = Gtk.ComboBoxText()
        for position in self.positions:
            image_position_combobox.append_text(position)
        image_position_combobox.set_active(1)
        image_position_combobox.set_margin_left(24)
        image_position_combobox.set_sensitive(False)  # DEV

        self.info_confirm_button = self._build_confirm_changes_button(
                callback=self.on_confirm_clicked)
        self.info_confirm_button.set_label("Confirm")

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(6)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_margin_right(6)
        _pack_widgets(vbox,
                      title,
                      text_overlay_entry,
                      text_position_combobox,
                      image_chooser_button,
                      image_position_combobox,
                      self.info_confirm_button,
                      separator)

        return vbox

    def get_text_overlay(self):
        """
        Return a :class:`tuple` containing setting for text_overlay.
        """
        return (self.requested_text_overlay,
                self.h_alignment, self.v_alignment)

    def on_info_clicked(self, widget):
        self._manage_revealer(self.menu_revealer, self.info_vbox)

    def on_text_change(self, widget):
        self.requested_text_overlay = widget.get_text()
        self.info_confirm_button.set_sensitive(True)

    def on_image_selected(self, widget):
        self.requested_image_path = widget.get_filename()
        self.info_confirm_button.set_sensitive(True)

    def on_confirm_clicked(self, widget):
        if self.requested_text_overlay != self.current_text_overlay:
            self.pipeline.set_text_overlay(
                self.requested_text_overlay, "left", "top")
            self.current_text_overlay = self.requested_text_overlay

        if self.requested_image_path != self.current_image_path:
            self.pipeline.set_image_overlay(self.requested_image_path, -6, 6)
            self.current_image_path = self.requested_image_path

        self.info_confirm_button.set_sensitive(False)