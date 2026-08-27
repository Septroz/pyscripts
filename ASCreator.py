import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, colorchooser
import os
import sys

SNAP_DISTANCE = 30  # Pixel distance to trigger snapping
SAVE_FILENAME = "ASCreator.save"

# --- DROPDOWN OPTIONS ---
ANT_OPTIONS = [
    "Fire ant 1", "Fire ant 2", "Fire ant 3", "Fire ant 4", "Fire ant 5",
    "Weaver ant 1", "Weaver ant 2", "Weaver ant 3",
    "#weaverants",
    "#fireants",
    "!#fireants",
    "!#weaverants",
    "!Fire ant 1",
    "!Fire ant 2",
    "!Fire ant 3",
    "!Weaver ant 1",
    "!Weaver ant 2",
    "!Weaver ant 3"
]

SUMMON_ANT_OPTIONS = [
    "Fire ant", "Weaver ant", "Weaver ant queen", "Fire ant queen"
]

OBJECT_OPTIONS = [
    "Leaf", "Lava", "Water", "Wood", "Metal", "Silk",
    "Citrus", "Mangosteen", "Mango", "Apple", "Orange", "Lemon"
]

HAND_OPTIONS = ["Main hand", "Off-hand"]
DIRECTION_OPTIONS = ["Up", "Down", "Left", "Right", "Behind", "In front"]

# --- COLOR PRESETS ---
BLOCK_COLORS = {
    "Green": "#27AE60",
    "Blue": "#2980B9",
    "Red": "#C0392B",
    "Purple": "#8E44AD",
    "Orange": "#D35400",
    "Dark Gray": "#34495E",
    "Teal": "#16A085"
}


# --- AUTO-RESIZING ENTRY WIDGET ---
class AutoResizingEntry(tk.Entry):
    def __init__(self, parent, min_width=3, **kwargs):
        self.min_width = min_width
        super().__init__(parent, **kwargs)
        self.var = tk.StringVar(master=self)
        self.config(textvariable=self.var)
        self.var.trace_add("write", self.resize)
        self.resize()

    def resize(self, *args):
        text_length = len(self.var.get())
        new_width = max(self.min_width, text_length + 1)
        self.config(width=new_width)


