"""Configuration module.

It provides data, an instance of Config class.

It is meant to be used this way::

  import config
  print "Userid: %s" % config.data.userid

@var data: an instance of Config (Singleton)
"""
import sys
import os
import cPickle

class Config(object):
    """Configuration information, platform specific.

    It is possible to override the configuration variables in a config
    file ($HOME/.advenerc), with a python syntax (I{warning}, it is
    evaluated so harmful instructions in it can do damage).

    Example .advenerc file::

      config.data.path['vlc']='/usr/local/src/vlc-0.5.0'
      config.data.path['plugins']='/usr/local/src/vlc-0.5.0'
      config.data.path['advene']='/usr/local/bin'

    @ivar path: dictionary holding path values. The keys are:
      - vlc : path to the VLC binary
      - plugins : path to the VLC plugins
      - advene : path to the Advene modules
      - resources : path to the Advene resources (glade, template, ...)
      - data : default path to the Advene data files

    @ivar namespace: the XML namespace for Advene extensions.

    @ivar templatefilename: the filename for the XML template file
    @ivar gladefilename: the filename for the Glade XML file

    @ivar preferences: the GUI preferences
    @type preferences: dict

    @ivar options: the player options
    @type options: dict

    @ivar namespace_prefix: the list of default namespace prefixes (with alias)
    @type namespace_prefix: dict

    @ivar webserver: webserver options (port number and running mode)
    @type webserver: dict

    @ivar orb_max_tries: maximum number of tries for VLC launcher
    @type orb_max_tries: int
    """

    def __init__ (self):
        if os.sys.platform == 'win32':
            self.os='win32'
        else:
            self.os='linux'

        if self.os != 'win32':
            self.path = {
                # VLC binary path
                'vlc': '/usr/bin',
                # VLC plugins path
                'plugins': '/usr/lib/vlc',
                # Advene modules path
                'advene': '/usr/lib/advene',
                # Advene resources (.glade, template, ...) path
                'resources': '/usr/share/advene',
                # Advene data files default path
                'data': self.get_homedir(),
                # Imagecache save directory
                'imagecache': '/tmp/advene',
                # Web data files
                'web': '/usr/share/advene/web',
                # Movie files search path. _ is the
                # current package path
                'moviepath': '_',
                }
        else:
            self.path = {
                # VLC binary path
                'vlc': 'c:\\Program Files\\VideoLAN\\VLC',
                # VLC plugins path
                'plugins': 'c:\\Program Files\\VideoLAN\\VLC',
                # Advene modules path
                'advene': 'c:\\Program Files\\Advene',
                # Advene resources (.glade, template, ...) path
                'resources': 'c:\\Program Files\\Advene\\share',
                # Advene data files default path
                'data': self.get_homedir(),
                # Imagecache save directory
                'imagecache': os.getenv('TEMP') or 'c:\\',
                # Web data files
                'web': 'c:\\Program Files\\Advene\\share\\web',
                # Movie files search path. _ is the
                # current package path
                'moviepath': '_',
                }
            
        # Web-related preferences
        self.web = {
            'edit-width': 80,
            'edit-height': 25,
            }

        self.namespace = "http://experience.univ-lyon1.fr/advene/ns/advenetool"

        # These files are stored in the resources directory
        self.templatefilename = "template.xml"
        self.gladefilename = "advene.glade"

        # Generic options
        self.preferences = {
            # Various sizes of windows.
            'windowsize': { 'main': (800, 600),
                            'editpopup': (640,480),
                            'evaluator': (800, 600),
                            'relationview': (640, 480),
                            'sequenceview': (640, 480),
                            'timelineview': (800, 400),
                            'transcriptionview': (640, 480),
                            'transcribeview': (640, 480),
                            'treeview': (800, 600),
                            'browserview': (800, 600),
                            },
            'gui': { 'popup-textwidth': 40 },
            # File history
            'history': [],
            }

        # Player options
        self.player_preferences = {
            'osdtext': True,
            'default_caption_duration': 3000,
            'time_increment': 2000,
            }

        # Player options
        self.player = {
            'plugin': 'vlcnative',
            'embedded': True,
            'name': 'vlc',
            'osdfont': '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
            'verbose': None, # None, 0, 1, 2
            'snapshot': True,
            'caption': True,
            'snapshot-dimensions': (160,100),
            'snapshot-chroma': 'RV32',
            'dvd-device': 'dvd:///dev/dvd',
            }

        self.webserver = {
            'port': 1234,
            # Whether to launch the HTTP server in the gtk interface
            # 0 for no, 1 for gtk_input, 2 for threading
            'mode': 1,
            # 'default' or 'raw'
            'displaymode': 'default',
            }
        # Threading does not work correctly on Win32. Use gtk_input
        # method.
        if self.os == 'win32':            
            self.webserver['mode'] = 1
            
        # Global context options
        self.namespace_prefix = {'advenetool': self.namespace,
                                 'dc': 'http://purl.org/dc/elements/1.1/'}

        # Internal options. These should generally not be modified.

        # Used to memorize the volume level
        self.sound_volume=0


        # How many times do we try to read the iorfile before quitting ?
        self.orb_max_tries=7
        # Update delay for position marker in views (in ms)
        self.slow_update_delay=200

        # Reaction time offset (in ms) used when setting annotations
        self.reaction_time=200

        self.target_type = {
            'annotation' : 42,
            'rule' : 43,
            'view': 44,
            'schema': 45,
            'annotation-type': 46,
            'relation-type': 47,
            'relation': 48,
            }
        self.drag_type={}
        for t in self.target_type:
            self.drag_type[t] = [ ( "application/x-advene-%s-uri" % t,
                                    0,
                                    self.target_type[t] ) ]

        if self.os == 'win32':
            self.win32_specific_config()

    def win32_specific_config(self):
        if self.os != 'win32':
            return
        advenehome=self.get_registry_value('software\\advene','path')
        if advenehome is None:
            print "Cannot determine the Advene location"
            return
        print "Setting Advene paths for %s" % advenehome
        self.path['advene'] = advenehome
        self.path['resources'] = os.path.sep.join( (advenehome, 'share') )
        self.path['web'] = os.path.sep.join( (advenehome, 'share', 'web') )

    def get_registry_value (self, subkey, name):
        if self.os != 'win32':
            return None
        try:
            a=_winreg.HKEY_LOCAL_MACHINE
        except NameError:
            import _winreg
        value = None
        for hkey in _winreg.HKEY_LOCAL_MACHINE, _winreg.HKEY_CURRENT_USER:
            try:
                reg = _winreg.OpenKey(hkey, subkey)
                value, type_id = _winreg.QueryValueEx(reg, name)
                _winreg.CloseKey(reg)
            except _winreg.error:
                pass
        return value
        
    def get_homedir(self):
        if os.environ.has_key('HOME'):
            return os.environ['HOME']
        elif os.environ.has_key('HOMEPATH'):
            # Windows
            return os.sep.join((os.environ['HOMEDRIVE'],
                                     os.environ['HOMEPATH']))
        else:
            raise Exception ('Unable to find homedir')

    def read_preferences(self):
        homedir=self.get_homedir()
        if self.os == 'win32':
            filename='advene.prefs'
        else:
            filename='.advene_prefs'
        preffile=os.sep.join((homedir, filename))
        try:
            f = open(preffile, "r")
        except IOError:
            return False
        try:
            prefs=cPickle.load(f)
        except:
            return False
        self.preferences.update(prefs)
        return True

    def save_preferences(self):
        homedir=self.get_homedir()
        if self.os == 'win32':
            filename='advene.prefs'
        else:
            filename='.advene_prefs'
        preffile=os.sep.join((homedir, filename))
        try:
            f = open(preffile, "w")
        except IOError:
            return False
        try:
            cPickle.dump(self.preferences, f)
        except:
            return False
        return True

    def read_config_file (self):
        """Read the configuration file ~/.advenerc.
        """
        c=[ a for a in sys.argv if a.startswith('-c') ]
        if c:
            if len(c) > 1:
                print "Error: multiple config files are given on the command line"
                sys.exit(1)
            sys.argv.remove(c[0])
            conffile=c[0][2:]
        else:
            homedir=self.get_homedir()
            if self.os == 'win32':
                filename='advene.ini'
            else:
                filename='.advenerc'

            conffile=os.sep.join((homedir, filename))
            
        try:
            file = open(conffile, "r")
        except IOError:
            self.config_file=''
            return False

        print "Reading configuration from %s" % conffile
        config=sys.modules['advene.core.config']
        for li in file:
            if li.startswith ("#"):
                continue
            object = compile (li, conffile, 'single')
            try:
                exec object
            except Exception, e:
                print "Error in %s:\n%s" % (conffile, str(e))
        file.close ()

        self.config_file=conffile

    def get_player_args (self):
        """Build the VLC player argument list.

        @return: the list of arguments
        """
        args = [ '--plugin-path', self.path['plugins'] ]
        if self.player['verbose'] is not None:
            args.append ('--verbose')
            args.append (self.player['verbose'])
        filters=[]
        if self.player['snapshot']:
            filters.append("clone")
            args.extend (['--clone-vout-list', 'snapshot,default',
                          '--snapshot-width',
                          self.player['snapshot-dimensions'][0],
                          '--snapshot-height',
                          self.player['snapshot-dimensions'][1],
                          '--snapshot-chroma', self.player['snapshot-chroma']
                          ])
        if filters != []:
            # Some filters have been defined
            args.extend (['--filter', ":".join(filters)])
        return [ str(i) for i in args ]

    def get_userid (self):
        """Return the userid (login name).

        @return: the user id
        @rtype: string
        """
        # FIXME: allow override via .advenerc
        id = "Undefined id"
        for name in ('USER', 'USERNAME', 'LOGIN'):
            if os.environ.has_key (name):
                id = os.environ[name]
                break
        return id

    def get_typelib (self):
        """Return the name (absolute path) of the typelib file.

        @return: the absolute pathname of the typelib
        @rtype: string
        """
        if sys.platform == 'win32':
            file='MediaControl.dll'
        else:
            file='MediaControl.so'
        return self.advenefile(file, category='advene')

    def get_iorfile (self):
        """Return the absolute name of the IOR file.

        @return: the absolute pathname of the IOR file
        @rtype: string
        """
        # FIXME
        #d=self.get_homedir()

        if sys.platform == 'win32':
            if os.environ.has_key ('TEMP'):
                d = os.environ['TEMP']
            else:
                d = "\\"
        else:
            d="/tmp"
        return os.path.join (d, 'vlc-ior.ref')

    def advenefile(self, filename, category='resources'):
        """Return an absolute pathname for the given file.

        @param filename: a filename or a path to a file (tuple)
        @type filename: string or tuple
        @param category: the category of the file
        @type category: string
        
        @return: an absolute pathname
        @rtype: string
        """
        if isinstance(filename, list) or isinstance(filename, tuple):
            filename=os.sep.join(filename)
        return os.sep.join ( ( self.path[category], filename ) )

    userid = property (fget=get_userid,
                       doc="Login name of the user")
    typelib = property (fget=get_typelib,
                        doc="Typelib module library")
    iorfile = property (fget=get_iorfile,
                        doc="Location of the IOR file for the VLC corba interface")
    player_args = property (fget=get_player_args,
                            doc="List of arguments for the VLC player")

data = Config ()
data.read_config_file ()
data.read_preferences()
#print "Read config file %s" % data.config_file
