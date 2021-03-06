# -*- python -*-

# Port to python of gtkgauge widget from Asctec Ground Station (ROS GCS).
#
# Original author: Gautier Dumonteil <gautier.dumonteil@gmail.com>
# Copyright (C) 2010, CCNY Robotics Lab
# Licensed under GPLv3.

import logging
from gi.repository import GObject, Gtk, Gdk, Pango, PangoCairo
import cairo
import math

log = logging.getLogger(__name__)


class GtkGauge(Gtk.DrawingArea):
    """
    Gtk Gauge Widget

    This widget provide an easy to read gauge instrument. <br>
    The design is made to look like to a real gauge<br>
    flight instrument in order to be familiar to aircraft and<br>
    helicopter pilots. This widget is fully comfigurable and<br>
    useable for several gauge type (Battery Voltage, Current,<br>
    Velocity, ...).
    """

    # main properties
    name = GObject.property(type=str, default="...not set...")
    start_value = GObject.property(type=int, default=0)
    end_value = GObject.property(type=int, default=100)
    initial_step = GObject.property(type=int, default=10)
    sub_step = GObject.property(type=float, default=2.0)
    drawing_step = GObject.property(type=int, default=10)
    smooth_interval = GObject.property(type=int, default=0)

    # drawing props
    # grayscale_color = GObject.property(type=bool, default=False)
    # radial_color = GObject.property(type=bool, default=True)
    strip_color_order = GObject.property(type=str, default='YOR')
    green_strip_start = GObject.property(type=int, default=0)
    yellow_strip_start = GObject.property(type=int, default=0)
    orange_strip_start = GObject.property(type=int, default=0)
    red_strip_start = GObject.property(type=int, default=0)

    # colors RGB
    bg_color_inv = (0.7, ) * 3
    bg_color_gauge = (0.05, ) * 3
    bg_color_bounderie = (0.1, ) * 3
    bg_radial_color_begin_gauge = (0.7, ) * 3
    bg_radial_color_begin_bounderie = (0.2, ) * 3

    def __init__(self):
        Gtk.DrawingArea.__init__(self)

        self._x = 0
        self._y = 0
        self._radius = 0
        self._value = 0.0
        self._static_surface = None
        # smooth change hand position
        self._target_value = 0.0
        self._smooth_evid = None

        for p in ('name', 'start-value', 'end-value', 'initial-step', 'sub-step',
                  'drawing-step', 'smooth-interval', 'strip-color-order',
                  'green-strip-start', 'yellow-strip-start', 'orange-strip-start',
                  'red-strip-start'):
            self.connect("notify::" + p, self.on_notify_props)

    def make_reflection_pattern(self, x, y, radius):
        return cairo.RadialGradient(x - 0.392 * radius, y - 0.967 * radius, 0.167 * radius,
                                    x - 0.477 * radius, y - 0.967 * radius, 0.836 * radius)

    def draw_static_base(self, cr):
        # calculations from gtk_gauge_draw_base
        al = self.get_allocation()
        x = al.width / 2
        y = al.height / 2
        radius = min(x, y)  # - 5

        rec_x0 = x - radius
        rec_y0 = y - radius
        rec_width = radius * 2
        rec_height = radius * 2
        rec_aspect = 1.0
        rec_corner_radius = rec_height / 8.0
        rec_radius = rec_corner_radius / rec_aspect

        # gauge base
        cr.new_sub_path()
        cr.arc(rec_x0 + rec_width - rec_radius, rec_y0 + rec_radius,
               rec_radius, math.radians(-90), math.radians(0))
        cr.arc(rec_x0 + rec_width - rec_radius, rec_y0 + rec_height - rec_radius,
               rec_radius, math.radians(0), math.radians(90))
        cr.arc(rec_x0 + rec_radius, rec_y0 + rec_height - rec_radius,
               rec_radius, math.radians(90), math.radians(180))
        cr.arc(rec_x0 + rec_radius, rec_y0 + rec_radius,
               rec_radius, math.radians(180), math.radians(270))
        cr.close_path()

        # fake light reflection (drawen when
        # radial_color=True and grayscale_color=False)
        # reflection 1
        pat = self.make_reflection_pattern(x, y, radius)
        rgba0 = self.bg_radial_color_begin_bounderie + (1.0, )
        rgba1 = self.bg_color_bounderie + (1.0, )
        pat.add_color_stop_rgba(0, *rgba0)
        pat.add_color_stop_rgba(1, *rgba1)

        cr.set_source(pat)
        cr.fill_preserve()
        cr.stroke()

        # meter circle
        cr.arc(x, y, radius, 0, 2 * math.pi)
        cr.set_source_rgb(0., 0., 0.)
        cr.fill_preserve()
        cr.stroke()

        cr.arc(x, y, radius - 0.04 * radius, 0, 2 * math.pi)
        cr.set_source_rgb(0.6, 0.5, 0.5)
        cr.stroke()

        # inner ring
        cr.set_line_width(0.01 * radius)
        radius -= 0.1 * radius
        cr.arc(x, y, radius, 0, 2 * math.pi)

        # reflection 2
        pat = self.make_reflection_pattern(x, y, radius)
        rgba0 = self.bg_radial_color_begin_gauge + (1.0, )
        rgba1 = self.bg_color_gauge + (1.0, )
        pat.add_color_stop_rgba(0, *rgba0)
        pat.add_color_stop_rgba(1, *rgba1)

        cr.set_source(pat)
        cr.fill_preserve()
        cr.stroke()

        self._x = x
        self._y = y
        self._radius = radius

    def draw_static_color_strip(self, cr):
        x = self._x
        y = self._y
        radius = self._radius

        # clolor strips
        self._alpha = 0.0
        self._alpha_inv = 1.0

        # helper functions for strip_order_XYZ()
        def draw_strip_arc():
            step_count = (self.end_value - self.start_value) / self.sub_step
            cr.set_line_width(0.12 * radius)
            cr.arc(x, y, radius - 0.06 * radius,
                   -5 * math.pi / 4 + i * ((5 * math.pi / 4) / step_count),
                   -5 * math.pi / 4 + (i + 1) * ((5 * math.pi / 4) / step_count))
            cr.stroke()

        def draw_strip_additional_red_arc():
            step_count = (self.end_value - self.start_value) / self.sub_step
            cr.set_line_width(0.1 * radius)
            cr.set_source_rgba(1, 0, 0, 0.2)
            cr.arc(x, y, radius - 0.23 * radius,
                   -5 * math.pi / 4 + i * ((5 * math.pi / 4) / step_count),
                   -5 * math.pi / 4 + (i + 1) * ((5 * math.pi / 4) / step_count))
            cr.stroke()

        # draw one sub_step
        def strip_order_YOR(i):
            alpha_step = abs(1 / ((self.yellow_strip_start - self.orange_strip_start) / self.sub_step))
            step = i * self.sub_step

            if self.orange_strip_start > step >= self.yellow_strip_start:
                self._alpha += alpha_step
                cr.set_source_rgba(1, 1, 0, self._alpha)
            elif self.red_strip_start > step >= self.orange_strip_start:
                cr.set_source_rgb(1, 0.65, 0)
            elif step >= self.red_strip_start:
                draw_strip_additional_red_arc()
                cr.set_source_rgb(1, 0, 0)

            draw_strip_arc()

        def strip_order_GYR(i):
            alpha_step = abs(1 / ((self.yellow_strip_start - self.green_strip_start) / self.sub_step))
            step = i * self.sub_step

            if self.yellow_strip_start > step >= self.green_strip_start:
                self._alpha += alpha_step
                cr.set_source_rgba(0, 0.65, 0, self._alpha)
            elif self.red_strip_start > step >= self.yellow_strip_start:
                cr.set_source_rgb(1, 1, 0)
            elif step >= self.red_strip_start:
                draw_strip_additional_red_arc()
                cr.set_source_rgb(1, 0, 0)

            draw_strip_arc()

        def strip_order_ROY(i):
            alpha_step = abs(1 / ((self.end_value - self.yellow_strip_start) / self.sub_step))
            step = i * self.sub_step

            if self.orange_strip_start > step >= self.red_strip_start:
                draw_strip_additional_red_arc()
                cr.set_source_rgb(1, 0, 0)
            elif self.yellow_strip_start > step >= self.orange_strip_start:
                cr.set_source_rgb(1, 0.65, 0)
            elif step >= self.yellow_strip_start:
                cr.set_source_rgba(1, 1, 0, self._alpha_inv)
                self._alpha_inv -= alpha_step

            draw_strip_arc()

        def strip_order_RYG(i):
            alpha_step = abs(1 / ((self.end_value - self.green_strip_start) / self.sub_step))
            step = i * self.sub_step

            if self.yellow_strip_start > step >= self.red_strip_start:
                draw_strip_additional_red_arc()
                cr.set_source_rgb(1, 0, 0)
            elif self.green_strip_start > step >= self.yellow_strip_start:
                cr.set_source_rgb(1, 1, 0)
            elif step >= self.green_strip_start:
                cr.set_source_rgba(0, 0.65, 0, self._alpha_inv)
                self._alpha_inv -= alpha_step

            draw_strip_arc()

        STRIP_ORDERS = {
            'YOR': strip_order_YOR,
            'GYR': strip_order_GYR,
            'ROY': strip_order_ROY,
            'RYG': strip_order_RYG,
        }

        # color strips can be disabled
        step_count = (self.end_value - self.start_value) / self.sub_step
        draw_strip = STRIP_ORDERS.get(self.strip_color_order, lambda i: None)
        for i in range(0, int(step_count)):
            cr.save()
            draw_strip(i)
            cr.restore()

    def draw_static_marks(self, cr):
        end_value = self.end_value * 10
        start_value = self.start_value * 10
        sub_step = self.sub_step * 10
        initial_step = self.initial_step * 10
        x = self._x
        y = self._y
        radius = self._radius

        step_count = (end_value - start_value) / sub_step
        for i in range(0, int(step_count) + 1):
            cr.save()
            if (i * int(sub_step)) % initial_step == 0:
                cr.set_source_rgb(1, 1, 1)
                cr.set_line_width(0.015 * radius)
                inset = 0.18 * radius
            else:
                cr.set_source_rgba(1, 1, 1, 0.5)
                cr.set_line_width(0.01 * radius)
                inset = 0.12 * radius

            angle = -5 * math.pi / 4 + i * ((5 * math.pi / 4) / step_count)
            cr.move_to(x + (radius - inset) * math.cos(angle),
                       y + (radius - inset) * math.sin(angle))
            cr.line_to(x + radius * math.cos(angle),
                       y + radius * math.sin(angle))
            cr.stroke()
            cr.restore()

        cr.set_source_rgb(1, 1, 1)
        cr.move_to(x + (radius - 0.18 * radius) * math.cos(0),
                   y + (radius - 0.18 * radius) * math.sin(0))
        cr.line_to(x + radius * math.cos(0),
                   y + radius * math.sin(0))

    def draw_static_numbers(self, cr):
        x = self._x
        y = self._y
        radius = self._radius

        def draw_number(i, val, ixk, iyk, xk, yk, fk):
            cr.set_source_rgb(1, 1, 1)
            cr.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(fk * radius)

            step_count = float(self.end_value - self.start_value) / self.drawing_step
            angle = -5 * math.pi / 4 + i * ((5 * math.pi / 4) / step_count)

            inset_x = ixk * radius
            inset_y = iyk * radius if iyk is not None else inset_x

            cr.move_to(x - xk * radius + (radius - inset_x) * math.cos(angle),
                       y + yk * radius + (radius - inset_y) * math.sin(angle))
            cr.show_text(str(val))
            cr.stroke()

        for i in range(0, ((self.end_value - self.start_value) / self.drawing_step) + 1):
            cr.save()
            val = i * self.drawing_step + self.start_value
            if 10 > val:
                draw_number(i, val, 0.3, None, 0.05, 0.045, 0.15)
            elif 100 > val >= 10:
                draw_number(i, val, 0.33, None, 0.08, 0.04, 0.15)
            elif 1000 > val >= 100:
                draw_number(i, val, 0.36, 0.34, 0.14, 0.03, 0.14)
            elif 10000 > val >= 1000:
                draw_number(i, val, 0.4, 0.32, 0.18, 0.04, 0.14)
            else:
                log.error("%s: draw number: value too big", self)

            cr.restore()

    def draw_static_screws(self, cr):
        x = self._x
        y = self._y
        radius = self._radius
        radius += 0.12 * radius

        def draw_screw(sx, sy):
            # draw screw head
            cr.arc(x + 0.82 * sx * radius, y + 0.82 * sy * radius,
                   0.1 * radius, 0, 2 * math.pi)
            pat = cairo.RadialGradient(x + 0.82 * sx * radius, y + 0.82 * sy * radius, 0.07 * radius,
                                       x + 0.82 * sx * radius, y + 0.82 * sy * radius, 0.1 * radius)
            pat.add_color_stop_rgba(0, 0, 0, 0, 0.7)
            pat.add_color_stop_rgba(1, 0, 0, 0, 0.1)
            cr.set_source(pat)
            cr.fill_preserve()
            cr.stroke()

            cr.arc(x + 0.82 * sx * radius, y + 0.82 * sy * radius,
                   0.07 * radius, 0, 2 * math.pi)
            pat = self.make_reflection_pattern(x, y, radius)
            rgba0 = self.bg_color_bounderie + (1.0, )
            rgba1 = (0.15, ) * 3 + (1.0, )
            pat.add_color_stop_rgba(0, *rgba0)
            pat.add_color_stop_rgba(1, *rgba1)
            cr.set_source(pat)
            cr.fill_preserve()
            cr.stroke()

            def draw_x():
                # draw -
                cr.move_to(x + 0.88 * sx * radius, y + 0.82 * sy * radius)
                cr.line_to(x + 0.76 * sx * radius, y + 0.82 * sy * radius)
                cr.fill_preserve()
                cr.stroke()
                # draw |
                cr.move_to(x + 0.82 * sx * radius, y + 0.88 * sy * radius)
                cr.line_to(x + 0.82 * sx * radius, y + 0.76 * sy * radius)
                cr.fill_preserve()
                cr.stroke()

            cr.set_line_width(0.02 * radius)
            cr.set_source_rgb(0, 0, 0)
            draw_x()
            cr.set_line_width(0.01 * radius)
            cr.set_source_rgb(0.1, 0.1, 0.1)
            draw_x()

        draw_screw(-1, -1)  # top left
        draw_screw(+1, -1)   # top right
        draw_screw(-1, +1)   # bottom left
        draw_screw(+1, +1)    # bottom right

    def draw_static_name(self, cr):
        rect = Gdk.Rectangle()
        rect.x = self._x - 0.2 * self._radius
        rect.y = self._y + 0.35 * self._radius
        rect.width = 1.0 * self._radius
        rect.height = 0.4 * self._radius

        layout = PangoCairo.create_layout(cr)
        layout.set_markup(self.name)
        layout.set_alignment(Pango.Alignment.CENTER)

        # TODO: save last good known size
        desc = Pango.FontDescription()
        font_size = 30

        desc.set_size(font_size * Pango.SCALE)
        layout.set_font_description(desc)

        width, height = layout.get_pixel_size()
        while width > rect.width or height > rect.height:
            font_size -= 1
            if font_size <= 1:
                log.error("%s: name area too small", self)
                return

            desc.set_size(font_size * Pango.SCALE)
            layout.set_font_description(desc)
            width, height = layout.get_pixel_size()

        log.debug("%s: name font size: %s", self, font_size)
        x_pos = rect.x + (rect.width - width) / 2
        y_pos = rect.y + (rect.height - height) / 2

        cr.set_source_rgb(1, 1, 1)
        cr.move_to(x_pos, y_pos)
        PangoCairo.show_layout(cr, layout)
        cr.stroke()

    def darw_dynamic_hand(self, cr):
        x = self._x
        y = self._y
        radius = self._radius
        value = int(self._value * 1000)

        # central circle
        cr.save()
        cr.set_source_rgb(0, 0, 0)
        cr.arc(x, y, radius - 0.9 * radius, 0, 2 * math.pi)
        cr.fill_preserve()
        cr.stroke()
        cr.set_source_rgb(0.2, 0.2, 0.2)
        cr.arc(x, y, radius - 0.9 * radius, 0, 2 * math.pi)
        cr.stroke()
        cr.restore()

        # gauge hand
        cr.save()
        cr.set_source_rgb(1, 1, 1)
        cr.set_line_width(0.02 * radius)
        cr.move_to(x, y)

        if value * (5 * math.pi / 4) / ((self.end_value - self.start_value) * 1000) \
                <= 5 * math.pi / 4:
            angle = (-5 * math.pi / 4) + value * (5 * math.pi / 4) / \
                ((self.end_value - self.start_value) * 1000)
            cr.line_to(x + (radius - 0.2 * radius) * math.cos(angle),
                       y + (radius - 0.2 * radius) * math.sin(angle))
            cr.move_to(x, y)
            cr.line_to(x - (radius - 0.9 * radius) * math.cos(angle),
                       y - (radius - 0.9 * radius) * math.sin(angle))
        else:
            log.warn("%s: Value out of range", self)

        cr.stroke()
        cr.restore()

    def draw_static_once(self):
        if self._static_surface is not None:
            return

        rect = self.get_allocation()

        log.debug("%s: draw_static_once: x: %s, y: %s, w: %s, h: %s",
                  self, rect.x, rect.y, rect.width, rect.height)

        self._static_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, rect.width, rect.height)
        cr_static = cairo.Context(self._static_surface)
        cr_static.rectangle(0, 0, rect.width, rect.height)
        cr_static.clip()

        self.draw_static_base(cr_static)
        self.draw_static_screws(cr_static)
        self.draw_static_color_strip(cr_static)
        self.draw_static_marks(cr_static)
        self.draw_static_numbers(cr_static)
        self.draw_static_name(cr_static)

    def do_draw(self, cr):
        self.draw_static_once()

        w, h = self._static_surface.get_width(), self._static_surface.get_height()

        dynamic_surface = cairo.Surface.create_similar(self._static_surface, cairo.CONTENT_COLOR_ALPHA, w, h)
        cr_dyn = cairo.Context(dynamic_surface)
        cr_dyn.rectangle(0, 0, w, h)
        cr_dyn.clip()

        self.darw_dynamic_hand(cr_dyn)

        cr.set_source_surface(self._static_surface, 0, 0)
        cr.paint()
        cr.set_source_surface(dynamic_surface, 0, 0)
        cr.paint()
        return False

    def do_configure_event(self, event=None):
        # invalidate old static surface
        self._static_surface = None

    def on_notify_props(self, obj=None, gparamstring=None):
        # log.debug("%s: property change: %s", self, gparamstring)
        self.do_configure_event()
        self._stop_smooth()
        if self.smooth_interval > 0:
            self._start_smooth()
        self.queue_draw()

    def smooth_update(self):
        if self._value == self._target_value:
            return True

        # TODO: need to find out how to calculate this constant
        if abs(self._value - self._target_value) > 0.1:
            value = (self._value * 3 + self._target_value) / 4
        else:
            value = self._target_value

        self._set_value(value)
        return True

    def _start_smooth(self):
        if self._smooth_evid is None:
            self._smooth_evid = GObject.timeout_add(self.smooth_interval, self.smooth_update)

    def _stop_smooth(self):
        if self._smooth_evid is not None:
            GObject.source_remove(self._smooth_evid)
            self._smooth_evid = None

    def _set_value(self, value):
        self._value = value
        self.queue_draw()

    def set_value(self, value):
        if self.smooth_interval > 0:
            self._start_smooth()
            self._target_value = value
        else:
            self._stop_smooth()
            self._target_value = value
            self._set_value(value)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    win = Gtk.Window()
    vbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
    win.add(vbox)

    win.set_title('GtkGauge test')
    win.resize(300 * 4, 300)
    win.connect('delete-event', Gtk.main_quit)

    gauge_yor = GtkGauge()
    gauge_yor.name = 'YOR type'
    gauge_yor.strip_color_order = 'YOR'
    gauge_yor.yellow_strip_start = 0
    gauge_yor.orange_strip_start = 50
    gauge_yor.red_strip_start = 75
    vbox.pack_start(gauge_yor, True, True, 0)

    gauge_gyr = GtkGauge()
    gauge_gyr.name = 'GYR type'
    gauge_gyr.strip_color_order = 'GYR'
    gauge_gyr.green_strip_start = 0
    gauge_gyr.yellow_strip_start = 50
    gauge_gyr.red_strip_start = 75
    gauge_gyr.smooth_interval = 50
    vbox.pack_start(gauge_gyr, True, True, 0)

    gauge_roy = GtkGauge()
    gauge_roy.name = 'ROY type'
    gauge_roy.strip_color_order = 'ROY'
    gauge_roy.red_strip_start = 0
    gauge_roy.orange_strip_start = 25
    gauge_roy.yellow_strip_start = 50
    gauge_roy.smooth_interval = 100
    vbox.pack_start(gauge_roy, True, True, 0)

    gauge_ryg = GtkGauge()
    gauge_ryg.name = 'RYG type'
    gauge_ryg.strip_color_order = 'RYG'
    gauge_ryg.red_strip_start = 0
    gauge_ryg.yellow_strip_start = 25
    gauge_ryg.green_strip_start = 50
    gauge_ryg.smooth_interval = 250
    vbox.pack_start(gauge_ryg, True, True, 0)

    def update():
        import random

        r1 = random.random() * 100
        log.debug("set_value: %s", r1)

        gauge_yor.set_value(r1)
        gauge_gyr.set_value(r1)
        gauge_roy.set_value(r1)
        gauge_ryg.set_value(r1)
        return True

    GObject.timeout_add(1000, update)

    win.show_all()
    Gtk.main()
