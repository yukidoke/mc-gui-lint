package your.mod.debug;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.inventory.Slot;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Development-only helper for mc-gui-lint. */
public final class GuiDebugDump {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    private GuiDebugDump() {}

    public static void dump(
            Path output,
            String source,
            int physicalWidth,
            int physicalHeight,
            int guiScale,
            int logicalScreenWidth,
            int logicalScreenHeight,
            int leftPos,
            int topPos,
            int imageWidth,
            int imageHeight,
            List<Slot> slots,
            Map<String, Integer> state
    ) throws IOException {
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("source", source);

        root.put("viewport", Map.of(
                "width", physicalWidth,
                "height", physicalHeight,
                "gui_scale", guiScale
        ));

        Map<String, Object> screen = new LinkedHashMap<>();
        screen.put("logical_width", logicalScreenWidth);
        screen.put("logical_height", logicalScreenHeight);
        screen.put("left_pos", leftPos);
        screen.put("top_pos", topPos);
        screen.put("image_width", imageWidth);
        screen.put("image_height", imageHeight);
        root.put("screen", screen);

        List<Map<String, Object>> dumpedSlots = new ArrayList<>();
        Map<String, Object> stacks = new LinkedHashMap<>();

        for (int menuIndex = 0; menuIndex < slots.size(); menuIndex++) {
            Slot slot = slots.get(menuIndex);
            String name = "slot_" + menuIndex;

            Map<String, Object> slotInfo = new LinkedHashMap<>();
            slotInfo.put("index", menuIndex);
            slotInfo.put("name", name);
            slotInfo.put("x", slot.x);
            slotInfo.put("y", slot.y);
            slotInfo.put("w", 16);
            slotInfo.put("h", 16);
            dumpedSlots.add(slotInfo);

            ItemStack stack = slot.getItem();
            if (!stack.isEmpty()) {
                stacks.put(name, Map.of(
                        "item", BuiltInRegistries.ITEM.getKey(stack.getItem()).toString(),
                        "count", stack.getCount()
                ));
            }
        }

        root.put("menu_slots", dumpedSlots);
        root.put("slots", stacks);
        root.put("state", new LinkedHashMap<>(state));

        Path parent = output.toAbsolutePath().getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        Files.writeString(output, GSON.toJson(root));
    }
}
