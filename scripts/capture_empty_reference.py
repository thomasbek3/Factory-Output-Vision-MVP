import argparse
import cv2
import json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rtsp", required=True)
    parser.add_argument("--roi", required=True, help='ROI JSON string, e.g. "[100,200,500,300]"')
    parser.add_argument("--output", default="config/empty_cam1.jpg")
    args = parser.parse_args()

    roi = json.loads(args.roi)
    cap = cv2.VideoCapture(args.rtsp)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError("Unable to capture RTSP frame")

    x, y, w, h = roi
    roi_frame = frame[y:y+h, x:x+w]
    cv2.imwrite(args.output, roi_frame)
    print(f"Saved empty reference: {args.output}")


if __name__ == "__main__":
    main()