# --- BASE BLOCK CLASS ---
class Block(tk.Frame):
    def __init__(self, parent, title, bg_color, is_palette=False, **kwargs):
        super().__init__(parent, bg=bg_color, bd=2, relief="raised", padx=6, pady=6, **kwargs)
        self.title = title
        self.bg_color = bg_color
        self.is_palette = is_palette
        
        # Snapping relationships
        self.parent_block = None
        self.child_block = None
        
        # Dragging state
        self._drag_start_x = 0
        self._drag_start_y = 0

        # Title Label
        if title:
            self.label = tk.Label(self, text=title, bg=bg_color, fg="white", font=("Helvetica", 10, "bold"))
            self.label.pack(side="left", padx=(0, 5))

        self.setup_widgets()
        self.bind_events_recursively(self)

    def bind_events_recursively(self, widget):
        """Bind click, drag, right-click menu, and double-click delete to components."""
        is_interactive = isinstance(widget, (ttk.Combobox, tk.Entry, tk.Spinbox, tk.Button))
        right_click_event = "<Button-3>" if sys.platform != "darwin" else "<Button-2>"
        
        if self.is_palette:
            if not is_interactive:
                widget.bind("<Button-1>", self.on_palette_click)
                widget.bind(right_click_event, self.show_palette_context_menu)
        else:
            if not is_interactive:
                widget.bind("<Button-1>", self.on_drag_start)
                widget.bind("<B1-Motion>", self.on_drag_motion)
                widget.bind("<ButtonRelease-1>", self.on_drag_end)
                widget.bind("<Double-Button-1>", self.confirm_destroy_block)
            
            widget.bind(right_click_event, self.show_context_menu)

        for child in widget.winfo_children():
            self.bind_events_recursively(child)

    def setup_widgets(self):
        pass

    def show_palette_context_menu(self, event):
        """Override in child classes if palette right-click menu is needed."""
        pass

    def get_workspace(self):
        top = self.winfo_toplevel()
        return getattr(top, 'workspace', self.master)

    def show_context_menu(self, event):
        """Right-click menu to remove block in workspace mode."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="🗑️ Remove Block", command=self.confirm_destroy_block)
        if self.child_block:
            menu.add_command(label="🗑️ Remove Block & Stack Below", command=lambda: self.destroy_block(delete_stack=True))
        menu.tk_popup(event.x_root, event.y_root)

    def confirm_destroy_block(self, event=None):
        """Safely destroy this block and heal the chain if sub-blocks exist."""
        self.destroy_block(delete_stack=False)

    def destroy_block(self, delete_stack=False):
        """Unlink connections and remove widget(s)."""
        if delete_stack:
            if self.child_block:
                self.child_block.destroy_block(delete_stack=True)
        else:
            if self.parent_block and self.child_block:
                self.parent_block.child_block = self.child_block
                self.child_block.parent_block = self.parent_block
                self.child_block.snap_to_parent()
            elif self.parent_block:
                self.parent_block.child_block = None
            elif self.child_block:
                self.child_block.parent_block = None

        self.parent_block = None
        self.child_block = None
        self.destroy()

        top = self.winfo_toplevel()
        if hasattr(top, 'update_workspace_scroll'):
            top.update_workspace_scroll()

    def on_palette_click(self, event):
        """Spawn copy in workspace reliably."""
        workspace = self.get_workspace()
        new_block = self.__class__(workspace)
        
        canvas_x = workspace.canvasx(event.x_root - workspace.winfo_rootx()) - 20
        canvas_y = workspace.canvasy(event.y_root - workspace.winfo_rooty()) - 10
        
        new_block.place(x=max(10, canvas_x), y=max(10, canvas_y))
        top = self.winfo_toplevel()
        if hasattr(top, 'update_workspace_scroll'):
            top.update_workspace_scroll()

    def on_drag_start(self, event):
        self.lift_stack()
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        
        if self.parent_block:
            self.parent_block.child_block = None
            self.parent_block = None

    def on_drag_motion(self, event):
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        self.move_stack(dx, dy)

    def on_drag_end(self, event):
        """Check proximity to other blocks and snap if close enough."""
        workspace = self.get_workspace()
        for widget in workspace.winfo_children():
            if isinstance(widget, Block) and widget is not self and not widget.is_palette:
                root = widget
                while root.parent_block:
                    root = root.parent_block
                if root is self:
                    continue

                my_x, my_y = self.winfo_x(), self.winfo_y()
                target_x = widget.winfo_x()
                target_y = widget.winfo_y() + widget.winfo_height()

                if abs(my_x - target_x) < SNAP_DISTANCE and abs(my_y - target_y) < SNAP_DISTANCE:
                    if widget.child_block:
                        self.child_block = widget.child_block
                        self.child_block.parent_block = self
                    
                    widget.child_block = self
                    self.parent_block = widget
                    self.snap_to_parent()
                    break

        top = self.winfo_toplevel()
        if hasattr(top, 'update_workspace_scroll'):
            top.update_workspace_scroll()

    def snap_to_parent(self):
        if self.parent_block:
            new_x = self.parent_block.winfo_x()
            new_y = self.parent_block.winfo_y() + self.parent_block.winfo_height() + 2
            self.place(x=new_x, y=new_y)
            if self.child_block:
                self.child_block.snap_to_parent()

    def lift_stack(self):
        self.lift()
        if self.child_block:
            self.child_block.lift_stack()

    def move_stack(self, dx, dy):
        new_x = self.winfo_x() + dx
        new_y = self.winfo_y() + dy
        self.place(x=new_x, y=new_y)
        if self.child_block:
            self.child_block.move_stack(dx, dy)


# --- DYNAMIC CUSTOM BLOCK ---
class DynamicCustomBlock(Block):
    def __init__(self, parent, elements_schema=None, color="#27AE60", is_palette=False, block_id=None):
        self.elements_schema = elements_schema or []
        self.block_color = color
        self.block_id = block_id
        super().__init__(parent, "", self.block_color, is_palette)

    def setup_widgets(self):
        for elem in self.elements_schema:
            etype = elem.get("type")
            val = elem.get("val", "")

            if etype == "text":
                lbl = tk.Label(self, text=val, bg=self.bg_color, fg="white", font=("Helvetica", 10, "bold"))
                lbl.pack(side="left", padx=(0, 4))
            elif etype == "empty_slot":
                slot = tk.Label(self, text=" [  ] ", bg="#1E8449", fg="white", font=("Helvetica", 9, "bold"), bd=1, relief="sunken")
                slot.pack(side="left", padx=(0, 4))
            elif etype == "ant":
                combo = ttk.Combobox(self, values=ANT_OPTIONS, width=12, state="readonly")
                combo.current(0)
                combo.pack(side="left", padx=(0, 4))
            elif etype == "hand":
                combo = ttk.Combobox(self, values=HAND_OPTIONS, width=10, state="readonly")
                combo.current(0)
                combo.pack(side="left", padx=(0, 4))
            elif etype == "direction":
                combo = ttk.Combobox(self, values=DIRECTION_OPTIONS, width=8, state="readonly")
                combo.current(0)
                combo.pack(side="left", padx=(0, 4))
            elif etype == "custom_dropdown":
                opts = val if isinstance(val, list) and val else ["Option 1"]
                combo = ttk.Combobox(self, values=opts, width=10, state="readonly")
                combo.current(0)
                combo.pack(side="left", padx=(0, 4))
            elif etype == "input":
                ent = AutoResizingEntry(self, min_width=6)
                ent.var.set("...")
                ent.pack(side="left", padx=(0, 4))
            elif etype == "number":
                spin = tk.Spinbox(self, from_=0, to=999, width=4)
                spin.pack(side="left", padx=(0, 4))
            elif etype == "object":
                combo = ttk.Combobox(self, values=OBJECT_OPTIONS, width=10, state="readonly")
                combo.current(0)
                combo.pack(side="left", padx=(0, 4))

    def show_palette_context_menu(self, event):
        """Right-click menu for custom blocks residing in the palette sidebar."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="✏️ Edit", command=self.edit_custom_block)
        menu.add_command(label="🗑️ Delete", command=self.delete_custom_block)
        menu.tk_popup(event.x_root, event.y_root)

    def edit_custom_block(self):
        top = self.winfo_toplevel()
        if hasattr(top, 'edit_custom_block'):
            top.edit_custom_block(self.block_id, self.elements_schema, self.block_color)

    def delete_custom_block(self):
        top = self.winfo_toplevel()
        if hasattr(top, 'delete_custom_block'):
            top.delete_custom_block(self.block_id)

    def on_palette_click(self, event):
        workspace = self.get_workspace()
        new_block = DynamicCustomBlock(
            workspace, 
            elements_schema=self.elements_schema, 
            color=self.block_color, 
            is_palette=False,
            block_id=self.block_id
        )
        canvas_x = workspace.canvasx(event.x_root - workspace.winfo_rootx()) - 20
        canvas_y = workspace.canvasy(event.y_root - workspace.winfo_rooty()) - 10
        new_block.place(x=max(10, canvas_x), y=max(10, canvas_y))
        top = self.winfo_toplevel()
        if hasattr(top, 'update_workspace_scroll'):
            top.update_workspace_scroll()


