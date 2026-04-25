import sys
import types

# Unit tests exercise label math/viewport state without requiring OpenCV installed.
if "cv2" not in sys.modules:
    sys.modules["cv2"] = types.SimpleNamespace()

import label_tool


def test_yolo_label_round_trip_with_custom_labels_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(label_tool, "LABELS_DIR", str(tmp_path))
    image_path = "/tmp/frame_001.jpg"
    boxes = [(10, 20, 110, 220), (300, 100, 500, 260)]

    label_tool.save_labels(image_path, boxes, img_h=400, img_w=800)

    loaded = label_tool.load_labels(image_path, img_h=400, img_w=800)
    assert loaded == boxes


def test_load_labels_clamps_malformed_out_of_bounds_values(tmp_path, monkeypatch):
    monkeypatch.setattr(label_tool, "LABELS_DIR", str(tmp_path))
    label_file = tmp_path / "frame_002.txt"
    label_file.write_text(
        "0 1.2 -0.2 0.5 2.0\n"
        "not valid\n"
        "0 nan 0.5 0.2 0.2\n"
        "0 inf 0.5 0.2 0.2\n"
        "0 1e309 0.5 0.2 0.2\n"
        "0 1e100 0.5 0.2 0.2\n"
    )

    loaded = label_tool.load_labels("/tmp/frame_002.jpg", img_h=100, img_w=200)

    assert loaded == [(190, 0, 200, 80)]


def test_viewport_coordinate_mapping_with_zoom_and_pan():
    state = label_tool.ViewState(img_w=1000, img_h=800, window_w=500, window_h=400)
    state.zoom = 2.0
    state.pan_x = 100
    state.pan_y = 50

    assert state.screen_to_image(0, 0) == (100, 50)
    assert state.screen_to_image(250, 200) == (225, 150)
    assert state.image_to_screen(225, 150) == (250, 200)


def test_view_state_zoom_around_cursor_keeps_point_under_cursor():
    state = label_tool.ViewState(img_w=1000, img_h=800, window_w=500, window_h=400)
    before = state.screen_to_image(200, 150)

    state.zoom_at(1.5, cursor_x=200, cursor_y=150)

    assert state.screen_to_image(200, 150) == before
    assert state.zoom == 1.5


def test_display_size_preserves_uniform_scale_for_letterboxed_images():
    state = label_tool.ViewState(img_w=1920, img_h=1080, window_w=1400, window_h=900)

    state.reset()
    x1, y1, x2, y2 = state.visible_crop_bounds()
    display_w, display_h = state.display_size_for_crop(x2 - x1, y2 - y1)

    assert (x1, y1, x2, y2) == (0, 0, 1920, 1080)
    assert display_w == 1400
    assert display_h < 900
    assert display_h == round(1080 * state.zoom)


def test_key_to_action_uses_waitkeyex_arrows_without_ascii_collisions():
    assert label_tool.key_to_action(2555904) == "pan_right"
    assert label_tool.key_to_action(2424832) == "pan_left"
    assert label_tool.key_to_action(2490368) == "pan_up"
    assert label_tool.key_to_action(2621440) == "pan_down"

    assert label_tool.key_to_action(ord("S")) == "negative"
    assert label_tool.key_to_action(ord("Q")) == "quit"
    assert label_tool.key_to_action(ord("R")) == "reset"
