import asyncio
import aiohttp
import json
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.settings import SettingsPanel, SettingItem, SettingBoolean


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
        super().__init__(*args, **kwargs)
        self.monitors_items = []
        self.all_monitors = []
        self.add_widget(SettingItem(
            panel=self,
            title='Refresh',
            desc='Get all monitors list',
            on_release=self.refresh_touch
        ))

    def refresh_touch(self, instance):
        asyncio.create_task(self._update_list())

    async def _list_monitors(self):
        shinobi_monitors_url = '/'.join([
            self.config['shinobi']['server'].rstrip('/'),
            self.config['shinobi']['apikey'],
            'monitor',
            self.config['shinobi']['groupkey'],
        ])
        monitors = []
        async with aiohttp.ClientSession() as session:
            async with session.get(shinobi_monitors_url) as response:
                monitor_list = await response.json()
                for monitor in monitor_list:
                    details = json.loads(monitor['details'])
                    monitors.append({
                        'mid': monitor['mid'],
                        'name': monitor['name'],
                        'groups': details['groups']
                    })
        return monitors

    async def _update_list(self):
        for item in self.monitors_items:
            self.remove_widget(item)
        self.monitors_items = []
        self.all_monitors = await self._list_monitors()

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
