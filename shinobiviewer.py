#!/usr/bin/python3
from io import BytesIO
import os
import time
import json
import math
import threading
import requests
import kivy
from glob import glob
from kivy.app import App
from kivy.clock import Clock
from kivy.config import Config, ConfigParser
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.lang.builder import Builder
from kivy.logger import Logger
from kivy.properties import StringProperty, BooleanProperty
from kivy.loader import Loader
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.uix.settings import SettingsWithSidebar, SettingsPanel, SettingItem, SettingBoolean

kivy.require('2.0.0')


class ShinobiMonitor(BoxLayout):
    serverURL = StringProperty()
    monitorPath = StringProperty()
    loading = BooleanProperty(False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._data = {}
        self._state = 'stop'
        self._update_event = None
        self.image = Image(
            allow_stretch=True,
            keep_ratio=False
        )
        self.loading_image = Image(
            source='data/images/image-loading.gif',
            allow_stretch=False,
            keep_ratio=True
        )

    def on_loading(self, instnace, value):
        if value:
            self.remove_widget(self.image)
            self.add_widget(self.loading_image)
        else:
            self.add_widget(self.image)
            self.remove_widget(self.loading_image)

    @property
    def state(self):
        return self._state

    def start(self):
        self.loading = True
        self._state = 'play'
        self._image_lock = threading.Lock()
        self._image_buffer = None
        self.image_thread = threading.Thread(target=self._fetch_image, daemon=True)
        self.meta_thread = threading.Thread(target=self._fetch_metadata, daemon=True)
        self.meta_thread.start()

    def stop(self):
        self._state = 'stop'
        self.loading = False
        Clock.unschedule(self._update_event)

    def _fetch_metadata(self):
        monitor_url = '%s/%s' % (self.serverURL.rstrip('/'), self.monitorPath.strip('/'))
        while self.state == 'play':
            try:
                response = requests.get(monitor_url,timeout=10)
            except Exception as ex:
                Logger.debug('Failed to fetch monitor data: %s' % ex)
                time.sleep(1)
                continue
            if response.status_code == 200:
                self._data = response.json()[0]
                self.image_thread.start()
                self._update_event = Clock.schedule_interval(self._update_image, 1)
                break

    def _fetch_image(self):
        image_url = '%s%s'  % (self.serverURL.rstrip('/'), self._data.get('snapshot'))
        while self.state == 'play':
            try:
                response = requests.get(image_url, timeout=0.5)
            except Exception as ex:
                Logger.debug('Failed to fetch image: %s' % ex)
                time.sleep(0.5)
                self.loading = True
                continue
            if response.status_code == 200:
                data = BytesIO(response.content)
                im = CoreImage(data, ext="jpeg", nocache=True)
                with self._image_lock:
                    self._image_buffer = im
                if self.loading:
                    self.loading = False
            time.sleep(1)

    def _update_image(self, *args):
        im = None
        with self._image_lock:
            im = self._image_buffer
            self._image_buffer = None
        if im is not None:
            self.image.texture = im.texture
            self.image.texture_size = im.texture.size


class SortableSettingBoolean(SettingBoolean):
    def __init__(self, *args, **kwargs):
        self.__init = True
        super().__init__(*args, **kwargs)
        self.__init = False
        widget = BoxLayout(
            orientation='horizontal',
            padding=[0, 10, 0, 8])
        widget.add_widget(
            Button(
                text='up',
                on_release=lambda i: self.parent.move_updown(self, 1))
            )
        widget.add_widget(
            Button(
                text='down',
                on_release=lambda i: self.parent.move_updown(self, -1))
            )
        self.add_widget(widget)

    def on_value(self, instance, value):
        if not self.__init:
            return super().on_value(instance, value)


class MonitorSettingsPanel(SettingsPanel):
    def __init__(self, *args, **kwargs):
        self.fetch_func = kwargs.pop('fetch_func', None)
        super().__init__(*args, **kwargs)
        self.monitors_items = []
        self.all_monitors = []
        self._do_update_list = Clock.create_trigger(self._update_list)
        self._list_thread = threading.Thread(
            target=self._fetch_monitors, daemon=True
        )
        self.add_widget(SettingItem(
            panel=self,
            title='Refresh',
            desc='Get all monitors list',
            on_release=self.refresh_touch
        ))

    def refresh_touch(self, instance):
        for item in self.monitors_items:
            self.remove_widget(item)
        if not self._list_thread.is_alive():
            self._list_thread.start()

    def _fetch_monitors(self):
        monitor_list_url = '/'.join([
            self.config['shinobi']['server'].rstrip('/'),
            self.config['shinobi']['apikey'],
            'monitor',
            self.config['shinobi']['groupkey'],
        ])
        try:
            response = requests.get(monitor_list_url, timeout=30)
        except:
            pass
        else:
            for monitor in response.json():
                details = json.loads(monitor['details'])
                self.all_monitors.append({
                    'mid': monitor['mid'],
                    'name': monitor['name'],
                    'groups': details['groups']
                })
        self._do_update_list()

    def _update_list(self, *args, **kwargs):
        if len(self.all_monitors) > 0:
            enabled_monitors = []
            for mid in self.config['monitors'].values():
                for monitor in self.all_monitors:
                    if mid == monitor['mid']:
                        enabled_monitors.append(monitor)
            for monitor in enabled_monitors + [
                m for m in self.all_monitors
                if m['mid'] not in self.config['monitors'].values()
            ]:
                item = SortableSettingBoolean(
                    panel=self,
                    title=monitor['name'],
                    desc=monitor['mid'],
                    section='monitors',
                    key=monitor['mid']
                )
                self.add_widget(item)
                self.monitors_items.append(item)
        else:
            item = SettingItem(
                panel=self,
                title='No monitors to show',
                desc=''
            )
            self.add_widget(item)
            self.monitors_items.append(item)

    def get_value(self, section, key):
        if key is None:
            return
        if key in self.config[section].values():
            return '1'
        else:
            return '0'

    def set_value(self, section, key, value):
        self.save_monitors()
        if self.settings:
            self.settings.dispatch(
                'on_config_change', self.config, section, key, value
            )

    def move_updown(self, item, offset):
        for index, child in enumerate(self.children):
            if child == item:
                break
        if index + offset > - 1 and index + offset < len(self.monitors_items):
            self.remove_widget(item)
            self.add_widget(item, index+offset)
            self.save_monitors()

    def save_monitors(self):
        items_ids = [
            c.key for c in self.children
            if isinstance(c, SortableSettingBoolean) and c.value == '1'
        ]
        config = self.config
        section = 'monitors'
        if config.has_section(section):
            config.remove_section(section)
        config.add_section(section)
        for i, item in enumerate(reversed(items_ids)):
            config.set(section, str(i + 1), item)
        config.write()


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
        monitors = self.config['monitors']
        self.root = BoxLayout()
        self.add_monitors()
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
            layout = self.auto_layout(len(monitors))
        else:
            layout = Builder.load_file('layouts/%s.kv' % config['layout'])

        self.monitor_widgets = [
            widget for widget in layout.walk(restrict=True)
            if isinstance(widget, ShinobiMonitor)
        ]
        for url, monitor in zip(monitor_urls, self.monitor_widgets):
            monitor.serverURL = server_url
            monitor.monitorPath = url
            monitor.start()
        self.root.add_widget(layout)
        return self.root

    def fetch_monitors(self):
        shinobi_monitors_url = '/'.join([
            self.config['shinobi']['server'].rstrip('/'),
            self.config['shinobi']['apikey'],
            'monitor',
            self.config['shinobi']['groupkey'],
        ])
        try:
            response = requests.get(shinobi_monitors_url, timeout=60)
        except:
            return []
        finally:
            for monitor in response.json():
                details = json.loads(monitor['details'])
                yield {
                    'mid': monitor['mid'],
                    'name': monitor['name'],
                    'groups': details['groups']
                }

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
            config=self.config,
            fetch_func=self.fetch_monitors,
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

    def on_keyboard(self, window, key, scancode, codepoint, modifier):
        if scancode == 68: # F11
            self.fullscreen = not self.fullscreen

    def auto_layout(self, qtd):
        cols = math.ceil(math.sqrt(qtd))
        layout = GridLayout(cols=cols)
        for i in range(qtd):
            layout.add_widget(ShinobiMonitor())
        return layout

    def start_stop_monitors(self, start):
        for monitor in getattr(self, 'monitor_widgets', []):
            if start:
                monitor.start()
            else:
                monitor.stop()

    def open_settings(self, *args, **kwargs):
        self.start_stop_monitors(False)
        self.root.clear_widgets()
        return super().open_settings(*args, **kwargs)

    def close_settings(self, *args, **kwargs):
        self.start_stop_monitors(True)
        self.add_monitors()
        return super().close_settings(*args, **kwargs)

    def on_pause(self):
        self.start_stop_monitors(False)
        return True

    def on_resume(self):
        self.start_stop_monitors(True)

if __name__ == '__main__':
    ShinobiViewer().run()
