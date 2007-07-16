#
# This file is part of Advene.
#
# Advene is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Advene is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#

import advene.core.config as config

from gettext import gettext as _

from advene.rules.elements import RegisteredAction, Condition
from advene.model.tal.context import AdveneTalesException

name="Default core actions"

def register(controller=None):
    ac=DefaultActionsRepository(controller)

    controller.register_action(RegisteredAction(
            name="Message",
            method=ac.Message,
            description=_("Display a message"),
            parameters={'message': _("Message to display")},
            defaults={'message': 'annotation/content/data'},
            category='gui',
            )
                               )
    controller.register_action(RegisteredAction(
            name="PlayerStart",
            method=ac.PlayerStart,
            description=_("Start the player"),
            parameters={'position': _("Start position (in ms)")},
            defaults={'position': 'string:0'},
            category='player',
            )
                               )

    controller.register_action(RegisteredAction(
            name="PlayerGoto",
            method=ac.PlayerGoto,
            description=_("Go to the given position"),
            parameters={'position': _("Goto position (in ms)")},
            defaults={'position': 'annotation/fragment/begin'},
            category='player',
            )
                               )
    controller.register_action(RegisteredAction(
            name="PlayerStop",
            method=ac.PlayerStop,
            description=_("Stop the player"),
            category='player',
            #            parameters={'position': _("Stop position (in ms)")}
            )
                               )
    controller.register_action(RegisteredAction(
            name="PlayerPause",
            method=ac.PlayerPause,
            description=_("Pause the player"),
            #            parameters={'position': _("Pause position (in ms)")}
            category='player',
            )
                               )
    controller.register_action(RegisteredAction(
            name="PlayerResume",
            method=ac.PlayerResume,
            description=_("Resume the player"),
            #            parameters={'position': _("Resume position (in ms)")}
            category='player',
            )
                               )
    controller.register_action(RegisteredAction(
            name="Snapshot",
            method=ac.Snapshot,
            description=_("Take a snapshot"),
            #            parameters={'position': _("Snapshot position (in ms)")}
            category='advanced',
            )
                               )
    controller.register_action(RegisteredAction(
            name="Caption",
            method=ac.Caption,
            description=_("Display a caption"),
            parameters={'message': _("Message to display"),
                        'duration': _("Duration of the caption")},
            defaults={'message': 'annotation/content/data',
                      'duration': 'annotation/fragment/duration'},
            category='advanced',
            )
                               )
    controller.register_action(RegisteredAction(
            name="AnnotationCaption",
            method=ac.AnnotationCaption,
            description=_("Caption the annotation"),
            parameters={'message': _("Message to display")},
            defaults={'message': 'annotation/content/data'},
            category='advanced',
            )
                               )
    controller.register_action(RegisteredAction(
            name="DisplayMarker",
            method=ac.DisplayMarker,
            description=_("Display a marker"),
            parameters={'shape': _("Marker shape (square, circle, triangle)"),
                        'color': _("Marker color"),
                        'x': _("x-position (percentage of screen)"),
                        'y': _("y-position (percentage of screen)"),
                        'size': _("Size (arbitrary units)"),
                        'duration': _("Duration of the display in ms")},
            defaults={'shape': 'string:circle',
                      'color': 'string:red',
                      'x': 'string:10',
                      'y': 'string:10',
                      'size': 'string:5',
                      'duration': 'annotation/fragment/duration'},
            category='advanced',
            )
                               )
    controller.register_action(RegisteredAction(
            name="AnnotationMute",
            method=ac.AnnotationMute,
            description=_("Zero the volume during the annotation"),
            category='player',
            )
                               )
    controller.register_action(RegisteredAction(
            name="SoundOff",
            method=ac.SoundOff,
            description=_("Zero the volume"),
            category='player',
            )
                               )
    controller.register_action(RegisteredAction(
            name="SoundOn",
            method=ac.SoundOn,
            description=_("Restore the volume"),
            category='player',
            )
                               )

    controller.register_action(RegisteredAction(
            name="ActivateSTBV",
            method=ac.ActivateSTBV,
            description=_("Activate a STBV"),
            parameters={'viewid': _("STBV id")},
            defaults={'viewid': 'string:stbv_id'},
            category='gui',
            )
                               )

    controller.register_action(RegisteredAction(
            name="SendUserEvent",
            method=ac.SendUserEvent,
            description=_("Send a user event"),
            parameters={'identifier': _("Identifier"),
                        'delay': _("Delay in ms before sending the event.")},
            defaults={'identifier': 'string:name',
                      'delay': 'string:2000'},
            category='generic',
            )
                               )

    controller.register_action(RegisteredAction(
            name="OpenURL",
            method=ac.OpenURL,
            description=_("Open a URL in the web browser"),
            parameters={'url': _("URL")},
            defaults={'url': 'string:http://liris.cnrs.fr/advene/'},
            category='gui',
            )
                               )

    controller.register_action(RegisteredAction(
            name="SetVolume",
            method=ac.SetVolume,
            description=_("Set the audio volume"),
            parameters={'volume': _("Volume level (from 0 to 100)")},
            defaults={'volume': 'string:50'},
            category='player',
            )
                               )

    controller.register_action(RegisteredAction(
            name="SetRate",
            method=ac.SetRate,
            description=_("Set the playing rate"),
            parameters={'rate': _("Rate (100: normal rate, 200: twice slower)")},
            defaults={'rate': 'string:100'},
            category='player',
            )
                               )

