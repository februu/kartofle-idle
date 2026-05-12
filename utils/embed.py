from discord import Embed
from datetime import datetime


EMBED_COLOR = 0xFFFF00
EMBED_FOOTER_ICON_URL = "https://png.pngtree.com/png-clipart/20230915/original/pngtree-steamy-cog-wheel-cartoon-illustration-vector-png-image_12168440.png"
EMBED_FOOTER_TEXT = "test_name"


class CustomEmbed(Embed):
    def __init__(self, title: str, description: str):
        super().__init__(title=title, description=description, color=EMBED_COLOR, timestamp=datetime.now())
        self.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