# --- ACTION BLOCKS ---

class HealAntBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "Heal ant", "#4CAF50", is_palette)

    def setup_widgets(self):
        self.combo = ttk.Combobox(self, values=ANT_OPTIONS, width=15, state="readonly")
        self.combo.current(0)
        self.combo.pack(side="left")


class KillAntBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "Kill", "#F44336", is_palette)

    def setup_widgets(self):
        self.combo = ttk.Combobox(self, values=ANT_OPTIONS, width=15, state="readonly")
        self.combo.current(0)
        self.combo.pack(side="left")


class ChangeDisplayNameBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "Change display name of", "#2196F3", is_palette)

    def setup_widgets(self):
        self.combo = ttk.Combobox(self, values=ANT_OPTIONS, width=15, state="readonly")
        self.combo.current(0)
        self.combo.pack(side="left", padx=(0, 5))

        self.label_to = tk.Label(self, text="to", bg=self.bg_color, fg="white", font=("Helvetica", 10, "bold"))
        self.label_to.pack(side="left", padx=(0, 5))

        self.entry = AutoResizingEntry(self, min_width=8)
        self.entry.var.set("New Name")
        self.entry.pack(side="left")


class GetLeaderBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "Get main leader/queen of", "#9C27B0", is_palette)

    def setup_widgets(self):
        self.combo = ttk.Combobox(self, values=ANT_OPTIONS, width=15, state="readonly")
        self.combo.current(0)
        self.combo.pack(side="left", padx=(0, 5))

        self.btn_remove = tk.Button(self, text="Remove Dropdown", command=self.replace_with_target, 
                                    bg="#7B1FA2", fg="white", font=("Helvetica", 8), bd=1)
        self.btn_remove.pack(side="left")

    def replace_with_target(self):
        self.combo.destroy()
        self.btn_remove.destroy()
        
        target_label = tk.Label(self, text="[Target ant]", bg="#BA68C8", fg="white", 
                                font=("Helvetica", 9, "bold"), bd=1, relief="solid", padx=4)
        target_label.pack(side="left")
        self.bind_events_recursively(self)


class SetObjectBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "Set object at", "#009688", is_palette)

    def setup_widgets(self):
        self.entry_x = AutoResizingEntry(self, min_width=2)
        self.entry_x.var.set("0")
        self.entry_x.pack(side="left", padx=(0, 3))

        self.entry_y = AutoResizingEntry(self, min_width=2)
        self.entry_y.var.set("0")
        self.entry_y.pack(side="left", padx=(0, 3))

        self.entry_z = AutoResizingEntry(self, min_width=2)
        self.entry_z.var.set("0")
        self.entry_z.pack(side="left", padx=(0, 5))

        self.label_to = tk.Label(self, text="to", bg=self.bg_color, fg="white", font=("Helvetica", 10, "bold"))
        self.label_to.pack(side="left", padx=(0, 5))

        self.combo = ttk.Combobox(self, values=OBJECT_OPTIONS, width=10, state="readonly")
        self.combo.current(0)
        self.combo.pack(side="left")


class SummonBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "Summon", "#E91E63", is_palette)

    def setup_widgets(self):
        self.combo = ttk.Combobox(self, values=SUMMON_ANT_OPTIONS, width=15, state="readonly")
        self.combo.current(0)
        self.combo.pack(side="left", padx=(0, 5))

        self.label_coords = tk.Label(self, text="at coordinates", bg=self.bg_color, fg="white", font=("Helvetica", 10, "bold"))
        self.label_coords.pack(side="left", padx=(0, 5))

        self.entry_x = AutoResizingEntry(self, min_width=2)
        self.entry_x.var.set("0")
        self.entry_x.pack(side="left", padx=(0, 3))

        self.entry_y = AutoResizingEntry(self, min_width=2)
        self.entry_y.var.set("0")
        self.entry_y.pack(side="left", padx=(0, 3))

        self.entry_z = AutoResizingEntry(self, min_width=2)
        self.entry_z.var.set("0")
        self.entry_z.pack(side="left")


class ChangeItemHandBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "Change item in", "#009688", is_palette)

    def setup_widgets(self):
        self.combo_hand = ttk.Combobox(self, values=HAND_OPTIONS, width=10, state="readonly")
        self.combo_hand.current(0)
        self.combo_hand.pack(side="left", padx=(0, 5))

        self.lbl_to = tk.Label(self, text="to", bg=self.bg_color, fg="white", font=("Helvetica", 10, "bold"))
        self.lbl_to.pack(side="left", padx=(0, 5))

        self.combo_obj = ttk.Combobox(self, values=OBJECT_OPTIONS, width=10, state="readonly")
        self.combo_obj.current(0)
        self.combo_obj.pack(side="left")


# --- CONTROL BLOCKS ---

class IfDoBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "if", "#FF5722", is_palette)

    def setup_widgets(self):
        self.condition_slot = tk.Label(self, text=" [  ] ", bg="#E64A19", fg="white", font=("Helvetica", 9))
        self.condition_slot.pack(side="left", padx=(0, 5))

        self.lbl_do = tk.Label(self, text="do", bg=self.bg_color, fg="white", font=("Helvetica", 10, "bold"))
        self.lbl_do.pack(side="left", padx=(0, 5))

        self.action_slot = tk.Label(self, text=" [  ] ", bg="#E64A19", fg="white", font=("Helvetica", 9))
        self.action_slot.pack(side="left")


class IfDoElseBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "if", "#FF5722", is_palette)

    def setup_widgets(self):
        self.condition_slot = tk.Label(self, text=" [  ] ", bg="#E64A19", fg="white", font=("Helvetica", 9))
        self.condition_slot.pack(side="left", padx=(0, 5))

        self.lbl_do = tk.Label(self, text="do", bg=self.bg_color, fg="white", font=("Helvetica", 10, "bold"))
        self.lbl_do.pack(side="left", padx=(0, 5))

        self.action_slot1 = tk.Label(self, text=" [  ] ", bg="#E64A19", fg="white", font=("Helvetica", 9))
        self.action_slot1.pack(side="left", padx=(0, 5))

        self.lbl_else = tk.Label(self, text="else", bg=self.bg_color, fg="white", font=("Helvetica", 10, "bold"))
        self.lbl_else.pack(side="left", padx=(0, 5))

        self.action_slot2 = tk.Label(self, text=" [  ] ", bg="#E64A19", fg="white", font=("Helvetica", 9))
        self.action_slot2.pack(side="left")


# --- CHECK BLOCKS ---

class CheckDisplayNameBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "Display name of", "#607D8B", is_palette)

    def setup_widgets(self):
        self.combo = ttk.Combobox(self, values=ANT_OPTIONS, width=15, state="readonly")
        self.combo.current(0)
        self.combo.pack(side="left", padx=(0, 5))

        self.lbl_is = tk.Label(self, text="is", bg=self.bg_color, fg="white", font=("Helvetica", 10, "bold"))
        self.lbl_is.pack(side="left", padx=(0, 5))

        self.entry = AutoResizingEntry(self, min_width=8)
        self.entry.pack(side="left")


class CheckInsideWaterBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "", "#607D8B", is_palette)

    def setup_widgets(self):
        self.combo = ttk.Combobox(self, values=ANT_OPTIONS, width=15, state="readonly")
        self.combo.current(0)
        self.combo.pack(side="left", padx=(0, 5))

        self.lbl_water = tk.Label(self, text="Currently inside water", bg=self.bg_color, fg="white", font=("Helvetica", 10, "bold"))
        self.lbl_water.pack(side="left")


class CheckTouchesBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "", "#607D8B", is_palette)

    def setup_widgets(self):
        self.combo_ant = ttk.Combobox(self, values=ANT_OPTIONS, width=15, state="readonly")
        self.combo_ant.current(0)
        self.combo_ant.pack(side="left", padx=(0, 5))

        self.lbl_touches = tk.Label(self, text="Touches", bg=self.bg_color, fg="white", font=("Helvetica", 10, "bold"))
        self.lbl_touches.pack(side="left", padx=(0, 5))

        self.combo_obj = ttk.Combobox(self, values=OBJECT_OPTIONS, width=10, state="readonly")
        self.combo_obj.current(0)
        self.combo_obj.pack(side="left")


# --- VARIABLE & REPORTERS BLOCKS ---

class GetCoordBlock(Block):
    def __init__(self, parent, coord_name="X", is_palette=False):
        self.coord_name = coord_name
        super().__init__(parent, f"Get {coord_name} Coordinate of", "#00BCD4", is_palette)

    def setup_widgets(self):
        self.combo = ttk.Combobox(self, values=ANT_OPTIONS, width=15, state="readonly")
        self.combo.current(0)
        self.combo.pack(side="left")


class GetEmptyCoordBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "Get", "#00BCD4", is_palette)

    def setup_widgets(self):
        self.slot = tk.Label(self, text=" [  ] ", bg="#00838F", fg="white", font=("Helvetica", 9))
        self.slot.pack(side="left", padx=(0, 4))

        self.lbl = tk.Label(self, text="coordinate of", bg=self.bg_color, fg="white", font=("Helvetica", 10, "bold"))
        self.lbl.pack(side="left", padx=(0, 4))

        self.combo = ttk.Combobox(self, values=ANT_OPTIONS, width=15, state="readonly")
        self.combo.current(0)
        self.combo.pack(side="left")


class MaxHealthVariableBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "Max health of", "#FF9800", is_palette)

    def setup_widgets(self):
        self.entry = AutoResizingEntry(self, min_width=5)
        self.entry.pack(side="left")


class TargetAntVariableBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "Target ant", "#FF9800", is_palette)


class SourceAntVariableBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "Source ant", "#FF9800", is_palette)


class XVariableBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "x", "#00BCD4", is_palette)


class YVariableBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "y", "#00BCD4", is_palette)


class ZVariableBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "z", "#00BCD4", is_palette)


