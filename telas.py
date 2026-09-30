"""Pequenos helpers visuais; as telas maiores permanecem em app.py nesta versão."""
def active_nav_config(button,active):
    button.configure(fg_color="#464a4e" if active else "transparent",text_color="white" if active else "#efefef")
