import os
import json
import requests
import kivy
from urllib3.exceptions import InsecureRequestWarning
from glob import glob
from kivy.app import App
from kivy.core.window import Window
from kivy.properties import BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.settings import SettingsWithSidebar
from .settings import MonitorSettingsPanel
from .layout import auto_layout, load_layout
from .monitor import ShinobiMonitor
from .login import LoginPopup

kivy.require('2.1.0')

# disable HTTPS certificate check warning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


class ShinobiViewer(App):
    fullscreen = BooleanProperty(False)

    def on_fullscreen(self, instance, value):
        if value:
            Window.fullscreen = 'auto'
        else:
            Window.fullscreen = False

    def build(self):
        self.settings_cls = SettingsWithSidebar
        self.available_layouts = [
            os.path.splitext(os.path.basename(l))[0]
            for l in glob("layouts/*.kv")
        ]
        Window.bind(on_keyboard=self.on_keyboard)  # bind our handler
        self.root = BoxLayout()
        # Check if apikey is defined in config
        if self.config['shinobi']['apikey'] and self.config['shinobi']['groupkey']:
            self.add_monitors()
            return self.root
        # prompt for login if API key is not defined
        login = LoginPopup(config=self.config)
        login.open()
        login.on_dismiss = lambda: self.add_monitors()
        return self.root

    def add_monitors(self):
        monitors = self.config['monitors'].values()
        if not monitors:
            self.root.add_widget(Label(text='No monitors'))
            return self.root
        config = self.config['shinobi']
        monitor_urls = [
            '/%s/monitor/%s/%s' % (
                config['apiKey'], config['groupKey'], mid
            ) for mid in monitors
        ]
        server_url = config['server'].rstrip('/')
        if config['layout'] == 'auto':
            layout = auto_layout(len(monitors))
        else:
            layout = load_layout(config['layout'])

        self.monitor_widgets = [
            widget for widget in layout.walk(restrict=True)
            if isinstance(widget, ShinobiMonitor)
        ]
        for url, monitor in zip(monitor_urls, self.monitor_widgets):
            monitor.serverURL = server_url
            monitor.monitorPath = url
            monitor.start()
        self.root.add_widget(layout)

    def build_settings(self, settings):
        settings.add_json_panel('Connection', self.config, data=json.dumps([
            {
                "type": "string",
                "title": "Server URL",
                "desc": "URL of shinobi server",
                "section": "shinobi",
                "key": "server"
            },
            {
                "type": "string",
                "title": "API Key",
                "desc": "Server API key",
                "section": "shinobi",
                "key": "apikey"
            },
            {
                "type": "string",
                "title": "Group Key",
                "desc": "User API key",
                "section": "shinobi",
                "key": "groupkey"
            },
            {
                "type": "title",
                "title": "Monitors"
            },
            {
                "type": "options",
                "title": "Layout",
                "desc": "Monitors layout on screen",
                "section": "shinobi",
                "key": "layout",
                "options": ["auto"] + self.available_layouts
            },
        ]))
        monitors_panel = MonitorSettingsPanel(
            title="Monitors",
            settings=settings,
            config=self.config
        )
        settings.interface.add_panel(
            monitors_panel, 'Monitors', monitors_panel.uid
        )

    def build_config(self, config):
        config.setdefaults('shinobi', {
            'layout': 'auto',
            'server': '',
            'apiKey': '',
            'groupKey': ''
        })
        config.adddefaultsection('monitors')

    def get_application_config(self):
        return super().get_application_config('./%(appname)s.ini')

    def on_keyboard(self, window, key, scancode, codepoint, modifier):
        if scancode == 68: # F11
            self.fullscreen = not self.fullscreen
        if scancode == 69: # F12
            self.open_settings()

    def open_settings(self, *args, **kwargs):
        # remove all monitors
        [monitor.stop() for monitor in getattr(self, 'monitor_widgets', [])]
        self.root.clear_widgets()
        return super().open_settings(*args, **kwargs)

    def close_settings(self, *args, **kwargs):
        # re-add all monitors
        #[monitor.start() for monitor in getattr(self, 'monitor_widgets', [])]
        self.add_monitors()
        return super().close_settings(*args, **kwargs)

    def on_pause(self):
        [monitor.stop() for monitor in getattr(self, 'monitor_widgets', [])]

    def on_resume(self):
        [monitor.start() for monitor in getattr(self, 'monitor_widgets', [])]
