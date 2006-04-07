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
"""
Advene controller
=================

This is the core of the Advene framework. It holds the various
components together (data model, webserver, GUI, event handler...),
and can be seen as a Facade design pattern for these components.

The X{AdveneEventHandler} is used by the application to handle events
notifications and actions triggering.
"""

import sys, time
import os
import socket
import sre
import webbrowser
import urllib
import StringIO
import gobject

import advene.core.config as config

from gettext import gettext as _

import advene.core.plugin
import advene.core.mediacontrol
from advene.core.imagecache import ImageCache
import advene.core.idgenerator

import advene.rules.elements
import advene.rules.ecaengine
import advene.rules.actions

from advene.model.package import Package
from advene.model.zippackage import ZipPackage
from advene.model.annotation import Annotation
from advene.model.fragment import MillisecondFragment
import advene.model.tal.context

import advene.util.vlclib as vlclib

if config.data.webserver['mode']:
    import advene.core.webserver

import threading

class AdveneController:
    """AdveneController class.

    The main attributes for this class are:
      - L{package} : the currently active package
      - L{packages} : a dict of loaded packages, indexed by their alias

      - L{active_annotations} : the currently active annotations
      - L{player} : the player (X{advene.core.mediacontrol.Player} instance)
      - L{event_handler} : the event handler
      - L{server} : the embedded web server

    Some entry points in the methods:
      - L{__init__} : controller initialization
      - L{update} : regularly called method used to update information about the current stream
      - L{update_status} : use this method to interact with the player

    On loading, we append the following attributes to package:
      - L{imagecache} : the associated imagecache
      - L{_idgenerator} : the associated idgenerator
      - L{_modified} : boolean

    @ivar active_annotations: the currently active annotations.
    @type active_annotations: list
    @ivar future_begins: the annotations that should be activated next (sorted)
    @type future_begins: list
    @ivar future_ends: the annotations that should be desactivated next (sorted)
    @type future_ends: list

    @ivar last_position: a cache to check whether an update is necessary
    @type last_position: int

    @ivar package: the package currently loaded and active
    @type package: advene.model.Package

    @ivar preferences: the current preferences
    @type preferences: dict

    @ivar player: a reference to the player
    @type player: advene.core.mediacontrol.Player

    @ivar event_handler: the event handler instance
    @type event_handler: AdveneEventHandler

    @ivar server: the embedded web server
    @type server: webserver.AdveneWebServer

    @ivar gui: the embedding GUI (may be None)
    @type gui: AdveneGUI
    """

    def __init__ (self, args=None):
        """Initializes player and other attributes.
        """

        # Dictionaries indexed by alias
        self.packages = {}
        # Reverse mapping indexed by package
        self.aliases = {}
        self.current_alias = None

        self.cleanup_done=False
        if args is None:
            args = []

        # Regexp to recognize DVD URIs
        self.dvd_regexp = sre.compile("^dvd.*@(\d+):(\d+)")

        # List of active annotations
        self.active_annotations = []
        self.future_begins = None
        self.future_ends = None
        self.last_position = -1
        self.cached_duration = 0

        # GUI (optional)
        self.gui=None
        # Useful for debug in the evaluator window
        self.config=config.data

        # STBV
        self.current_stbv = None

        self.package = None

        playerfactory=advene.core.mediacontrol.PlayerFactory()
        self.player = playerfactory.get_player()
        self.player.get_default_media = self.get_default_media
        self.player_restarted = 0

        # Some player can define a cleanup() method
        try:
            self.player.cleanup()
        except AttributeError:
            pass

        # Event handler initialization
        self.event_handler = advene.rules.ecaengine.ECAEngine (controller=self)
        self.event_queue = []
	# Load default actions
	advene.rules.actions.register(self)	

        # Used in update_status to emit appropriate notifications
        self.status2eventname = {
            'pause':  'PlayerPause',
            'resume': 'PlayerResume',
            'start':  'PlayerStart',
            'stop':   'PlayerStop',
            'set':    'PlayerSet',
            }
        self.event_handler.register_action(advene.rules.elements.RegisteredAction(
            name="Message",
            method=self.message_log,
            description=_("Display a message"),
            parameters={'message': _("String to display.")},
            category='gui',
            ))
        try:
            self.user_plugins=self.load_plugins(config.data.advenefile('plugins', 'settings'),
                                                prefix="advene_plugins_user")
        except OSError:
            pass

    def self_loop(self):
	"""Autonomous gobject loop for controller.
	"""
	self.mainloop = gobject.MainLoop()
        if config.data.webserver['mode'] == 1:
	    # Run webserver in gobject mainloop
	    if self.server:
		self.log(_("Using Mainloop input handling for webserver..."))
		gobject.io_add_watch (self.server,
				      gobject.IO_IN | gobject.IO_ERR | gobject.IO_HUP,
				      self.handle_http_request)
	    else:
		self.log(_("No available webserver"))

	def update_wrapper():
	    """Wrapper for the application update.

	    This is necessary, since update() returns a position, that
	    may be 0, thus interpreted as False by the loop handler if
	    we directly invoke it.
	    """
	    self.update()
	    return True

        gobject.timeout_add (100, update_wrapper)
        self.notify ("ApplicationStart")
        self.mainloop.run ()
        self.notify ("ApplicationEnd")

    def load_plugins(self, directory, prefix="advene_plugins"):
        """Load the plugins from the given directory.
        """
        #print "Loading plugins from ", directory
        l=advene.core.plugin.PluginCollection(directory, prefix)
        for p in l:
            try:
                self.log("Registering " + p.name)
                p.register(controller=self)
            except AttributeError:
                pass
        return l

    def queue_action(self, method, *args, **kw):
        self.event_queue.append( (method, args, kw) )
        return True
    
    def queue_registered_action(self, ra, parameters):
        """Queue a registered action for execution.  
        """
        c=self.build_context(here=self.package)
        self.queue_action(ra.method, c, parameters)
        return True

    def process_queue(self):
        """Batch process pending events.

        We process all the pending events since the last notification.
        Cannot use a while loop on event_queue, since triggered
        events can generate new notification.
        """
        # Dump the pending events into a local queue
        ev=self.event_queue[:]
        self.event_queue=[]

        # Now we can process the events
        for (method, args, kw) in ev:
            #print "Process action: %s" % str(method)
            try:
                method(*args, **kw)
            except Exception, e:
                self.queue_action(self.log, _("Exception :") + str(e))
        return True

    def register_gui(self, gui):
        self.gui=gui

    def register_view(self, view):
        if self.gui:
            self.gui.register_view(view)
        else:
            self.log(_("No available GUI"))

    # Register methods for user-defined plugins
    def register_content_handler(self, handler):
        config.data.register_content_handler(handler)

    def register_global_method(self, method, name=None):
        config.data.register_global_method(method, name)

    def register_action(self, action):
        if self.event_handler:
            self.event_handler.register_action(action)
        else:
            self.log(_("No available event handler"))

    def build_context(self, here=None, alias=None):
        c=advene.model.tal.context.AdveneContext(here,
						 options={
		u'package_url': self.get_default_url(root=True, alias=alias),
		u'snapshot': self.package.imagecache,
		u'namespace_prefix': config.data.namespace_prefix,
		u'config': config.data.web,
		})
	c.addGlobal(u'package', self.package)
	c.addGlobal(u'packages', self.packages)
	c.addGlobal(u'player', self.player)
	for name, method in config.data.global_methods.iteritems():
	    c.addMethod(name, method)
	return c

    def busy_port_info(self):
        """Display the processes using the webserver port.
        """
        processes=[]
        pat=':%d' % config.data.webserver['port']
        f=os.popen('netstat -atlnp 2> /dev/null', 'r')
        for l in f.readlines():
            if pat not in l:
                continue
            pid=l.rstrip().split()[-1]
            processes.append(pid)
        f.close()
        self.log(_("Cannot start the webserver\nThe following processes seem to use the %s port: %s") % (pat, processes))

    def init(self, args=None):
        if args is None:
            args=[]

        # Read the default rules
        self.event_handler.read_ruleset_from_file(config.data.advenefile('default_rules.xml'),
                                                  type_='default', priority=100)

        self.event_handler.internal_rule (event="PackageLoad",
                                          method=self.manage_package_load)

        if config.data.webserver['mode']:
            self.server=None
            try:
                self.server = advene.core.webserver.AdveneWebServer(controller=self,
                                                                    port=config.data.webserver['port'])
            except socket.error:
                if config.data.os != 'win32':
                    self.busy_port_info()
                self.log(_("Deactivating web server"))

            # If == 1, it is the responsibility of the Gtk app
            # to set the input loop
            if config.data.webserver['mode'] == 2 and self.server:
                self.serverthread = threading.Thread (target=self.server.serve_forawhile)
                self.serverthread.start ()

        # Arguments handling
        for uri in args:
	    if '=' in uri:
		# alias=uri syntax
		alias, uri = uri.split('=', 2)
		alias = sre.sub('[^a-zA-Z0-9_]', '_', alias)
                try:
                    self.load_package (uri=uri, alias=alias)
                    self.log(_("Loaded %s as %s") % (uri, alias))
                except Exception, e:
                    self.log(_("Cannot load package from file %s: %s") % (uri,
                                                                          unicode(e)))
	    else:
		name, ext = os.path.splitext(uri)
		if ext.lower() in ('.xml', '.azp'):
		    alias = sre.sub('[^a-zA-Z0-9_]', '_', os.path.basename(name))
		    try:
			self.load_package (uri=uri, alias=alias)
			self.log(_("Loaded %s as %s") % (uri, alias))
		    except Exception, e:
			self.log(_("Cannot load package from file %s: %s") % (uri,
									      unicode(e)))
		else:
		    # Try to load the file as a video file
		    if ('dvd' in name 
			or ext.lower() in config.data.video_extensions):
			self.set_default_media(uri)
            
        # If no package is defined yet, load the template
        if self.package is None:
            self.load_package ()

        self.player.check_player()

        return True

    def create_position (self, value=0, key=None, origin=None):
        return self.player.create_position(value=value, key=key, origin=origin)

    def notify (self, event_name, *param, **kw):
        if False:
            print "Notify %s (%s): %s" % (
                event_name,
                vlclib.format_time(self.player.current_position_value),
                str(kw))
        if kw.has_key('immediate'):
            del kw['immediate']
            self.event_handler.notify(event_name, *param, **kw)
        else:
            self.queue_action(self.event_handler.notify, event_name, *param, **kw)
        return

    def update_snapshot (self, position=None):
        """Event handler used to take a snapshot for the given position (current).

        @return: a boolean (~desactivation)
        """
        if (config.data.player['snapshot'] 
	    and not self.package.imagecache.is_initialized (position)):
            # FIXME: only 0-relative position for the moment
            # print "Update snapshot for %d" % position
            try:
                i = self.player.snapshot (self.player.relative_position)
            except self.player.InternalException, e:
                print "Exception in snapshot: %s" % e
                return False
            if i is not None and i.height != 0:
                self.package.imagecache[position] = vlclib.snapshot2png (i)
        else:
            # FIXME: do something useful (warning) ?
            pass
        return True

    def open_url(self, url):
        if config.data.os == 'win32' or config.data.os == 'darwin':
            # webbrowser is not broken on win32 or Mac OS X
            webbrowser.get().open(url)
            return True
        # webbrowser is broken on UNIX/Linux : if the browser
        # does not exist, it does not always launch it in the
        # backgroup, so it can freeze the GUI
        web_browser = os.getenv("BROWSER", None)
        if web_browser == None:
            term_command = os.getenv("TERMCMD", "xterm")
            browser_list = ("firefox", "firebird", "epiphany", "galeon", "mozilla", "opera", "konqueror", "netscape", "dillo", ("links", "%s -e links" % term_command), ("w3m", "%s -e w3m" % term_command), ("lynx", "%s -e lynx" % term_command), "amaya", "gnome-open")
            breaked = 0
            for browser in browser_list:
                if type(browser) == str:
                    browser_file = browser_cmd = browser
                elif type(browser) == tuple and len(browser) == 2:
                    browser_file = browser[0]
                    browser_cmd = browser[1]
                else:
                    continue

                for directory in os.getenv("PATH", "").split(os.path.pathsep):
                    if os.path.isdir(directory):
                        browser_path = os.path.join(directory, browser_file)
                        if os.path.isfile(browser_path) and os.access(browser_path, os.X_OK):
                            web_browser = browser_cmd
                            breaked = 1
                            break
                if breaked:
                    break
        if web_browser != None:
            os.system("%s \"%s\" &" % (web_browser, url))

        return True

    def get_url_for_alias (self, alias):
        if self.server:
            return urllib.basejoin(self.server.urlbase, "/packages/" + alias)
        else:
            return "/packages/" + alias

    def get_url_for_package (self, p):
        a=self.aliases[p]
        return self.get_url_for_alias(a)

    def get_default_url(self, root=False, alias=None):
        """Return the default package URL.

        If root, then return only the package URL even if it defines
        a default view.
        """
        if alias is None:
            alias=self.aliases[self.package]
        url = self.get_url_for_alias(alias)
        if not url:
            return None
        if root:
            return unicode(url)
        defaultview=self.package.getMetaData(config.data.namespace, 'default_utbv')
        if defaultview:
            url=u"%s/view/%s" % (url, defaultview)
        return url

    def get_title(self, element, representation=None):
        return vlclib.get_title(self, element, representation)

    def get_default_media (self, package=None):
        if package is None:
            package=self.package

        mediafile = package.getMetaData (config.data.namespace,
                                         "mediafile")
        if mediafile is None or mediafile == "":
            return ""
        m=self.dvd_regexp.match(mediafile)
        if m:
            title,chapter=m.group(1, 2)
            mediafile=self.player.dvd_uri(title, chapter)
        elif mediafile.startswith('http:'):
            # FIXME: check for the existence of the file
            pass
        elif not os.path.exists(mediafile):
            # It is a file. It should exist. Else check for a similar
            # one in moviepath
            # UNIX/Windows interoperability: convert pathnames
            n=mediafile.replace('\\', os.sep).replace('/', os.sep)

            name=os.path.basename(n)
            for d in config.data.path['moviepath'].split(os.pathsep):
                if d == '_':
                    # Get package dirname
                    d=self.package.uri
                    # And convert it to a pathname (for Windows)
                    d=urllib.url2pathname(d)
                    if d.startswith('file:'):
                        d=d.replace('file://', '')
                    d=os.path.dirname(d)

                if '~' in d:
                    # Expand userdir
                    d=os.path.expanduser(d)

                n=os.path.join(d, name)
                # FIXME: if d is a URL, use appropriate method (urllib.??)
                if os.path.exists(n):
                    mediafile=n
                    self.log(_("Found matching video file in moviepath: %s") % n)
                    break
        return mediafile

    def set_default_media (self, uri, package=None):
        if package is None:
            package=self.package
	self.cached_duration = 0
        m=self.dvd_regexp.match(uri)
        if m:
            title,chapter=m.group(1,2)
            uri="dvd@%s:%s" % (title, chapter)
        if isinstance(uri, unicode):
            uri=uri.encode('utf8')
        package.setMetaData (config.data.namespace, "mediafile", uri)
        if m:
            uri=self.player.dvd_uri(title, chapter)
        self.player.playlist_clear()
	if uri is not None and uri != "":
	    self.player.playlist_add_item (uri)
	self.notify("MediaChange", uri=uri)

    def transmute_annotation(self, annotation, annotationType, delete=False):
        """Transmute an annotation to a new type.
        """
        if annotation.type == annotationType:
            # Do not duplicate the annotation
            return annotation
        ident=self.package._idgenerator.get_id(Annotation)
        an = self.package.createAnnotation(type = annotationType,
                                           ident=ident,
                                           fragment=annotation.fragment.clone())
        self.package.annotations.append(an)
        an.author=config.data.userid
        an.content.data=annotation.content.data
        an.setDate(self.get_timestamp())
        # FIXME: check if the types are compatible
        self.notify("AnnotationCreate", annotation=an)

        if delete and not annotation.relations:
            self.package.annotations.remove(annotation)
            self.notify('AnnotationDelete', annotation=annotation)

        return an

    def restart_player (self):
        """Restart the media player."""
        self.player.restart_player ()
        mediafile = self.get_default_media()
        if mediafile != "":
            if isinstance(mediafile, unicode):
                mediafile=mediafile.encode('utf8')
            self.player.playlist_clear()
            self.player.playlist_add_item (mediafile)
	    self.notify("MediaChange", uri=uri)

    def get_timestamp(self):
	return time.strftime("%Y-%m-%d")

    def load_package (self, uri=None, alias=None):
        """Load a package.

        This method is esp. used as a callback for webserver. If called
        with no argument, or an empty string, it will create a new
        empty package.

        @param uri: the URI of the package
        @type uri: string
        @param alias: the name of the package (ignored in the GUI, always "advene")
        @type alias: string
        """
        if uri is None or uri == "":
            try:
                self.package = Package (uri="new_pkg",
                                        source=config.data.advenefile(config.data.templatefilename))
            except (IOError, OSError), e:
                self.log(_("Cannot find the template package %s: %s") 
			 % (config.data.advenefile(config.data.templatefilename),
			    unicode(e)))
                alias='new_pkg'
                self.package = Package (alias, source=None)
            self.package.author = config.data.userid
	    self.package.date = self.get_timestamp()
        else:
            self.package = Package (uri=uri)

        if alias is None:
            # Autogenerate the alias
            if uri:
                alias, ext = os.path.splitext(os.path.basename(uri))
            else:
                alias = 'new_pkg'

        # Replace forbidden characters. The GUI is responsible for
        # letting the user specify a valid alias.
        alias = sre.sub('[^a-zA-Z0-9_]', '_', alias)

        self.package.imagecache=ImageCache()
        self.package._idgenerator = advene.core.idgenerator.Generator(self.package)
        self.package._modified = False

        self.register_package(alias, self.package)
        self.notify ("PackageLoad")
        self.activate_package(alias)

    def remove_package(self, package=None):
        if package is None:
            package=self.package
        alias=self.aliases[package]
        self.unregister_package(alias)
        del(package)
        return True

    def register_package (self, alias, package):
        """Register a package in the server loaded packages lists.

        @param alias: the package's alias
        @type alias: string
        @param package: the package itself
        @type package: advene.model.Package
        @param imagecache: the imagecache associated to the package
        @type imagecache: advene.core.ImageCache
        """
        # If we load a new file and only the template package was present,
        # then remove the template package
        if len(self.packages) <= 2 and 'new_pkg' in self.packages.keys():
            self.unregister_package('new_pkg')
        self.packages[alias] = package
        self.aliases[package] = alias

    def unregister_package (self, alias):
        """Remove a package from the loaded packages lists.

        @param alias: the  package alias
        @type alias: string
        """
        # FIXME: check if the unregistered package was the current one
        p = self.packages[alias]
        del (self.aliases[p])
        del (self.packages[alias])
        if self.package == p:
            l=[ a for a in self.packages.keys() if a != 'advene' ]
            # There should be at least 1 key
            if l:
                self.activate_package(l[0])
            else:
                # We removed the last package. Create a new empty one.
                self.load_package()
                #self.activate_package(None)

    def activate_package(self, alias=None):
        if alias:
            self.package = self.packages[alias]
            self.current_alias = alias
        else:
            self.package = None
            self.current_alias = None
        self.packages['advene']=self.package

        # Reset the cached duration
        duration = self.package.getMetaData (config.data.namespace, "duration")
        if duration is not None:
            self.cached_duration = long(duration)
        else:
            self.cached_duration = 0

        mediafile = self.get_default_media()
        if mediafile is not None and mediafile != "":
            if self.player.is_active():
                if mediafile not in self.player.playlist_get_list ():
                    # Update the player playlist
                    if isinstance(mediafile, unicode):
                        mediafile=mediafile.encode('utf8')
                    self.player.playlist_clear()
                    self.player.playlist_add_item (mediafile)
		    self.notify("MediaChange", uri=mediafile)
	else:
	    self.player.playlist_clear()
	    self.notify("MediaChange", uri=None)

        self.notify ("PackageActivate", package = self.package)

    def reset(self):
        """Reset all packages.
        """
        self.log("FIXME: reset not implemented yet")
        #FIXME: remove all packages from self.packages
        # and
        # recreate a template package
        pass

    def save_package (self, name=None, alias=None):
        """Save the package (current or specified)

        @param name: the URI of the package
        @type name: string
        """
        if alias is None:
            p=self.package
        else:
            p=self.packages[alias]

        if name is None:
            name=p.uri
        old_uri = p.uri

        if alias is None:
            # Check if we know the stream duration. If so, save it as
            # package metadata
            if self.cached_duration > 0:
                p.setMetaData (config.data.namespace,
                               "duration",
                               unicode(self.cached_duration))
            # Set if necessary the mediafile metadata
            if self.get_default_media() == "":
                pl = self.player.playlist_get_list()
                if pl:
                    self.set_default_media(pl[0])

        p.save(name=name)
        p._modified = False

        self.notify ("PackageSave", package=p)
        if old_uri != name:
            # Reload the package with the new name
            self.log(_("Package URI has changed. Reloading package with new URI."))
            self.load_package(uri=name)
            # FIXME: we keep here the old and the new package.
            # Maybe we could autoclose the old package

    def manage_package_load (self, context, parameters):
        """Event Handler executed after loading a package.

        self.package should be defined.

        @return: a boolean (~desactivation)
        """

        # Check that all fragments are Millisecond fragments.
        l = [a.id for a in self.package.annotations
             if not isinstance (a.fragment, MillisecondFragment)]
        if l:
            self.package = None
            self.log (_("Cannot load package: the following annotations do not have Millisecond fragments:"))
            self.log (", ".join(l))
            return True

	self.package.imagecache.clear ()
        mediafile = self.get_default_media()
        if mediafile is not None and mediafile != "":
            # Load the imagecache
            id_ = vlclib.mediafile2id (mediafile)
            self.package.imagecache.load (id_)
            # Populate the missing keys
            for a in self.package.annotations:
                self.package.imagecache.init_value (a.fragment.begin)
                self.package.imagecache.init_value (a.fragment.end)

        # Activate the default STBV
        default_stbv = self.package.getMetaData (config.data.namespace, "default_stbv")
        if default_stbv:
	    view=vlclib.get_id( self.package.views, default_stbv )
	    if view:
		self.activate_stbv(view)

        return True

    def get_stbv_list(self):
        if self.package:
            return [ v
                     for v in self.package.views
                     if v.content.mimetype == 'application/x-advene-ruleset' ]
        else:
            return []

    def activate_stbv(self, view=None, force=False):
        """Activates a given STBV.

        If view is None, then reset the user STBV.  The force
        parameter is used to handle the ViewEditEnd case, where the
        view may already be active, but must be reloaded anyway since
        its contents changed.
        """
        if view == self.current_stbv and not force:
            return
        self.current_stbv=view
        if view is None:
            self.event_handler.clear_ruleset(type_='user')
            self.notify("ViewActivation", view=None)
            return
        rs=advene.rules.elements.RuleSet()
        rs.from_dom(catalog=self.event_handler.catalog,
                    domelement=view.content.model,
                    origin=view.uri)
        self.event_handler.set_ruleset(rs, type_='user')
        self.notify("ViewActivation", view=view)
        return

    def handle_http_request (self, source, condition):
        """Handle a HTTP request.

        This method is used if config.data.webserver['mode'] == 1.
        """
        if condition in (gobject.IO_ERR, gobject.IO_HUP):  
	    self.log("Aborted connection")
	    return True
        # Make sure that all exceptions are catched, else the gtk mainloop
        # will not execute update_display.
        try:
            source.handle_request ()
        except socket.error, e:
            print _("Network exception: %s") % str(e)
        except Exception, e:
            import traceback
            s=StringIO.StringIO()
            traceback.print_exc (file = s)
            self.log(_("Got exception %s in web server.") % str(e), s.getvalue())
        return True

    def log (self, msg, level=None):
        """Add a new log message.

        Should be overriden by the application (GUI for instance)

        @param msg: the message
        @type msg: string
        """
        if self.gui:
            self.gui.log(msg, level)
        else:
            # FIXME: handle the level parameter
            print msg
        return

    def message_log (self, context, parameters):
        """Event Handler for the message action.

        Essentialy a wrapper for the X{log} method.

        @param context: the action context
        @type context: TALContext
        @param parameters: the parameters (should have a 'message' one)
        @type parameters: dict
        """
        if parameters.has_key('message'):
            message=context.evaluateValue(parameters['message'])
        else:
            message="No message..."
        self.log (message)
        return True

    def on_exit (self, source=None, event=None):
        """General exit callback."""
        if not self.cleanup_done:
	    # Stop the event handler
	    self.event_handler.reset_queue()
	    self.event_handler.clear_state()
	    self.event_handler.update_rulesets()

            # Save preferences
            config.data.save_preferences()

            # Cleanup the ZipPackage directories
            ZipPackage.cleanup()

            # Terminate the web server
            try:
                self.server.stop_serving ()
            except:
                pass

            # Terminate the VLC server
            try:
                print "Exiting vlc player"
                self.player.exit()
                print "done"
            except Exception, e:
                import traceback
                s=StringIO.StringIO()
                traceback.print_exc (file = s)
                self.log(_("Got exception %s when stopping player.") % str(e), s.getvalue())
            self.cleanup_done = True
        return True

    def move_position (self, value, relative=True):
        """Helper method : fast forward or rewind by value milliseconds.

        @param value: the offset in milliseconds
        @type value: int
        """
        if relative:
            self.update_status ("set", self.create_position (value=value,
                                                             key=self.player.MediaTime,
                                                             origin=self.player.RelativePosition))
        else:
            self.update_status ("set", self.create_position (value=value,
                                                             key=self.player.MediaTime,
                                                             origin=self.player.AbsolutePosition))

    def generate_sorted_lists (self, position):
        """Return two sorted lists valid for a given position.

        (i.e. all annotations beginning or ending after the
        position). The lists are sorted according to the begin and end
        position respectively.

        The elements of the list are (annotation, begin, end).

        The update_display method only has to check the first element
        of each list. If there is a match, it should trigger the
        events and pop the element.

        If there is a seek operation, we should regenerate the lists.

        @param position: the current position
        @type position: int
        @return: a tuple of two lists containing triplets
        @rtype: tuple
        """
        l = [ (a, a.fragment.begin, a.fragment.end)
              for a in self.package.annotations
              if a.fragment.begin >= position or a.fragment.end >= position ]
        future_begins = list(l)
        future_ends = l
        future_begins.sort(lambda a, b: cmp(a[1], b[1]))
        future_ends.sort(lambda a, b: cmp(a[2], b[2]))

        #print "Position: %s" % vlclib.format_time(position)
        #print "Begins: %s\nEnds: %s" % ([ a[0].id for a in future_begins[:4] ],
        #                                [ a[0].id for a in future_ends[:4] ])
        return future_begins, future_ends

    def reset_annotation_lists (self):
        """Reset the future annotations lists."""
        #print "reset annotation lists"
        self.future_begins = None
        self.future_ends = None
        self.active_annotations = []

    def update_status (self, status=None, position=None, notify=True):
        """Update the player status.

        Wrapper for the player.update_status method, used to notify the
        AdveneEventHandler.

        @param status: the status (cf advene.core.mediacontrol.Player)
        @type status: string
        @param position: an optional position
        @type position: Position
        """
        position_before=self.player.current_position_value
        #print "update status: %s" % status
        if status == 'set' or status == 'start':
            self.reset_annotation_lists()
            # It was defined in a rule, but this prevented the snapshot
            # to be taken *before* moving
            self.update_snapshot(position_before)
        try:
            # if hasattr(position, 'value'):
            #     print "update_status %s %i" % (status, position.value)
            # else:
            #     print "update_status %s %s" % (status, position)
            if self.player.playlist_get_list():
                self.player.update_status (status, position)
        except Exception, e:
            # FIXME: we should catch more specific exceptions and
            # devise a better feedback than a simple print
            import traceback
            s=StringIO.StringIO()
            traceback.print_exc (file = s)
            self.log(_("Raised exception in update_status: %s") % str(e), s.getvalue())
        else:
            if self.status2eventname.has_key (status) and notify:
                self.notify (self.status2eventname[status],
                             position=position,
                             position_before=position_before,
                             immediate=True)
        return

    def position_update (self):
        """Updates the current_position_value.

        This method, regularly called, restarts the player in case of
        a communication failure.

        It updates the slider range if necessary.

        @return: the current position in ms
        @rtype: a long
        """
        try:
            self.player.position_update ()
        except self.player.InternalException:
            # The server is down. Restart it.
            print _("Restarting player...")
            self.player_restarted += 1
            if self.player_restarted > 5:
                raise Exception (_("Unable to start the player."))
            self.restart_player ()

        return self.player.current_position_value

    def update (self):
        """Update the information.

        This method is regularly called by the upper application (for
        instance a Gtk mainloop).

        Hence, it is a critical execution path and care should be
        taken with the code used here.

	@return: the current position value
        """
        # Process the event queue
        self.process_queue()

        pos=self.position_update ()

        if pos < self.last_position:
            # We did a seek compared to the last time, so we
            # invalidate the future_begins and future_ends lists
            # as well as the active_annotations
            self.reset_annotation_lists()

        self.last_position = pos

        if self.future_begins is None or self.future_ends is None:
            self.future_begins, self.future_ends = self.generate_sorted_lists (pos)

        if self.future_begins and self.player.status == self.player.PlayingStatus:
            a, b, e = self.future_begins[0]
            while b <= pos:
                # Ignore if we were after the annotation end
                self.future_begins.pop(0)
                if e > pos:
                    self.notify ("AnnotationBegin",
                                 annotation=a,
                                 immediate=True)
                    self.active_annotations.append(a)
                if self.future_begins:
                    a, b, e = self.future_begins[0]
                else:
                    break

        if self.future_ends and self.player.status == self.player.PlayingStatus:
            a, b, e = self.future_ends[0]
            while e <= pos:
                #print "Comparing %d < %d for %s" % (e, pos, a.content.data)
                try:
                    self.active_annotations.remove(a)
                except ValueError:
                    pass
                self.future_ends.pop(0)
                self.notify ("AnnotationEnd",
                             annotation=a,
                             immediate=True)
                if self.future_ends:
                    a, b, e = self.future_ends[0]
                else:
                    break

        # Update the cached duration if necessary
        if self.cached_duration <= 0 and self.player.stream_duration > 0:
            print "updating cached duration"
            self.cached_duration = self.player.stream_duration

        return pos

    def delete_annotation(self, annotation):
        """Remove the annotation from the package."""
        self.package.annotations.remove(annotation)
        self.notify('AnnotationDelete', annotation=annotation)
        return True

if __name__ == '__main__':
    c = AdveneController()
    try:
        c.main ()
    except Exception, e:
        print _("Got exception %s. Stopping services...") % str(e)
        import code
        e, v, tb = sys.exc_info()
        code.traceback.print_exception (e, v, tb)
        c.on_exit ()
        print _("*** Exception ***")
