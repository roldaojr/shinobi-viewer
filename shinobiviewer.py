#!/usr/bin/python3
from io import BytesIO
from os import path
import math
import threading
import requests
import kivy
from kivy.app import App
from kivy.clock import Clock
from kivy.config import ConfigParser
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.lang.builder import Builder
from kivy.properties import StringProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.gridlayout import GridLayout
from kivy.uix.settings import SettingsWithSidebar


kivy.require('1.11.0')


class ShinobiMonitor(BoxLayout):
    serverURL = StringProperty()
    monitorPath = StringProperty()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)        
        self._data = {}
        self._state = 'stop'
        self.image = Image(allow_stretch=True, keep_ratio=False)
        self.add_widget(self.image)

    @property
    def snapshot_url(self):
        return '%s%s'  % (self.serverURL.rstrip('/'), self._data['snapshot'])

    @property
    def state(self):
        return self._state

    def start(self):
        self._state = 'play'
        self._image_lock = threading.Lock()
        self._image_buffer = None
        try:
            response = requests.get(
                '%s/%s' % (self.serverURL.rstrip('/'), self.monitorPath.strip('/')),
                timeout=60
            )
        except requests.exceptions.ConnectionError:
            self._retry()
        if response.status_code == 200:
            self._data = response.json()
            self.update_image()
            Clock.schedule_interval(self.update_image, 1)
        else:
            self._retry()

    def stop(self):
        self._state = 'stop'
        Clock.unschedule(self.update_image)

    def _retry(self):
        if self.state == 'play':
            self.start()

    def update_image(self, *args):
        try:
            response = requests.get(self.snapshot_url, timeout=0.5)
            if response.status_code == 200:
                data = BytesIO(response.content)
                im = CoreImage(data, ext="jpeg", nocache=True)
                self.image.texture = im.texture
                self.image.texture_size = im.texture.size
        except:
            pass


class ShinobiViewer(App):
    fullscreen = BooleanProperty()

    def on_fullscreen(self, instance, value):
        if value:
            Window.fullscreen = 'auto'
        else:
            Window.fullscreen = False
        self.config.set('graphics', 'fullscreen', value)
        self.config.write()

    def build(self):
        self.fullscreen = self.config.get('graphics', 'fullscreen')
        Window.bind(on_keyboard=self.on_keyboard)  # bind our handler
        config = self.config['shinobi']
        monitors = config['monitors'].strip().split('\n')
        monitor_urls = [
            '/%s/monitor/%s/%s' % (
                config['apiKey'], config['groupKey'], mid
            ) for mid in monitors
        ]
        server_url = config['server'].rstrip('/')
        if config['layout'] == 'auto':
            layout = self.auto_layout(len(monitors))
        else:
            layout = Builder.load_file('layouts/%s.kv' % config['layout'])

        monitor_slots = [
            widget for widget in layout.walk(restrict=True)
            if isinstance(widget, ShinobiMonitor)
        ]
        for url, monitor in zip(monitor_urls, monitor_slots):
            monitor.serverURL = server_url
            monitor.monitorPath = url
            monitor.start()
        return layout

    def build_config(self, config):
        config.setdefaults('shinobi', {
            'layout': '', 'server': '', 'apiKey': '',
            'groupKey': '', 'monitors': ''
        })
        config.setdefaults('graphics', {
            'fullscreen': 'auto'
        })

    def on_keyboard(self, window, key, scancode, codepoint, modifier):
        if scancode == 68: # F11
            self.fullscreen = not self.fullscreen

    def auto_layout(self, qtd):
        cols = math.ceil(math.sqrt(qtd))
        layout = GridLayout(cols=cols)
        for i in range(qtd):
            layout.add_widget(ShinobiMonitor())
        return layout


if __name__ == '__main__':
    ShinobiViewer().run()
