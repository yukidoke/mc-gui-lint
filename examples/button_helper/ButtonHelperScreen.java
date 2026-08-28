package example;

public final class ButtonHelperScreen extends AbstractContainerScreen<ButtonHelperMenu> {
    public ButtonHelperScreen(ButtonHelperMenu menu, Inventory inventory, Component title) {
        super(menu, inventory, title);
        imageHeight = 166;
    }

    @Override
    protected void init() {
        super.init();
        addActionButton(leftPos + 8, topPos + 20, Component.translatable("gui.example.action.0"));
        addActionButton(leftPos + 60, topPos + 20, Component.translatable("gui.example.action.1"));
        addButtonPair(leftPos + 8, topPos + 46);
    }

    private void addButtonPair(int x, int y) {
        addActionButton(x, y, Component.translatable("gui.example.action.2"));
        addActionButton(x + 52, y, Component.translatable("gui.example.action.3"));
    }

    private void addActionButton(int x, int y, Component label) {
        addRenderableWidget(
            Button.builder(label, button -> {})
                .bounds(x, y, 50, 20)
                .build()
        );
    }
}
