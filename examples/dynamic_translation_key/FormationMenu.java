package example;

public final class FormationMenu extends AbstractContainerMenu {
    private final ContainerData data;

    public FormationMenu(int id, ContainerData data) {
        super(TYPE, id);
        this.data = data;
        addDataSlots(data);
    }

    public int formation() {
        return data.get(0);
    }
}
