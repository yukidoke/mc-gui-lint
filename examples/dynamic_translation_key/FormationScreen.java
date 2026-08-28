package example;

public final class FormationScreen extends AbstractContainerScreen<FormationMenu> {
    public FormationScreen(FormationMenu menu, Inventory inventory, Component title) {
        super(menu, inventory, title);
        imageWidth = 176;
        imageHeight = 80;
    }

    @Override
    protected void renderLabels(GuiGraphics graphics, int mouseX, int mouseY) {
        graphics.drawString(
            font,
            Component.translatable("gui.example.formation." + menu.formation()),
            8,
            20,
            0xFFFFFF,
            false
        );
    }
}