class GetPositionVariableBlock(Block):
    def __init__(self, parent, is_palette=False):
        super().__init__(parent, "Get position", "#673AB7", is_palette)

    def setup_widgets(self):
        self.spin = tk.Spinbox(self, from_=1, to=100, width=3)
        self.spin.pack(side="left", padx=(0, 4))

        self.lbl1 = tk.Label(self, text="Blocks away of", bg=self.bg_color, fg="white", font=("Helvetica", 9, "bold"))
        self.lbl1.pack(side="left", padx=(0, 4))

        self.combo_ant = ttk.Combobox(self, values=ANT_OPTIONS, width=12, state="readonly")
        self.combo_ant.current(0)
        self.combo_ant.pack(side="left", padx=(0, 4))

        self.lbl2 = tk.Label(self, text="in direction", bg=self.bg_color, fg="white", font=("Helvetica", 9, "bold"))
        self.lbl2.pack(side="left", padx=(0, 4))

        self.combo_dir = ttk.Combobox(self, values=DIRECTION_OPTIONS, width=8, state="readonly")
        self.combo_dir.current(0)
        self.combo_dir.pack(side="left")


# --- CUSTOM BLOCK CREATOR MODAL ---

class CustomBlockCreatorDialog(tk.Toplevel):
    def __init__(self, parent, on_create_callback, initial_schema=None, initial_color="#27AE60", is_editing=False):
        super().__init__(parent)
        self.title("Edit Custom Block" if is_editing else "Custom Block Setup")
        self.geometry("850x500")
        self.transient(parent)
        self.grab_set()

        self.on_create_callback = on_create_callback
        self.active_elements = []
        self.selected_color = initial_color
        self.is_editing = is_editing

        self.setup_ui()
        if initial_schema:
            self.load_initial_schema(initial_schema)

    def setup_ui(self):
        lbl_info = tk.Label(self, text="Click components to add them to your custom block:", font=("Helvetica", 10, "bold"))
        lbl_info.pack(anchor="w", padx=10, pady=5)

        main_frame = tk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)

        palette = tk.Frame(main_frame, bg="#34495E", width=240, padx=8, pady=8)
        palette.pack(side="left", fill="y", padx=(0, 10))

        tk.Label(palette, text="COMPONENTS", bg="#34495E", fg="white", font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(0, 5))

        components = [
            ("(Text)", "text"),
            ("(Empty Block Slot)", "empty_slot"),
            ("(Ant options dropdown)", "ant"),
            ("(Hand options dropdown)", "hand"),
            ("(Direction options dropdown)", "direction"),
            ("(Custom dropdown)", "custom_dropdown"),
            ("(Input box)", "input"),
            ("(Number box)", "number"),
            ("(Object options dropdown)", "object")
        ]

        for label, comp_type in components:
            btn = tk.Button(palette, text=label, anchor="w", bg="#1ABC9C", fg="white", 
                            font=("Helvetica", 9, "bold"), bd=1, relief="raised",
                            command=lambda t=comp_type: self.add_element(t))
            btn.pack(fill="x", pady=2)

        preview_frame = tk.Frame(main_frame, bg="#ECF0F1", bd=2, relief="sunken")
        preview_frame.pack(side="right", fill="both", expand=True)

        top_controls = tk.Frame(preview_frame, bg="#ECF0F1")
        top_controls.pack(fill="x", padx=10, pady=5)

        tk.Label(top_controls, text="Block Color:", bg="#ECF0F1", font=("Helvetica", 9, "bold")).pack(side="left", padx=(0, 5))

        self.color_combo = ttk.Combobox(top_controls, values=list(BLOCK_COLORS.keys()) + ["Custom..."], state="readonly", width=12)
        
        match_preset = False
        for name, hex_val in BLOCK_COLORS.items():
            if hex_val.lower() == self.selected_color.lower():
                self.color_combo.set(name)
                match_preset = True
                break
        if not match_preset:
            self.color_combo.set("Custom...")

        self.color_combo.pack(side="left", padx=(0, 5))
        self.color_combo.bind("<<ComboboxSelected>>", self.on_color_select)

        self.color_preview = tk.Label(top_controls, width=3, bg=self.selected_color, relief="solid", bd=1)
        self.color_preview.pack(side="left")

        tk.Label(preview_frame, text="Custom Block Preview:", bg="#ECF0F1", font=("Helvetica", 9, "bold")).pack(anchor="w", padx=10, pady=(5, 0))

        preview_canvas_frame = tk.Frame(preview_frame, bg="#ECF0F1")
        preview_canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.preview_scrollbar = tk.Scrollbar(preview_canvas_frame, orient="horizontal")
        self.preview_scrollbar.pack(side="bottom", fill="x")

        self.preview_canvas = tk.Canvas(preview_canvas_frame, bg="#ECF0F1", highlightthickness=0,
                                        xscrollcommand=self.preview_scrollbar.set)
        self.preview_canvas.pack(side="top", fill="both", expand=True)

        self.preview_scrollbar.config(command=self.preview_canvas.xview)

        self.block_container = tk.Frame(self.preview_canvas, bg=self.selected_color, bd=2, relief="raised", padx=8, pady=8)
        self.canvas_window = self.preview_canvas.create_window((0, 0), window=self.block_container, anchor="nw")

        self.block_container.bind("<Configure>", self.update_scroll_region)

        footer = tk.Frame(self)
        footer.pack(fill="x", padx=10, pady=10)

        btn_title = "Update Block" if self.is_editing else "Create Block"
        btn_save = tk.Button(footer, text=btn_title, bg="#27AE60", fg="white", font=("Helvetica", 10, "bold"), padx=15, command=self.save_block)
        btn_save.pack(side="right", padx=5)

        btn_clear = tk.Button(footer, text="Clear All", bg="#E74C3C", fg="white", font=("Helvetica", 10, "bold"), padx=10, command=self.clear_elements)
        btn_clear.pack(side="right", padx=5)

    def load_initial_schema(self, schema):
        for elem in schema:
            etype = elem.get("type")
            val = elem.get("val", "")
            self.add_element(etype, initial_val=val)

    def update_scroll_region(self, event=None):
        self.preview_canvas.config(scrollregion=self.preview_canvas.bbox("all"))

    def on_color_select(self, event):
        val = self.color_combo.get()
        if val == "Custom...":
            color_code = colorchooser.askcolor(title="Choose Block Color", initialcolor=self.selected_color)[1]
            if color_code:
                self.selected_color = color_code
        else:
            self.selected_color = BLOCK_COLORS.get(val, "#27AE60")

        self.color_preview.config(bg=self.selected_color)
        self.block_container.config(bg=self.selected_color)
        for item in self.active_elements:
            item["widget"].config(bg=self.selected_color)

    def add_element(self, comp_type, initial_val=None):
        wrapper = tk.Frame(self.block_container, bg=self.selected_color)
        wrapper.pack(side="left", padx=2)

        elem_data = {"type": comp_type, "val": "", "widget": wrapper}

        if comp_type == "text":
            ent = AutoResizingEntry(wrapper, min_width=4)
            ent.var.set(initial_val if initial_val is not None else "Text")
            ent.pack(side="left")
            elem_data["entry_var"] = ent.var

        elif comp_type == "empty_slot":
            slot = tk.Label(wrapper, text=" [  ] ", bg="#1E8449", fg="white", font=("Helvetica", 9, "bold"), bd=1, relief="sunken")
            slot.pack(side="left")

        elif comp_type == "ant":
            cb = ttk.Combobox(wrapper, values=ANT_OPTIONS, width=10, state="readonly")
            cb.current(0)
            cb.pack(side="left")

        elif comp_type == "hand":
            cb = ttk.Combobox(wrapper, values=HAND_OPTIONS, width=8, state="readonly")
            cb.current(0)
            cb.pack(side="left")

        elif comp_type == "direction":
            cb = ttk.Combobox(wrapper, values=DIRECTION_OPTIONS, width=8, state="readonly")
            cb.current(0)
            cb.pack(side="left")

        elif comp_type == "custom_dropdown":
            opts = initial_val if isinstance(initial_val, list) and initial_val else ["Option 1"]
            cb = ttk.Combobox(wrapper, values=opts, width=10, state="readonly")
            cb.current(0)
            cb.pack(side="left", padx=(0, 2))

            btn_add = tk.Button(wrapper, text="+", bg="#2ECC71", fg="white", font=("Helvetica", 8, "bold"),
                                command=lambda: self.add_custom_dropdown_option(cb, opts))
            btn_add.pack(side="left", padx=(0, 1))

            btn_remove = tk.Button(wrapper, text="X", bg="#E74C3C", fg="white", font=("Helvetica", 8, "bold"),
                                   command=lambda: self.remove_custom_dropdown_option(cb, opts))
            btn_remove.pack(side="left")
            
            elem_data["opts"] = opts

        elif comp_type == "input":
            ent = AutoResizingEntry(wrapper, min_width=5)
            ent.var.set(initial_val if initial_val is not None else "...")
            ent.pack(side="left")

        elif comp_type == "number":
            spin = tk.Spinbox(wrapper, from_=0, to=999, width=4)
            spin.pack(side="left")

        elif comp_type == "object":
            cb = ttk.Combobox(wrapper, values=OBJECT_OPTIONS, width=9, state="readonly")
            cb.current(0)
            cb.pack(side="left")

        btn_del_elem = tk.Button(wrapper, text="×", bg="#C0392B", fg="white", font=("Helvetica", 9, "bold"),
                                 bd=0, padx=2, command=lambda e=elem_data: self.remove_single_element(e))
        btn_del_elem.pack(side="left", padx=(3, 0))

        self.active_elements.append(elem_data)
        self.update_scroll_region()

    def remove_single_element(self, elem_data):
        if elem_data in self.active_elements:
            elem_data["widget"].destroy()
            self.active_elements.remove(elem_data)
            self.update_scroll_region()

    def add_custom_dropdown_option(self, cb, opts_list):
        new_opt = simpledialog.askstring("Add Option", "Enter option name:", parent=self)
        if new_opt:
            opts_list.append(new_opt)
            cb["values"] = list(opts_list)
            cb.current(len(opts_list) - 1)

    def remove_custom_dropdown_option(self, cb, opts_list):
        if not opts_list:
            messagebox.showinfo("Info", "No options left to remove!", parent=self)
            return

        remove_dialog = tk.Toplevel(self)
        remove_dialog.title("Remove Option")
        remove_dialog.geometry("300x130")
        remove_dialog.transient(self)
        remove_dialog.grab_set()

        tk.Label(remove_dialog, text="Select option to remove:", font=("Helvetica", 9, "bold")).pack(pady=(10, 5))

        target_combo = ttk.Combobox(remove_dialog, values=opts_list, state="readonly", width=20)
        target_combo.current(0)
        target_combo.pack(pady=5)

        def do_remove():
            selected = target_combo.get()
            if selected in opts_list:
                opts_list.remove(selected)
                cb["values"] = list(opts_list)
                if opts_list:
                    cb.current(0)
                else:
                    cb.set("")
            remove_dialog.destroy()

        btn_confirm = tk.Button(remove_dialog, text="Remove", bg="#E74C3C", fg="white", 
                                font=("Helvetica", 9, "bold"), command=do_remove)
        btn_confirm.pack(pady=5)

    def clear_elements(self):
        for item in self.active_elements:
            item["widget"].destroy()
        self.active_elements.clear()
        self.update_scroll_region()

    def save_block(self):
        if not self.active_elements:
            messagebox.showwarning("Warning", "Add at least one element to your block!", parent=self)
            return

        schema = []
        for item in self.active_elements:
            t = item["type"]
            val = ""
            if t == "text":
                val = item["entry_var"].get()
            elif t == "custom_dropdown":
                val = list(item["opts"])
            schema.append({"type": t, "val": val})

        self.on_create_callback(schema, self.selected_color)
        self.destroy()


