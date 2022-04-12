import math
from kivy.uix.gridlayout import GridLayout
from kivy.lang.builder import Builder
from .monitor import ShinobiMonitor


def auto_layout(qtd):
    cols = math.ceil(math.sqrt(qtd))
    layout = GridLayout(cols=cols)
    for _ in range(qtd):
        layout.add_widget(ShinobiMonitor())
    return layout


def load_layout(name):
    return Builder.load_file(f'layouts/{name}.kv')
