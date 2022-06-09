import asyncio
import aiohttp
import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.button import Button


class LoginPopup(Popup):
    def __init__(self, config, *args, **kwargs):
        self.config = config
        content = self.build()
        super().__init__(
            title='Login', content=content, auto_dismiss=False,
            padding=10, size=(350, 400), size_hint=(None, None)
        )

    def build(self):
        server_url = self.config['shinobi']['server']
        input_opts = dict(write_tab=False, multiline=False, size_hint_max_y=32)

        self.input_url = TextInput(text=server_url, **input_opts)
        self.input_email = TextInput(**input_opts)
        self.input_password = TextInput(password=True, **input_opts, on_text_validate=self.do_login)
        self.login_button = Button(text ='Login', size_hint_max_y=45, on_press=self.do_login)

        layout = BoxLayout(orientation='vertical', spacing=10)
        layout.add_widget(Label(text='Server URL', size_hint_max_y=32))
        layout.add_widget(self.input_url)
        layout.add_widget(Label(text='E-mail', size_hint_max_y=32))
        layout.add_widget(self.input_email)
        layout.add_widget(Label(text='Password', size_hint_max_y=32))
        layout.add_widget(self.input_password)
        self.message = Label(text='')
        layout.add_widget(self.message)
        layout.add_widget(self.login_button)
        return layout

    def lock_controls(self, lock=False):
        self.input_url.disabled = lock
        self.input_email.disabled = lock
        self.input_password.disabled = lock
        self.login_button.disabled = lock

    def do_login(self, sender):
        if not self.input_url.text:
            self.message.text = 'Invalid server URL'
            return
        if not self.input_email.text:
            self.message.text = 'Invalid e-mail'
            return
        if not self.input_email.text:
            self.message.text = 'Invalid password'
            return

        asyncio.create_task(self._async_login())
        self.lock_controls(True)

    async def _async_login(self):
        server_url = self.input_url.text
        data = {
            'function': 'dash',
            'machineID': str(platform.node()),
            'mail': self.input_email.text,
            'pass': self.input_password.text
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f'{server_url}/?json=true', data=data) as response:
                    data = await response.json()
                    if data['ok']:
                        self.message.text = ""
                        self.config['shinobi']['server'] = server_url
                        self.config.write()
                        self.config['shinobi']['groupkey'] = data['$user']['ke']
                        self.config['shinobi']['apikey'] = data['$user']['auth_token']
                        self.dismiss()
                    else:
                        self.message.text = 'Invalid e-mail or password'
            except Exception as ex:
                self.message.text = ex.message
        self.lock_controls(False)