# --- MAIN APPLICATION FRAMEWORK ---

class MakeBlockApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MakeBlock Ant Builder")
        self.geometry("1150x750")

        self.custom_blocks_list = []
        self.palette_block_widgets = {}

        self.notebook = ttk.Notebook(self, width=420)
        self.notebook.pack(side="left", fill="y")

        self.workspace_frame = tk.Frame(self)
        self.workspace_frame.pack(side="right", fill="both", expand=True)

        self.v_scroll = tk.Scrollbar(self.workspace_frame, orient="vertical")
        self.v_scroll.pack(side="right", fill="y")

        self.h_scroll = tk.Scrollbar(self.workspace_frame, orient="horizontal")
        self.h_scroll.pack(side="bottom", fill="x")

        self.workspace = tk.Canvas(
            self.workspace_frame, 
            bg="#ECF0F1", 
            xscrollcommand=self.h_scroll.set, 
            yscrollcommand=self.v_scroll.set
        )
        self.workspace.pack(side="left", fill="both", expand=True)

        self.h_scroll.config(command=self.workspace.xview)
        self.v_scroll.config(command=self.workspace.yview)

        self.setup_tabs()
        self.load_custom_blocks()
        self.update_workspace_scroll()

    def update_workspace_scroll(self):
        self.workspace.config(scrollregion=(0, 0, 3000, 3000))

    def setup_tabs(self):
        tab_actions = tk.Frame(self.notebook, bg="#2C3E50")
        self.notebook.add(tab_actions, text=" Actions & Logic ")

        tab_checks = tk.Frame(self.notebook, bg="#2C3E50")
        self.notebook.add(tab_checks, text=" Check Blocks ")

        tab_vars = tk.Frame(self.notebook, bg="#2C3E50")
        self.notebook.add(tab_vars, text=" Variables ")

        self.tab_custom = tk.Frame(self.notebook, bg="#2C3E50")
        self.notebook.add(self.tab_custom, text=" Custom Blocks ")

        # Actions & Logic
        tk.Label(tab_actions, text="ACTIONS", bg="#2C3E50", fg="#BDC3C7", font=("Helvetica", 9, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
        HealAntBlock(tab_actions, is_palette=True).pack(anchor="w", padx=10, pady=3)
        KillAntBlock(tab_actions, is_palette=True).pack(anchor="w", padx=10, pady=3)
        ChangeDisplayNameBlock(tab_actions, is_palette=True).pack(anchor="w", padx=10, pady=3)
        GetLeaderBlock(tab_actions, is_palette=True).pack(anchor="w", padx=10, pady=3)
        SetObjectBlock(tab_actions, is_palette=True).pack(anchor="w", padx=10, pady=3)
        SummonBlock(tab_actions, is_palette=True).pack(anchor="w", padx=10, pady=3)
        ChangeItemHandBlock(tab_actions, is_palette=True).pack(anchor="w", padx=10, pady=3)

        tk.Label(tab_actions, text="CONTROL", bg="#2C3E50", fg="#BDC3C7", font=("Helvetica", 9, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
        IfDoBlock(tab_actions, is_palette=True).pack(anchor="w", padx=10, pady=3)
        IfDoElseBlock(tab_actions, is_palette=True).pack(anchor="w", padx=10, pady=3)

        # Check Blocks
        tk.Label(tab_checks, text="CONDITIONS & CHECKS", bg="#2C3E50", fg="#BDC3C7", font=("Helvetica", 9, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
        CheckDisplayNameBlock(tab_checks, is_palette=True).pack(anchor="w", padx=10, pady=4)
        CheckInsideWaterBlock(tab_checks, is_palette=True).pack(anchor="w", padx=10, pady=4)
        CheckTouchesBlock(tab_checks, is_palette=True).pack(anchor="w", padx=10, pady=4)

        # Variables
        tk.Label(tab_vars, text="VARIABLES & REPORTERS", bg="#2C3E50", fg="#BDC3C7", font=("Helvetica", 9, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
        MaxHealthVariableBlock(tab_vars, is_palette=True).pack(anchor="w", padx=10, pady=4)
        TargetAntVariableBlock(tab_vars, is_palette=True).pack(anchor="w", padx=10, pady=4)
        SourceAntVariableBlock(tab_vars, is_palette=True).pack(anchor="w", padx=10, pady=4)

        xyz_frame = tk.Frame(tab_vars, bg="#2C3E50")
        xyz_frame.pack(anchor="w", padx=10, pady=4)
        XVariableBlock(xyz_frame, is_palette=True).pack(side="left", padx=(0, 4))
        YVariableBlock(xyz_frame, is_palette=True).pack(side="left", padx=(0, 4))
        ZVariableBlock(xyz_frame, is_palette=True).pack(side="left")

        GetCoordBlock(tab_vars, "X", is_palette=True).pack(anchor="w", padx=10, pady=4)
        GetCoordBlock(tab_vars, "Y", is_palette=True).pack(anchor="w", padx=10, pady=4)
        GetCoordBlock(tab_vars, "Z", is_palette=True).pack(anchor="w", padx=10, pady=4)
        GetEmptyCoordBlock(tab_vars, is_palette=True).pack(anchor="w", padx=10, pady=4)

        GetPositionVariableBlock(tab_vars, is_palette=True).pack(anchor="w", padx=10, pady=4)

        # Custom Blocks Tab Setup
        btn_add_custom = tk.Button(self.tab_custom, text="+ Add Custom Block", bg="#27AE60", fg="white", 
                                   font=("Helvetica", 10, "bold"), padx=10, pady=5, command=self.open_custom_dialog)
        btn_add_custom.pack(anchor="w", padx=10, pady=10)

        self.custom_palette_frame = tk.Frame(self.tab_custom, bg="#2C3E50")
        self.custom_palette_frame.pack(fill="both", expand=True)

    def open_custom_dialog(self):
        CustomBlockCreatorDialog(self, on_create_callback=self.add_custom_block)

    def add_custom_block(self, schema, color="#27AE60"):
        block_id = id(schema)
        block_data = {"id": block_id, "schema": schema, "color": color}
        self.custom_blocks_list.append(block_data)
        self.render_custom_block_in_palette(block_data)
        self.save_custom_blocks()

    def edit_custom_block(self, block_id, current_schema, current_color):
        def on_save_edit(new_schema, new_color):
            for block in self.custom_blocks_list:
                if block["id"] == block_id:
                    block["schema"] = new_schema
                    block["color"] = new_color
                    break

            if block_id in self.palette_block_widgets:
                self.palette_block_widgets[block_id].destroy()

            updated_data = {"id": block_id, "schema": new_schema, "color": new_color}
            self.render_custom_block_in_palette(updated_data)
            self.save_custom_blocks()

        CustomBlockCreatorDialog(
            self, 
            on_create_callback=on_save_edit, 
            initial_schema=current_schema, 
            initial_color=current_color,
            is_editing=True
        )

    def delete_custom_block(self, block_id):
        confirm = messagebox.askyesno("Delete Custom Block", "Are you sure you want to delete this custom block type?", parent=self)
        if not confirm:
            return

        self.custom_blocks_list = [b for b in self.custom_blocks_list if b["id"] != block_id]

        if block_id in self.palette_block_widgets:
            self.palette_block_widgets[block_id].destroy()
            del self.palette_block_widgets[block_id]

        self.save_custom_blocks()

    def render_custom_block_in_palette(self, block_data):
        block_id = block_data["id"]
        schema = block_data["schema"]
        color = block_data["color"]

        blk = DynamicCustomBlock(
            self.custom_palette_frame, 
            elements_schema=schema, 
            color=color, 
            is_palette=True,
            block_id=block_id
        )
        blk.pack(anchor="w", padx=10, pady=5)
        self.palette_block_widgets[block_id] = blk

    def serialize_block_data(self, block_data):
        schema = block_data["schema"]
        color = block_data.get("color", "#27AE60")
        parts = []
        for elem in schema:
            etype = elem["type"]
            val = elem["val"]
            if etype == "custom_dropdown":
                opts_str = ";".join(val) if isinstance(val, list) else str(val)
                parts.append(f'{etype}."{opts_str}"')
            else:
                parts.append(f'{etype}."{val}"')
        return f'{color}::{{' + ", ".join(parts) + "}"

    def deserialize_block_data(self, raw_str):
        raw_str = raw_str.strip()
        color = "#27AE60"
        
        if "::" in raw_str:
            color, block_str = raw_str.split("::", 1)
        else:
            block_str = raw_str

        block_str = block_str.strip()
        if block_str.startswith("{") and block_str.endswith("}"):
            block_str = block_str[1:-1]
        
        schema = []
        if not block_str:
            return {"id": None, "schema": schema, "color": color}

        parts = block_str.split(", ")
        for p in parts:
            if '."' in p:
                etype, val_part = p.split('."', 1)
                val = val_part.rstrip('"')
                if etype == "custom_dropdown":
                    val = val.split(";") if val else []
                schema.append({"type": etype, "val": val})

        return {"id": id(schema), "schema": schema, "color": color}

    def save_custom_blocks(self):
        serialized_blocks = [self.serialize_block_data(b) for b in self.custom_blocks_list]
        file_content = " | ".join(serialized_blocks)
        with open(SAVE_FILENAME, "w", encoding="utf-8") as f:
            f.write(file_content)

    def load_custom_blocks(self):
        if not os.path.exists(SAVE_FILENAME):
            return

        try:
            with open(SAVE_FILENAME, "r", encoding="utf-8") as f:
                file_content = f.read().strip()

            if not file_content:
                return

            block_strings = file_content.split(" | ")
            for b_str in block_strings:
                data = self.deserialize_block_data(b_str)
                if data["schema"]:
                    self.custom_blocks_list.append(data)
                    self.render_custom_block_in_palette(data)
        except Exception as e:
            print(f"Error loading {SAVE_FILENAME}: {e}")


if __name__ == "__main__":
    app = MakeBlockApp()
    app.mainloop()