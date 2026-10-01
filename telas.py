"""Pequenos helpers visuais; as telas maiores permanecem em app.py nesta versão."""
def active_nav_config(button,active):
    # Destaque azul discreto para manter o menu legível e consistente com a nova sidebar.
    button.configure(
        fg_color="#2563eb" if active else "transparent",
        hover_color="#1a2535",
        text_color="white" if active else "#f4f7fb"
    )