class DefaultActionsRepository:
    def __init__(self, controller=None):
        self.controller=controller

    def parse_parameter(self, context, parameters, name, default_value):
        if parameters.has_key(name):
            try:
                result=context.evaluateValue(parameters[name])
            except AdveneTalesException, e:
                self.controller.log(_("Error in the evaluation of the parameter %s:" % name))
                self.controller.log(str(e))
                result=default_value
        else:
            result=default_value
        return result

    def Message(self, context, parameters):
        """Display a message.

        This method is overriden in the GUI by self.log
        """
        message=self.parse_parameter(context, parameters, 'message', "An event occurred.")
        print _("** Message ** ") + message.encode('utf8')
        return True

    def PlayerStart (self, context, parameters):
        """Start the player."""
        position=self.parse_parameter(context, parameters, 'position', None)
        if position is not None:
            position=long(position)
        self.controller.update_status ("start", position)
        return True

    def PlayerGoto (self, context, parameters):
        """Goto the given position."""
        position=self.parse_parameter(context, parameters, 'position', None)

        #print "Goto from %s to %s" % (helper.format_time(self.controller.player.current_position_value),
        #                              helper.format_time(position))
        if position is not None:
            position=long(position)
        c=self.controller
        pos = c.create_position (value=position,
                                 key=c.player.MediaTime,
                                 origin=c.player.AbsolutePosition)
        self.controller.update_status ("set", pos)
        return True

    def PlayerStop (self, context, parameters):
        """Stop the player."""
        position=self.parse_parameter(context, parameters, 'position', None)
        if position is not None:
            position=long(position)
        self.controller.update_status ("stop", position)
        return True

    def PlayerPause (self, context, parameters):
        """Pause the player."""
        position=self.parse_parameter(context, parameters, 'position', None)
        if position is not None:
            position=long(position)
        self.controller.update_status ("pause", position)
        return True

    def PlayerResume (self, context, parameters):
        """Resume the playing."""
        position=self.parse_parameter(context, parameters, 'position', None)
        if position is not None:
            position=long(position)
        self.controller.update_status ("resume", position)
        return True

    def Snapshot (self, context, parameters):
        """Take a snapshot at the given position (in ms)."""
        if not config.data.player['snapshot']:
            return False
        pos=self.parse_parameter(context, parameters, 'position', None)
        if pos is None:
            pos=self.controller.player.current_position_value
        else:
            pos = long(pos)
        if abs(pos - self.controller.player.current_position_value) > 100:
            # The current position is too far away from the requested position
            # FIXME: do something useful (warning) ?
            return
        self.controller.update_snapshot(position=pos)
        return True

    def Caption (self, context, parameters):
        """Display a message as a caption for a given duration.

        If the 'duration' parameter is not defined, a default duration will be used.
        """
        message=self.parse_parameter(context, parameters, 'message', "Default caption.")
        duration=self.parse_parameter(context, parameters, 'duration', None)

        begin = self.controller.player.relative_position
        if duration is not None:
            duration=long(duration)
        else:
            duration=config.data.player_preferences['default_caption_duration']

        c=self.controller
        end = c.create_position (value=duration,
                                 key=c.player.MediaTime,
                                 origin=c.player.RelativePosition)
        if c.gui and c.gui.captionview:
            c.gui.captionview.display_text(message.encode('utf8'),
                                           duration)
        else:
            c.player.display_text (message.encode('utf8'), begin, end)
        return True

    def DisplayMarker (self, context, parameters):
        """Display a marker on the video.

        If the 'duration' parameter is not defined, a default duration will be used.
        Parameters:
        Shape: square, circle, triangle.
        Color: named color.
        Position: x, y in percentage of the screen. (0,0) is on top-left.
        Duration: in ms
        """
        shape=self.parse_parameter(context, parameters, 'shape', 'square')
        color=self.parse_parameter(context, parameters, 'color', 'white')
        x=self.parse_parameter(context, parameters, 'x', '95')
        y=self.parse_parameter(context, parameters, 'y', '95')
        size=self.parse_parameter(context, parameters, 'size', '4')
        duration=self.parse_parameter(context, parameters, 'duration', None)

        if shape == 'square':
            code='<rect x="%s%%" y="%s%%" width="%sem" height="%sem" fill="%s" />' % (x, y, size, size, color)
        elif shape == 'circle':
            code='<circle cx="%s%%" cy="%s%%" r="%sem" fill="%s" />' % (x, y, size, color)
        elif shape == 'triangle':
            # Size is 800x600 (see code below)
            x=long(x)*8
            y=long(y)*6
            s=long(size)*10
            code='<polygon fill="%s" points="%d,%d %d,%d %d,%d" />' % (color,
                                                                       x-s, y+s,
                                                                       x+s, y+s,
                                                                       x, y-s)
        else:
            code='<text x="%s%%" y="%s%%" font-size="%s0" color="%s">TODO</text>' % (x, y,
                                                                                     size,
                                                                                     color)

        message="""<svg version='1' preserveAspectRatio='xMinYMin meet' viewBox='0 0 800 600'>%s</svg>""" % code

        c=self.controller
        begin = c.player.relative_position
        if duration is not None:
            duration=long(duration)
        else:
            duration=config.data.player_preferences['default_caption_duration']
        end = c.create_position (value=duration,
                                 key=c.player.MediaTime,
                                 origin=c.player.RelativePosition)
        if c.gui and c.gui.captionview:
            c.gui.captionview.display_text(message.encode('utf8'),
                                           duration)
        else:
            c.player.display_text (message.encode('utf8'), begin, end)
        return True

    def AnnotationCaption (self, context, parameters):
        """Display a message as a caption during the triggering annotation timeframe.
        """
        message=self.parse_parameter(context, parameters, 'message', "Default caption.")
        annotation=context.evaluateValue('annotation')

        if annotation is not None:
            c=self.controller
            begin = c.player.relative_position
            duration=annotation.fragment.end - c.player.current_position_value
            end = c.create_position (value=duration,
                                     key=c.player.MediaTime,
                                     origin=c.player.RelativePosition)
            #begin = c.create_position (value=annotation.fragment.begin)
            #end = c.create_position (value=annotation.fragment.end)
            if c.gui and c.gui.captionview:
                c.gui.captionview.display_text(message.encode('utf8'),
                                               duration)
            else:
                c.player.display_text (message.encode('utf8'), begin, end)
        return True

    def SoundOff (self, context, parameters):
        """Zero the video volume."""
        v=self.controller.player.sound_get_volume()
        if v > 0:
            config.data.volume = v
        self.controller.player.sound_set_volume(0)
        return True

    def SoundOn (self, context, parameters):
        """Restore the video volume."""
        if config.data.volume != 0:
            self.controller.player.sound_set_volume(config.data.volume)
        return True

    def ActivateSTBV (self, context, parameters):
        """Activate the given STBV."""
        stbvid=self.parse_parameter(context, parameters, 'viewid', None)
        if not stbvid:
            return True
        try:
            stbv=context.evaluateValue('package/views/%s' % stbvid)
        except ValueError:
            stbv=None
        if stbv is not None and stbv.content.mimetype == 'application/x-advene-ruleset':
            self.controller.activate_stbv(stbv)
        else:
            self.controller.log(_("Cannot find the stbv %s") % stbvid)
        return True

    def SendUserEvent(self, context, parameters):
        """Send a user event.

        The user must provide an identifier, that will be checked in the
        correponding rule (that match UserEvent)
        """
        identifier=self.parse_parameter(context, parameters, 'identifier', None)
        if identifier is None:
            return True
        delay=self.parse_parameter(context, parameters, 'delay', None)
        if delay is None:
            delay=0
        delay=long(delay)

        self.controller.notify('UserEvent', identifier=identifier, delay=delay)
        return True

    def AnnotationMute(self, context, parameters):
        """Zero the volume for the duration of the annotation."""
        annotation=context.evaluateValue('annotation')
        if annotation is None:
            return True
        self.SoundOff(context, parameters)
        # We create a new internal rule which will match the end of the
        # current annotation :
        cond=Condition(lhs='annotation/id',
                       operator='equals',
                       rhs="string:%s" % annotation.id)
        self.controller.event_handler.internal_rule(event='AnnotationEnd',
                                                    condition=cond,
                                                    method=self.SoundOn)
        return True

    def OpenURL (self, context, parameters):
        """Open the given URL in the web browser."""
        url=self.parse_parameter(context, parameters, 'url', None)
        if not url:
            return True
        self.controller.open_url(url)
        return True

    def SetVolume (self, context, parameters):
        """Set the video volume."""
        volume=self.parse_parameter(context, parameters, 'volume', None)
        if volume is None:
            return True
        self.controller.player.sound_set_volume(int(volume))
        return True

    def SetRate (self, context, parameters):
        """Set the playing rate.

        The value is the percentage of frame display time, so
        100 means normal rate,
        200 means twice slower than normal
        """
        rate=self.parse_parameter(context, parameters, 'rate', None)
        if rate is None:
            return True
        try:
            self.controller.player.set_rate(int(rate))
        except AttributeError:
            self.controller.log(_("The set_rate method is unavailable."))
        return True
