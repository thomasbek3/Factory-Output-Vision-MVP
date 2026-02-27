import argparse
import cv2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="RTSP URL or local image path")
    parser.add_argument("--output", default="config/roi.txt")
    args = parser.parse_args()

    if args.source.startswith("rtsp://"):
        cap = cv2.VideoCapture(args.source)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError("Unable to capture frame from RTSP")
    else:
        frame = cv2.imread(args.source)

    roi = cv2.selectROI("Select DONE ZONE ROI", frame, fromCenter=False, showCrosshair=True)
    cv2.destroyAllWindows()
    x, y, w, h = map(int, roi)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(f"[{x}, {y}, {w}, {h}]\n")
    print(f"Saved ROI to {args.output}: [{x}, {y}, {w}, {h}]")


if __name__ == "__main__":
    main()
