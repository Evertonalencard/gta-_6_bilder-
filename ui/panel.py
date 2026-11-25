"""Interface inferior fixa com status, categorias e acoes contextuais."""
import arcade


STATUS_HEIGHT = 44
CATEGORY_HEIGHT = 42
CONTEXT_HEIGHT = 92

WHITE = (250, 250, 252)
LIGHT_GRAY = (224, 225, 229)
INK = (38, 40, 48)
BLUE = (55, 111, 226)
PURPLE = (130, 93, 220)


class ControlPanel:
    def __init__(self):
        self.categories = []
        self.context_actions = {"roads": [], "lots": []}
        self.status_actions = []
        self.demolition_action = None
        self.status = {}
        self.message_text = ""
        self.category = None
        self.active = None
        self._hitboxes = []

    @property
    def height(self):
        return STATUS_HEIGHT + CATEGORY_HEIGHT + (CONTEXT_HEIGHT if self.category else 0)

    def contains(self, x, y):
        return y < self.height

    def add_category(self, key, label, icon, callback):
        self.categories.append((key, label, icon, callback))

    def add_action(self, category, key, label, icon, callback):
        self.context_actions[category].append({
            "key": key, "label": label, "icon": icon, "callback": callback,
        })

    def add_status_action(self, key, label, icon, callback):
        self.status_actions.append({
            "key": key, "label": label, "icon": icon, "callback": callback,
        })

    def add_demolition_action(self, key, label, icon, callback):
        self.demolition_action = {
            "key": key, "label": label, "icon": icon, "callback": callback,
        }

    def set_category(self, category):
        self.category = category

    def set_active(self, key):
        self.active = key

    def set_status(self, key, value):
        self.status[key] = value

    def set_action_label(self, key, label):
        actions = self.status_actions + ([self.demolition_action] if self.demolition_action else [])
        for action in actions:
            if action["key"] == key:
                action["label"] = label

    def set_action_icon(self, key, icon):
        actions = self.status_actions + ([self.demolition_action] if self.demolition_action else [])
        for action in actions:
            if action["key"] == key:
                action["icon"] = icon

    def mensagem(self, texto):
        self.message_text = texto

    def handle_click(self, x, y, width):
        for left, bottom, right, top, callback in reversed(self._hitboxes):
            if left <= x <= right and bottom <= y <= top:
                callback()
                return True
        return False

    def _hit(self, left, bottom, right, top, callback):
        self._hitboxes.append((left, bottom, right, top, callback))

    def _pill(self, left, bottom, width, height, color):
        radius = height / 2
        arcade.draw_lbwh_rectangle_filled(left + radius, bottom, width - height, height, color)
        arcade.draw_circle_filled(left + radius, bottom + radius, radius, color)
        arcade.draw_circle_filled(left + width - radius, bottom + radius, radius, color)

    def _action_button(self, action, x, y, width, height, active=False, compact=False):
        fill = (235, 239, 251) if active else WHITE
        accent = BLUE if active else PURPLE
        self._pill(x, y, width, height, fill)
        icon_radius = min(13, height * 0.30)
        icon_x, icon_y = x + 23, y + height / 2
        arcade.draw_circle_filled(icon_x, icon_y, icon_radius, accent)
        arcade.draw_text(
            action["icon"], icon_x, icon_y, WHITE, 12 if compact else 13,
            anchor_x="center", anchor_y="center", bold=True,
        )
        arcade.draw_text(
            action["label"], x + 43, icon_y, INK, 8.5 if compact else 10,
            anchor_y="center",
        )
        self._hit(x, y, x + width, y + height, action["callback"])

    def draw(self, width):
        self._hitboxes = []
        self._draw_status(width)
        self._draw_categories(width)
        if self.category:
            self._draw_context(width)

    def _draw_status(self, width):
        arcade.draw_lbwh_rectangle_filled(0, 0, width, STATUS_HEIGHT, WHITE)
        arcade.draw_lbwh_rectangle_filled(0, STATUS_HEIGHT - 1, width, 1, LIGHT_GRAY)
        for index, action in enumerate(self.status_actions):
            x = 10 + index * 52
            self._action_button(action, x, 5, 46, 34, action["key"] == self.active, compact=True)

        self._pill(176, 6, 220, 32, (231, 233, 237))
        arcade.draw_text("＄", 191, 22, PURPLE, 17, anchor_x="center", anchor_y="center", bold=True)
        arcade.draw_text(self.status.get("money", "0"), 214, 22, INK, 12, anchor_y="center", bold=True)

        self._pill(410, 6, 178, 32, (231, 233, 237))
        arcade.draw_text("♟", 428, 22, BLUE, 16, anchor_x="center", anchor_y="center")
        arcade.draw_text(self.status.get("population", "0"), 449, 22, INK, 12, anchor_y="center", bold=True)

        arcade.draw_text(self.status.get("cycle", ""), 612, 22, (104, 106, 115), 10, anchor_y="center")
        arcade.draw_text(self.status.get("flow", ""), 700, 22, (104, 106, 115), 10, anchor_y="center")
        if self.message_text:
            arcade.draw_text(
                self.message_text[:55], 820, 22, (104, 106, 115), 9,
                anchor_y="center",
            )
        if self.demolition_action:
            self._action_button(
                self.demolition_action, width - 112, 5, 102, 34,
                self.demolition_action["key"] == self.active, compact=True,
            )

    def _draw_categories(self, width):
        y = STATUS_HEIGHT
        arcade.draw_lbwh_rectangle_filled(0, y, width, CATEGORY_HEIGHT, LIGHT_GRAY)
        button_width, gap = 190, 12
        left = (width - button_width * 2 - gap) / 2
        for index, (key, label, icon, callback) in enumerate(self.categories):
            x = left + index * (button_width + gap)
            active = self.category == key
            action = {"key": key, "label": label, "icon": icon, "callback": callback}
            self._action_button(action, x, y + 4, button_width, 34, active)

    def _draw_context(self, width):
        y = STATUS_HEIGHT + CATEGORY_HEIGHT
        arcade.draw_lbwh_rectangle_filled(0, y, width, CONTEXT_HEIGHT, WHITE)
        actions = self.context_actions[self.category]
        if not actions:
            return
        rows = [actions] if len(actions) <= 8 else [
            actions[:7], actions[7:],
        ]
        for row_index, row in enumerate(rows):
            item_width = min(150, (width - 20) / len(row))
            total_width = item_width * len(row)
            left = (width - total_width) / 2
            row_y = y + (50 if row_index == 0 and len(rows) > 1 else 7)
            if len(rows) == 1:
                row_y = y + 27
            for index, action in enumerate(row):
                self._action_button(
                    action, left + index * item_width, row_y, item_width - 3, 34,
                    action["key"] == self.active, compact=True,
                )
