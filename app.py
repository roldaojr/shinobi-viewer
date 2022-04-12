import asyncio
from shinobiviewer import ShinobiViewer

if __name__ == '__main__':
    app = ShinobiViewer()
    asyncio.run(app.async_run(async_lib='asyncio'))
    print('Kivy async app finished...')
