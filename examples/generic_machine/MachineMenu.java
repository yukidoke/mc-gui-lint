package example;

public final class MachineMenu extends AbstractContainerMenu {
    private final ContainerData data;

    public MachineMenu(int id, Inventory playerInventory, ContainerData data) {
        super(TYPE, id);
        this.data = data;
        addDataSlots(data);

        for (int slot = 0; slot < 4; slot++)
            addSlot(new Slot(machineInventory, slot, 14 + slot * 22, 35));

        addSlot(new Slot(machineInventory, 4, 36, 58));
        addSlot(new Slot(machineInventory, 5, 82, 58));

        for (int row = 0; row < 3; row++)
            for (int column = 0; column < 9; column++)
                addSlot(new Slot(
                    playerInventory,
                    column + row * 9 + 9,
                    8 + column * 18,
                    97 + row * 18
                ));

        for (int column = 0; column < 9; column++)
            addSlot(new Slot(playerInventory, column, 8 + column * 18, 155));
    }

    public int progressTicks() { return data.get(0); }
    public int durationTicks() { return data.get(1); }
    public int powerRemaining() {
        return (data.get(2) & 0xFFFF) | ((data.get(3) & 0xFFFF) << 16);
    }
}
