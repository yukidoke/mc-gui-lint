package example;

public final class MachineScreen extends AbstractContainerScreen<MachineMenu> {
    public MachineScreen(MachineMenu menu, Inventory inventory, Component title) {
        super(menu, inventory, title);
        imageHeight = 179;
        inventoryLabelY = 86;
    }

    @Override
    protected void init() {
        super.init();
        addRenderableWidget(Button.builder(
            Component.translatable("gui.example.machine.primary_action"),
            button -> sendAction(0)
        ).bounds(leftPos + 106, topPos + 24, 63, 20).build());

        addRenderableWidget(Button.builder(
            Component.translatable("gui.example.machine.secondary_action"),
            button -> sendAction(1)
        ).bounds(leftPos + 106, topPos + 50, 63, 20).build());
    }

    private void sendAction(int id) {
        // Example only.
    }

    @Override
    protected void renderBg(GuiGraphics graphics, float tick, int mouseX, int mouseY) {
        graphics.fill(leftPos, topPos, leftPos + imageWidth, topPos + imageHeight, 0xFF20252B);
        graphics.fill(leftPos + 7, topPos + 18, leftPos + 169, topPos + 85, 0xFF343B44);

        for (int slot = 0; slot < 4; slot++)
            drawSlot(graphics, leftPos + 13 + slot * 22, topPos + 34);

        drawSlot(graphics, leftPos + 35, topPos + 57);
        drawSlot(graphics, leftPos + 81, topPos + 57);

        graphics.fill(leftPos + 7, topPos + 77, leftPos + 97, topPos + 83, 0xFF14181D);
        int duration = menu.durationTicks();
        int width = duration <= 0 ? 0 : Math.min(88, menu.progressTicks() * 88 / duration);
        graphics.fill(leftPos + 8, topPos + 78, leftPos + 8 + width, topPos + 82, 0xFF55C878);

        drawPlayerInventorySlots(graphics, leftPos, topPos, 97, 155);
    }

    private static void drawSlot(GuiGraphics graphics, int x, int y) {
        graphics.fill(x, y, x + 18, y + 18, 0xFF9A9A9A);
        graphics.fill(x + 1, y + 1, x + 17, y + 17, 0xFF171B20);
    }

    private static void drawPlayerInventorySlots(
        GuiGraphics graphics, int left, int top, int inventoryY, int hotbarY
    ) {
        for (int row = 0; row < 3; row++) {
            for (int column = 0; column < 9; column++) {
                drawSlot(graphics, left + 7 + column * 18, top + inventoryY - 1 + row * 18);
            }
        }
        for (int column = 0; column < 9; column++)
            drawSlot(graphics, left + 7 + column * 18, top + hotbarY - 1);
    }

    @Override
    protected void renderLabels(GuiGraphics graphics, int mouseX, int mouseY) {
        graphics.drawString(font, title, titleLabelX, titleLabelY, 0xFFFFFF, false);
        graphics.drawString(font, playerInventoryTitle, inventoryLabelX, inventoryLabelY, 0xFFFFFF, false);
        graphics.drawString(
            font,
            Component.translatable("gui.example.machine.power", menu.powerRemaining()),
            8, 18, 0xDDDDDD, false
        );
    }
}
