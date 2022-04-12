from io import BytesIO
import asyncio
import aiohttp
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.properties import StringProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image


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
        asyncio.create_task(self._fetch_metadata())

    def stop(self):
        self._state = 'stop'
        self.loading = False
        Clock.unschedule(self._update_task)

    async def _fetch_metadata(self):
        monitor_url = '%s/%s' % (self.serverURL.rstrip('/'), self.monitorPath.strip('/'))
        if self.state != 'play':
            return
        async with aiohttp.ClientSession() as session:
            async with session.get(monitor_url, verify_ssl=False) as response:
                if response.status == 200:
                    metadata = await response.json()
                    self._data = metadata[0]
                    self._update_task = Clock.schedule_interval(self._update_image, 1)

    def _update_image(self, instance):
        asyncio.create_task(self._fetch_image())

    async def _fetch_image(self):
        image_url = '%s%s'  % (self.serverURL.rstrip('/'), self._data.get('snapshot'))
        if self.state != 'play':
            return
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, verify_ssl=False) as response:
                if response.status == 200:
                    data = BytesIO(await response.read())
                    im = CoreImage(data, ext="jpeg", nocache=True)
                    self.image.texture = im.texture
                    self.image.texture_size = im.texture.size
                    if self.loading:
                        self.loading = False
